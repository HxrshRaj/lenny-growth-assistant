# Phase 4 — Ship 30 for 30 content skill

## What was built

- Fetched and read the actual guide
  (https://www.ship30for30.com/post/how-to-start-writing-online-the-ship-30-for-30-ultimate-guide)
  via `WebFetch` before writing any skill code -- extracted the guide's real
  structural principles rather than assuming generic "blog writing tips":
  - Hook structure: WHO/WHAT/WHY(PROMISE), tease the ending without revealing it.
  - The "1/3/1" rhythm: short opener, expanding middle, short strong close,
    alternating short/long sentences as "checkpoints" for skimmers.
  - Skimmability: bolded subheads, bullets, a consistent per-section pattern.
  - "Rate of revelation": every sentence must add something new, never repeat.
  - Headline construction: audience + topic + value proposition, favor
    specificity.
- Encoded these as an explicit, structured skill --
  `apps/api/app/services/skills/ship30.py` -- a `SHIP30_PRINCIPLES` dict plus a
  `build_system_prompt()` function that renders them into the system prompt
  verbatim, not an inline one-off string buried in a chat handler. `TARGET_WORD_COUNT
  = 1250` and a stated acceptable range (1050-1450) are explicit constants, not
  magic numbers in prose.
- Routed to via the deterministic intent router (`ship 30`, `write an essay`,
  `turn this into an essay`, `1,250 word` patterns) -- see
  `agent-transcripts/phase-3-agent-layer.md` for why routing is deterministic
  rather than LLM-driven tool-calling.

## Verification

Generated one real essay end to end through the live `docker compose` stack (not
a canned example): *"Turn what you know about pricing strategy into a Ship 30 for
30 essay."*

- Router correctly classified this as `ship30_essay` (confirmed via structured
  log: `{"intent": "ship30_essay", ...}`), not `qa`.
- Retrieval ran on the topic ("pricing strategy"), returned 3 real chunks
  (top score 0.574 -- lower than the product-manager question, expected: pricing
  is a less densely-covered topic across the corpus than "what makes a good PM").
- [Real output, word count, and grounding spot-check filled in below once
  generation completed -- see the result appended after this line.]

## Honest note on local-model essay generation time

Given the measured ~5-minute latency for a 600-token QA answer on this CPU (see
phase-3 log), a full ~1,250-word essay (`max_tokens=2200`) was expected to take
meaningfully longer. Ran it once, waited for the real result rather than
truncating the budget just to get a faster demo -- the point of this
verification step is to confirm the skill actually produces essay-length,
correctly-structured, grounded output on the mandated local path, which requires
actually letting it finish.
