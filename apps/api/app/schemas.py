"""Pydantic request/response models -- real validation, not just type hints."""
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# --- Sessions ---
class SessionCreate(BaseModel):
    user_id: str = Field(default="anonymous", max_length=255)
    title: str | None = Field(default=None, max_length=500)


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: str
    title: str | None
    created_at: datetime
    updated_at: datetime


# --- Messages ---
class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


class Citation(BaseModel):
    """Shape written by app/services/context.py::build_citations -- kept in sync
    with it deliberately (score included, since the UI surfaces it)."""

    episode_slug: str
    guest: str
    title: str
    source_url: str
    start_timestamp: str
    score: float
    text_preview: str


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    role: Literal["user", "assistant", "system"]
    content: str
    model_provider: str | None
    model_name: str | None
    retrieval_hit_count: int | None
    citations: list[Citation] | None
    latency_ms: int | None
    error: str | None
    created_at: datetime


# --- Errors ---
class ErrorResponse(BaseModel):
    error: str
    detail: str
    code: str


# --- Health / config ---
class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["ok", "unreachable"]
    ollama: Literal["ok", "unreachable", "not_configured"]
    model_provider: str


class ConfigOut(BaseModel):
    model_provider: str
    anthropic_model: str
    ollama_model: str
    anthropic_configured: bool
    ollama_reachable: bool
