"""Inbound webhook for automation tools (n8n, Make, Zapier, WhatsApp bridges).

Auth is an HMAC-SHA256 signature over `"<timestamp>.<raw body>"` with a shared
secret, sent as `X-Signature: sha256=<hex>` plus `X-Timestamp` (unix seconds).
Requests older than the replay window are rejected, and the comparison is
constant-time. The raw body is signed (not re-serialised JSON) so the sender and
receiver can never disagree about whitespace or key order."""
import hashlib
import hmac
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from app.config import get_settings
from app.database import get_db
from app.services import agent

router = APIRouter(tags=["webhooks"])

REPLAY_WINDOW_SECONDS = 300


class AskPayload(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


def sign(secret: str, timestamp: str, body: bytes) -> str:
    mac = hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256)
    return "sha256=" + mac.hexdigest()


@router.post("/webhooks/ask")
async def ask(request: Request, db: DBSession = Depends(get_db)):
    secret = get_settings().webhook_secret
    if not secret:
        raise HTTPException(status_code=503, detail="Webhook is disabled (WEBHOOK_SECRET not set).")

    body = await request.body()
    timestamp = request.headers.get("x-timestamp", "")
    signature = request.headers.get("x-signature", "")
    try:
        age = abs(time.time() - int(timestamp))
    except ValueError:
        raise HTTPException(status_code=401, detail="Missing or invalid X-Timestamp.")
    if age > REPLAY_WINDOW_SECONDS:
        raise HTTPException(status_code=401, detail="Request timestamp outside the replay window.")
    if not hmac.compare_digest(sign(secret, timestamp, body), signature):
        raise HTTPException(status_code=401, detail="Invalid signature.")

    payload = AskPayload.model_validate_json(body)
    result = agent.run_turn(db, payload.question, [])
    return {
        "answer": result.content,
        "citations": result.citations,
        "retrieval_hit_count": result.retrieval_hit_count,
        "error": result.error,
    }
