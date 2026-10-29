from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Hit:
    id: str
    text: str
    score: float  # cosine similarity, 1.0 = identical (same convention as retrieval.py)
    metadata: dict = field(default_factory=dict)


class VectorStore(Protocol):
    def upsert(self, ids: list[str], vectors: list[list[float]], texts: list[str], metadatas: list[dict]) -> None: ...

    def query(self, vector: list[float], top_k: int, min_score: float) -> list[Hit]: ...

    def count(self) -> int: ...
