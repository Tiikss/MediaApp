from typing import Annotated
from langchain_core.tools import tool


def create_search_tool(retriever):
    @tool
    def search_documents(query: Annotated[str, "Upit za pretragu"]) -> str:
        """Pretražuje dokumente u bazi prema zadatom upitu i vraća relevantne rezultate."""
        try:
            results = retriever.invoke(query)

            if not results:
                return "Nema relevantnih informacija u bazi za ovaj upit."

            context_parts = []
            for i, doc in enumerate(results, 1):
                source = doc.metadata.get('filename', doc.metadata.get('source', 'Unknown source'))
                content = doc.page_content.strip()

                context_parts.append(
                    f"[Izvor {i}: {source}]\n"
                    f"Sadržaj: {content}\n"
                )

            return "\n---\n".join(context_parts)

        except Exception as e:
            return f"Greška prilikom pretrage baze: {str(e)}."

    return search_documents
