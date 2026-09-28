"""An engine proxy: a hosted LLM answering from the simulated web."""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True)
class Doc:
    doc_id: str
    title: str
    body: str
    is_official: bool

@dataclass(frozen=True)
class EngineAnswer:
    answer: str
    cited_doc_ids: list[str]
    retrieved_doc_ids: list[str]

class Retriever(Protocol):
    def search(self, query: str, k: int) -> list[Doc]: ...

class ChatClient(Protocol):
    def complete(self, endpoint: str, messages: list[dict], max_tokens: int = 600) -> str: ...

SYSTEM = ("You are an AI answer engine like ChatGPT or Perplexity. Answer the user's question in 2 to 4 sentences "
          "using only the sources provided. Name specific brands and prices when the sources give them. "
          "Cite sources inline as [doc_id].")
_CITE = re.compile(r"\[([A-Za-z0-9_\-]+)\]")

class EngineProxy:
    def __init__(self, name: str, endpoint: str, retriever: Retriever, chat: ChatClient, k: int = 6):
        self.name, self.endpoint, self.retriever, self.chat, self.k = name, endpoint, retriever, chat, k

    def answer(self, prompt: str) -> EngineAnswer:
        docs = self.retriever.search(prompt, self.k)
        sources = "\n\n".join(f"[{d.doc_id}] {d.title}\n{d.body}" for d in docs)
        text = self.chat.complete(self.endpoint, [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Sources:\n{sources}\n\nQuestion: {prompt}"},
        ])
        allowed = [d.doc_id for d in docs]
        cited = []
        for m in _CITE.findall(text or ""):
            if m in allowed and m not in cited:
                cited.append(m)
        return EngineAnswer(text or "", cited, allowed)
