"""ChromaStore against a real (in-memory) ChromaDB. Vectors are deterministic
bag-of-words hashes so no model download is needed; what is under test is the
store's ranking, scoring convention, min_score filter and upsert semantics."""
import hashlib
import math

from app.services.vectorstore import ChromaStore

DIM = 64


def embed(text: str) -> list[float]:
    v = [0.0] * DIM
    for w in text.lower().split():
        v[int(hashlib.md5(w.encode()).hexdigest(), 16) % DIM] += 1.0
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def make_store(name: str) -> ChromaStore:
    s = ChromaStore(collection=name)
    docs = {
        "a": "retention and activation metrics for growth",
        "b": "pricing strategy and packaging for saas",
        "c": "hiring product managers and interviews",
    }
    s.upsert(list(docs), [embed(t) for t in docs.values()], list(docs.values()), [{"guest": g} for g in "xyz"])
    return s


def test_nearest_chunk_ranks_first_with_cosine_similarity_score():
    s = make_store("t_rank")
    hits = s.query(embed("saas pricing and packaging"), top_k=3, min_score=0.0)
    assert hits[0].id == "b"
    assert 0.0 < hits[0].score <= 1.0
    assert [h.score for h in hits] == sorted((h.score for h in hits), reverse=True)


def test_identical_text_scores_one():
    s = make_store("t_ident")
    top = s.query(embed("hiring product managers and interviews"), top_k=1, min_score=0.0)[0]
    assert top.id == "c" and abs(top.score - 1.0) < 1e-3


def test_min_score_filters_unrelated_queries():
    s = make_store("t_min")
    assert s.query(embed("quantum chromodynamics lattice"), top_k=3, min_score=0.3) == []


def test_upsert_replaces_existing_id_and_count_is_stable():
    s = make_store("t_upsert")
    s.upsert(["a"], [embed("totally new text about onboarding")], ["totally new text about onboarding"], [{"guest": "q"}])
    assert s.count() == 3
    assert s.query(embed("onboarding"), 1, 0.0)[0].id == "a"


def test_empty_store_returns_no_hits():
    assert ChromaStore(collection="t_empty").query(embed("anything"), 3, 0.0) == []
