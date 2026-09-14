"""
Turn-aware chunker. Implements the strategy documented in docs/architecture.md
sec 2: accumulate whole speaker turns to a ~300-word target (220-380 range), never
split a turn, and carry the last turn of each chunk forward into the next chunk as
overlap.
"""
from dataclasses import dataclass, field

from parser import Turn

TARGET_WORDS = 300
MAX_WORDS = 380


@dataclass
class ChunkDraft:
    turns: list[Turn] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n\n".join(f"{t.speaker}: {t.text}" for t in self.turns)

    @property
    def word_count(self) -> int:
        return sum(len(t.text.split()) for t in self.turns)

    @property
    def speakers(self) -> list[str]:
        seen = []
        for t in self.turns:
            if t.speaker not in seen:
                seen.append(t.speaker)
        return seen

    @property
    def start_hms(self) -> str:
        return self.turns[0].start_hms

    @property
    def end_hms(self) -> str:
        return self.turns[-1].start_hms

    @property
    def start_seconds(self) -> int:
        return self.turns[0].start_seconds


def chunk_turns(turns: list[Turn]) -> list[ChunkDraft]:
    chunks: list[ChunkDraft] = []
    current = ChunkDraft()

    def flush() -> None:
        nonlocal current
        if not current.turns:
            return
        chunks.append(current)
        # Overlap: carry the last turn forward, unless this chunk was only that one
        # turn (a long monologue) -- carrying it would just recreate the same
        # single-turn chunk again.
        if len(current.turns) > 1:
            current = ChunkDraft(turns=[current.turns[-1]])
        else:
            current = ChunkDraft()

    for turn in turns:
        turn_words = len(turn.text.split())

        if turn_words > MAX_WORDS:
            flush()
            chunks.append(ChunkDraft(turns=[turn]))
            current = ChunkDraft()
            continue

        if current.turns and current.word_count + turn_words > MAX_WORDS:
            flush()

        current.turns.append(turn)

        if current.word_count >= TARGET_WORDS:
            flush()

    flush()
    return [c for c in chunks if c.turns]
