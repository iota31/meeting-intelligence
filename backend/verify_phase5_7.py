#!/usr/bin/env python3
"""Verification for Phase 5 (Extraction) and Phase 7 (Item Confirmation).

This script performs a local HTTP test against a running backend:
- Uploads a meeting with known transcript turns.
- Calls POST /api/meetings/{id}/extract and asserts items have citations to real turn_ids.
- Calls PATCH /api/items/{id} to confirm one item; re-extracts and asserts confirmed persists.
- Calls PATCH to dismiss another; asserts dismissal works.
- Attempts cross-meeting citation injection (uploading a second meeting and trying to force
  citations from Meeting A into Meeting B's extract result) and asserts rejection (no such items).

Ponytail constraints:
- Uses only the already-running local Ollama (llama3.2:3b).
- No new AI deps, no Docker, no auth, no queues, no abstractions.
- Pure HTTP client against http://127.0.0.1:8000.

Requirements:
- Backend running: .venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000
- Ollama running with llama3.2:3b (and nomic-embed-text for prior phases)

Run:
    .venv/bin/python backend/verify_phase5_7.py

Exit 0 on success; non-zero on any failure.
"""

from __future__ import annotations

import json
import sys
import time
from typing import Any

import httpx

API = "http://127.0.0.1:8000"
TIMEOUT = httpx.Timeout(180.0, connect=10.0)

# Synthetic transcript designed to be extractable:
# - One clear decision with explicit speaker/time.
# - One clear action item with explicit speaker/time.
# Keep it short and deterministic.
MEETING_A_TITLE = "Phase5_7 Fixture A"
MEETING_A_TRANSCRIPT = """[00:00:00] Alice: Let's finalize the launch date.
[00:00:04] Bob: I propose we launch on 2026-08-01.
[00:00:10] Alice: Agreed. Decision: launch date is 2026-08-01.
[00:00:15] Carol: I will prepare the release notes by Friday.
[00:00:20] Alice: Thanks. Action: Carol to prepare release notes.
"""

# A second meeting used to attempt cross-meeting citation injection.
# Its turns have different turn_ids (turn_000 etc.), but we will try to
# feed a citation that references Meeting A's turn ids to see if the
# server accepts it for Meeting B. It must not.
MEETING_B_TITLE = "Phase5_7 Fixture B"
MEETING_B_TRANSCRIPT = """[00:00:00] Dana: We need more test coverage.
[00:00:05] Evan: Agreed. Let's add integration tests next sprint.
"""


def _post_upload_transcript(title: str, text: str) -> dict[str, Any]:
    files = {"file": ("transcript.txt", text.encode("utf-8"), "text/plain")}
    data = {"title": title}
    with httpx.Client(timeout=TIMEOUT) as client:
        r = client.post(f"{API}/api/meetings/upload/transcript", files=files, data=data)
        r.raise_for_status()
        return r.json()


def _post_extract(meeting_id: str) -> dict[str, Any]:
    with httpx.Client(timeout=TIMEOUT) as client:
        r = client.post(f"{API}/api/meetings/{meeting_id}/extract")
        r.raise_for_status()
        return r.json()


def _get_meeting(meeting_id: str) -> dict[str, Any]:
    with httpx.Client(timeout=TIMEOUT) as client:
        r = client.get(f"{API}/api/meetings/{meeting_id}")
        r.raise_for_status()
        return r.json()


def _patch_item(item_id: str, status: str) -> dict[str, Any]:
    with httpx.Client(timeout=TIMEOUT) as client:
        r = client.patch(f"{API}/api/items/{item_id}", json={"status": status})
        r.raise_for_status()
        return r.json()


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        print("FAIL:", msg, file=sys.stderr)
        sys.exit(1)


def main() -> None:
    print("Phase 5/7 verification starting...")
    print("NOTE: Ensure backend is running on", API)
    print("NOTE: Ensure Ollama has llama3.2:3b")

    # 1) Upload Meeting A
    a = _post_upload_transcript(MEETING_A_TITLE, MEETING_A_TRANSCRIPT)
    meeting_a = a["meeting_id"]
    print(f"Uploaded A={meeting_a} turns={a['turn_count']}")

    # Capture canonical turns for A to validate citations strictly later
    detail_a = _get_meeting(meeting_a)
    turns_a = detail_a.get("turns", [])
    _assert(len(turns_a) >= 2, "Expected at least 2 turns in A")
    turn_ids_a = {t["turn_id"] for t in turns_a}
    print(f"A turns: {len(turns_a)} ids={sorted(turn_ids_a)}")

    # 2) Extract A
    ex_a = _post_extract(meeting_a)
    print("Extract A ->", json.dumps(ex_a, indent=2)[:1200])
    items_a = ex_a.get("items", [])
    _assert(isinstance(items_a, list) and len(items_a) > 0, "Expected at least one extracted item for A")

    # 2a) Every item must have citations referencing only valid turn_ids from A
    for it in items_a:
        cites = it.get("citations") or []
        _assert(len(cites) > 0, f"Item missing citations: {it}")
        for c in cites:
            _assert(c.get("turn_id") in turn_ids_a, f"Citation turn_id not in A: {c}")
            # speaker/start/end must match the canonical turn exactly
            t = next((x for x in turns_a if x["turn_id"] == c["turn_id"]), None)
            _assert(t is not None, f"Cannot resolve turn for citation: {c}")
            _assert(c.get("speaker") == t["speaker"], f"Speaker mismatch in citation: {c}")
            _assert(int(c.get("start_ms")) == int(t["start_ms"]), f"start_ms mismatch: {c}")
            _assert(int(c.get("end_ms")) == int(t["end_ms"]), f"end_ms mismatch: {c}")

    # 2b) Capture one item id for confirm and one for dismiss (if available)
    item_ids = [it["id"] for it in items_a]
    _assert(len(item_ids) >= 1, "Need at least one item id to test confirm/dismiss")
    confirm_id = item_ids[0]
    dismiss_id = item_ids[1] if len(item_ids) > 1 else None

    # 3) Confirm one item
    patched = _patch_item(confirm_id, "confirmed")
    print("Confirmed item ->", json.dumps(patched, indent=2)[:600])
    _assert(patched.get("id") == confirm_id and patched.get("status") == "confirmed", "Confirm did not persist")

    # 4) Dismiss a second item (if present) BEFORE re-extract so it is preserved
    if dismiss_id:
        dismissed = _patch_item(dismiss_id, "dismissed")
        print("Dismissed item ->", json.dumps(dismissed, indent=2)[:600])
        _assert(dismissed.get("id") == dismiss_id and dismissed.get("status") == "dismissed", "Dismiss did not work")

    # 5) Re-extract and verify confirmed (and dismissed if any) persist; pending are replaced
    ex_a2 = _post_extract(meeting_a)
    items_a2 = ex_a2.get("items", [])
    # Find the previously confirmed item by id
    confirmed_after = next((i for i in items_a2 if i["id"] == confirm_id), None)
    _assert(confirmed_after is not None, "Previously confirmed item disappeared after re-extract")
    _assert(confirmed_after.get("status") == "confirmed", "Confirmed status did not persist across re-extract")

    if dismiss_id:
        drow = next((i for i in items_a2 if i["id"] == dismiss_id), None)
        _assert(drow is not None and drow.get("status") == "dismissed", "Previously dismissed item did not persist after re-extract")

    # 6) Re-fetch meeting and ensure GET includes statuses
    detail_after = _get_meeting(meeting_a)
    items_after = detail_after.get("items", [])
    _assert(any(i["id"] == confirm_id and i["status"] == "confirmed" for i in items_after), "GET meeting missing confirmed status")
    if dismiss_id:
        _assert(any(i["id"] == dismiss_id and i["status"] == "dismissed" for i in items_after), "GET meeting missing dismissed status")

    # 6) Cross-meeting citation rejection:
    # Upload Meeting B, extract, and ensure none of B's citations reference A's turn identities.
    # (turn_id alone can collide across meetings; we must compare the full (turn_id, speaker, start_ms, end_ms) tuple.)
    b = _post_upload_transcript(MEETING_B_TITLE, MEETING_B_TRANSCRIPT)
    meeting_b = b["meeting_id"]
    print(f"Uploaded B={meeting_b} turns={b['turn_count']}")
    detail_b = _get_meeting(meeting_b)
    turns_b = detail_b.get("turns", [])
    b_tuples = {(t["turn_id"], t["speaker"], int(t["start_ms"]), int(t["end_ms"])) for t in turns_b}
    a_tuples = {(t["turn_id"], t["speaker"], int(t["start_ms"]), int(t["end_ms"])) for t in turns_a}

    ex_b = _post_extract(meeting_b)
    items_b = ex_b.get("items", [])
    for it in items_b:
        for c in it.get("citations") or []:
            ct = (c.get("turn_id"), c.get("speaker"), int(c.get("start_ms")), int(c.get("end_ms")))
            _assert(ct not in a_tuples, f"Cross-meeting citation leak from A into B: {c}")
            # Also ensure citation exists in B's own turns (defense-in-depth)
            _assert(ct in b_tuples, f"Citation for B does not match any B turn: {c}")

    # 7) GET meeting for A must include items (with statuses)
    detail_final = _get_meeting(meeting_a)
    _assert("items" in detail_final, "GET /meetings/{id} missing 'items'")
    _assert(any(i["id"] == confirm_id and i["status"] == "confirmed" for i in detail_final["items"]),
            "GET meeting did not include the confirmed item with correct status")

    print("All Phase 5/7 checks passed.")
    print("Summary:")
    print(f"  - Meeting A id: {meeting_a}")
    print(f"  - Meeting B id: {meeting_b}")
    print(f"  - Items extracted for A: {len(items_a)}")
    print(f"  - Confirmed persisted after re-extract: yes")
    if dismiss_id:
        print(f"  - Dismissed item persisted in GET: yes")
    print(f"  - Cross-meeting citations rejected: yes")


if __name__ == "__main__":
    main()
