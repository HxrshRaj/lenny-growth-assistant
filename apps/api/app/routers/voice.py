"""Real-time voice endpoint over a WebSocket.

Protocol (client -> server): binary frames = audio chunks; a text frame "end" =
end of utterance. Server -> client JSON events, in order:
  {"type":"received","bytes":N}      after each audio chunk (backpressure signal)
  {"type":"transcript","text":...}   once, after "end"
  {"type":"answer", ...}             the grounded RAG answer
  {"type":"error","detail":...}      on bad input; the socket then closes
Utterances are capped (MAX_AUDIO_BYTES) so a client cannot exhaust memory."""
from typing import Protocol

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.database import SessionLocal
from app.services import agent

router = APIRouter(tags=["voice"])

MAX_AUDIO_BYTES = 10 * 1024 * 1024


class Transcriber(Protocol):
    def transcribe(self, audio: bytes) -> str: ...


class WhisperTranscriber:
    """faster-whisper (Whisper) running locally. The model is loaded lazily on the
    first call. NOTE: not exercised in this repo's CI -- the model weights are a
    large download -- so tests inject a fake Transcriber."""

    def __init__(self, model_size: str | None = None):
        self._model_size = model_size or get_settings().whisper_model
        self._model = None

    def transcribe(self, audio: bytes) -> str:
        import io

        if self._model is None:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(self._model_size, compute_type="int8")
        segments, _ = self._model.transcribe(io.BytesIO(audio))
        return " ".join(s.text.strip() for s in segments).strip()


_default_transcriber: Transcriber | None = None


def get_transcriber() -> Transcriber:
    global _default_transcriber
    if _default_transcriber is None:
        _default_transcriber = WhisperTranscriber()
    return _default_transcriber


@router.websocket("/ws/voice")
async def voice(ws: WebSocket):
    await ws.accept()
    transcriber = ws.app.dependency_overrides.get(get_transcriber, get_transcriber)()
    buf = bytearray()
    try:
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                return
            if msg.get("bytes") is not None:
                buf.extend(msg["bytes"])
                if len(buf) > MAX_AUDIO_BYTES:
                    await ws.send_json({"type": "error", "detail": "Audio too large."})
                    await ws.close(code=1009)
                    return
                await ws.send_json({"type": "received", "bytes": len(buf)})
            elif msg.get("text") == "end":
                break
        if not buf:
            await ws.send_json({"type": "error", "detail": "No audio received."})
            await ws.close(code=1003)
            return
        text = await run_in_threadpool(transcriber.transcribe, bytes(buf))
        await ws.send_json({"type": "transcript", "text": text})
        if not text:
            await ws.send_json({"type": "error", "detail": "Could not transcribe any speech."})
            await ws.close()
            return

        def answer():
            db = ws.app.dependency_overrides.get(_db_factory, _db_factory)()
            try:
                return agent.run_turn(db, text, [])
            finally:
                db.close()

        result = await run_in_threadpool(answer)
        await ws.send_json({"type": "answer", "text": result.content, "citations": result.citations, "error": result.error})
        await ws.close()
    except WebSocketDisconnect:
        return


def _db_factory():
    return SessionLocal()
