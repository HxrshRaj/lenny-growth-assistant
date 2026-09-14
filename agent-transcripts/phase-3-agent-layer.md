# Phase 3 — Agent layer & LLM configuration

## Real blocker flagged: Anthropic Claude Agent SDK vs. direct API tool-calling

The task prompt explicitly said "Agent SDK preferred unless you hit a real blocker
-- tell me if you do." Flagging it here rather than silently picking one:

The **Claude Agent SDK** (the Python `claude-agent-sdk` package) is built around
wrapping/spawning the **Claude Code CLI** -- it's designed for autonomous
coding-agent workflows (a sandboxed environment the agent can read/write files and
run shell commands in), not for embedding inside a stateless, multi-session FastAPI
backend that needs to make a single grounded-completion call per HTTP request. Using
it here would mean shelling out to a Node/Claude-Code-CLI subprocess per chat
turn, managing its streaming JSON-lines protocol, and depending on a CLI binary
being present in the API container -- real added complexity and a real added
runtime dependency, for a use case (retrieval-augmented single-turn completion,
plus two additional "skills" that are really just different system prompts) that
doesn't need a coding agent's file/shell tool access at all.

**Decision**: used the **Anthropic Python SDK's Messages API directly**
(`anthropic.Anthropic().messages.create(...)`) as the agent's LLM-calling layer,
with the actual "agentic" structure -- router -> retrieval -> skill selection ->
provider call -- implemented as real application code
(`app/services/{router,retrieval,agent,llm}.py` + `app/services/skills/`) rather
than delegated to an SDK's tool-loop. This satisfies the underlying requirement
(clear skill boundaries, reliable routing, a real agent architecture) without
taking on a dependency (a coding-agent CLI wrapper) that doesn't fit a hosted API's
runtime model. Documented in `docs/architecture.md` sec 8c/8d.

## Model-provider abstraction

`app/services/llm.py::complete(system, messages, settings)` is the single function
every skill calls; it branches on `settings.model_provider` and is the only module
that imports `anthropic` or calls Ollama's HTTP API. Verified real behavior (not
mocked):

- **Anthropic, no API key set**: `complete()` raises `LLMProviderError("anthropic",
  "ANTHROPIC_API_KEY is not set...")` immediately, no network call attempted.
  Covered by `tests/test_provider_toggle.py::test_anthropic_without_api_key_raises_structured_error`
  (passing).
- **Ollama, unreachable host**: raises `LLMProviderError("ollama", ...)` with a
  clear message, either "not reachable" (connection actively refused) or "timed
  out" depending on how the OS's network stack handles the specific unreachable
  address -- both are exercised for real in
  `tests/test_provider_toggle.py::test_ollama_unreachable_raises_structured_error_not_crash`
  (initially written too strict -- asserted only the "not reachable" wording, which
  is real ConnectError behavior against a refused port, but connecting to
  `localhost:1` on this machine instead times out after the configured 2s rather
  than refusing instantly; fixed the test to accept either real outcome instead of
  loosening what the code does).
- **Ollama, real request against a local model under CPU load**: during a live API
  test (see below), a real 60s timeout was hit while Ollama was competing for CPU
  with the ingestion embedding process running concurrently -- exactly the kind of
  real resource-contention failure this error path exists for. Bumped the default
  `OLLAMA_TIMEOUT_SECONDS` from 60 to 120 as a result (small local models on CPU,
  especially under load, legitimately need more headroom than a cloud API call
  would).

## Live end-to-end verification (real retrieval + real provider call)

Ran a real chat turn against the live API (partial index at the time, ~9k chunks)
via curl:

```
POST /sessions/{id}/messages {"content": "What is product-market fit?"}
```

Retrieval worked correctly -- 5 real, highly relevant chunks (scores 0.66-0.74)
from Karri Saarinen, Benjamin Lauzier, Christopher Lochhead, Manik Gupta, and
Nikita Bier episodes, each with a working timestamped YouTube citation. The LLM
call itself timed out (see above -- CPU contention with concurrent ingestion), and
the system did exactly what it's supposed to do on that failure: persisted the
turn with a clear ⚠️ error message, `error` field set, `retrieval_hit_count: 5` and
full `citations` still attached (retrieval succeeded even though generation
didn't) -- not a crash, not a lost message. This is documented here as a *passing*
resilience test, not a failure of the build: the graceful-degradation path is
exactly what Phase 6 asks to verify, and it happened here for real rather than
needing to be manufactured artificially.

Full success-case verification (a real grounded answer with a real completion, plus
the "corpus doesn't cover this" negative case) is captured in
`agent-transcripts/phase-3-verification-followup.md` once the full corpus was
ingested and the local model wasn't competing with a concurrent embedding job for
CPU (see that file for the actual answer text and timing).
