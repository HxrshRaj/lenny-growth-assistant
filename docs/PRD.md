# PRD — The Lenny Growth Assistant

> Note on how this document came to exist: the take-home brief asked for a product
> draft to be supplied and written up in this format. No draft was supplied with the
> task, so this PRD was written directly from the brief's own "Forward Deployment
> Brief" requirements (sec 2 of the assignment) and refined against what the actual
> transcript data and build turned out to look like -- not backfilled from a
> pre-existing document. Flagged here rather than silently presented as if a client
> draft existed.

## 1. User and problem

**Primary user**: an internal product/growth team member (PM, growth lead, founder)
at a company that treats Lenny's Podcast as a trusted, high-signal source of
tactical product/growth advice -- but doesn't have time to re-watch or re-search
300+ hours of interviews every time a question comes up.

**Job to be done**: "I have a specific product or growth question right now (e.g.
'how do I think about pricing a B2B SaaS product?', 'what does a good PM interview
loop look like?') and I want a fast, trustworthy answer grounded in what real
operators have actually said -- with a way to verify it -- not a generic LLM
answer that might be confidently wrong."

A secondary job: "I need to turn something I just learned into a piece of writing
(an internal doc, a shareable essay, a quick HTML mockup) without starting from a
blank page."

**Pain removed**: the alternative today is manually searching/skimming transcripts
(slow, easy to miss the right episode) or asking a general-purpose LLM (fast, but
ungrounded -- no way to tell confident-sounding invention from something an actual
guest said).

## 2. Success metric

Primary (product): **% of assistant answers that carry at least one citation the
user actually clicks through to verify** -- a proxy for "the user trusted this
enough to check it, and the system made that checking easy." Target for a
production version: >30% click-through on cited answers (citations exist on every
grounded answer; not every answer needs verification, but a meaningful fraction of
users doing so is the signal that citations are actually functioning as trust
infrastructure rather than decoration).

Secondary (operational, easier to instrument day one and what this build actually
supports): **% of turns where retrieval returns zero hits above the relevance
floor** -- tracked via `retrieval_hit_count` on every `messages` row (see
architecture.md). A rising empty-retrieval rate is the earliest signal that either
the corpus needs refreshing or users are asking outside the corpus's actual
coverage (e.g. asking about a topic no guest ever discussed).

## 3. Assumptions

The brief was intentionally incomplete in a few places; assumptions made explicit:

1. **"Users" is one internal team, not the public.** No multi-tenant auth, no rate
   limiting per external customer. `user_id` exists as a placeholder column
   (`"anonymous"` default) so a real auth layer can be added later without a schema
   migration, but no login flow was built for this take-home.
2. **The transcript repo is the single source of truth**, refreshed by re-running
   ingestion (`git pull` + re-embed changed episodes), not a live sync/webhook.
   Acceptable for an internal knowledge tool where the underlying podcast doesn't
   publish hourly.
3. **"Reliable" matters more than "impressive" for the local-model path**, because
   the brief makes Ollama the mandatory demo path. Routing, error handling, and
   citation behavior were designed to degrade gracefully with a small local model
   rather than assuming GPT/Claude-tier reasoning is always available.
4. **Artifacts are single-shot per turn**, not an iterative canvas the user edits
   back and forth with the assistant across many turns. Simpler, and matches "the
   assistant must generate Markdown/HTML **when requested**" in the brief rather
   than implying a persistent document-editing product.

## 4. Scope choices

**Included** (all verified working, not aspirational):
- FastAPI backend with real Postgres-backed sessions/messages, structured errors,
  live health checks.
- Full ingestion pipeline against the real transcript repo (303 episodes as of this
  build), turn-aware chunking, pgvector retrieval with citations.
- Model-provider toggle (Anthropic Claude / local Ollama) via one env var, with
  graceful per-provider failure handling.
- Grounded Q&A with explicit "I don't know" behavior when retrieval is thin.
- Ship 30 for 30 essay skill, built from the actual published guide's structural
  principles.
- Markdown/HTML artifact generation with a sandboxed, XSS-tested viewer.
- Docker Compose one-command startup, structured JSON logs, documented failure
  modes.

**Explicitly excluded** (and why):
- **Multi-session browsing UI** (a sidebar listing past sessions). One active
  session, resumable via `localStorage`, is enough to demonstrate the full
  product loop; a session list is pure CRUD UI with no new backend risk, cut for
  time under the deadline.
- **Streaming responses.** Both providers are called synchronously. Streaming
  would improve perceived latency (especially for the ~1,250-word Ship 30 essay)
  but adds meaningful complexity to both the provider abstraction and the frontend
  state machine; cut to protect correctness of the harder requirements
  (grounding, provider toggle, artifact security) under a one-day deadline.
- **Topic/keyword filtering UI** using the `keywords` field already captured per
  chunk. Data is there (unused today) for a fast follow-up.
- **Auth / multi-tenant isolation.** Out of scope per assumption #1.
- **Automatic corpus refresh on a schedule.** Ingestion is a manual/CI-triggerable
  command, not a cron job, for this build.

## 5. Core flows

1. **Ask a grounded question** → session auto-created on first load → message sent
   → router classifies intent as QA (default) → retrieval → LLM answers strictly
   from retrieved context → response + citations rendered, citations collapsed by
   default.
2. **Ask something the corpus doesn't cover** → retrieval returns 0 hits above the
   relevance floor → assistant explicitly states the transcripts don't support an
   answer → no citations shown → `retrieval_hit_count: 0` visible in the message
   metadata tag.
3. **Request a Ship 30 essay** → router detects essay intent → retrieval on the
   requested topic → ship30 skill's structured system prompt (hook / 1-3-1 rhythm /
   skimmability / rate-of-revelation / specific takeaway, ~1,250 words) → essay
   returned as chat content.
4. **Request a Markdown or HTML artifact** → router detects artifact intent →
   generation wrapped in a fenced code block → frontend detects the fence, splits
   it into the Artifact Viewer panel beside chat, renders (Markdown directly,
   HTML in a sandboxed iframe).
5. **Switch model provider** → operator edits `MODEL_PROVIDER` in `.env`, restarts
   the API container → `/config` and the UI badge immediately reflect the new
   provider on next request; zero application code changes.
6. **A dependency fails** (DB down / Ollama unreachable / Anthropic key missing) →
   structured error surfaced at the appropriate layer (503 for DB-down before any
   row exists; a persisted error-bubble message for a model-provider failure after
   the user's message was already saved) -- see architecture.md sec 8d for why
   these two cases are handled differently.

## 6. Acceptance criteria

- [ ] A fresh clone + `docker compose up` (with `.env` filled in) serves a working
      chat UI, API, and Postgres+pgvector without manual DB setup.
- [ ] `POST /sessions` → `POST /sessions/{id}/messages` → `GET
      /sessions/{id}/messages` round-trips and survives an API restart.
- [ ] A question answerable from the corpus returns a response with ≥1 citation
      that resolves to a real, correct YouTube timestamp link (where the source
      episode has timestamp data).
- [ ] A question outside the corpus's coverage gets an explicit "not supported by
      the transcripts" answer, not a fabricated one.
- [ ] Switching `MODEL_PROVIDER` between `anthropic` and `ollama` requires zero
      code changes and is visible in the UI within one request.
- [ ] Stopping the Ollama server produces a structured, non-crashing failure
      visible to the user, not a hang or a stack trace.
- [ ] Stopping Postgres mid-session produces a structured 503, and the app
      recovers automatically once Postgres is back.
- [ ] A generated HTML artifact containing `<script>alert(1)</script>` does not
      execute the script when rendered.
- [ ] The Ship 30 essay skill produces ~1,250-word output (1,050-1,450 acceptable)
      whose claims trace back to real retrieved transcript chunks (spot-checked).
- [ ] `pytest` passes for session persistence, retrieval-against-real-data,
      provider-toggle logic, and API contract validation.

## 7. Risks and trade-offs

| Risk | Mitigation / honest status |
|---|---|
| **Hallucination** | System prompts hard-require "only use provided context, say so when insufficient" across all three skills; retrieval relevance floor (`RETRIEVAL_MIN_SCORE`) prevents low-relevance chunks from being presented as support. Not a hard guarantee -- an LLM can still ignore instructions, especially the small local model. Spot-checked, not exhaustively red-teamed. |
| **Local-model quality** | The mandatory local demo path (a 3.8B general-purpose Ollama model) is measurably weaker than Claude at following the Ship 30 structural constraints and at declining ungrounded questions cleanly. This is disclosed, not hidden -- the provider badge always shows which model answered so the evaluator can calibrate trust accordingly. |
| **Latency** | Both providers are called synchronously with no streaming; a ~1,250-word essay can take a noticeable number of seconds, worse on local hardware. Acceptable for an internal tool used a handful of times a session, not acceptable at higher-traffic scale without adding streaming. |
| **Cost** | Cloud path costs real API tokens per turn (~a few thousand input tokens of retrieved context + output). No caching of repeated-question embeddings/answers in this build -- a real cost-control follow-up. |
| **Data leakage** | Low risk in this build: no PII in the corpus (public podcast transcripts), no user auth/accounts to leak, and the DB has no other tenants' data. The main leakage surface is the `.env` file (real API keys) -- mitigated by `.gitignore` and a documented "never commit secrets" check before every push. |
| **Unsafe artifact rendering** | Addressed structurally (sandboxed iframe, `allow-scripts` never granted, defense-in-depth string sanitization) rather than only via prompt instructions not to include scripts -- see architecture.md sec 8e. Verified with a real script-injection test, not just described. |
| **Stale/incomplete corpus** | Ingestion is a manual re-run, not continuous; if Lenny's Podcast publishes a new episode, the assistant won't know until someone re-runs ingestion. Documented as an operational task in the README, not automated in this build. |

## 8. Implementation plan (as actually executed)

Phase 0 (scaffolding + real data-format recon) → Phase 1 (FastAPI/Postgres core,
verified with live curl + restart + DB-down tests) → Phase 2 (ingestion against the
real 303-episode corpus + pgvector retrieval, verified with real retrieved-chunk
output before any chat wiring) → Phase 3 (provider abstraction + deterministic
agent router + three skills) → Phase 4 (Ship 30 skill, principles read from the
real guide) → Phase 5 (React + Vite frontend, Artifact Viewer, responsive +
accessibility pass) → Phase 6 (Docker Compose, structured logging, deliberate
failure-mode testing) → Phase 7 (pytest suite + manual test plan) → Phase 8 (this
document + README + design.md + architecture.md) → Phase 9 (fresh-clone
verification, secret-scan, honest final summary). See `agent-transcripts/` for the
real per-phase build/verification log, including the actual dead ends hit (e.g. the
Postgres port collision in Phase 1, the no-timestamp transcript format discovered
mid-Phase-2) and how they were resolved.
