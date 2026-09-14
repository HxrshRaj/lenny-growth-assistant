# Phase 0 — Scaffolding & decisions

## Environment recon (done before any scaffolding)

Checked what's actually available on this machine before committing to tooling:

- git 2.53.0, Python 3.11.9, Node 24.13.0, npm 11.6.2 — all present.
- Docker CLI + Compose v5.1.4 installed, **but the Docker Desktop engine is not
  running** (`docker ps` fails to reach the named pipe). This blocks verifying
  `docker compose up` until the user starts Docker Desktop. Flagged to user; not a
  blocker for Phase 0/early Phase 1 work (can run Postgres later once Docker is up,
  or install a local Postgres — decided to wait for Docker since docker-compose is
  the assignment's documented deployment path anyway).
- No local `psql` — no bare-metal Postgres. Confirms Postgres will come from the
  Docker container, not a host install.
- `ANTHROPIC_API_KEY` is **not set** in this shell. Needed for real Phase 3 cloud-path
  verification. Flagged to user — will ask them to put it in `apps/api/.env` (not
  pasted into chat) once we reach Phase 3, rather than guessing a value or stubbing
  the cloud path.
- Ollama **is** running locally (`localhost:11434` reachable) with one model already
  pulled: `mymodel:latest`, a 3.8B llama-family model, Q4_K_M quant, 4096 context.
  This is enough to verify the local-provider path for real. Noting for later: a
  generic 3.8B chat model will produce noticeably weaker structured output (e.g. the
  Ship 30 essay skill) than Claude — that's an expected, honest limitation of the
  "local" path, not a bug.

## Repo structure

Created the exact layout the assignment specifies:
```
lenny-growth-assistant/
  apps/api/  apps/web/  ingestion/  docs/  agent-transcripts/
```
`git init` + `git config user.name "Harsh Raj"` / `user.email hraj15709@gmail.com` as
instructed. No AI co-author trailers will be added to commits (explicit instruction
from the user, which overrides the harness's default attribution footer for this
repo's commits).

## Inspecting the actual transcript repo (before writing ingestion code)

Cloned `https://github.com/ChatPRD/lennys-podcast-transcripts` (shallow clone) into
the scratch dir to inspect real files rather than trust the assignment's assumption
about format. Findings (full detail now in `docs/architecture.md` §1):

- It's **Markdown with YAML frontmatter**, one file per episode at
  `episodes/{guest-slug}/transcript.md` — not JSON, not plain text, not one giant
  file. 303 episode folders present (the repo's own README says 269 — stale; we go
  with what's actually on disk, 303, and the ingestion pipeline should always trust
  a live count over any hardcoded number).
- Frontmatter gives us guest name, episode title, YouTube URL + video_id, publish
  date, description, duration, view count, and a keywords list — everything needed
  for a real citation, no additional metadata source required.
- Transcript body uses per-turn timestamps (`Speaker (HH:MM:SS):`) with no
  end-timestamp and no word-level alignment. This directly shaped the chunking
  decision: chunk boundaries have to align to turn boundaries (parsed from this
  exact pattern), and citation deep-links can only be as precise as "start of this
  turn," not "start of this sentence."
- Measured word-count distribution across all 303 files (min 1,666 / median 15,047 /
  max 28,813 words) before picking a chunk size, instead of guessing — this is what
  justified ~300 words/chunk as small enough for precision, large enough to avoid
  needless fragmentation of typical 150–400 word Q&A exchanges.

## Decision, recorded before writing ingestion code (Phase 2)

Chunking strategy and embedding-model choice are written up in
`docs/architecture.md` §2–4:
- Turn-aware chunking (~300 words/chunk, 220–380 range, never split mid-turn),
  1-turn overlap.
- Local `all-MiniLM-L6-v2` via `sentence-transformers` for embeddings — decoupled
  from the Claude/Ollama generation-provider toggle, zero-cost, fast enough for a
  one-time ~303-episode ingestion run on a laptop.

No dead ends yet in Phase 0 — recon and repo inspection went as expected. The one
real surprise was the stale episode count in the source repo's own README (269 vs
303 actual), which is exactly why the ingestion pipeline will glob the filesystem at
run time rather than trust any document's stated count.

## Open items to raise with the user before Phase 3

1. Docker Desktop needs to be started before we can verify Postgres+pgvector and the
   full `docker compose up` path.
2. Need a real `ANTHROPIC_API_KEY` (user's own) to verify the cloud provider path.
   Will ask them to drop it into `apps/api/.env` directly rather than pasting into
   chat.

## Update: original assignment brief located

The user provided the source document the task prompt was derived from:
`Forward_Deployed_Engineer_Take_Home_Assignment (1) (1).docx`. Extracted its text
(no pandoc/python-docx available, so unzipped the .docx and stripped
`word/document.xml` tags directly) and saved a copy at
`docs/original-assignment-brief.txt` for reference against every deliverable.

Critical facts from the source doc that change execution priorities:
- **Due date: 15/09/26 EOD** -- i.e. tomorrow, not an open-ended timeline. Shifted
  from "be thorough at every phase" to "hit every required deliverable, verify for
  real, but move fast and don't gold-plate."
- Two deliverables cannot be produced by the agent at all and are called out to the
  user explicitly: (1) the 2-3 minute demo video with camera enabled, uploaded to
  YouTube: (2) submitting the Google Form
  (https://forms.gle/LgotDHNVxW1mbzNE7). Both require the user.
- Source doc confirms the task prompt's phase breakdown is a faithful expansion of
  the brief -- no material conflicts found. One nuance: the brief allows "Anthropic
  Claude Agent SDK **or** Pi Coding Agent" and "Anthropic Claude **or** OpenAI" for
  the cloud provider -- already defaulting to Claude Agent SDK + Anthropic per the
  task prompt's stated preference.
