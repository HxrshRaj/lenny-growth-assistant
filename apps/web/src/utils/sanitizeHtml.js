// Defense-in-depth sanitization for HTML artifacts. The iframe sandbox (see
// ArtifactViewer.jsx: sandbox="allow-same-origin", deliberately WITHOUT
// "allow-scripts") is the primary control -- without allow-scripts, no <script>
// tag, inline event handler, or javascript: URI can execute, full stop. This pass
// is a second, independent layer so the artifact never even contains an obvious
// injection attempt, in case a future change ever loosens the sandbox.
export function sanitizeHtml(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, "")
    .replace(/<script[^>]*>/gi, "")
    .replace(/\son\w+\s*=\s*"(?:[^"]*)"/gi, "")
    .replace(/\son\w+\s*=\s*'(?:[^']*)'/gi, "")
    .replace(/\son\w+\s*=\s*[^\s>]+/gi, "")
    .replace(/(href|src)\s*=\s*"(\s*javascript:[^"]*)"/gi, '$1="#"')
    .replace(/(href|src)\s*=\s*'(\s*javascript:[^']*)'/gi, "$1='#'");
}
