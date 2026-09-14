"""
ORM models. See docs/architecture.md "Database schema" for the rationale behind
each column, especially the audit/observability fields on `Message`.
"""
import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ChatSession(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Placeholder for real auth later -- every session/message is attributable to
    # *someone* even though this build has no login flow.
    user_id: Mapped[str] = mapped_column(String(255), default="anonymous", nullable=False)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="Message.created_at"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # "user" | "assistant" | "system"
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # --- Audit / observability fields (Phase 1 ground rule: support this later) ---
    model_provider: Mapped[str | None] = mapped_column(String(20), nullable=True)  # "anthropic" | "ollama"
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    retrieval_hit_count: Mapped[int | None] = mapped_column(nullable=True)
    citations: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # list of source-chunk metadata
    latency_ms: Mapped[int | None] = mapped_column(nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)  # set on a failed assistant turn

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    session: Mapped["ChatSession"] = relationship(back_populates="messages")

    __table_args__ = (Index("ix_messages_session_id_created_at", "session_id", "created_at"),)
