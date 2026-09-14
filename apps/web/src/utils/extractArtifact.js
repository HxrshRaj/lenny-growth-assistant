// Detects a ```markdown or ```html fenced code block in an assistant message and
// splits it out as an "artifact" the ArtifactViewer can render, separate from the
// chat bubble's own prose. See docs/architecture.md "artifact security" for why
// only these two fence types are treated as renderable artifacts.
//
// Newlines around the fence markers are optional (\n? not \n) -- smaller local
// models don't always follow the "put a newline before the closing fence"
// instruction exactly, and a missed artifact is a worse failure mode than a
// slightly-loose regex.
const FENCE_RE = /```(markdown|html)\n?([\s\S]*?)\n?```/;

export function extractArtifact(content) {
  const match = FENCE_RE.exec(content);
  if (!match) return { prose: content, artifact: null };
  const [full, type, body] = match;
  const prose = (content.slice(0, match.index) + content.slice(match.index + full.length)).trim();
  return { prose, artifact: { type, body: body.trim() } };
}
