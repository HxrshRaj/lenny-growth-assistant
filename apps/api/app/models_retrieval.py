"""
The `chunks` table -- the pgvector-backed knowledge base populated by `ingestion/`
and queried by `app/services/retrieval.py`. See docs/architecture.md secs 2-4 for
the chunking/embedding rationale.

This table is written by a *separate* Docker build context (`ingestion/`, which has
no import access to this `app` package by design -- see architecture.md "component
boundaries"). Alembic (here) is the single source of truth for the schema; the
ingestion pipeline writes to it with plain SQL against these exact column names.
"""
import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Date, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 -- update alongside embedding_model if it ever changes


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # --- episode-level metadata (from transcript.md frontmatter) ---
    episode_slug: Mapped[str] = mapped_column(String(255), nullable=False)
    guest: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    youtube_url: Mapped[str] = mapped_column(String(500), nullable=False)
    video_id: Mapped[str] = mapped_column(String(50), nullable=False)
    publish_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    channel: Mapped[str] = mapped_column(String(255), nullable=False, default="Lenny's Podcast")
    keywords: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # --- chunk-level metadata (computed at ingestion time) ---
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    speakers: Mapped[list] = mapped_column(JSONB, nullable=False)
    start_timestamp: Mapped[str] = mapped_column(String(20), nullable=False)
    end_timestamp: Mapped[str] = mapped_column(String(20), nullable=False)
    start_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    source_url: Mapped[str] = mapped_column(String(600), nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False)

    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("episode_slug", "chunk_index", name="uq_chunks_episode_chunk_index"),
        Index("ix_chunks_episode_slug", "episode_slug"),
    )
