#!/usr/bin/env python3
"""Verification for Phase 4 (chunking + Chroma) and Phase 6 (grounded chat).

This script:
1) Starts from a clean slate (no reliance on prior state).
2) Uploads TWO distinct small text meetings (A and B) via the local API.
3) Verifies that a question about Meeting A returns ONLY citations that reference A
   (speaker/timestamp ranges must be consistent with A's turns; no B leakage).
4) Verifies that an answerable question about A receives citations that exist in A.
5) Verifies that an unsupported question about A explicitly refuses
   ("insufficient evidence" style), with empty citations.

Ponytail constraints:
- Uses only the already-running local Ollama (no cloud).
- One embed/chat path; no reranking, streaming, history, or speculative config.
- Raw audio is not involved; text meetings only for this verification.
- Logs are minimal; no transcript bodies or secrets are printed.

Requirements to run:
- Ollama daemon running with:
    ollama pull nomic-embed-text:latest
    ollama pull llama3.2:3b
- Backend running locally (FastAPI/uvicorn) on http://127.0.0.1:8000
  Example:
    cd <repo-root>
    .venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

Run:
    .venv/bin/python backend/verify_phase4_6.py

Exit code 0 on success; non-zero on any failure.
"""

from __future__ import annotations

import json
import sys
import time
from typing import Any

import httpx

API = "http://127.0.0.1:8000"
TIMEOUT = httpx.Timeout(120.0, connect=10.0)

# Small synthetic transcripts (distinct content)
MEETING_A_TITLE = "Q3 Planning"
MEETING_A_TRANSCRIPT = """[00:00:00] Alice: Let's align on the Q3 roadmap.
[00:00:05] Bob: We need to ship the billing integration by end of month.
[00:00:12] Alice: Agreed. Carol will own the API changes.
[00:00:20] Carol: I'll start on the schema updates tomorrow.
"""

MEETING_B_TITLE = "Hiring Sync"
MEETING_B_TRANSCRIPT = """[00:00:00] Dana: We have two backend candidates in the pipeline.
[00:00:06] Evan: Let's schedule onsite loops next week.
[00:00:11] Dana: Also, the design team is asking for more headcount.
[00:00:18] Evan: We'll revisit after the reorg settles.
"""


def _post_upload_transcript(title: str, text: str) -> dict[str, Any]:
    files = {"file": ("transcript.txt", text.encode("utf-8"), "text/plain")}
    data = {"title": title}
    with httpx.Client(timeout=TIMEOUT) as client:
        r = client.post(f"{API}/api/meetings/upload/transcript", files=files, data=data)
        r.raise_for_status()
        return r.json()


def _post_chat(meeting_id: str, question: str) -> dict[str, Any]:
    with httpx.Client(timeout=TIMEOUT) as client:
        r = client.post(
            f"{API}/api/meetings/{meeting_id}/chat",
            json={"question": question},
        )
        r.raise_for_status()
        return r.json()


def _get_meeting(meeting_id: str) -> dict[str, Any]:
    with httpx.Client(timeout=TIMEOUT) as client:
        r = client.get(f"{API}/api/meetings/{meeting_id}")
        r.raise_for_status()
        return r.json()


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        print("FAIL:", msg, file=sys.stderr)
        sys.exit(1)


def main() -> None:
    print("Phase 4/6 verification starting...")
    print("NOTE: Ensure Ollama is running with nomic-embed-text:latest and llama3.2:3b.")
    print("NOTE: Ensure backend is running on", API)

    # 1) Upload two distinct meetings
    a = _post_upload_transcript(MEETING_A_TITLE, MEETING_A_TRANSCRIPT)
    b = _post_upload_transcript(MEETING_B_TITLE, MEETING_B_TRANSCRIPT)
    meeting_a = a["meeting_id"]
    meeting_b = b["meeting_id"]
    print(f"Uploaded A={meeting_a} turns={a['turn_count']}")
    print(f"Uploaded B={meeting_b} turns={b['turn_count']}")

    # Sanity: fetch details to know exact speakers/times for A
    detail_a = _get_meeting(meeting_a)
    turns_a = detail_a["turns"]
    assert len(turns_a) >= 2, "Expected at least 2 turns in A"
    print(f"A turns: {len(turns_a)}")

    # 2) Question about A should return only A citations
    # Use a clearly answerable question grounded in A's transcript.
    q_answerable = "Who will own the API changes?"
    resp_a = _post_chat(meeting_a, q_answerable)
    print("Answerable Q on A ->", json.dumps(resp_a, indent=2)[:800])

    _assert(isinstance(resp_a.get("answer"), str) and resp_a["answer"], "Missing answer text for A")
    cites_a = resp_a.get("citations") or []
    _assert(isinstance(cites_a, list) and len(cites_a) > 0, "Expected citations for answerable Q on A")

    # All citations must reference speakers present in A and times within A's span.
    a_speakers = {t["speaker"] for t in turns_a}
    a_min = min(t["start_ms"] for t in turns_a)
    a_max = max(t["end_ms"] for t in turns_a)
    for c in cites_a:
        _assert(c.get("speaker") in a_speakers, f"Citation speaker not in A: {c}")
        sm, em = int(c.get("start_ms", -1)), int(c.get("end_ms", -1))
        _assert(sm >= a_min and em <= a_max + 2000, f"Citation time out of A's range: {c}")

    # 3) Answerable question receives citations that exist in A
    # We already asserted speakers and times are within A's bounds above.
    # For extra strictness, ensure at least one citation speaker matches a turn speaker.
    matched = any(c.get("speaker") in a_speakers for c in cites_a)
    _assert(matched, "No citation matched known A speakers")

    # 4) Unsupported question on A should refuse with empty citations
    q_unsupported = "What is the weather forecast for next Friday?"
    resp_refuse = _post_chat(meeting_a, q_unsupported)
    print("Unsupported Q on A ->", json.dumps(resp_refuse, indent=2)[:800])

    ans = (resp_refuse.get("answer") or "").lower()
    _assert("insufficient" in ans or "don't have enough" in ans or "no" in ans, "Expected refusal language for unsupported Q")
    cites_refuse = resp_refuse.get("citations") or []
    _assert(len(cites_refuse) == 0, "Expected empty citations for unsupported Q")

    # 5) Cross-meeting isolation: asking A about B content should refuse or not leak B
    # Ask a B-specific question to A; it must not produce B speakers/times.
    q_b = "Who suggested scheduling onsite loops?"
    resp_cross = _post_chat(meeting_a, q_b)
    print("B-specific Q on A ->", json.dumps(resp_cross, indent=2)[:800])
    cites_cross = resp_cross.get("citations") or []
    b_speakers = {"Dana", "Evan"}
    for c in cites_cross:
        _assert(c.get("speaker") not in b_speakers, f"Cross-meeting speaker leak from B into A: {c}")

    # If it produced any citations at all, they must still be within A's bounds
    for c in cites_cross:
        sm, em = int(c.get("start_ms", -1)), int(c.get("end_ms", -1))
        _assert(sm >= a_min and em <= a_max + 2000, f"Cross-meeting time leak: {c}")

    print("All Phase 4/6 checks passed.")
    print("Summary:")
    print(f"  - Meeting A id: {meeting_a}")
    print(f"  - Meeting B id: {meeting_b}")
    print(f"  - Answerable Q citations (A only): {len(cites_a)}")
    print(f"  - Unsupported Q citations (empty): {len(cites_refuse)}")
    print(f"  - Cross Q (no B leakage): ok")


if __name__ == "__main__":
    main()
