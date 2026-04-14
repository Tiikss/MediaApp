from typing import List
from langchain_core.tools import BaseTool
from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

SYSTEM_MESSAGE = """
Ti si inteligentni agent specijalizovan za pretragu i analizu dokumenata. Tvoj zadatak je da pomogneš korisnicima da pronađu informacije u dokumentima koje su prethodno učitali. Koristi alate koje imaš na raspolaganju kako bi odgovorio na pitanja korisnika i pružio relevantne informacije iz dokumenata.
SMJERNICE:
- Koristi search_documents da bi pronašao relevantne informacije
- Budi efikasan: jedna dobro osmišljena pretraga je obično dovoljna
- Pretraži ponovo samo ako su prvi rezultati očigledno nepotpuni
- Daj jasne, tačne odgovore na osnovu sadržaja dokumenata
- Ako informacije nisu pronađene, jasno to navedi
- Budi koncizan, ali temeljan u svojim odgovorima
- Ne navodi koji fajl je izvor informacija osim ako korisnik ne zatraži

Prilikom odgovaranja:
1. Pretraži dokumente fokusiranim upitom
2. Ako pretraga po imenu osobe ne da rezultate, pokušaj ponovo koristeći njenu funkciju, titulu ili kontekst
3. Sintetizuj jasan odgovor iz rezultata
4. Pretraži ponovo sa drugačijim upitom samo ako su prvi rezultati očigledno nepotpuni
"""

def create_documentation_agent(tools: List[BaseTool], model_name: str = "claude-sonnet-4-6"):

    llm = ChatAnthropic(model=model_name, temperature=0, max_retries=3)

    memory = MemorySaver()

    agent = create_react_agent(
        llm,
        tools=tools,
        prompt=SYSTEM_MESSAGE,
        checkpointer=memory
    )

    return agent