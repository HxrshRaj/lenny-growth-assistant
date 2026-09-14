"""
Parses one `episodes/{slug}/transcript.md` file into (frontmatter, turns).

Format confirmed by inspecting the real repo (docs/architecture.md sec 1):
YAML frontmatter, then a body where every speaker turn starts with a line that is
*exactly* `Speaker Name (HH:MM:SS):` or, for a continuation of the same speaker,
just `(HH:MM:SS):` with no name. Timestamps are NOT consistently HH:MM:SS --
episodes under an hour often use MM:SS instead (discovered only after a first full
ingestion run skipped 29 episodes as "no turns parsed"; see
agent-transcripts/phase-2-ingestion-retrieval.md). Both formats are accepted.
"""
import re
from dataclasses import dataclass

import yaml

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)
# Accepts both MM:SS and H(H):MM:SS.
TURN_MARKER_RE = re.compile(r"^(?P<name>.*?)\((?P<ts>\d{1,2}(?::\d{2}){1,2})\):\s*$", re.MULTILINE)
# Fallback for the ~10% of episodes (measured: 30/303) that have no timestamps at
# all -- just "Speaker Name:" on its own line. Restricted to short, capitalized,
# punctuation-free lines so it doesn't false-positive on a sentence that happens to
# end with a colon inside a paragraph.
NO_TS_MARKER_RE = re.compile(r"^(?P<name>[A-Z][A-Za-z.'-]*(?: [A-Z][A-Za-z.'-]*){0,3}):\s*$", re.MULTILINE)


@dataclass
class Turn:
    speaker: str
    start_hms: str
    start_seconds: int
    text: str


def _hms_to_seconds(hms: str) -> int:
    parts = [int(p) for p in hms.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    h, m, s = parts
    return h * 3600 + m * 60 + s


def parse_transcript(raw: str) -> tuple[dict, list[Turn]]:
    """Returns (frontmatter_dict, list_of_turns). Turns are already merged so that
    consecutive turns from the same speaker (including timestamp-only continuation
    lines) become one logical turn -- see architecture.md sec 2 step 1."""
    m = FRONTMATTER_RE.match(raw)
    if not m:
        raise ValueError("transcript.md missing YAML frontmatter block")
    frontmatter = yaml.safe_load(m.group(1)) or {}
    body = m.group(2)

    # Drop everything before the "## Transcript" heading if present (title/heading noise).
    heading_idx = body.find("## Transcript")
    if heading_idx != -1:
        body = body[heading_idx + len("## Transcript") :]

    markers = list(TURN_MARKER_RE.finditer(body))
    has_timestamps = bool(markers)
    if not markers:
        # ~10% of the corpus (measured: 30/303) has no timestamps at all, just
        # "Speaker Name:" lines. Fall back so we don't silently drop these episodes.
        markers = list(NO_TS_MARKER_RE.finditer(body))

    raw_turns: list[Turn] = []
    for i, mo in enumerate(markers):
        name = mo.group("name").strip()
        ts = mo.group("ts") if has_timestamps else None
        start = mo.end()
        end = markers[i + 1].start() if i + 1 < len(markers) else len(body)
        text = body[start:end].strip()
        if not text:
            continue
        speaker = name if name else (raw_turns[-1].speaker if raw_turns else "Unknown")
        if ts is not None:
            start_hms, start_seconds = ts, _hms_to_seconds(ts)
        else:
            # No timestamp data in source -- citations for these chunks link to the
            # episode start rather than an exact moment (documented limitation).
            start_hms, start_seconds = "unknown", 0
        raw_turns.append(Turn(speaker=speaker, start_hms=start_hms, start_seconds=start_seconds, text=text))

    # Merge consecutive turns from the same speaker into one logical turn.
    merged: list[Turn] = []
    for t in raw_turns:
        if merged and merged[-1].speaker == t.speaker:
            merged[-1] = Turn(
                speaker=merged[-1].speaker,
                start_hms=merged[-1].start_hms,
                start_seconds=merged[-1].start_seconds,
                text=f"{merged[-1].text} {t.text}",
            )
        else:
            merged.append(t)

    return frontmatter, merged
