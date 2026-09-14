import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { extractArtifact } from "../utils/extractArtifact";

export default function Message({ message, onViewArtifact }) {
  const [showSources, setShowSources] = useState(false);
  const isUser = message.role === "user";
  const { prose, artifact } = isUser ? { prose: message.content, artifact: null } : extractArtifact(message.content);
  const hasCitations = message.citations && message.citations.length > 0;

  return (
    <div className={`message message--${message.role}${message.error ? " message--error" : ""}`}>
      <div className="message__role" aria-hidden="true">
        {isUser ? "You" : "Lenny Growth Assistant"}
      </div>
      <div className="message__bubble">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{prose}</ReactMarkdown>

        {artifact && (
          <button className="message__artifact-btn" onClick={() => onViewArtifact(artifact)}>
            📄 View {artifact.type === "html" ? "HTML" : "Markdown"} artifact
          </button>
        )}

        {!isUser && !message.error && (
          <div className="message__meta">
            {message.model_provider && (
              <span className="message__meta-tag" title={message.model_name || ""}>
                {message.model_provider}
              </span>
            )}
            {typeof message.retrieval_hit_count === "number" && (
              <span className="message__meta-tag">{message.retrieval_hit_count} sources retrieved</span>
            )}
            {typeof message.latency_ms === "number" && (
              <span className="message__meta-tag">{message.latency_ms}ms</span>
            )}
          </div>
        )}

        {hasCitations && (
          <div className="message__citations">
            <button
              className="message__citations-toggle"
              onClick={() => setShowSources((s) => !s)}
              aria-expanded={showSources}
            >
              {showSources ? "Hide" : "Show"} {message.citations.length} source
              {message.citations.length !== 1 ? "s" : ""}
            </button>
            {showSources && (
              <ul className="message__citations-list">
                {message.citations.map((c, i) => (
                  <li key={i}>
                    <a href={c.source_url} target="_blank" rel="noreferrer">
                      {c.guest} — {c.title}
                    </a>{" "}
                    <span className="message__citation-ts">@ {c.start_timestamp}</span>
                    <div className="message__citation-preview">{c.text_preview}</div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
