"""Unit tests for the skill modules and context-building helpers (no network/DB)."""
from datetime import date

from app.models_retrieval import Chunk
from app.services.context import build_citations, format_context_block
from app.services.retrieval import RetrievedChunk
from app.services.skills import ship30


def _fake_chunk(**overrides) -> Chunk:
    defaults = dict(
        episode_slug="test-guest",
        guest="Test Guest",
        title="A Test Episode",
        youtube_url="https://www.youtube.com/watch?v=abc123",
        video_id="abc123",
        publish_date=date(2024, 1, 1),
        channel="Lenny's Podcast",
        keywords=["growth"],
        chunk_index=0,
        speakers=["Test Guest"],
        start_timestamp="00:01:00",
        end_timestamp="00:01:30",
        start_seconds=60,
        source_url="https://www.youtube.com/watch?v=abc123&t=60s",
        word_count=42,
        text="This is a test chunk about product-market fit.",
    )
    defaults.update(overrides)
    return Chunk(**defaults)


def test_format_context_block_includes_guest_and_text():
    hits = [RetrievedChunk(chunk=_fake_chunk(), score=0.8)]
    block = format_context_block(hits)
    assert "Test Guest" in block
    assert "product-market fit" in block


def test_format_context_block_handles_no_hits():
    block = format_context_block([])
    assert "No relevant" in block


def test_build_citations_shape():
    hits = [RetrievedChunk(chunk=_fake_chunk(), score=0.812345)]
    citations = build_citations(hits)
    assert len(citations) == 1
    c = citations[0]
    assert c["guest"] == "Test Guest"
    assert c["source_url"].endswith("&t=60s")
    assert c["score"] == 0.812  # rounded


def test_ship30_system_prompt_encodes_real_structural_principles():
    prompt = ship30.build_system_prompt()
    # These phrases anchor to the actual guide's language (see ship30.py docstring
    # + the fetched source), not a generic "write a good essay" placeholder.
    assert "1250" in prompt or "1,250" in prompt
    assert "hook" in prompt.lower()
    assert "takeaway" in prompt.lower()
    assert "skim" in prompt.lower()


def test_ship30_messages_include_topic_and_context():
    messages = ship30.build_messages("CONTEXT_BLOCK_MARKER", "pricing strategy")
    assert len(messages) == 1
    assert "CONTEXT_BLOCK_MARKER" in messages[0]["content"]
    assert "pricing strategy" in messages[0]["content"]
