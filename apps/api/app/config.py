"""
Central app configuration. Every value here can be overridden by an env var of the
same name (see /.env.example at the repo root). This is the single place the
model-provider toggle lives -- routers/services read `settings.model_provider`,
never an env var directly, so switching providers never touches application code.
"""
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Database ---
    database_url: str = "postgresql+psycopg://lenny:lenny@localhost:5432/lenny"

    # --- Model provider toggle (the whole point of Phase 3) ---
    # "anthropic" -> cloud Claude via Anthropic API
    # "ollama"    -> local Ollama server
    model_provider: Literal["anthropic", "ollama"] = "ollama"

    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"
    ollama_timeout_seconds: float = 240.0
    # Ollama silently defaults num_ctx to 2048 even when the underlying model
    # supports more -- see llm.py::_complete_ollama for the real failure this
    # caused (HTTP 200, empty completion, no error at all). 4096 matches this
    # build's default local model; raise it if you swap in a larger-context model.
    ollama_num_ctx: int = 4096

    # --- Retrieval ---
    embedding_model: str = "all-MiniLM-L6-v2"
    # 3, not 5: measured live on this build's local model (3.8B, CPU, 4096 ctx) --
    # 5 chunks pushed prompt processing past even a 240s timeout. 3 chunks keeps
    # answers grounded (still multiple independent sources) while actually being
    # answerable in reasonable time on constrained local hardware. Cloud providers
    # have no such constraint; this is a local-path-driven default, documented as
    # a real, measured trade-off in docs/architecture.md, not an arbitrary guess.
    retrieval_top_k: int = 3
    retrieval_min_score: float = 0.15  # cosine similarity floor; below this we treat as "no hit"

    # --- CORS ---
    cors_origins: str = "http://localhost:5173"

    # --- App ---
    log_level: str = "INFO"
    environment: str = "development"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
