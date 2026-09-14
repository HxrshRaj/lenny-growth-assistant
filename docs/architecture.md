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
Full schema documented in §"Database schema" below, added in Phase 1.
