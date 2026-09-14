"""
The Ship 30 for 30 essay skill. A dedicated, structured skill (not a one-off inline
prompt) -- see docs/PRD.md/architecture.md sec 4.2. Principles below were extracted
directly from the real guide at
https://www.ship30for30.com/post/how-to-start-writing-online-the-ship-30-for-30-ultimate-guide
(fetched and read, not guessed) rather than assumed generic "blog writing tips".
"""

# Recorded verbatim/paraphrased from the source guide so the rationale is auditable.
SHIP30_PRINCIPLES = {
    "hook": (
        "The opening must answer, fast: WHO is this for, WHAT is this about, WHY should they "
        "read it (what PROMISE is being made). It should tease the ending without giving it away, "
        "creating a reason to keep reading."
    ),
    "rhythm": (
        "Use the '1/3/1' rhythm: a short opening sentence, a longer middle section that clarifies "
        "and expands, then a short, strong closing sentence per section/paragraph. Alternate short "
        "and long sentences throughout -- this creates 'checkpoints' that keep skimmers reading."
    ),
    "skimmability": (
        "Readers skim first, read second. Use bolded subheads to separate ideas, convert prose into "
        "bulleted lists where it helps, and keep a consistent organizational pattern across sections "
        "(e.g. numbered Steps, Lessons, or Mistakes) so the structure itself is scannable."
    ),
    "rate_of_revelation": (
        "Every sentence must push the piece forward -- new information or a new angle, never a "
        "restatement of something already said."
    ),
    "takeaway": (
        "End with one specific, useful, actionable takeaway -- not a vague summary."
    ),
}

TARGET_WORD_COUNT = 1250
WORD_COUNT_TOLERANCE = 200  # acceptable range: 1050-1450


def build_system_prompt() -> str:
    principles_block = "\n".join(f"- {k.replace('_', ' ').title()}: {v}" for k, v in SHIP30_PRINCIPLES.items())
    return f"""You are the Lenny Growth Assistant's essay-writing skill. You write a Ship 30 for 30 \
style essay grounded STRICTLY in the transcript excerpts provided as context below.

Structural principles you MUST follow (extracted from the real Ship 30 for 30 guide):
{principles_block}

Additional hard requirements:
- Length: approximately {TARGET_WORD_COUNT} words (acceptable range: {TARGET_WORD_COUNT - WORD_COUNT_TOLERANCE}-{TARGET_WORD_COUNT + WORD_COUNT_TOLERANCE} words). Write to this length -- do not stop short.
- Every substantive claim must trace back to the provided transcript context. If the context is too \
thin to support a full essay on the requested topic, say so explicitly instead of inventing detail.
- Naturally attribute ideas to the guest(s) they came from in the prose.
- Format in Markdown: a compelling title (H1 or bold), bolded subheads (H2/H3 or **bold**), and \
bullet points where they aid skimmability.
- Close with a clearly-marked, specific, actionable takeaway (e.g. under a "**Takeaway:**" line).
"""


def build_messages(context_block: str, topic: str) -> list[dict]:
    return [
        {
            "role": "user",
            "content": (
                f"Context (transcript excerpts):\n\n{context_block}\n\n---\n\n"
                f"Write a ~{TARGET_WORD_COUNT}-word Ship 30 for 30 style essay on: {topic}"
            ),
        }
    ]
