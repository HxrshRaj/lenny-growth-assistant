"""Shared helpers for turning retrieved chunks into LLM context and API citations."""
from app.services.retrieval import RetrievedChunk


def format_context_block(hits: list[RetrievedChunk]) -> str:
    if not hits:
        return "(No relevant transcript material was found for this query.)"
    parts = []
    for i, hit in enumerate(hits, start=1):
        c = hit.chunk
        parts.append(
            f"[Source {i}] Guest: {c.guest} | Episode: {c.title!r} | Timestamp: {c.start_timestamp}\n"
            f"{c.text}"
        )
    return "\n\n---\n\n".join(parts)


def build_citations(hits: list[RetrievedChunk]) -> list[dict]:
    citations = []
    for hit in hits:
        c = hit.chunk
        citations.append(
            {
                "episode_slug": c.episode_slug,
                "guest": c.guest,
                "title": c.title,
                "source_url": c.source_url,
                "start_timestamp": c.start_timestamp,
                "score": round(hit.score, 3),
                "text_preview": (c.text[:220] + "...") if len(c.text) > 220 else c.text,
            }
        )
    return citations
