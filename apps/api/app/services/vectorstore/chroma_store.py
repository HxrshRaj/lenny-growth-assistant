"""ChromaDB backend. Vectors are always supplied by the caller (the same
sentence-transformers embedder the pgvector path uses), never by Chroma's own
default embedder, so both backends rank with identical embeddings.

Chroma returns cosine *distance* for a collection created with hnsw:space=cosine;
we convert to similarity (1 - distance) so scores match retrieval.py."""
import chromadb

from app.services.vectorstore.base import Hit


class ChromaStore:
    def __init__(self, path: str | None = None, collection: str = "lenny_chunks"):
        # path=None -> in-memory (tests); a directory path -> persistent on disk.
        self._client = chromadb.PersistentClient(path=path) if path else chromadb.EphemeralClient()
        self._col = self._client.get_or_create_collection(name=collection, metadata={"hnsw:space": "cosine"})

    def upsert(self, ids, vectors, texts, metadatas):
        clean = [{k: v for k, v in (m or {}).items() if v is not None} or {"_": "1"} for m in metadatas]
        self._col.upsert(ids=ids, embeddings=vectors, documents=texts, metadatas=clean)

    def query(self, vector, top_k, min_score):
        n = self._col.count()
        if n == 0:
            return []
        res = self._col.query(query_embeddings=[vector], n_results=min(top_k, n))
        hits = [
            Hit(id=i, text=d, score=1.0 - float(dist), metadata=m)
            for i, d, dist, m in zip(res["ids"][0], res["documents"][0], res["distances"][0], res["metadatas"][0])
        ]
        return [h for h in hits if h.score >= min_score]

    def count(self):
        return self._col.count()
