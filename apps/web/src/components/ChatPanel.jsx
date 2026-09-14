import { useEffect, useRef, useState } from "react";
import Message from "./Message";

export default function ChatPanel({ messages, onSend, loading, onViewArtifact }) {
  const [draft, setDraft] = useState("");
  const listRef = useRef(null);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  function handleSubmit(e) {
    e.preventDefault();
    const trimmed = draft.trim();
    if (!trimmed || loading) return;
    onSend(trimmed);
    setDraft("");
  }

  return (
    <div className="chat-panel">
      <div className="chat-panel__messages" ref={listRef} role="log" aria-live="polite" aria-label="Conversation">
        {messages.length === 0 && !loading && (
          <div className="chat-panel__empty">
            <p>Ask a product or growth question grounded in Lenny&apos;s Podcast transcripts.</p>
            <p className="chat-panel__empty-hint">
              Try: &quot;What makes a great PM?&quot; or &quot;Turn this into a Ship 30 for 30 essay&quot;
            </p>
          </div>
        )}
        {messages.map((m) => (
          <Message key={m.id} message={m} onViewArtifact={onViewArtifact} />
        ))}
        {loading && (
          <div className="message message--assistant message--loading" aria-label="Assistant is responding">
            <div className="message__role">Lenny Growth Assistant</div>
            <div className="message__bubble">
              <span className="typing-dot" />
              <span className="typing-dot" />
              <span className="typing-dot" />
            </div>
          </div>
        )}
      </div>
      <form className="chat-panel__input" onSubmit={handleSubmit}>
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              handleSubmit(e);
            }
          }}
          placeholder="Ask a question, or ask for a Ship 30 essay / Markdown / HTML artifact..."
          aria-label="Message"
          rows={2}
        />
        <button type="submit" disabled={loading || !draft.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}
