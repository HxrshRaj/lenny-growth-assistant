"""Webhook auth + voice WebSocket protocol. The agent and the transcriber are faked
(no LLM, no Whisper weights, no embedding model); what is under test is signature
verification, replay protection, input validation and the streaming protocol."""
import json
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import get_db
from app.main import app
from app.routers import voice, webhooks
from app.services import agent

SECRET = "test-secret"


def fake_turn(db, text, history):
    return SimpleNamespace(content=f"answer to: {text}", citations=[{"title": "ep1"}], retrieval_hit_count=1, error=None)


@pytest.fixture()
def c(monkeypatch):
    monkeypatch.setattr(get_settings(), "webhook_secret", SECRET)
    monkeypatch.setattr(agent, "run_turn", fake_turn)
    app.dependency_overrides[get_db] = lambda: None
    app.dependency_overrides[voice.get_transcriber] = lambda: SimpleNamespace(transcribe=lambda audio: f"heard {len(audio)} bytes")
    app.dependency_overrides[voice._db_factory] = lambda: SimpleNamespace(close=lambda: None)
    yield TestClient(app)  # no `with`: skips the lifespan that loads the embedding model
    app.dependency_overrides.clear()


def signed(body: dict, ts: int | None = None, secret: str = SECRET):
    raw = json.dumps(body).encode()
    t = str(ts if ts is not None else int(time.time()))
    return raw, {"X-Timestamp": t, "X-Signature": webhooks.sign(secret, t, raw), "Content-Type": "application/json"}


def test_valid_signature_returns_answer(c):
    raw, h = signed({"question": "What is a PRD?"})
    r = c.post("/webhooks/ask", content=raw, headers=h)
    assert r.status_code == 200 and r.json()["answer"] == "answer to: What is a PRD?"


def test_wrong_secret_is_rejected(c):
    raw, h = signed({"question": "hi"}, secret="not-the-secret")
    assert c.post("/webhooks/ask", content=raw, headers=h).status_code == 401


def test_tampered_body_is_rejected(c):
    raw, h = signed({"question": "hi"})
    assert c.post("/webhooks/ask", content=raw.replace(b"hi", b"yo"), headers=h).status_code == 401


def test_stale_timestamp_is_rejected_as_replay(c):
    raw, h = signed({"question": "hi"}, ts=int(time.time()) - 3600)
    assert c.post("/webhooks/ask", content=raw, headers=h).status_code == 401


def test_missing_headers_rejected(c):
    assert c.post("/webhooks/ask", json={"question": "hi"}).status_code == 401


def test_disabled_without_secret(c, monkeypatch):
    monkeypatch.setattr(get_settings(), "webhook_secret", "")
    raw, h = signed({"question": "hi"})
    assert c.post("/webhooks/ask", content=raw, headers=h).status_code == 503


def test_voice_streams_chunks_then_transcript_then_answer(c):
    with c.websocket_connect("/ws/voice") as ws:
        ws.send_bytes(b"\x00" * 100)
        assert ws.receive_json() == {"type": "received", "bytes": 100}
        ws.send_bytes(b"\x01" * 50)
        assert ws.receive_json() == {"type": "received", "bytes": 150}
        ws.send_text("end")
        assert ws.receive_json() == {"type": "transcript", "text": "heard 150 bytes"}
        ans = ws.receive_json()
        assert ans["type"] == "answer" and ans["text"] == "answer to: heard 150 bytes"


def test_voice_end_without_audio_is_an_error(c):
    with c.websocket_connect("/ws/voice") as ws:
        ws.send_text("end")
        assert ws.receive_json()["type"] == "error"


def test_voice_rejects_oversized_audio(c, monkeypatch):
    monkeypatch.setattr(voice, "MAX_AUDIO_BYTES", 1000)
    with c.websocket_connect("/ws/voice") as ws:
        ws.send_bytes(b"\x00" * 2000)
        assert ws.receive_json() == {"type": "error", "detail": "Audio too large."}
