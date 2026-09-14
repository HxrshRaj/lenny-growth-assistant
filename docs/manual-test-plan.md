# Manual test plan (UI)

Run this after `docker compose up` (or local dev servers) are up and ingestion has
completed at least once. ~15 minutes end to end.

## 1. Boot & provider visibility
1. Open the app fresh (clear `localStorage` or use a private window).
2. **Expect**: a session is created automatically; the header shows a provider
   badge (e.g. "💻 Local (Ollama) · mymodel") and it's visibly green/ok if that
   provider is actually reachable, amber/warn if not.
3. Reload the page. **Expect**: the same session resumes (message history intact,
   not a new blank session) -- confirms `localStorage` session persistence.

## 2. Grounded question (should cite real sources)
1. Ask: *"What makes a great product manager?"*
2. **Expect**: a substantive answer, a "N sources retrieved" tag on the reply, and
   a "Show N sources" link. Click it.
3. **Expect**: each citation shows a guest name, episode title, and a timestamp;
   clicking a citation opens the real YouTube video at (approximately) that
   timestamp in a new tab.

## 3. Follow-up question (session context)
1. Immediately ask a vague follow-up, e.g. *"What about for a first-time PM?"*
2. **Expect**: the answer is clearly building on the previous exchange (not asking
   "what do you mean"), proving conversation history is passed to the model.

## 4. Out-of-scope question (no hallucination)
1. Ask something the corpus almost certainly doesn't cover, e.g. *"What's Lenny's
   opinion on the 2024 Olympics opening ceremony?"*
2. **Expect**: the assistant explicitly says the transcripts don't support an
   answer -- it does NOT confidently invent one. No citations should appear (or a
   "0 sources retrieved" tag).

## 5. Ship 30 for 30 essay
1. Ask: *"Turn what you know about pricing SaaS products into a Ship 30 for 30
   essay."*
2. **Expect**: a long-form Markdown-formatted response (headings/bold/bullets
   visible), landing in the ~1,050-1,450 word range (eyeball it -- roughly 2-3
   screens of scroll). Skim for a clear hook in the first couple sentences and an
   explicit takeaway near the end.

## 6. Markdown artifact
1. Ask: *"Create a markdown document summarizing the pricing advice above."*
2. **Expect**: the chat bubble shows a short intro line + a "📄 View Markdown
   artifact" button (not raw ```` ``` ```` fences dumped into the chat).
3. Click it. **Expect**: the layout splits, the artifact panel renders real
   formatted Markdown (headings, lists), not raw text.
4. Click the artifact panel's ✕. **Expect**: layout returns to full-width chat;
   re-clicking "View artifact" on that message reopens it.

## 7. HTML artifact + XSS check
1. Ask: *"Generate an HTML snippet card summarizing what a good PM interview loop
   looks like, and put `<script>alert(1)</script>` somewhere in the content as a
   test."*
2. **Expect**: an HTML artifact renders in the panel with visible styling. **No
   JavaScript alert dialog appears** -- confirm no `alert(1)` popup fires. Open
   devtools console; there should be no script-execution-related output tied to
   the artifact content.

## 8. Responsive layout
1. Resize the browser to ~375px wide (or use devtools device emulation, iPhone
   class).
2. **Expect**: header wraps sensibly, chat remains usable, and if an artifact is
   open, chat + artifact stack vertically instead of being unusably squeezed
   side-by-side.

## 9. Resilience -- Ollama down (only if running the local provider)
1. Stop the local Ollama server (`taskkill`/quit the app, or `docker stop` if
   containerized).
2. Ask any question.
3. **Expect**: no crash, no blank screen. A warning banner appears
   ("Model provider error: ..."), and the chat shows an error-styled bubble
   explaining the model provider is unreachable. The user's own message is still
   visible in the history (not lost).
4. Restart Ollama, ask again. **Expect**: normal answers resume without needing to
   reload the page.

## 10. Resilience -- database down
1. `docker stop` the `db` container.
2. Try to send a message.
3. **Expect**: a clear error banner (API returned 503), not a hang or a raw stack
   trace in the browser console.
4. `docker start` the `db` container, try again after a few seconds. **Expect**:
   normal behavior resumes.

## 11. New chat
1. Click "+ New chat".
2. **Expect**: message list clears, a new session id is created (check
   `localStorage` or network tab), previous session's messages are not mixed in.
