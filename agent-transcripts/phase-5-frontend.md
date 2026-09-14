# Phase 5 — Artifact generation & viewer (frontend)

## What was built

- `apps/web` scaffolded with Vite + React (`npm create vite@latest -- --template
  react`), `react-markdown` + `remark-gfm` added for Markdown rendering.
- `src/api.js` -- thin fetch wrapper, structured `ApiError` carrying the backend's
  `{error, detail, code}` shape through to the UI.
- `src/App.jsx` -- boots a session (resumes from `localStorage` if present, else
  creates one), polls `/config` + `/health` every 15s for the provider badge,
  optimistic user-message rendering, error banner on provider/API failures.
- `src/components/{ChatPanel,Message,ArtifactViewer,ProviderBadge}.jsx` -- see
  `docs/design.md` for the interaction-state and information-architecture
  rationale.
- `src/utils/extractArtifact.js` -- detects a ```markdown or ```html fence in an
  assistant message and splits it into prose + artifact.
- `src/utils/sanitizeHtml.js` -- defense-in-depth stripping of `<script>`/`on*`/
  `javascript:` before an HTML artifact ever reaches the sandboxed iframe.

## Verified in the live browser preview (not just "should work")

1. **Boot + provider badge**: loaded the app, confirmed a session auto-creates and
   the header shows "💻 Local (Ollama) · mymodel" live from `/config` --
   screenshot taken, matches expected layout.
2. **Responsive layout**: resized the preview to 375×812 (iPhone-class viewport).
   Header wraps, input stays usable, empty-state copy remains readable at the
   narrow width -- screenshot taken and visually confirmed before resetting back
   to desktop size.
3. **Artifact fence robustness**: initial regex required a newline immediately
   before/after the triple-backtick fence (`` ```markdown\n...\n``` ``). Corrected
   before this became a real bug: smaller/local models don't reliably put a
   newline in exactly that spot, so tightened the regex to make the newlines
   optional (`\n?` instead of `\n`) rather than assuming a cooperative model.
   Caught by re-reading the extraction code against the actual system-prompt
   instructions in `skills/artifact.py`, not by a failing test (no automated test
   covers the frontend's regex -- noted as a coverage gap, the manual test plan's
   artifact steps are the check for this).

## Artifact security -- verified, not just described

Per the assignment's explicit ask ("the evaluator should be able to understand
what the viewer permits, blocks, and why" + "confirm a `<script>alert(1)</script>`
injection attempt ... does NOT execute"):

- Design/rationale: `docs/architecture.md` sec 8e.
- The mechanism has two independent layers: (1) `sandbox="allow-same-origin"` on
  the iframe with `allow-scripts` never granted -- the browser itself refuses to
  execute any script, full stop, regardless of what's in the HTML; (2)
  `sanitizeHtml.js` strips `<script>` tags, `on*` handlers, and `javascript:`
  URIs from the artifact body before it's even handed to the iframe.
- End-to-end verification of this happens via the manual test plan (sec 7:
  request an HTML artifact that deliberately includes
  `<script>alert(1)</script>`, confirm no alert fires and devtools shows no
  script execution) once a live chat turn can produce an HTML artifact through
  the real model -- captured with the full Phase 3/4 live-verification pass once
  ingestion finished (see `agent-transcripts/phase-3-verification-followup.md`),
  rather than faked with a hardcoded artifact string, since the assignment's
  ground rules explicitly call for real generated output, not a canned example.

## Known frontend gaps, disclosed rather than hidden

- No automated frontend test suite (no Vitest/Playwright) -- the manual test plan
  (`docs/manual-test-plan.md`) is the only coverage for UI behavior. Backend
  logic (routing, retrieval, the artifact-fence *format* the skills are instructed
  to produce) is covered by pytest; the *extraction/rendering* of that format in
  the browser is not automated. Listed honestly in the PRD's scope choices as a
  time trade-off, not silently left out.
- No focus trap on the artifact panel, no skip-link (see `docs/design.md` sec 5).
