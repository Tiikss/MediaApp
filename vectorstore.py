import os
import pickle
from typing import List, Optional
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_community.retrievers import BM25Retriever
from langchain_classic.retrievers.ensemble import EnsembleRetriever
import chromadb

CHUNKS_FILE = "chunks.pkl"


class VectorStoreManager:

    def __init__(self):
        self.embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=2000,
            chunk_overlap=200,
            length_function=len,
        )
        self.chroma_client = chromadb.CloudClient(
            tenant="0b1d9f98-bea3-44ed-85b4-b4c85d6994ae",
            database="vijesti-db-chroma",
            api_key=os.environ["CHROMA_API_KEY"]
        )

    def chunk_documents(self, documents: List[Document]) -> List[Document]:
        chunks = self.text_splitter.split_documents(documents)
        print(f"Napravljeni chunkovi: {len(chunks)}.")
        return chunks

    def save_chunks(self, chunks: List[Document]):
        with open(CHUNKS_FILE, "wb") as f:
            pickle.dump(chunks, f)
        print(f"Sačuvano {len(chunks)} chunkova za BM25.")

    def load_chunks(self) -> Optional[List[Document]]:
        if not os.path.exists(CHUNKS_FILE):
            return None
        with open(CHUNKS_FILE, "rb") as f:
            chunks = pickle.load(f)
        print(f"Učitano {len(chunks)} chunkova za BM25.")
        return chunks

    def create_vectorstore(self, chunks: List[Document]) -> Chroma:
        try:
            vectorstore = Chroma.from_documents(
                documents=chunks,
                embedding=self.embeddings,
                collection_name="documents",
                client=self.chroma_client
            )
            self.save_chunks(chunks)
            print("Uspješno kreirana baza.")
            return vectorstore

        except Exception as e:
            print(f"Greška prilikom kreiranja baze: {str(e)}.")
            raise

    def load_vectorstore(self) -> Chroma:
        vectorstore = Chroma(
            collection_name="documents",
            embedding_function=self.embeddings,
            client=self.chroma_client,
        )
        return vectorstore

    def create_hybrid_retriever(self, vectorstore: Chroma, chunks: Optional[List[Document]] = None) -> EnsembleRetriever:
        vector_retriever = vectorstore.as_retriever(search_kwargs={"k": 8})

        if chunks:
            bm25_retriever = BM25Retriever.from_documents(chunks)
            bm25_retriever.k = 8
            return EnsembleRetriever(
                retrievers=[bm25_retriever, vector_retriever],
                weights=[0.4, 0.6]
            )

        return EnsembleRetriever(
            retrievers=[vector_retriever],
            weights=[1.0]
        )
