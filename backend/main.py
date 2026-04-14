import os
import sys
import json
from typing import List, AsyncGenerator

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from document_processor import DocumentProcessor
from vectorstore import VectorStoreManager
from tools import create_search_tool
from agent import create_documentation_agent
from langchain_core.messages import HumanMessage

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

app_state = {
    "agent": None,
    "processing_status": "not_started",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        vs_manager = VectorStoreManager()
        vectorstore = vs_manager.load_vectorstore()
        if vectorstore._collection.count() > 0:
            chunks = vs_manager.load_chunks()
            retriever = vs_manager.create_hybrid_retriever(vectorstore, chunks)
            search_tool = create_search_tool(retriever)
            app_state["agent"] = create_documentation_agent([search_tool])
            app_state["processing_status"] = "completed"
            print("Vectorstore učitan pri pokretanju.")
    except Exception as e:
        print(f"Startup: nije moguće učitati bazu: {e}")
    yield


app = FastAPI(title="Vijesti Arhiva API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    thread_id: str = "document_chat"


@app.get("/api/status")
def get_status():
    return {"status": app_state["processing_status"]}


@app.post("/api/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="Nema fajlova za upload.")

    app_state["processing_status"] = "processing"

    class MockUploadedFile:
        def __init__(self, name: str, content: bytes, content_type: str):
            self.name = name
            self.type = content_type
            self._content = content

        def getbuffer(self):
            return self._content

    try:
        mock_files = []
        for f in files:
            content = await f.read()
            mock_files.append(MockUploadedFile(f.filename, content, f.content_type or ""))

        processor = DocumentProcessor()
        documents, _ = processor.process_uploaded_files(mock_files)

        if not documents:
            app_state["processing_status"] = "error"
            raise HTTPException(status_code=422, detail="Nijedan validan fajl nije pronađen.")

        vs_manager = VectorStoreManager()
        chunks = vs_manager.chunk_documents(documents)
        vectorstore = vs_manager.create_vectorstore(chunks)
        retriever = vs_manager.create_hybrid_retriever(vectorstore, chunks)
        search_tool = create_search_tool(retriever)
        app_state["agent"] = create_documentation_agent([search_tool])
        app_state["processing_status"] = "completed"

        return {"message": f"{len(documents)} fajl(ova) uspješno obrađeno.", "count": len(documents)}

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        app_state["processing_status"] = "error"
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat")
async def chat(request: ChatRequest):
    if app_state["agent"] is None:
        raise HTTPException(
            status_code=400,
            detail="Agent nije inicijalizovan. Molimo dodajte fajlove prvo."
        )

    async def generate() -> AsyncGenerator[str, None]:
        config = {"configurable": {"thread_id": request.thread_id}}

        try:
            yield f"data: {json.dumps({'type': 'status', 'content': 'thinking'})}\n\n"

            tool_call_detected = False
            final_answer_started = False
            pre_tool_buffer: list[str] = []

            async for msg, metadata in app_state["agent"].astream(
                {"messages": [HumanMessage(content=request.message)]},
                config=config,
                stream_mode="messages",
            ):
                langgraph_node = metadata.get("langgraph_node", "")

                if "tools" in langgraph_node.lower() or "tool" in langgraph_node.lower():
                    if not tool_call_detected:
                        yield f"data: {json.dumps({'type': 'status', 'content': 'searching'})}\n\n"
                        tool_call_detected = True
                        pre_tool_buffer.clear()
                    continue

                if "agent" in langgraph_node.lower() and hasattr(msg, "content"):
                    raw = msg.content
                    if isinstance(raw, list):
                        content = "".join(
                            block.get("text", "") if isinstance(block, dict) else str(block)
                            for block in raw
                        )
                    else:
                        content = raw
                    if content:
                        if tool_call_detected:
                            if not final_answer_started:
                                yield f"data: {json.dumps({'type': 'status', 'content': 'responding'})}\n\n"
                                final_answer_started = True
                            yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"
                        else:
                            pre_tool_buffer.append(content)

            if not tool_call_detected and pre_tool_buffer:
                yield f"data: {json.dumps({'type': 'status', 'content': 'responding'})}\n\n"
                for chunk in pre_tool_buffer:
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            import traceback
            traceback.print_exc()
            error_str = str(e).lower()
            if 'overloaded' in error_str:
                msg = 'Server je trenutno preopterećen. Pokušajte ponovo za nekoliko sekundi.'
            else:
                msg = str(e)
            yield f"data: {json.dumps({'type': 'error', 'content': msg})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
