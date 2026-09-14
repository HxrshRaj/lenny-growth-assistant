"""
/health and /config. Both actually probe live state (DB connectivity, Ollama
reachability) instead of returning a hardcoded 200 -- see the ground rule in the
assignment ("actually verifies DB connectivity ... not just return 200").
"""
import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session as DBSession

from app.config import Settings, get_settings
from app.database import get_db
from app.logging_config import get_logger
from app.schemas import ConfigOut, HealthOut

router = APIRouter(tags=["system"])
logger = get_logger(__name__)


def _check_db(db: DBSession) -> bool:
    try:
        db.execute(text("SELECT 1"))
        return True
    except OperationalError:
        return False


def _check_ollama(settings: Settings) -> bool:
    try:
        resp = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=3.0)
        return resp.status_code == 200
    except httpx.HTTPError:
        return False


@router.get("/health", response_model=HealthOut)
def health(db: DBSession = Depends(get_db), settings: Settings = Depends(get_settings)) -> HealthOut:
    db_ok = _check_db(db)

    if settings.model_provider == "ollama":
        ollama_status = "ok" if _check_ollama(settings) else "unreachable"
    else:
        ollama_status = "not_configured"

    overall = "ok" if db_ok and ollama_status != "unreachable" else "degraded"

    if not db_ok:
        logger.error("health_check_db_down")
    if ollama_status == "unreachable":
        logger.error("health_check_ollama_unreachable", ollama_base_url=settings.ollama_base_url)

    return HealthOut(
        status=overall,
        database="ok" if db_ok else "unreachable",
        ollama=ollama_status,
        model_provider=settings.model_provider,
    )


@router.get("/config", response_model=ConfigOut)
def get_config(settings: Settings = Depends(get_settings)) -> ConfigOut:
    ollama_reachable = _check_ollama(settings) if settings.model_provider == "ollama" else False
    return ConfigOut(
        model_provider=settings.model_provider,
        anthropic_model=settings.anthropic_model,
        ollama_model=settings.ollama_model,
        anthropic_configured=bool(settings.anthropic_api_key),
        ollama_reachable=ollama_reachable,
    )
