#!/usr/bin/env python3
"""Verification script for Phase 2 (Transcript Upload → Canonical Turns using SQLite).

Runs a local FastAPI test client:
1. Uploads a four-turn synthetic transcript via POST /api/meetings/upload/transcript
2. Asserts exact stored normalized values via GET /api/meetings/{id}

No AI, no external services. Uses only stdlib + FastAPI TestClient.

Grammar exercised:
    [HH:MM:SS] Speaker: text
    (with a multi-line continuation for turn_001)

Expected canonical turns (exact values):
- turn_000: Alice, 0-60000, "Let's kick off the project."
- turn_001: Bob, 60000-120000, "Agreed. The timeline looks tight but doable."
- turn_002: Alice, 120000-180000, "I'll send the draft by Friday."
- turn_003: Bob, 180000-181000, "Thanks."

Run (from repo root):
    .venv/bin/python backend/verify_phase2.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make repo root importable so 'backend' package resolves
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient

from backend.main import app  # type: ignore[attr-defined]
from backend.db import init_db  # type: ignore[attr-defined]


def main() -> int:
    # Ensure a clean slate for this run's expectations (idempotent init)
    init_db()

    client = TestClient(app)

    # Synthetic four-turn transcript (UTF-8)
    # Note the continuation line for Bob's turn (no leading bracket).
    transcript = (
        "[00:00:00] Alice: Let's kick off the project.\n"
        "[00:01:00] Bob: Agreed.\n"
        " The timeline looks tight but doable.\n"
        "[00:02:00] Alice: I'll send the draft by Friday.\n"
        "[00:03:00] Bob: Thanks.\n"
    )

    # Upload via multipart form; provide an explicit title
    files = {
        "file": ("meeting_notes.txt", transcript.encode("utf-8"), "text/plain"),
    }
    data = {"title": "Phase2 Verification Meeting"}

    resp = client.post("/api/meetings/upload/transcript", files=files, data=data)
    if resp.status_code != 200:
        print("FAIL: upload returned", resp.status_code, resp.text)
        return 1

    payload = resp.json()
    if payload.get("status") != "ok":
        print("FAIL: unexpected upload payload", payload)
        return 1

    meeting_id = payload.get("meeting_id")
    turn_count = payload.get("turn_count")
    if not meeting_id or turn_count != 4:
        print("FAIL: upload response mismatch", payload)
        return 1

    # Fetch via GET /api/meetings/{id}
    detail_resp = client.get(f"/api/meetings/{meeting_id}")
    if detail_resp.status_code != 200:
        print("FAIL: detail returned", detail_resp.status_code, detail_resp.text)
        return 1

    detail = detail_resp.json()

    # Basic shape checks
    if detail.get("turn_count") != 4:
        print("FAIL: turn_count mismatch", detail.get("turn_count"))
        return 1

    turns = detail.get("turns") or []
    if len(turns) != 4:
        print("FAIL: turns length", len(turns))
        return 1

    # Exact assertions per plan's "exactly those 4 turns with correct speaker, start_ms, end_ms, text"
    expected = [
        {"turn_id": "turn_000", "speaker": "Alice", "start_ms": 0, "end_ms": 60000, "text": "Let's kick off the project."},
        {"turn_id": "turn_001", "speaker": "Bob", "start_ms": 60000, "end_ms": 120000, "text": "Agreed. The timeline looks tight but doable."},
        {"turn_id": "turn_002", "speaker": "Alice", "start_ms": 120000, "end_ms": 180000, "text": "I'll send the draft by Friday."},
        {"turn_id": "turn_003", "speaker": "Bob", "start_ms": 180000, "end_ms": 181000, "text": "Thanks."},
    ]

    for i, (t, exp) in enumerate(zip(turns, expected)):
        for k, v in exp.items():
            actual = t.get(k)
            if actual != v:
                print(f"FAIL: turn {i} field {k}: got {actual!r}, expected {v!r}")
                print("Full turn:", t)
                return 1

    # Also verify list endpoint contains our meeting
    list_resp = client.get("/api/meetings")
    if list_resp.status_code != 200:
        print("FAIL: list returned", list_resp.status_code, list_resp.text)
        return 1
    listings = list_resp.json()
    ids = [m.get("id") for m in listings]
    if meeting_id not in ids:
        print("FAIL: meeting not present in list", ids)
        return 1

    print("PASS: Phase 2 verification complete.")
    print(f"meeting_id={meeting_id} turns={turn_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
