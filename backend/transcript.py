"""Transcript parsing for Phase 2.

Grammar (documented, canonical):
    [HH:MM:SS] Speaker: text

Rules:
- Timestamp must be [HH:MM:SS] with two-digit hours, minutes, seconds (00-99 for hours).
- Speaker is a non-empty label up to the first colon after the closing bracket.
- Text is everything after the first colon (and its following space) until the next
  timestamp line or end of file.
- Continuation lines (indented or plain) that do not start a new timestamped turn
  are appended to the current turn's text (with a single space separator).
- Empty lines between turns are ignored.
- If a turn has no explicit end timestamp, the next turn's start becomes its end.
  The final turn ends at its start + a small default duration (e.g., 1000 ms) to
  ensure end_ms >= start_ms.

Normalization:
- All times are converted to milliseconds (int).
- Whitespace is trimmed; internal runs of whitespace are collapsed to single spaces.
- turn_id is generated deterministically as f"turn_{idx:03d}" based on appearance order.

Validation (reject with clear 4xx):
- Any line that looks like a timestamped turn but is malformed (bad timestamp,
  missing speaker, missing colon) causes a parse error.
- If no valid turns are produced, this is an error.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import TranscriptTurn

# Matches a timestamped turn header:
#   [HH:MM:SS] Speaker: rest...
# HH allows 00-99 (lenient for long recordings), MM/SS are 00-59.
_TIMESTAMP_LINE_RE = re.compile(
    r"^\[(?P<h>\d{2}):(?P<m>\d{2}):(?P<s>\d{2})\]\s*(?P<speaker>[^:]+?)\s*:\s*(?P<text>.*)$"
)

# Any line that starts with a bracketed time is considered a potential timestamp line.
# If it fails to parse as a proper header, we treat it as a malformed error.
_MAYBE_TIMESTAMP_RE = re.compile(r"^\[\d{2}:\d{2}:\d{2}\]")


def _to_ms(h: int, m: int, s: int) -> int:
    """Convert HH:MM:SS to milliseconds."""
    if not (0 <= m <= 59 and 0 <= s <= 59):
        # Hours may be >= 24 for long sessions; minutes/seconds must be valid.
        raise ValueError("minutes and seconds must be 00-59")
    return ((h * 60 + m) * 60 + s) * 1000


def _normalize_text(s: str) -> str:
    """Collapse internal whitespace and trim."""
    return " ".join(s.split())


@dataclass
class _RawTurn:
    start_ms: int
    speaker: str
    text_parts: list[str]


def parse_transcript_text(raw: str) -> list[TranscriptTurn]:
    """Parse raw transcript text into ordered TranscriptTurn list.

    Raises ValueError with a clear message for malformed input (caller maps to 4xx).
    """
    if raw is None:
        raise ValueError("empty transcript")

    # Normalize newlines
    text = raw.replace("\r\n", "\n").replace("\r", "\n")

    lines = text.split("\n")

    raw_turns: list[_RawTurn] = []
    current: _RawTurn | None = None

    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()

        # Blank line: end current turn accumulation (but do not start a new one)
        if not stripped:
            # Keep current open for continuations that might appear after blank lines
            # (per "multi-line turn continuations"). Only finalize on next header.
            continue

        # If line looks like it might be a timestamped header
        if _MAYBE_TIMESTAMP_RE.match(stripped):
            m = _TIMESTAMP_LINE_RE.match(stripped)
            if not m:
                # Malformed timestamped line
                raise ValueError(
                    f"malformed timestamped line at {lineno}: {stripped[:120]}"
                )

            h = int(m.group("h"))
            m_ = int(m.group("m"))
            s = int(m.group("s"))
            speaker = m.group("speaker").strip()
            first_text = m.group("text")

            if not speaker:
                raise ValueError(f"missing speaker at line {lineno}")

            try:
                start_ms = _to_ms(h, m_, s)
            except ValueError as e:
                raise ValueError(f"invalid time at line {lineno}: {e}") from e

            # Finalize previous
            if current is not None:
                raw_turns.append(current)

            current = _RawTurn(
                start_ms=start_ms,
                speaker=speaker,
                text_parts=[first_text] if first_text.strip() else [],
            )
            continue

        # Continuation line for current turn (if any)
        if current is not None:
            # Append as part of the same turn
            current.text_parts.append(stripped)
        else:
            # Text before any timestamped turn: treat as error for strictness
            # (prevents accidental ingestion of prose without timing)
            raise ValueError(f"content before first timestamped turn at line {lineno}")

    # Finalize last turn
    if current is not None:
        raw_turns.append(current)

    if not raw_turns:
        raise ValueError("no turns found; transcript must contain at least one [HH:MM:SS] Speaker: line")

    # Reject out-of-order timestamps (equal starts are allowed for rapid
    # exchanges within the same second). Silently accepting decreasing times
    # would produce wrong end_ms values downstream.
    for idx in range(1, len(raw_turns)):
        if raw_turns[idx].start_ms < raw_turns[idx - 1].start_ms:
            raise ValueError(
                f"turns are not in chronological order: turn {idx + 1} starts before turn {idx}"
            )

    # Assign end times:
    # - next turn's start becomes current end
    # - last turn gets start + 1000 ms
    turns: list[TranscriptTurn] = []
    for idx, rt in enumerate(raw_turns):
        if idx + 1 < len(raw_turns):
            end_ms = raw_turns[idx + 1].start_ms
        else:
            end_ms = rt.start_ms + 1000

        # Ensure monotonicity
        if end_ms < rt.start_ms:
            # Should not happen if inputs are ordered; guard anyway
            end_ms = rt.start_ms + 1000

        text = _normalize_text(" ".join(rt.text_parts))
        if not text:
            # Allow empty text? Prefer to keep the turn but with empty text.
            text = ""

        turns.append(
            TranscriptTurn(
                turn_id=f"turn_{idx:03d}",
                speaker=rt.speaker,
                start_ms=rt.start_ms,
                end_ms=end_ms,
                text=text,
            )
        )

    return turns
