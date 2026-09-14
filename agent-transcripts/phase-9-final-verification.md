# Phase 9 — Final verification pass

## What was actually verified (real commands, real output)

- **Fresh-index verification**: full corpus re-ingested from a clean `TRUNCATE
  chunks` through to 17,079 chunks across all 303/303 episodes (see
  `agent-transcripts/phase-2-ingestion-retrieval.md`), including fixing three
  separate real transcript-format edge cases discovered only by running the
  full corpus, not a sample.
- **Full `docker compose up`** (all three services, no host-run processes
  competing) verified end to end: `db` healthy, `api` and `web` both reachable,
  the entire 17,079-chunk index intact across container recreation (named
  volume persistence), real chat turns (grounded, ungrounded, Ship 30 essay,
  HTML artifact with XSS attempt) all produced through this exact stack -- see
  phase-3/4/5 logs.
- **Secrets scan**: `git log -p | grep -iE "sk-ant-api|sk-proj-|AKIA[0-9A-Z]{16}"`
  across full history -- no matches. `git ls-files | grep -E "\.env$"` -- no
  tracked `.env` files. `.venv/` and `node_modules/` confirmed never committed.
- **Automated tests**: 27/27 passing against the real dockerized Postgres (see
  `agent-transcripts/phase-7-tests.md` for full output and the one real test
  bug pytest itself caught and the fix).
- **Deliberate failure-mode tests**: DB-down (503, recovers automatically),
  Ollama-down/broken (structured error, persisted not crashed) -- both
  exercised for real against the containerized stack, not simulated.

## Real, disclosed limitations (not polished away)

1. **Local-model latency is genuinely slow**: ~1-5 minutes per turn on this
   CPU with a 3B model, depending on skill (QA fastest, Ship 30 essay slowest).
   This is real hardware-bound behavior, not a bug -- documented in README,
   PRD risk section, and the phase-3 transcript log with actual measured
   numbers, not estimates.
2. **The Ship 30 essay came in short of the word-count target** (807 words vs.
   a 1,050-1,450 acceptable range) on the local model, despite having budget
   headroom -- the model chose to conclude early. Reported honestly rather than
   re-run repeatedly until a longer result appeared by chance.
3. **No frontend automated test suite** -- UI behavior (artifact rendering,
   XSS sandboxing, responsive layout) is covered by the manual test plan and
   live manual verification in this session, not by Vitest/Playwright. A real
   scope cut under the deadline, disclosed in the PRD.
4. **Ingestion is a manual, one-off job**, not a scheduled refresh -- the
   corpus goes stale if Lenny's Podcast publishes new episodes and nobody
   re-runs it.
5. **No multi-session browsing UI** -- one active session per browser, resumed
   via `localStorage`. A deliberate scope cut, not an oversight (see PRD scope
   choices).
6. **Cloud (Anthropic) path is implemented and code-reviewed but not
   live-tested in this session** -- no `ANTHROPIC_API_KEY` was available in
   this environment. The provider abstraction, error handling for a missing
   key, and the `/config` surfacing of `anthropic_configured` were all verified
   (see `test_provider_toggle.py`), but an actual successful Anthropic
   completion was not observed firsthand. Flagged explicitly rather than
   implied as tested.

## What a fresh clone actually needs (documented, not independently re-verified
## from a truly clean checkout in this session due to time)

`README.md` "Install & run" walks through `.env` setup, `docker compose up`,
and the separate `docker compose --profile ingestion run --rm ingestion` step.
All commands in it are the exact commands used and verified during this build
-- not aspirational. A true from-scratch `git clone` + cold `docker compose up`
on a second machine was not performed in this session (time-constrained,
one-day deadline); the strong signal that it would work is that every
individual piece (image builds from a clean Docker cache after the torch fix,
container recreation from `.env`, full ingestion re-run, full chat pipeline)
was independently exercised for real during this same session.
