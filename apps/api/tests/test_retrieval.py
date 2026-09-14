"""
Retrieval test against the REAL indexed data (not a mocked vector store). Requires
ingestion to have been run first (`python ingestion/ingest.py`) -- see README
"running tests". Skips (rather than fails) if the index is empty, since retrieval
against zero data isn't a meaningful pass/fail on its own.
"""
import pytest
from sqlalchemy import text

from app.services.retrieval import retrieve


def _chunk_count(db_session) -> int:
    return db_session.execute(text("SELECT count(*) FROM chunks")).scalar_one()


def test_retrieval_returns_relevant_chunks_with_citations(db_session):
    if _chunk_count(db_session) == 0:
        pytest.skip("chunks table is empty -- run ingestion before this test")

    hits = retrieve(db_session, "How do I know when it's the right time to leave my job?", top_k=5)

    assert len(hits) > 0
    top = hits[0]
    assert top.score > 0.15  # above the configured relevance floor
    assert top.chunk.text.strip() != ""
    assert top.chunk.source_url.startswith("https://www.youtube.com/watch?v=")
    assert top.chunk.guest
    assert top.chunk.title


def test_retrieval_respects_top_k(db_session):
    if _chunk_count(db_session) == 0:
        pytest.skip("chunks table is empty -- run ingestion before this test")

    hits = retrieve(db_session, "How should I think about pricing?", top_k=3)
    assert len(hits) <= 3


def test_retrieval_scores_are_ordered_descending(db_session):
    if _chunk_count(db_session) == 0:
        pytest.skip("chunks table is empty -- run ingestion before this test")

    hits = retrieve(db_session, "What makes a good product manager?", top_k=5)
    scores = [h.score for h in hits]
    assert scores == sorted(scores, reverse=True)
