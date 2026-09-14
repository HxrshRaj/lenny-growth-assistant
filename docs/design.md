# Design

## 1. UI/UX principles

- **The chat is the product; the artifact viewer is a guest.** Chat always occupies
  the full width until an artifact exists, at which point the layout splits
  55/45 rather than shrinking chat to a sidebar -- artifacts (essays, docs, HTML
  snippets) deserve real reading room, not a cramped preview pane.
- **Never hide that an answer is ungrounded.** If retrieval comes back empty or thin,
  the assistant says so in plain language rather than the UI silently rendering a
  confident-looking answer. This is a product requirement (Phase 3), not just a
  backend concern -- the chat bubble for an error/ungrounded turn gets a visually
  distinct (red-tinted) treatment (`message--error` in `App.css`) so it's
  unmistakable at a glance, not just readable if you parse the text.
- **Every claim is checkable.** Citations are collapsed by default (avoid wall-of-
  links noise) but one click away, and link straight to the cited moment in the
  source video (`&t={seconds}s`) wherever the transcript had real timestamp data --
  not just "trust me."
- **Show the model provider at all times, unprompted.** Per the assignment's
  toggle-visibility requirement: the header badge is always visible, not tucked in
  a settings menu, because which model answered (cloud vs. local) materially
  affects how much to trust the answer's polish/latency.

## 2. Information architecture

```
App
├── Header: logo/title | provider badge (+ backend health) | "New chat"
├── Banner (conditional): boot error / provider-error-on-last-turn
└── Main (flex row, splits when an artifact is open)
    ├── ChatPanel
    │   ├── message list (scrollable, auto-scrolls to newest)
    │   │   └── Message (per turn: role label, markdown body, artifact-open
    │   │       button if this turn produced one, provider/latency/retrieval-count
    │   │       tags, collapsible citation list)
    │   └── input (textarea + Send, Enter to submit / Shift+Enter for newline)
    └── ArtifactViewer (mounted only when a message's artifact is opened)
        ├── header: type badge (Markdown/HTML) + close
        └── body: rendered markdown OR sandboxed iframe
```

One session is the unit of navigation (no thread list / history browser in this
build -- see PRD "scope choices" for why that's cut for v1). The current session id
persists in `localStorage` so a page refresh resumes the same conversation instead
of silently starting a new one.

## 3. Key interaction states

| State | Behavior |
|---|---|
| **Loading** (waiting on `POST /messages`) | User's message appears immediately (optimistic render), followed by a three-dot typing indicator in an assistant bubble. Input stays enabled but Send is disabled while a request is in flight. |
| **Empty retrieval** | The assistant still returns 201 with a real message -- content explicitly states the transcripts don't cover this, `retrieval_hit_count: 0` tag shown on the bubble. No special empty-state UI needed; the *message itself* is the empty state, which keeps behavior identical to any other turn (no extra states to test). |
| **Provider error** (Ollama unreachable / Anthropic key missing) | A warning-red banner appears above the chat ("Model provider error: ..."), AND the turn itself is persisted as an assistant message with an error-styled bubble -- both because a banner alone would vanish/be missed, and a bubble alone doesn't interrupt the user's flow of attention. |
| **Boot error** (API unreachable at all) | Full-width red banner, no chat rendered under it -- there's nothing usable to show until the API responds. |
| **Artifact ready** | Layout splits; clicking "View artifact" on the message that produced it opens/replaces the panel. Closing it (✕) returns to full-width chat; the artifact isn't lost, just collapsed back into the message (re-openable). |

## 4. Responsive behavior

Single breakpoint at 768px (see `App.css` media query):
- **≥768px**: chat and artifact side by side (55/45).
- **<768px**: they stack vertically instead of a horizontal split (each taking
  ~50% of viewport height when both are present) rather than either view fully
  hiding the other -- so a phone user can still see they asked something while
  reading the artifact, instead of losing context on a full-screen swap.
- Message bubbles widen from 78% to 92% of the column on narrow screens (long
  single-word lines waste more relative space on a phone).
- Verified visually at 375×812 (iPhone-class) and standard desktop width -- see
  `agent-transcripts/phase-5-frontend.md`.

## 5. Accessibility

- Message list: `role="log"` + `aria-live="polite"` so new assistant turns are
  announced to screen readers without re-announcing the whole history.
- Chat input: explicit `aria-label="Message"` (the placeholder text alone isn't a
  reliable accessible name across browsers/AT).
- Citation disclosure: real `<button aria-expanded>` toggle, not a bare clickable
  `<div>` -- keyboard-focusable and its state is announced.
- Artifact panel: `role="complementary" aria-label="Generated artifact"` so it's
  identifiable as a distinct landmark, and its close button has an explicit
  `aria-label` (a bare "✕" glyph has no accessible name on its own).
- Color is never the only signal: the error state pairs a background tint with the
  ⚠️ glyph and explicit "error"/"unreachable" text, not color alone.
- Known gap (documented, not fixed in this build): no dedicated focus-trap when the
  artifact panel opens, and no skip-link. Listed as a real limitation in the PRD
  risk section rather than silently left out of this doc.

## 6. Artifact rendering decision (design half of the security story)

Markdown artifacts render directly via `react-markdown` (safe -- no HTML
injection surface as long as the raw-HTML passthrough option is left off, which it
is). HTML/CSS artifacts render inside an `<iframe sandbox="allow-same-origin">`
with **no** `allow-scripts` -- see `docs/architecture.md` "artifact security" for
the full threat-model writeup; from a design standpoint the point is that the
Artifact Viewer is visually identical regardless of artifact type (same header,
same close affordance), so a user never has to learn "HTML artifacts behave
differently" -- they just do, safely, underneath.
