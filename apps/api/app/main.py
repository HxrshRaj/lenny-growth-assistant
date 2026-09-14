import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.errors import register_exception_handlers
from app.logging_config import configure_logging, get_logger
from app.routers import sessions, system

configure_logging()
logger = get_logger(__name__)
settings = get_settings()

app = FastAPI(title="Lenny Growth Assistant API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    duration_ms = int((time.monotonic() - start) * 1000)
    logger.info(
        "request_handled",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
    )
    return response


app.include_router(system.router)
app.include_router(sessions.router)


@app.on_event("startup")
async def on_startup():
    logger.info("app_startup", model_provider=settings.model_provider, environment=settings.environment)
