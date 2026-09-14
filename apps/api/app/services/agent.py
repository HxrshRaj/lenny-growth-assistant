"""
The agent orchestrator: router -> retrieval -> skill -> LLM provider. This is the
single place that ties Phase 2 (retrieval) and Phase 3 (provider abstraction +
skills) together. See docs/architecture.md "agent routing" for the design
rationale (deterministic router, why no LLM-driven tool-calling).
"""
import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session as DBSession

from app.config import get_settings
from app.logging_config import get_logger
from app.services import router as intent_router
from app.services.context import build_citations, format_context_block
from app.services.llm import LLMProviderError, complete
from app.services.retrieval import retrieve
from app.services.skills import artifact, qa, ship30

logger = get_logger(__name__)

HISTORY_TURNS_FOR_QA = 6  # last N messages included as conversation context for follow-ups


@dataclass
class AgentTurnResult:
    content: str
    model_provider: str | None
    model_name: str | None
    retrieval_hit_count: int
    citations: list[dict[str, Any]]
    latency_ms: int
    error: str | None
    intent: str


def run_turn(db: DBSession, user_message: str, history: list[dict]) -> AgentTurnResult:
    start = time.monotonic()
    settings = get_settings()

    intent = intent_router.classify_intent(user_message)
    hits = retrieve(db, user_message)
    context_block = format_context_block(hits)
    citations = build_citations(hits)

    logger.info(
        "agent_turn_routed",
        intent=intent.value,
        retrieval_hit_count=len(hits),
        model_provider=settings.model_provider,
    )

    if not hits:
        logger.info("retrieval_empty", query_preview=user_message[:120])

    try:
        # Output budgets are skill-specific: a QA answer is a paragraph or two,
        # while a Ship 30 essay needs room for ~1,250 words (~1,700 tokens) and an
        # artifact needs room for a full document. On the local provider this also
        # directly bounds how long CPU generation takes -- see
        # docs/architecture.md sec 8c for the measured trade-off.
        if intent == intent_router.Intent.SHIP30_ESSAY:
            system = ship30.build_system_prompt()
            messages = ship30.build_messages(context_block, user_message)
            max_tokens = 2200
        elif intent == intent_router.Intent.ARTIFACT_MARKDOWN:
            system = artifact.MARKDOWN_SYSTEM_PROMPT
            messages = artifact.build_messages(context_block, user_message)
            max_tokens = 1500
        elif intent == intent_router.Intent.ARTIFACT_HTML:
            system = artifact.HTML_SYSTEM_PROMPT
            messages = artifact.build_messages(context_block, user_message)
            max_tokens = 1500
        else:
            system = qa.SYSTEM_PROMPT
            recent_history = history[-HISTORY_TURNS_FOR_QA:]
            messages = qa.build_messages(context_block, recent_history, user_message)
            max_tokens = 600

        result = complete(system, messages, settings, max_tokens=max_tokens)
        latency_ms = int((time.monotonic() - start) * 1000)

        logger.info(
            "agent_turn_completed",
            intent=intent.value,
            model_provider=result.provider,
            model_name=result.model_name,
            latency_ms=latency_ms,
        )

        return AgentTurnResult(
            content=result.text,
            model_provider=result.provider,
            model_name=result.model_name,
            retrieval_hit_count=len(hits),
            citations=citations,
            latency_ms=latency_ms,
            error=None,
            intent=intent.value,
        )

    except LLMProviderError as e:
        latency_ms = int((time.monotonic() - start) * 1000)
        logger.error("agent_turn_provider_error", provider=e.provider, detail=e.detail, intent=intent.value)
        return AgentTurnResult(
            content=(
                f"⚠️ I couldn't reach the {e.provider} model provider, so I can't answer this turn.\n\n"
                f"Details: {e.detail}"
            ),
            model_provider=e.provider,
            model_name=None,
            retrieval_hit_count=len(hits),
            citations=citations,
            latency_ms=latency_ms,
            error=e.detail,
            intent=intent.value,
        )
