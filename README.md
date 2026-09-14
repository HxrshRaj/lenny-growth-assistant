# Lenny Growth Assistant

A full-stack, grounded conversational assistant over [Lenny's Podcast transcripts](https://github.com/ChatPRD/lennys-podcast-transcripts) — retrieval-augmented Q&A, a Ship 30 for 30 essay skill, and a Markdown/HTML artifact viewer, backed by FastAPI + PostgreSQL/pgvector, with a model-provider toggle between Anthropic Claude (cloud) and Ollama (local).

See also: [docs/PRD.md](docs/PRD.md) · [docs/architecture.md](docs/architecture.md) · [docs/design.md](docs/design.md) · [docs/manual-test-plan.md](docs/manual-test-plan.md) · [agent-transcripts/](agent-transcripts/)

## Architecture overview

```
apps/api/       FastAPI backend: sessions/messages (Postgres), retrieval (pgvector),
                 agent router + skills, model-provider abstraction (Anthropic/Ollama)
apps/web/        React + Vite frontend: chat UI, Artifact Viewer (sandboxed)
ingestion/       Standalone pipeline: clone transcript repo -> parse -> chunk ->
                 embed (sentence-transformers) -> upsert into pgvector
docs/            PRD, architecture, design, original assignment brief, manual test plan
agent-transcripts/  Phase-by-phase build/verification log (incl. dead ends + fixes)
```

Request flow for a chat turn: `POST /sessions/{id}/messages` → router classifies
intent (QA / Ship30 essay / Markdown artifact / HTML artifact) → pgvector retrieval
on the user's message → skill-specific prompt built from retrieved context → LLM
call via the active provider (Anthropic or Ollama) → response + citations persisted
and returned. Full detail: [docs/architecture.md](docs/architecture.md).

## Prerequisites

- Docker Desktop (with Docker Compose v2+)
- For local-model demo: [Ollama](https://ollama.com) running (`ollama serve`) with
  a model pulled -- **`ollama pull llama3.2:3b` is what this build was actually
  developed and verified against** and is recommended; other small models may
  work but were not tested (see "Troubleshooting" for a real issue found with
  an arbitrary local model)
- For cloud provider: either an Anthropic API key ([console.anthropic.com](https://console.anthropic.com/))
  or a Gemini API key ([aistudio.google.com/apikey](https://aistudio.google.com/apikey)) -- pick whichever
  you have; both are wired up identically via `MODEL_PROVIDER`
- Node.js 20+ and Python 3.11+ only if you want to run components outside Docker

## Install & run (one command)

```bash
cp .env.example .env
```

Edit `.env`:
- Set `MODEL_PROVIDER=ollama` (default, required for the mandatory local demo),
  `anthropic`, or `gemini`.
- If `ollama`: set `OLLAMA_MODEL` to a model you've actually pulled (`ollama list`
  to check). `OLLAMA_BASE_URL` defaults to `http://host.docker.internal:11434` so
  the containerized API can reach Ollama running on your host machine.
- If `anthropic`: set `ANTHROPIC_API_KEY`.
- If `gemini`: set `GEMINI_API_KEY` (get one free at
  [aistudio.google.com/apikey](https://aistudio.google.com/apikey)).

```bash
docker compose up
```

This brings up Postgres (with pgvector), the API (runs Alembic migrations
automatically on startup), and the web frontend.

- Web UI: http://localhost:5173
- API: http://localhost:8000 (docs at http://localhost:8000/docs)
- Postgres: `localhost:5442` (not 5432 — see "Troubleshooting" below)

**The knowledge base is empty until you run ingestion once** (not part of
`docker compose up` by default — it's a one-off job, not a server):

```bash
docker compose --profile ingestion run --rm ingestion
```

This clones `ChatPRD/lennys-podcast-transcripts`, chunks ~303 episodes, embeds them
locally (`all-MiniLM-L6-v2`), and upserts into Postgres. Takes roughly 15-20
minutes on a laptop CPU (downloads the embedding model once, then re-runnable
idempotently — re-running after a `git pull` on the source repo only re-embeds
changed/new episodes' worth of new rows, existing rows are upserted in place).

## Environment variables

See [.env.example](.env.example) for the full list with inline comments. Summary:

| Variable | Required | Purpose |
|---|---|---|
| `POSTGRES_USER`/`PASSWORD`/`DB`/`PORT` | no (safe defaults) | Postgres container config |
| `DATABASE_URL` | yes | SQLAlchemy connection string used by the API + Alembic |
| `MODEL_PROVIDER` | yes | `anthropic`, `gemini`, or `ollama` — the ONLY switch needed to change providers |
| `ANTHROPIC_API_KEY` | only if provider=anthropic | never commit a real value |
| `ANTHROPIC_MODEL` | no | defaults to `claude-sonnet-5` |
| `GEMINI_API_KEY` | only if provider=gemini | never commit a real value |
| `GEMINI_MODEL` | no | defaults to `gemini-2.0-flash` |
| `OLLAMA_BASE_URL` | only if provider=ollama | where `ollama serve` is reachable from the API container |
| `OLLAMA_MODEL` | only if provider=ollama | must match a model you've pulled |
| `EMBEDDING_MODEL` | no | defaults to `all-MiniLM-L6-v2`; change here AND re-run ingestion if you ever swap it |
| `RETRIEVAL_TOP_K` / `RETRIEVAL_MIN_SCORE` | no | retrieval tuning |
| `CORS_ORIGINS` | no | defaults to the local frontend origin |
| `VITE_API_BASE_URL` | yes (frontend) | where the frontend finds the API |

## Local (non-Docker) development

Useful for fast iteration on the API without rebuilding a container each time.

```bash
cd apps/api
python -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash; use bin/activate on macOS/Linux
pip install -r requirements.txt
# .env in apps/api/ should point DATABASE_URL at localhost:5442 (see apps/api/.env)
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

```bash
cd apps/web
npm install
npm run dev
```

```bash
cd ingestion
pip install -r requirements.txt
DATABASE_URL=postgresql+psycopg://lenny:lenny@localhost:5442/lenny python ingest.py
```

## Tests

```bash
cd apps/api
source .venv/Scripts/activate
pytest -v
```

Requires the `db` container (or a local Postgres) reachable via `DATABASE_URL`.
Retrieval tests skip gracefully (not fail) if ingestion hasn't been run yet.
Provider-toggle tests intentionally point at an unreachable Ollama URL / missing
Anthropic key to exercise real failure-handling code — they don't need a live
Ollama or Anthropic account to pass, so they're portable to any evaluator's
machine.

Retrieval verification script (prints real retrieved chunks for 5 real questions —
run this to *see* retrieval working, not just watch tests pass):

```bash
cd ingestion
DATABASE_URL=postgresql+psycopg://lenny:lenny@localhost:5442/lenny python scripts/verify_retrieval.py
```

Manual UI test plan: [docs/manual-test-plan.md](docs/manual-test-plan.md).

## Troubleshooting

- **Postgres port is 5442, not 5432.** This machine had another project already
  bound to 5432; `.env.example` defaults to 5442 to sidestep that whole class of
  "which Postgres did I actually connect to" bug. Override `POSTGRES_PORT` in your
  own `.env` if you'd rather use 5432 and it's free on your machine.
- **`/health` shows `"database": "unreachable"`**: Postgres container isn't up
  yet, or `DATABASE_URL` doesn't match `POSTGRES_PORT`. `docker compose ps` to
  check container status; `docker compose logs db` for Postgres's own logs.
- **`/health` shows `"ollama": "unreachable"`** (only checked when
  `MODEL_PROVIDER=ollama`): confirm `ollama serve` is actually running on the host
  and `OLLAMA_BASE_URL` is reachable *from inside the API container* — on
  Windows/Mac that's `http://host.docker.internal:11434`, not `localhost`, because
  `localhost` inside a container means the container itself.
- **A chat turn returns an ⚠️ error bubble instead of an answer**: check the
  `error` field / API logs. Most common causes: `OLLAMA_MODEL` isn't pulled
  (`ollama pull <model>`), Ollama timed out (CPU inference of even a small model
  can genuinely take several minutes for a RAG-sized prompt, depending on
  hardware and what else is running — `OLLAMA_TIMEOUT_SECONDS` is tunable, this
  build defaults to 240s), or `ANTHROPIC_API_KEY` is unset/invalid. This is
  graceful failure by design (see architecture.md sec 8d), not a bug — the turn
  is still saved so you don't lose your message.
- **A chat turn returns HTTP 200 with completely empty content, no error**: this
  bit us for real during development -- Ollama silently defaults `num_ctx` to
  2048 regardless of what the model actually supports, so a longer RAG prompt
  can consume the whole window and leave no room to generate. Already fixed in
  this build (`OLLAMA_NUM_CTX` is always sent explicitly), but if you swap in a
  model with a *smaller* context than 4096, lower `OLLAMA_NUM_CTX` to match it.
- **Model choice matters more than you'd expect for RAG.** This build was
  developed and tested against `llama3.2:3b` (`ollama pull llama3.2:3b`) after
  discovering, live, that an arbitrary small fine-tuned model can return
  well-formed HTTP responses containing *incoherent garbage text* despite
  correct retrieval underneath it — no error, just a bad answer. If you swap in
  a different local model and answers look wrong/garbled, suspect the model
  before suspecting the retrieval or prompt code (check `retrieval_hit_count`
  and `citations` on the response first — if those look right, the problem is
  the model, not this codebase).
- **A grounded answer is slow (multiple minutes) on the local provider.** This
  is real, measured CPU-inference latency for a ~3B model doing RAG generation,
  not a hang. `RETRIEVAL_TOP_K` defaults to 3 (not 5) specifically to keep this
  tractable; lowering it further, or switching `MODEL_PROVIDER=anthropic`, are
  the two levers if this matters for your use.
- **`docker compose restart api` doesn't pick up a `.env` change.** `restart`
  reuses the container's already-baked-in environment; use
  `docker compose up -d --force-recreate api` (or `down` + `up`) to actually
  re-read `.env`.
- **Every answer says "the transcripts don't support this"**: ingestion probably
  hasn't been run yet (`SELECT count(*) FROM chunks;` in `psql` should be in the
  thousands after a full run). Run the ingestion profile (see above).
- **Empty citations on an otherwise-good answer**: `RETRIEVAL_MIN_SCORE` may be
  filtering out genuinely-relevant-but-lower-scoring chunks for an unusual phrasing
  of the question — try lowering it in `.env` and restarting the API.
- **`docker compose up` fails building the API image (torch/sentence-transformers
  download)**: first build downloads a few hundred MB of ML dependencies; slow
  networks may need the build timeout raised, or run `ingestion`/`api` outside
  Docker per "Local development" above.

## Known limitations

See PRD "Risks and trade-offs" and the honest final-summary note at the end of
`agent-transcripts/` for the full list — briefly: no streaming responses, no
multi-session browsing UI, no scheduled corpus refresh, and local-model output
quality is measurably weaker than the cloud path (disclosed via the provider badge,
not hidden).
