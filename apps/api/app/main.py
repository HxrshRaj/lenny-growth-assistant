import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.errors import register_exception_handlers
from app.logging_config import configure_logging, get_logger
from app.routers import sessions, system

configure_logging()
logger = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("app_startup", model_provider=settings.model_provider, environment=settings.environment)
    # Eager-load the embedding model here rather than lazily on first request.
    # Found live: SentenceTransformer's first-ever `.to(device)` call is not
    # safe against concurrent invocation -- two requests arriving at once right
    # after a cold container start both triggered PyTorch's lazy meta-tensor
    # materialization simultaneously and one crashed with "Cannot copy out of
    # meta tensor; no data!". functools.lru_cache serializes the *function*
    # call, but real-world traffic (this app's own frontend polling /health and
    # /config every 15s, plus a real chat request) can still arrive in that
    # same narrow startup window. Loading it once here, before the app accepts
    # any request, removes the race entirely.
    from app.services.embeddings import get_embedder

    get_embedder()
    logger.info("embedding_model_preloaded")
    yield


app = FastAPI(title="Lenny Growth Assistant API", version="0.1.0", lifespan=lifespan)

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
