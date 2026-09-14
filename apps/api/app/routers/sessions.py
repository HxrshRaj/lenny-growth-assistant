import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.errors import NotFoundError
from app.models import ChatSession, Message
from app.schemas import MessageCreate, MessageOut, SessionCreate, SessionOut
from app.services import chat_service

router = APIRouter(tags=["sessions"])


def _get_session_or_404(db: DBSession, session_id: uuid.UUID) -> ChatSession:
    session = db.get(ChatSession, session_id)
    if session is None:
        raise NotFoundError(f"Session {session_id} does not exist.")
    return session


@router.post("/sessions", response_model=SessionOut, status_code=201)
def create_session(payload: SessionCreate, db: DBSession = Depends(get_db)) -> ChatSession:
    session = ChatSession(user_id=payload.user_id, title=payload.title)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/sessions/{session_id}", response_model=SessionOut)
def get_session(session_id: uuid.UUID, db: DBSession = Depends(get_db)) -> ChatSession:
    return _get_session_or_404(db, session_id)


@router.post("/sessions/{session_id}/messages", response_model=MessageOut, status_code=201)
def post_message(
    session_id: uuid.UUID, payload: MessageCreate, db: DBSession = Depends(get_db)
) -> Message:
    _get_session_or_404(db, session_id)  # 404s before doing any work if the session is bogus
    assistant_message = chat_service.generate_response(db, session_id, payload.content)
    return assistant_message


@router.get("/sessions/{session_id}/messages", response_model=list[MessageOut])
def list_messages(session_id: uuid.UUID, db: DBSession = Depends(get_db)) -> list[Message]:
    _get_session_or_404(db, session_id)
    stmt = select(Message).where(Message.session_id == session_id).order_by(Message.created_at)
    return list(db.scalars(stmt))
