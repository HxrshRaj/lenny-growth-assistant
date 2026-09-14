"""
Intent router: decides which skill handles a given user message.

Deterministic (regex/keyword) rather than LLM-driven tool-calling. This is a
documented trade-off (see docs/architecture.md "agent routing"): the assignment
requires the *local* Ollama path to work reliably for the demo, and small local
models are unreliable at structured tool-calling. A deterministic router gives
identical, reliable routing behavior on both providers, with clear, auditable
boundaries between skills -- at the cost of not letting the model itself decide to
invoke a skill mid-conversation. Each skill is still a real, separate, structured
component (not an inline prompt), which is what the assignment actually asks for.
"""
import re
from enum import Enum


class Intent(str, Enum):
    QA = "qa"
    SHIP30_ESSAY = "ship30_essay"
    ARTIFACT_MARKDOWN = "artifact_markdown"
    ARTIFACT_HTML = "artifact_html"


_SHIP30_PATTERNS = [
    r"\bship\s?30\b",
    r"\bship 30 for 30\b",
    r"\bturn (this|that|it) into an essay\b",
    r"\bwrite (an|the) essay\b",
    r"\b1[,.]?250[\s-]word",
]

_ARTIFACT_HTML_PATTERNS = [
    r"\bhtml\b.*\b(snippet|artifact|page|component)\b",
    r"\b(generate|create|build|make)\b.*\bhtml\b",
    r"\bhtml/css\b",
]

_ARTIFACT_MARKDOWN_PATTERNS = [
    r"\b(generate|create|build|make|write)\b.*\b(markdown|md)\b.*\b(doc|document|artifact|file|note)\b",
    r"\bas a markdown\b",
    r"\bmarkdown artifact\b",
]


def _matches_any(patterns: list[str], text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def classify_intent(message: str) -> Intent:
    if _matches_any(_SHIP30_PATTERNS, message):
        return Intent.SHIP30_ESSAY
    if _matches_any(_ARTIFACT_HTML_PATTERNS, message):
        return Intent.ARTIFACT_HTML
    if _matches_any(_ARTIFACT_MARKDOWN_PATTERNS, message):
        return Intent.ARTIFACT_MARKDOWN
    return Intent.QA
