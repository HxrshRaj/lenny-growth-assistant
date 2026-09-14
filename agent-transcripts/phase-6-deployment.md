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

## Full docker compose verification

*(filled in once the rebuilt images finish and the full stack is brought up --
see the follow-up section below / phase-9 log for the actual `docker compose up`
output, health checks, and deliberate failure-mode tests: stopping `db`
mid-session, pointing `OLLAMA_BASE_URL` at nothing, and a zero-retrieval-hit
question.)*
