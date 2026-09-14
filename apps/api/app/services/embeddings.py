"""
Shared embedding-model singleton. Loaded once per process (sentence-transformers
model load is the expensive part) and reused by both the retrieval query path and
any future re-embedding tooling.
"""
from functools import lru_cache

from app.config import get_settings


@lru_cache
def get_embedder():
    from sentence_transformers import SentenceTransformer

    settings = get_settings()
    return SentenceTransformer(settings.embedding_model)


def embed_query(text: str) -> list[float]:
    model = get_embedder()
    vec = model.encode([text], normalize_embeddings=True)[0]
    return [float(x) for x in vec]
