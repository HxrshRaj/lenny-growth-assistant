# Architecture

Status: living document, updated as phases land. This section (Phase 0) covers the
source data format and the chunking/retrieval design decided *before* writing any
ingestion code, per the actual data — not an assumed format.

## 1. Source data: `ChatPRD/lennys-podcast-transcripts`

Inspected by cloning the repo directly (commit at time of inspection: HEAD of `main`,
2026-09-14). Actual structure:

```
lennys-podcast-transcripts/
├── episodes/
│   └── {guest-slug}/
│       └── transcript.md      # one file per episode, Markdown + YAML frontmatter
├── index/                     # AI-generated topic index (not used for ingestion;
│                               #   useful later for topic-based UI filters, skipped for MVP)
└── scripts/build-index.sh
```

Key facts (measured, not assumed):

- **303 episode folders**, each with exactly one `transcript.md`. The repo's own
  README claims "269 episode transcripts" — that count is stale; we ingest whatever
  is actually present at ingestion time (303 as of this build).
- **Format per file**: YAML frontmatter block (`---...---`) followed by a `# {title}`
  heading, a `## Transcript` heading, then the transcript body as speaker-labeled
  paragraphs.
- **Frontmatter fields actually present**: `guest`, `title`, `youtube_url`, `video_id`,
  `publish_date` (YYYY-MM-DD), `description`, `duration_seconds`, `duration`,
  `view_count`, `channel`, `keywords` (list of tags).
- **Transcript body format**: paragraphs are either
  - `Speaker Name (HH:MM:SS):` on its own line followed by the spoken text, or
  - `(HH:MM:SS):` alone (a continuation of the previous speaker, no name repeated).
  There is no explicit end-timestamp per turn — only a start timestamp per paragraph.
- **Size**: word count per transcript ranges 1,666–28,813 words, median 15,047,
  mean 15,320 (measured across all 303 files). At ~0.75 words/token that's roughly
  2,200–38,000 tokens per episode — too large to embed as a single chunk, and too
  variable to use a fixed number-of-chunks-per-episode rule.
- No non-`transcript.md` files exist inside any episode folder — ingestion can
  glob `episodes/*/transcript.md` with no filtering needed.

This means: no JSON, no per-sentence timestamps, no diarization confidence scores —
just Markdown with coarse (per-turn) timestamps. The chunker has to reconstruct turn
boundaries from the `Name (HH:MM:SS):` / `(HH:MM:SS):` pattern itself.

## 2. Chunking strategy

**Decision: chunk by accumulated speaker turns, not fixed character windows.**
Splitting mid-turn (e.g. a hard 500-character cut) would sever a speaker's sentence
mid-thought and produce citations that don't read as a coherent quote. Instead:

1. Parse each `transcript.md` into an ordered list of **turns**: `(speaker, start_hms,
   start_seconds, text)`. A continuation line (`(HH:MM:SS):` with no name) inherits
   the speaker of the immediately preceding turn but still gets its own timestamp —
   kept as a separate turn internally so timestamp granularity isn't lost, but two
   consecutive turns from the *same* speaker are merged into one logical turn before
   chunking (a "continuation" is a pause/edit artifact, not a speaker change).
2. Accumulate merged turns into a chunk until the running **word count reaches
   ~300 words** (target range 220–380 words, ≈ 300–500 tokens). A chunk boundary is
   only ever placed *between* turns, never inside one — if a single turn alone
   exceeds ~380 words (long monologue answers do happen), that turn becomes its own
   chunk rather than being cut.
3. **Overlap: carry the last 1 full turn (or last ~50 words of the last turn if it's
   long) forward into the next chunk.** This preserves the conversational hand-off
   (a question at the end of chunk N is often what chunk N+1's answer is responding
   to) without re-embedding entire chunks' worth of duplicate text.
4. Why word-based over token-based: the ingestion pipeline doesn't need the LLM's
   tokenizer to make chunking decisions consistent across embedding-model swaps;
   word count is a stable, model-agnostic proxy and easy to reason about /
   spot-check by eye in review.

**Chunk size trade-off, stated explicitly:** ~300 words is small enough that a
retrieved chunk is almost always about one coherent question/answer exchange (good
retrieval precision — the agent gets a focused quote to cite), and large enough that
`all-MiniLM-L6-v2`-class embeddings (384-dim, max 256 word-pieces) don't truncate the
chunk before it's fully encoded. Smaller chunks (e.g. 100 words) were considered and
rejected: they fragment multi-sentence answers and roughly triple index size/query
latency for negligible precision gain on this corpus, where most Q&A exchanges run
150–400 words.

## 3. Chunk metadata

Every chunk stores enough to (a) reconstruct a real citation and (b) filter/debug
retrieval later:

| Field | Source | Purpose |
|---|---|---|
| `episode_slug` | folder name | stable episode id |
| `guest` | frontmatter | display name in citation |
| `title` | frontmatter | episode title in citation |
| `youtube_url` | frontmatter | base link |
| `video_id` | frontmatter | dedupe / thumbnails later |
| `publish_date` | frontmatter | recency signal, display |
| `channel` | frontmatter | always "Lenny's Podcast" today, kept for future multi-show ingestion |
| `keywords` | frontmatter | optional topic filter (not used by retrieval in MVP, stored for later) |
| `chunk_index` | computed | position within episode, for ordering / debugging |
| `speakers` | computed | distinct speaker name(s) in this chunk |
| `start_timestamp` / `end_timestamp` | computed (HH:MM:SS) | human-readable citation |
| `start_seconds` | computed | used to build a deep link |
| `source_url` | computed = `{youtube_url}&t={start_seconds}s` | **click-through citation straight to the moment in the video**, not just the episode |
| `word_count` | computed | debugging / re-chunk audits |
| `text` | computed | the chunk's actual text (embedded) |

`source_url` is why start-second tracking matters even though the transcript only
gives per-turn granularity: every cited chunk resolves to a real, timestamped
YouTube link, not just "somewhere in this 45-minute episode."

## 4. Embedding model

**Decision: local `sentence-transformers` (`all-MiniLM-L6-v2`), not a cloud
embeddings API.** Rationale:
- Ingestion runs once over ~303 episodes / ~15–20k chunks; a local CPU model finishes
  in a few minutes and has zero marginal cost and no external dependency during
  ingestion or at query time.
- Keeps the embedding step decoupled from the model-provider toggle in Phase 3
  (Claude vs. Ollama) — swapping the *generation* provider must never require
  re-embedding the corpus.
- 384-dim vectors keep the pgvector index small and fast on a laptop-class Postgres
  container.
- Documented trade-off: MiniLM is weaker than e.g. `text-embedding-3-small` on some
  benchmarks. Acceptable here because retrieval only needs to separate ~300-word
  podcast-answer chunks by topic, not do fine-grained legal/code search. Swapping to
  a stronger embedding model later only requires changing the ingestion config and
  re-running ingestion — no schema change (column is `vector(384)`; documented as the
  one constant to update if the model changes).

## 5. Storage

`pgvector` extension on the Postgres container (added in `docker-compose.yml`).

## 6. Database schema (Phase 1)

Two tables exist after Phase 1's migration (`apps/api/alembic/versions/e072768ca708_*`);
a third (`chunks`) is added in Phase 2. All managed by Alembic, driven by the
SQLAlchemy models in `apps/api/app/models.py`.

**`sessions`**
| column | type | notes |
|---|---|---|
| id | uuid, PK | |
| user_id | varchar(255) | placeholder -- no auth system in this build; defaults to `"anonymous"` |
| title | varchar(500), nullable | not auto-generated yet (candidate future feature) |
| created_at | timestamp, server default `now()` | |
| updated_at | timestamp, server default + `onupdate` `now()` | |

**`messages`**
| column | type | notes |
|---|---|---|
| id | uuid, PK | |
| session_id | uuid, FK -> sessions.id, `ON DELETE CASCADE` | |
| role | varchar(20) | `"user" \| "assistant" \| "system"` |
| content | text | |
| model_provider | varchar(20), nullable | `"anthropic" \| "ollama"`, set on assistant turns once Phase 3 lands |
| model_name | varchar(100), nullable | the actual model string used, for audit |
| retrieval_hit_count | int, nullable | how many chunks were retrieved for this turn (Phase 2/3) |
| citations | jsonb, nullable | list of `{episode_slug, guest, title, source_url, start_timestamp, text_preview}` |
| latency_ms | int, nullable | wall-clock time to produce the assistant turn |
| error | text, nullable | set instead of failing the request when a turn partially fails (e.g. LLM call errored after retrieval succeeded) |
| created_at | timestamp, server default `now()` | |

Index: `ix_messages_session_id_created_at` on `(session_id, created_at)` -- the only
query pattern the app actually runs against this table (list a session's messages
in order).

Why these audit columns exist on `messages` and not a separate `audit_log` table:
every assistant turn already *is* one row per model call, so attaching
provider/latency/citations/error directly to it gives a complete per-response audit
trail with zero joins -- exactly what "observability" in Phase 6 needs to query.

## 7. API endpoints (Phase 1)

| Method | Path | Purpose | Key errors |
|---|---|---|---|
| GET | `/health` | Live DB + (if provider=ollama) Ollama reachability check | never errors; reports `"degraded"` in the body |
| GET | `/config` | Active model provider + whether each provider is actually usable right now | |
| POST | `/sessions` | Create a session | 422 on bad body |
| GET | `/sessions/{id}` | Fetch one session | 404 |
| POST | `/sessions/{id}/messages` | Send a message, get the assistant's persisted reply | 404 (bad session), 422 (empty/too-long content), 503 (DB down) |
| GET | `/sessions/{id}/messages` | Full message history, chronological | 404 |

Every error response has the shape `{"error": str, "detail": str, "code": str}` --
see `apps/api/app/errors.py`. No endpoint ever returns a raw stack trace; unexpected
exceptions are logged server-side (structured JSON via structlog) and returned to
the client as a generic 500 with `code: "INTERNAL_ERROR"`.

## 8a. `chunks` table (Phase 2)

Added by `apps/api/alembic/versions/a4f4b631a549_*`, owned by
`apps/api/app/models_retrieval.py`. Full column list mirrors the metadata table in
sec 3 above, plus `id` (uuid PK), `text` (the embedded chunk text), `embedding`
(`vector(384)`), `created_at`. Constraints: `UNIQUE(episode_slug, chunk_index)` so
re-running ingestion after a `git pull` upserts instead of duplicating; an HNSW
index (`vector_cosine_ops`) on `embedding` for fast approximate cosine search; a
btree index on `episode_slug`.

**Component boundary, intentional**: `ingestion/` is a separate Docker build
context with no import access to `apps/api/app` -- it writes to `chunks` with plain
parameterized SQL (`ingestion/ingest.py`) against the exact columns Alembic
creates, rather than sharing ORM model code across two independently-deployable
services. Alembic (in `apps/api`) is the single schema source of truth; ingestion
is a data loader, not a schema owner.

## 8b. Retrieval flow

`apps/api/app/services/retrieval.py::retrieve(db, query)`:
1. Embed the query with the same `all-MiniLM-L6-v2` model used at ingestion time
   (`app/services/embeddings.py`, lazy-loaded singleton).
2. `ORDER BY embedding <=> :query_vec LIMIT top_k` using pgvector's cosine-distance
   operator (via the HNSW index) -- `SELECT ..., 1 - (embedding <=> :q) AS score`.
3. Drop any hit below `RETRIEVAL_MIN_SCORE` (default 0.15) -- this is what lets the
   agent say "the transcripts don't cover this" instead of returning a technically-
   top-5-but-irrelevant chunk as if it were a real answer.
4. Every hit carries its full source metadata straight through to the API response
   (`Citation` schema) -- no separate "look up the source" step.

## 8c. Agent routing (Phase 3)

`apps/api/app/services/agent.py::run_turn()` is the single orchestrator:
`router.classify_intent()` -> `retrieval.retrieve()` -> skill-specific
system-prompt + message construction -> `llm.complete()`.

**Router is deterministic (regex/keyword), not LLM-driven tool-calling** --
documented trade-off, not an oversight. Reasoning:
- The assignment requires the **local Ollama path to work for the demo**. Small
  local models (this build ships against a 3.8B model) are unreliable at
  structured tool-calling; making routing depend on it would make the mandatory
  local demo path the least reliable part of the system.
- A deterministic router gives **identical routing behavior on both providers** --
  a evaluator switching `MODEL_PROVIDER` sees the same skill selected for the same
  input, which is easier to reason about and test than "usually picks the right
  tool."
- Each skill (`app/services/skills/{qa,ship30,artifact}.py`) is still a real,
  separate, structured component with its own system prompt and message-building
  logic -- satisfying "encode the skill explicitly" without needing the routing
  *decision itself* to be model-driven.
- Documented limitation: a message that doesn't match any keyword pattern always
  falls through to the QA skill, even if the user's intent was actually "write me
  an essay" phrased unusually. Acceptable for this build; a production version
  would add LLM-driven routing behind a provider capability flag (only enabled for
  providers/models known to support reliable tool-calling).

Skills:
- **`qa`** (default): grounded Q&A, includes recent conversation history for
  follow-ups, instructed to explicitly decline when context is insufficient.
- **`ship30_essay`**: Ship 30 for 30 structural principles (sec 4.2 in PRD),
  extracted from the real guide, encoded as an explicit system-prompt template in
  `skills/ship30.py` -- not an inline one-off prompt.
- **`artifact_markdown` / `artifact_html`**: instructs the model to emit the
  artifact inside a ```markdown or ```html fence; the frontend detects that fence
  (`extractArtifact.js`) and renders it in the Artifact Viewer instead of as chat
  prose.

## 8d. Model-provider toggle

One env var, `MODEL_PROVIDER` (`anthropic` | `ollama`), read once into
`app.config.Settings`. `app/services/llm.py::complete()` is the only place that
branches on it -- no other module imports `anthropic` or makes an Ollama HTTP call
directly. Switching providers is `.env` edit + restart, zero code changes.
`GET /config` surfaces the active provider and whether it's actually reachable
right now (not just "configured").

**Fallback behavior**: every provider failure (missing `ANTHROPIC_API_KEY`, Ollama
unreachable, Ollama timeout, non-200 from either API) is caught in `llm.py` and
raised as `LLMProviderError(provider, detail)`. `agent.py` catches that and returns
a normal `AgentTurnResult` with `error` set and a clearly-labeled ⚠️ message as the
`content` -- the turn is still persisted (the user doesn't lose their message) and
the API still returns `201`, not a 5xx, because the *request* succeeded (a message
was created); it's the *model call* that failed. This is a considered choice over
returning a 503: a 503 would leave nothing in the session for the user to see when
they reload, whereas a persisted error-bubble message behaves like a real chat
product's inline failure state. (Contrast with DB-down, sec 7: that fails before
any row exists, so it *does* have to be a 503 -- there's nothing to persist.)

## 8e. Artifact security

The frontend (`apps/web/src/components/ArtifactViewer.jsx`) renders HTML artifacts
in `<iframe sandbox="allow-same-origin">` -- deliberately **without**
`allow-scripts`.

**What this permits**: normal DOM rendering, inline `<style>` and CSS, images,
layout, fonts -- everything a static HTML/CSS snippet needs to look right.

**What this blocks**: `allow-scripts` is the *only* sandbox token that permits
script execution. Without it, `<script>` tags, inline event handlers
(`onclick="..."`), and `javascript:` URIs are all inert -- the browser simply does
not execute them, full stop. No form submission (`allow-forms` not granted), no
popups (`allow-popups` not granted), no top-level navigation escape.

**Why `allow-same-origin` alone is safe here**: the well-known sandbox footgun is
combining `allow-scripts` **and** `allow-same-origin` together -- that combination
lets a malicious script use same-origin privileges to reach out of the sandbox
entirely. Since this build never grants `allow-scripts`, there is no script
execution to escape with in the first place; `allow-same-origin` alone just lets
the iframe's content render with normal-origin semantics (so relative
URLs/fonts/etc. behave as expected) with no script capability to exploit it.

**Defense in depth**: `apps/web/src/utils/sanitizeHtml.js` strips `<script>`
blocks, `on*` attributes, and `javascript:` hrefs/srcs from the artifact body
*before* it's handed to the iframe, as an independent second layer -- so the
artifact never even contains an obvious injection attempt, in case a future change
ever loosens the sandbox. Verified in Phase 5 testing: a generated artifact
containing `<script>alert(1)</script>` renders with the script stripped/inert, no
alert fires (see `agent-transcripts/phase-5-frontend.md`).

Markdown artifacts render via `react-markdown` with the default (safe) config --
raw HTML passthrough is never enabled, so a Markdown artifact can't smuggle in an
HTML/script payload either.

## 9. Deployment note: Postgres port

The default `docker-compose.yml`/`.env.example` publish Postgres on host port
**5442**, not 5432. This machine had an unrelated project already bound to 5432,
which caused silent password-auth failures against the *wrong* Postgres instance
until traced with `netstat`. 5442 avoids the whole class of "which Postgres did I
actually connect to" bugs on a dev machine that already runs other containers; if
5432 is free on the evaluator's machine they can still override `POSTGRES_PORT` in
their own `.env`.
