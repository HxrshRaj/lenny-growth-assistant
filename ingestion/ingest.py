"""
Main ingestion entrypoint.

    python ingest.py [--repo-dir DIR] [--limit N]

Steps (see docs/architecture.md secs 1-5 for the "why" behind each):
1. Clone (or pull, if already cloned) ChatPRD/lennys-podcast-transcripts.
2. Glob episodes/*/transcript.md -- trust the filesystem, not any stated count.
3. Parse frontmatter + turns, chunk turns, embed chunk text.
4. Upsert into Postgres `chunks` (idempotent on (episode_slug, chunk_index), so
   re-running ingestion after a `git pull` picks up new/changed episodes without
   duplicating existing rows).
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from pgvector.psycopg import register_vector
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent))
from chunker import chunk_turns  # noqa: E402
from parser import parse_transcript  # noqa: E402

REPO_URL = "https://github.com/ChatPRD/lennys-podcast-transcripts.git"

load_dotenv()


def to_psycopg_url(sqlalchemy_url: str) -> str:
    """DATABASE_URL is written in SQLAlchemy form (postgresql+psycopg://...); psycopg
    itself just wants postgresql://..."""
    return sqlalchemy_url.replace("postgresql+psycopg://", "postgresql://")


def clone_or_update(repo_dir: Path) -> None:
    if (repo_dir / ".git").exists():
        print(f"[ingest] repo already present at {repo_dir}, pulling latest...")
        subprocess.run(["git", "-C", str(repo_dir), "pull", "--ff-only"], check=True)
    else:
        print(f"[ingest] cloning {REPO_URL} -> {repo_dir}")
        repo_dir.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--depth", "1", REPO_URL, str(repo_dir)], check=True)


def load_embedder(model_name: str):
    from sentence_transformers import SentenceTransformer

    print(f"[ingest] loading embedding model '{model_name}' (first run downloads it)...")
    return SentenceTransformer(model_name)


UPSERT_SQL = """
INSERT INTO chunks (
    id, episode_slug, guest, title, youtube_url, video_id, publish_date, channel,
    keywords, chunk_index, speakers, start_timestamp, end_timestamp, start_seconds,
    source_url, word_count, text, embedding
) VALUES (
    gen_random_uuid(), %(episode_slug)s, %(guest)s, %(title)s, %(youtube_url)s,
    %(video_id)s, %(publish_date)s, %(channel)s, %(keywords)s, %(chunk_index)s,
    %(speakers)s, %(start_timestamp)s, %(end_timestamp)s, %(start_seconds)s,
    %(source_url)s, %(word_count)s, %(text)s, %(embedding)s
)
ON CONFLICT (episode_slug, chunk_index) DO UPDATE SET
    guest = EXCLUDED.guest,
    title = EXCLUDED.title,
    youtube_url = EXCLUDED.youtube_url,
    video_id = EXCLUDED.video_id,
    publish_date = EXCLUDED.publish_date,
    channel = EXCLUDED.channel,
    keywords = EXCLUDED.keywords,
    speakers = EXCLUDED.speakers,
    start_timestamp = EXCLUDED.start_timestamp,
    end_timestamp = EXCLUDED.end_timestamp,
    start_seconds = EXCLUDED.start_seconds,
    source_url = EXCLUDED.source_url,
    word_count = EXCLUDED.word_count,
    text = EXCLUDED.text,
    embedding = EXCLUDED.embedding
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-dir", default=str(Path(__file__).parent / "data" / "raw" / "lennys-podcast-transcripts"))
    ap.add_argument("--limit", type=int, default=None, help="only ingest first N episodes (debugging)")
    ap.add_argument("--skip-clone", action="store_true", help="reuse an already-cloned repo dir as-is")
    args = ap.parse_args()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL is not set.", file=sys.stderr)
        sys.exit(1)

    embedding_model_name = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

    repo_dir = Path(args.repo_dir)
    if not args.skip_clone:
        clone_or_update(repo_dir)

    episode_dirs = sorted((repo_dir / "episodes").glob("*/"))
    if args.limit:
        episode_dirs = episode_dirs[: args.limit]
    print(f"[ingest] found {len(episode_dirs)} episode folders")

    embedder = load_embedder(embedding_model_name)

    conn = psycopg.connect(to_psycopg_url(database_url), autocommit=False)
    register_vector(conn)
    total_chunks = 0
    skipped = []

    for ep_dir in tqdm(episode_dirs, desc="episodes"):
        transcript_path = ep_dir / "transcript.md"
        if not transcript_path.exists():
            skipped.append((ep_dir.name, "no transcript.md"))
            continue
        raw = transcript_path.read_text(encoding="utf-8")
        try:
            frontmatter, turns = parse_transcript(raw)
        except Exception as e:  # noqa: BLE001
            skipped.append((ep_dir.name, f"parse error: {e}"))
            continue
        if not turns:
            skipped.append((ep_dir.name, "no turns parsed"))
            continue

        drafts = chunk_turns(turns)
        texts = [d.text for d in drafts]
        embeddings = embedder.encode(texts, show_progress_bar=False, normalize_embeddings=True)

        youtube_url = frontmatter.get("youtube_url", "")
        rows = []
        for idx, (draft, emb) in enumerate(zip(drafts, embeddings)):
            rows.append(
                {
                    "episode_slug": ep_dir.name.rstrip("/"),
                    "guest": frontmatter.get("guest", "Unknown"),
                    "title": frontmatter.get("title", ep_dir.name),
                    "youtube_url": youtube_url,
                    "video_id": frontmatter.get("video_id", ""),
                    "publish_date": frontmatter.get("publish_date") or None,
                    "channel": frontmatter.get("channel", "Lenny's Podcast"),
                    "keywords": _to_jsonb(frontmatter.get("keywords") or []),
                    "chunk_index": idx,
                    "speakers": _to_jsonb(draft.speakers),
                    "start_timestamp": draft.start_hms,
                    "end_timestamp": draft.end_hms,
                    "start_seconds": draft.start_seconds,
                    "source_url": (
                        f"{youtube_url}&t={draft.start_seconds}s"
                        if youtube_url and draft.start_hms != "unknown"
                        else youtube_url
                    ),
                    "word_count": draft.word_count,
                    "text": draft.text,
                    "embedding": list(map(float, emb)),
                }
            )

        with conn.cursor() as cur:
            cur.executemany(UPSERT_SQL, rows)
        conn.commit()
        total_chunks += len(rows)

    conn.close()

    print(f"\n[ingest] done. {total_chunks} chunks upserted across {len(episode_dirs) - len(skipped)} episodes.")
    if skipped:
        print(f"[ingest] skipped {len(skipped)} episode(s):")
        for name, reason in skipped[:20]:
            print(f"  - {name}: {reason}")


def _to_jsonb(value):
    return psycopg.types.json.Jsonb(value)


if __name__ == "__main__":
    main()
