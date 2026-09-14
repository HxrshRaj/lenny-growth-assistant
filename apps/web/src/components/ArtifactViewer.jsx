import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { sanitizeHtml } from "../utils/sanitizeHtml";

// Renders a generated artifact beside the chat. HTML artifacts are rendered inside
// a sandboxed iframe with sandbox="allow-same-origin" ONLY -- no "allow-scripts",
// so no <script>, inline event handler, or javascript: URI can ever execute. See
// docs/architecture.md "artifact security" for the full explanation of what this
// permits (styling, layout, images, normal DOM rendering) and blocks (any script
// execution, form submission, popups, top-level navigation).
export default function ArtifactViewer({ artifact, onClose }) {
  if (!artifact) return null;

  return (
    <div className="artifact-viewer" role="complementary" aria-label="Generated artifact">
      <div className="artifact-viewer__header">
        <span className="artifact-viewer__badge">{artifact.type === "html" ? "HTML/CSS" : "Markdown"}</span>
        <button className="artifact-viewer__close" onClick={onClose} aria-label="Close artifact viewer">
          ✕
        </button>
      </div>
      <div className="artifact-viewer__body">
        {artifact.type === "html" ? (
          <iframe
            title="Generated HTML artifact"
            className="artifact-viewer__iframe"
            sandbox="allow-same-origin"
            srcDoc={sanitizeHtml(artifact.body)}
          />
        ) : (
          <div className="artifact-viewer__markdown">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{artifact.body}</ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}
