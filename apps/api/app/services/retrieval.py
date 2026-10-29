"""
Retrieval: given a query, return the top-k most relevant chunks with full source
metadata attached, ordered by cosine similarity. Uses the HNSW index created in the
Phase 2 migration -- see docs/architecture.md secs 2-6.
"""
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from app.config import get_settings
from app.logging_config import get_logger
from app.models_retrieval import Chunk
from app.services.embeddings import embed_query

logger = get_logger(__name__)


@dataclass
class RetrievedChunk:
    chunk: Chunk
    score: float  # cosine similarity, 1.0 = identical, higher = more relevant


def retrieve(db: DBSession, query: str, top_k: int | None = None, min_score: float | None = None) -> list[RetrievedChunk]:
    settings = get_settings()
    top_k = top_k or settings.retrieval_top_k
    min_score = min_score if min_score is not None else settings.retrieval_min_score

    query_vec = embed_query(query)

    if settings.vector_backend == "chroma":
        return _retrieve_chroma(db, query_vec, top_k, min_score)

    distance = Chunk.embedding.cosine_distance(query_vec)
    stmt = select(Chunk, (1 - distance).label("score")).order_by(distance).limit(top_k)

    rows = db.execute(stmt).all()
    results = [RetrievedChunk(chunk=row[0], score=float(row[1])) for row in rows]
    hits = [r for r in results if r.score >= min_score]

    logger.info(
        "retrieval_query",
        query_preview=query[:120],
        candidates=len(results),
        hits=len(hits),
        top_score=hits[0].score if hits else (results[0].score if results else None),
    )
    return hits


_chroma_store = None


def _get_chroma_store():
    global _chroma_store
    if _chroma_store is None:
        from app.services.vectorstore import ChromaStore

        _chroma_store = ChromaStore(path=get_settings().chroma_path)
    return _chroma_store


def _retrieve_chroma(db: DBSession, query_vec: list[float], top_k: int, min_score: float) -> list[RetrievedChunk]:
    """Same contract as the pgvector path: ranked by cosine similarity, filtered by
    min_score. Chroma holds only vectors + ids; the full Chunk row (with citation
    metadata) is hydrated from Postgres so downstream code is backend-agnostic."""
    import uuid

    hits = _get_chroma_store().query(query_vec, top_k, min_score)
    out = []
    for h in hits:
        chunk = db.get(Chunk, uuid.UUID(h.id))
        if chunk is not None:
            out.append(RetrievedChunk(chunk=chunk, score=h.score))
    logger.info("retrieval_query_chroma", hits=len(out))
    return out
