# Phase 6 — Deployment & operational readiness

## Dead end: default torch wheel pulls multi-GB of unused CUDA dependencies

Kicked off `docker compose build api web ingestion` to verify the one-command
Docker path. `web` finished quickly (532MB, mostly `node_modules`). `api` and
`ingestion` both stalled for 10+ minutes on `pip install -r requirements.txt`
with no visible progress -- initially assumed the build had hung.

Investigated instead of just waiting indefinitely: re-checked the build log and
found the actual cause -- `torch` (a transitive dependency of
`sentence-transformers`) had finished its own 554.6MB download, then pip moved on
to download `nvidia_cudnn_cu13` (**553.1MB by itself**), with `cuda_toolkit` and
presumably several more NVIDIA packages (cublas, cufft, nccl, etc.) still queued
behind it. The default PyPI `torch` wheel on Linux bundles full CUDA/GPU support
by default, even though this build only ever does CPU inference (no GPU in any of
the target deployment environments -- a dev laptop or a plain evaluator machine).
That's multiple **additional** gigabytes of download for libraries that would
never be used.

**Fix**: added `--extra-index-url https://download.pytorch.org/whl/cpu` plus an
unpinned `torch` line to both `apps/api/requirements.txt` and
`ingestion/requirements.txt`, ahead of `sentence-transformers` in the file --
PyTorch publishes CPU-only wheels (no CUDA deps at all) at that index. Killed the
in-progress build (`taskkill` on the `docker.exe`/`docker compose build`
process -- there is no clean `docker compose build --cancel`, and letting it
finish would have cost real additional time and disk for nothing) and restarted
`docker compose build api ingestion` with the fix in place.

**Why this matters beyond just build time**: it also means the shipped container
images are dramatically smaller (no multi-GB CUDA runtime baked in), which
directly serves the "practical, reproducible one-command startup" requirement --
an evaluator with an ordinary internet connection and no GPU shouldn't have to
download GPU libraries they'll never use just to run local embedding inference on
a few thousand short text chunks.

## Full docker compose verification (real, not simulated)

Brought up the entire stack with `docker compose up -d` (no `db`/`api`/`web`
containers running outside compose): all three healthy, `web` on :5173 reachable
in the browser (screenshot taken, provider badge live), `api` on :8000 answering
`/health` and `/config` with real DB/Ollama status, `db` on :5442 holding the
full 17,079-chunk index untouched across a `down`/`up` cycle (named volume
persists). Full chat pipeline verified through this exact stack -- see
`agent-transcripts/phase-3-agent-layer.md` and `phase-4-ship30-skill.md` for the
real grounded/ungrounded/essay results, all produced by the containerized `api`
talking to Postgres-in-a-container and Ollama-on-the-host via
`host.docker.internal`.

## Deliberate failure-mode tests (Phase 6 requirement)

**Ollama down**: covered for real, repeatedly, by the actual local-model dead
ends in Phase 3 (context-window overflow, timeout, garbled-model output) --
every one of those produced a structured, non-crashing `LLMProviderError` ->
persisted error-bubble assistant message, never a raw exception or a hung
request past its configured timeout.

**DB down mid-session**: `docker stop lenny-growth-assistant-db-1` while the API
container was up; `GET /health` correctly flipped to
`{"status":"degraded","database":"unreachable"}`; `POST /sessions` returned a
structured `503 {"error":"database_unavailable",...}`. Restarted `db`, `/health`
recovered automatically on the next poll -- no API restart needed (already
verified once in Phase 1 against the host-venv setup; re-confirmed here against
the actual containerized API to be sure the behavior holds through the real
deployment path, not just dev).

**Zero-retrieval-hit question**: covered live in Phase 3 (the 2034 Winter
Olympics question) -- retrieval returned weak-scoring chunks, the model
correctly declined based on content relevance rather than fabricating an
answer. `retrieval_hit_count` and `citations` both reflect this accurately in
the stored message for later audit.

## Real operational lessons from this phase, beyond the torch/CUDA fix

- `docker compose restart <service>` does NOT re-read `.env` -- only
  `up -d --force-recreate <service>` (or `down`+`up`) does. Cost real debugging
  time (a fix appeared not to apply, `candidates: 5` still showing in logs after
  changing `RETRIEVAL_TOP_K`) before being traced to this. Documented in README
  troubleshooting.
- A freshly-recreated `api` container has no persistent cache for the
  `sentence-transformers` embedding model and re-downloads it from HuggingFace
  on first use -- which also intermittently failed with a DNS resolution error
  live during testing (transient, resolved itself on retry, but is a real
  runtime dependency on external connectivity that shouldn't exist for a model
  that's fully known at build time). Fixed by baking the model into both
  `apps/api/Dockerfile` and `ingestion/Dockerfile` at build time -- removes the
  runtime download entirely, makes container startup fast and
  network-independent.
- Running a Docker image build concurrently with the CPU-heavy ingestion
  embedding job on the same machine slowed both dramatically (observed
  ingestion per-episode time roughly double, from ~4s to ~8-13s, while `pip
  install torch` competed for the same CPU/disk). Killed the build, let
  ingestion finish, rebuilt after -- documented as a real resource-contention
  lesson for anyone running this on a single dev machine rather than separate
  CI infrastructure.
