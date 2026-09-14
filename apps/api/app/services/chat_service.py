"""
Turns a user message into a persisted, grounded assistant reply.

Phase 3 status: this now runs the real pipeline (router -> retrieval -> skill ->
LLM provider) via app/services/agent.py. The Phase 1 placeholder this replaced
just echoed the user's message; see agent-transcripts/phase-1-backend-core.md.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from app.logging_config import get_logger
from app.models import Message
from app.services import agent

logger = get_logger(__name__)


def _history_for_llm(db: DBSession, session_id: uuid.UUID) -> list[dict]:
    stmt = select(Message).where(Message.session_id == session_id).order_by(Message.created_at)
    rows = db.scalars(stmt).all()
    return [{"role": m.role, "content": m.content} for m in rows if m.role in ("user", "assistant")]


def generate_response(db: DBSession, session_id: uuid.UUID, user_content: str) -> Message:
    history = _history_for_llm(db, session_id)  # BEFORE inserting the new user message

    user_message = Message(session_id=session_id, role="user", content=user_content)
    db.add(user_message)
    db.flush()

    result = agent.run_turn(db, user_content, history)

    assistant_message = Message(
        session_id=session_id,
        role="assistant",
        content=result.content,
        model_provider=result.model_provider,
        model_name=result.model_name,
        retrieval_hit_count=result.retrieval_hit_count,
        citations=result.citations,
        latency_ms=result.latency_ms,
        error=result.error,
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)

    logger.info(
        "message_handled",
        session_id=str(session_id),
        intent=result.intent,
        retrieval_hit_count=result.retrieval_hit_count,
        model_provider=result.model_provider,
        latency_ms=result.latency_ms,
        had_error=result.error is not None,
    )
    return assistant_message
