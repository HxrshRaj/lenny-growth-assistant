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
- **Real result** (full text: `agent-transcripts/phase-4-ship30-essay-evidence.json`):
  a Markdown essay titled "The Art of Pricing: Lessons from Design and
  Entrepreneurship," structured exactly as instructed -- H1 title, bolded H2
  subheads per section (Design Perspective / Entrepreneurial Perspective /
  Science of Pricing / Bottom Line), a bulleted 3-step formula, and a
  `**Takeaway:**`-labeled closing line. `retrieval_hit_count: 3`, `error: null`,
  `latency_ms: 237132` (~4 min), `model_name: "llama3.2:3b"`.

**Grounding spot-check (the actual required verification step)**: the essay
names and quotes three people -- Jessica Hische, Patrick Campbell, Madhavan
Ramanujam. Checked this against what `retrieve()` actually returned for this
query, not just trusted the model:
  - **Jessica Hische** -- real retrieved chunk, from her episode "How to see
    like a designer: The hidden power of typography and logos," whose preview
    text is literally about her "pretty unique way of pricing your work." Real
    match, not fabricated.
  - **Patrick Campbell** -- real retrieved chunk, from "10 lessons on
    bootstrapping a $200m business | Patrick Campbell (ProfitWell)," whose
    preview text is Lenny introducing him as one of the most experienced people
    on pricing. Real match.
  - **Madhavan Ramanujam** -- real retrieved chunk, from "The art and science
    of pricing | Madhavan Ramanujam," whose preview text mentions "nine
    strategies... to approach pricing, monetization." Real match -- and
    notably the essay did NOT fabricate that "nine strategies" detail into its
    own prose (it said "multi-strategy approach" generically), which is a good
    sign against over-claiming specifics beyond what a 300-word chunk excerpt
    can actually support.
  All three named sources are genuinely who was retrieved, not invented names --
  the skill is not hallucinating guests. The *exact quoted dialogue* attributed
  to each person is very likely paraphrased/invented by the model rather than
  verbatim transcript text (typical LLM behavior when asked to "quote" from a
  short excerpt) -- flagged here as a real, honest caveat rather than glossed
  over: the *who* and *what topic* grounding is solid, the *exact wording*
  presented as a direct quote is not independently verified against the source
  audio/transcript word-for-word.

**Word count, honestly reported**: 807 words -- below the 1,050-1,450 acceptable
range (target ~1,250). The model had a 2,200-token budget (`max_tokens`) and
stopped well short of using it, i.e. this is the model choosing to conclude
early, not a truncation cutoff. This is a real, disclosed limitation of the
local 3B model on this task: it did not reliably hit the target length despite
having room to. Not re-run with prompt tricks to force more output within this
build's time budget -- reported as-is, a genuine measured result rather than a
retried-until-it-looked-good number.

## Honest note on local-model essay generation time

Given the measured ~5-minute latency for a 600-token QA answer on this CPU (see
phase-3 log), a full ~1,250-word essay (`max_tokens=2200`) was expected to take
meaningfully longer. Ran it once, waited for the real result rather than
truncating the budget just to get a faster demo -- the point of this
verification step is to confirm the skill actually produces essay-length,
correctly-structured, grounded output on the mandated local path, which requires
actually letting it finish.
