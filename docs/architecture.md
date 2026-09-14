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

## 8. Deployment note: Postgres port

The default `docker-compose.yml`/`.env.example` publish Postgres on host port
**5442**, not 5432. This machine had an unrelated project already bound to 5432,
which caused silent password-auth failures against the *wrong* Postgres instance
until traced with `netstat`. 5442 avoids the whole class of "which Postgres did I
actually connect to" bugs on a dev machine that already runs other containers; if
5432 is free on the evaluator's machine they can still override `POSTGRES_PORT` in
their own `.env`.
