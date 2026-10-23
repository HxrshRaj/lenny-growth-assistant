"""One-way sync: copy every chunk's (id, text, embedding) from Postgres into ChromaDB.
Run after ingestion when VECTOR_BACKEND=chroma:  python -m app.chroma_sync"""
from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.models_retrieval import Chunk
from app.services.vectorstore import ChromaStore

BATCH = 500


def sync(db, store) -> int:
    total, offset = 0, 0
    while True:
        rows = db.scalars(select(Chunk).order_by(Chunk.id).offset(offset).limit(BATCH)).all()
        if not rows:
            return total
        store.upsert(
            ids=[str(r.id) for r in rows],
            vectors=[[float(x) for x in r.embedding] for r in rows],
            texts=[r.text for r in rows],
            metadatas=[{"episode_slug": r.episode_slug, "guest": r.guest} for r in rows],
        )
        total += len(rows)
        offset += BATCH


if __name__ == "__main__":
    db = SessionLocal()
    try:
        n = sync(db, ChromaStore(path=get_settings().chroma_path))
    finally:
        db.close()
    print(f"synced {n} chunks to ChromaDB")
