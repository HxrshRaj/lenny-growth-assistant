"""
Turns a user message into a persisted assistant reply.

Phase 1 status: NO retrieval and NO LLM call exist yet -- this intentionally does
NOT fabricate a grounded answer. It persists the user message and a clearly-labeled
placeholder assistant turn so the session/message persistence path (the actual
Phase 1 deliverable) can be verified end to end. This function is replaced in
Phase 3 with the real retrieval -> agent -> grounded-answer pipeline; nothing about
the router or schema changes when that happens.
"""
import time
import uuid

from sqlalchemy.orm import Session as DBSession

from app.logging_config import get_logger
from app.models import Message

logger = get_logger(__name__)

PHASE1_PLACEHOLDER_NOTICE = (
    "Retrieval and the model agent are not wired up yet (that lands in Phase 2/3). "
    "This is a placeholder response confirming the message was received and persisted."
)


def generate_response(db: DBSession, session_id: uuid.UUID, user_content: str) -> Message:
    start = time.monotonic()

    user_message = Message(session_id=session_id, role="user", content=user_content)
    db.add(user_message)
    db.flush()

    assistant_content = f"{PHASE1_PLACEHOLDER_NOTICE}\n\nYou said: {user_content!r}"
    latency_ms = int((time.monotonic() - start) * 1000)

    assistant_message = Message(
        session_id=session_id,
        role="assistant",
        content=assistant_content,
        model_provider=None,
        model_name=None,
        retrieval_hit_count=None,
        citations=None,
        latency_ms=latency_ms,
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)

    logger.info(
        "message_handled",
        session_id=str(session_id),
        phase="1-placeholder",
        latency_ms=latency_ms,
    )
    return assistant_message
