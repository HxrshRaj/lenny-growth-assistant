"""
Phase 2 verification script: run real questions against the pgvector index and
print back the actual retrieved chunks with citations. Deliberately standalone
(does not import the FastAPI app) so retrieval is proven correct *before* it gets
wired into the chat agent in Phase 3.

Usage:
    DATABASE_URL=postgresql+psycopg://lenny:lenny@localhost:5442/lenny python scripts/verify_retrieval.py
"""
import os
import sys
import textwrap

import psycopg
from dotenv import load_dotenv
from pgvector.psycopg import register_vector

load_dotenv()

QUESTIONS = [
    "How do I know when it's the right time to leave my job?",
    "What makes a good product manager?",
    "How should I think about pricing my product?",
    "What is the best way to run user research interviews?",
    "How do you build a strong company culture as a startup scales?",
]

TOP_K = 5


def to_psycopg_url(sqlalchemy_url: str) -> str:
    return sqlalchemy_url.replace("postgresql+psycopg://", "postgresql://")


def main() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        sys.exit(1)

    from sentence_transformers import SentenceTransformer

    embedding_model_name = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    print(f"Loading embedding model '{embedding_model_name}'...")
    model = SentenceTransformer(embedding_model_name)

    conn = psycopg.connect(to_psycopg_url(database_url))
    register_vector(conn)

    total_indexed = conn.execute("SELECT count(*) FROM chunks").fetchone()[0]
    print(f"Index currently holds {total_indexed} chunks.\n")
    print("=" * 100)

    for q in QUESTIONS:
        vec = model.encode([q], normalize_embeddings=True)[0]
        rows = conn.execute(
            """
            SELECT guest, title, source_url, start_timestamp, word_count, text,
                   1 - (embedding <=> %s) AS score
            FROM chunks
            ORDER BY embedding <=> %s
            LIMIT %s
            """,
            (vec, vec, TOP_K),
        ).fetchall()

        print(f"\nQ: {q}")
        print("-" * 100)
        for i, (guest, title, source_url, ts, word_count, text, score) in enumerate(rows, start=1):
            preview = textwrap.shorten(text.replace("\n", " "), width=280, placeholder=" ...")
            print(f"  [{i}] score={score:.3f}  guest={guest}  title={title[:60]!r}")
            print(f"      source: {source_url}  (@ {ts})")
            print(f"      text: {preview}")
        print("=" * 100)

    conn.close()


if __name__ == "__main__":
    main()
