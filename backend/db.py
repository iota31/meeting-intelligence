"""Minimal SQLite persistence for Phase 2 (no ORM, no migrations).

Schema:
- meetings: id, title, created_at, source_type, source_meta, turn_count
- transcript_turns: id (PK), meeting_id (FK), turn_id, speaker, start_ms, end_ms, text, turn_index

Source of truth: SQLite under data/meetings.db (gitignored).
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

# Resolve data directory relative to repo root (two levels up from backend/)
REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
DB_PATH = DATA_DIR / "meetings.db"

# Ensure data directory exists (safe, idempotent)
DATA_DIR.mkdir(parents=True, exist_ok=True)

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS meetings (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK (source_type IN ('transcript', 'audio')),
    source_meta TEXT,                 -- JSON blob (nullable)
    turn_count INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'ready' CHECK (status IN ('processing', 'ready', 'error'))
);

CREATE TABLE IF NOT EXISTS transcript_turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id TEXT NOT NULL,
    turn_id TEXT NOT NULL,
    speaker TEXT NOT NULL,
    start_ms INTEGER NOT NULL,
    end_ms INTEGER NOT NULL,
    text TEXT NOT NULL,
    turn_index INTEGER NOT NULL,
    FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_turns_meeting ON transcript_turns(meeting_id, turn_index);

CREATE TABLE IF NOT EXISTS extracted_items (
    id TEXT PRIMARY KEY,
    meeting_id TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('decision', 'action_item')),
    text TEXT NOT NULL,
    owner TEXT,
    due TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'confirmed', 'dismissed')),
    citations TEXT NOT NULL,  -- JSON array of Citation dicts
    created_at TEXT NOT NULL,
    FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_items_meeting ON extracted_items(meeting_id);

CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    service_mode TEXT NOT NULL DEFAULT 'local' CHECK (service_mode IN ('local', 'cloud')),
    deepgram_api_key TEXT NOT NULL DEFAULT '',
    groq_api_key TEXT NOT NULL DEFAULT ''
);
INSERT OR IGNORE INTO settings (id, service_mode, deepgram_api_key, groq_api_key) VALUES (1, 'local', '', '');
"""


def _connect() -> sqlite3.Connection:
    """Open a connection with safe defaults."""
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db() -> None:
    """Initialize schema if missing. Idempotent."""
    conn = _connect()
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()


def _now_iso() -> str:
    """Return current time in ISO8601 UTC with 'Z' suffix (no microseconds)."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _generate_meeting_id() -> str:
    """Generate a stable-ish meeting id. UUID4 is fine for local use."""
    return str(uuid.uuid4())


def create_meeting(
    *,
    title: str,
    source_type: str,
    source_meta: dict[str, Any] | None,
    turns: list[dict[str, Any]],
) -> str:
    """Persist a meeting and its canonical turns. Returns meeting id.

    turns: list of dicts matching TranscriptTurn shape (turn_id, speaker, start_ms, end_ms, text).
    Order of list defines turn_index (0-based).
    """
    if source_type not in ("transcript", "audio"):
        raise ValueError("source_type must be 'transcript' or 'audio'")

    meeting_id = _generate_meeting_id()
    created_at = _now_iso()
    turn_count = len(turns) if turns else 0
    source_meta_json = json.dumps(source_meta) if source_meta is not None else None
    
    # If turns are empty (like for audio background), status is 'processing', else 'ready'
    status = "processing" if turn_count == 0 and source_type == "audio" else "ready"

    conn = _connect()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO meetings (id, title, created_at, source_type, source_meta, turn_count, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (meeting_id, title, created_at, source_type, source_meta_json, turn_count, status),
            )
            for idx, t in enumerate(turns):
                conn.execute(
                    """
                    INSERT INTO transcript_turns
                        (meeting_id, turn_id, speaker, start_ms, end_ms, text, turn_index)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        meeting_id,
                        t["turn_id"],
                        t["speaker"],
                        int(t["start_ms"]),
                        int(t["end_ms"]),
                        t["text"],
                        idx,
                    ),
                )
    finally:
        conn.close()

    return meeting_id


def update_meeting_turns(meeting_id: str, turns: list[dict[str, Any]], status: str) -> None:
    """Update a meeting's turns and status (used for async processing)."""
    conn = _connect()
    try:
        with conn:
            conn.execute("DELETE FROM transcript_turns WHERE meeting_id = ?", (meeting_id,))
            conn.execute("UPDATE meetings SET turn_count = ?, status = ? WHERE id = ?", (len(turns), status, meeting_id))
            for idx, t in enumerate(turns):
                conn.execute(
                    """
                    INSERT INTO transcript_turns
                        (meeting_id, turn_id, speaker, start_ms, end_ms, text, turn_index)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (meeting_id, t["turn_id"], t["speaker"], int(t["start_ms"]), int(t["end_ms"]), t["text"], idx),
                )
    finally:
        conn.close()


def update_meeting_status_only(meeting_id: str, status: str) -> None:
    """Update only the status of a meeting."""
    if status not in ("processing", "ready", "error"):
        raise ValueError("invalid status")
    conn = _connect()
    try:
        with conn:
            conn.execute("UPDATE meetings SET status = ? WHERE id = ?", (status, meeting_id))
    finally:
        conn.close()


def list_meetings() -> list[dict[str, Any]]:
    """Return summaries for all meetings, newest first."""
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT id, title, created_at, source_type, source_meta, turn_count, status
            FROM meetings
            ORDER BY created_at DESC, id DESC
            """
        ).fetchall()
    finally:
        conn.close()

    out: list[dict[str, Any]] = []
    for r in rows:
        meta = json.loads(r["source_meta"]) if r["source_meta"] else None
        out.append(
            {
                "id": r["id"],
                "title": r["title"],
                "created_at": r["created_at"],
                "source_type": r["source_type"],
                "source_meta": meta,
                "turn_count": r["turn_count"],
                "status": r["status"],
            }
        )
    return out


def get_meeting(meeting_id: str) -> dict[str, Any] | None:
    """Return meeting + ordered turns, or None if not found."""
    conn = _connect()
    try:
        m = conn.execute(
            """
            SELECT id, title, created_at, source_type, source_meta, turn_count, status
            FROM meetings WHERE id = ?
            """,
            (meeting_id,),
        ).fetchone()
        if m is None:
            return None

        meta = json.loads(m["source_meta"]) if m["source_meta"] else None

        turns_rows = conn.execute(
            """
            SELECT turn_id, speaker, start_ms, end_ms, text
            FROM transcript_turns
            WHERE meeting_id = ?
            ORDER BY turn_index ASC
            """,
            (meeting_id,),
        ).fetchall()

        turns = [
            {
                "turn_id": tr["turn_id"],
                "speaker": tr["speaker"],
                "start_ms": tr["start_ms"],
                "end_ms": tr["end_ms"],
                "text": tr["text"],
            }
            for tr in turns_rows
        ]

        return {
            "id": m["id"],
            "title": m["title"],
            "created_at": m["created_at"],
            "source_type": m["source_type"],
            "source_meta": meta,
            "turn_count": m["turn_count"],
            "status": m["status"],
            "turns": turns,
        }
    finally:
        conn.close()


def delete_meeting(meeting_id: str) -> None:
    """Delete a meeting and all associated cascade records."""
    conn = _connect()
    try:
        with conn:
            conn.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))
    finally:
        conn.close()


# -------------------- Phase 5/7: Extracted Items --------------------

def _generate_item_id() -> str:
    """Generate a UUID for an extracted item."""
    return str(uuid.uuid4())


def get_turns_for_meeting(meeting_id: str) -> list[dict[str, Any]]:
    """Return canonical turns for a meeting, or [] if not found."""
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT turn_id, speaker, start_ms, end_ms, text
            FROM transcript_turns
            WHERE meeting_id = ?
            ORDER BY turn_index ASC
            """,
            (meeting_id,),
        ).fetchall()
        return [
            {
                "turn_id": r["turn_id"],
                "speaker": r["speaker"],
                "start_ms": r["start_ms"],
                "end_ms": r["end_ms"],
                "text": r["text"],
            }
            for r in rows
        ]
    finally:
        conn.close()


def replace_pending_items(meeting_id: str, items: list[dict[str, Any]]) -> int:
    """Delete all pending items for a meeting and insert the provided items.

    Returns the number of new items inserted.
    """
    conn = _connect()
    try:
        with conn:
            conn.execute(
                "DELETE FROM extracted_items WHERE meeting_id = ? AND status = 'pending'",
                (meeting_id,),
            )
            count = 0
            for it in items:
                iid = it.get("id") or _generate_item_id()
                conn.execute(
                    """
                    INSERT INTO extracted_items
                        (id, meeting_id, type, text, owner, due, status, citations, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        iid,
                        meeting_id,
                        it["type"],
                        it["text"],
                        it.get("owner"),
                        it.get("due"),
                        it.get("status", "pending"),
                        json.dumps(it.get("citations", [])),
                        it.get("created_at") or _now_iso(),
                    ),
                )
                count += 1
        return count
    finally:
        conn.close()


def list_items_for_meeting(meeting_id: str) -> list[dict[str, Any]]:
    """Return all extracted items for a meeting (all statuses)."""
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT id, meeting_id, type, text, owner, due, status, citations, created_at
            FROM extracted_items
            WHERE meeting_id = ?
            ORDER BY created_at ASC, rowid ASC
            """,
            (meeting_id,),
        ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            try:
                cites = json.loads(r["citations"]) if r["citations"] else []
            except Exception:
                cites = []
            out.append(
                {
                    "id": r["id"],
                    "meeting_id": r["meeting_id"],
                    "type": r["type"],
                    "text": r["text"],
                    "owner": r["owner"],
                    "due": r["due"],
                    "status": r["status"],
                    "citations": cites,
                    "created_at": r["created_at"],
                }
            )
        return out
    finally:
        conn.close()


def get_item(item_id: str) -> dict[str, Any] | None:
    """Return a single extracted item by id, or None."""
    conn = _connect()
    try:
        r = conn.execute(
            """
            SELECT id, meeting_id, type, text, owner, due, status, citations, created_at
            FROM extracted_items
            WHERE id = ?
            """,
            (item_id,),
        ).fetchone()
        if r is None:
            return None
        try:
            cites = json.loads(r["citations"]) if r["citations"] else []
        except Exception:
            cites = []
        return {
            "id": r["id"],
            "meeting_id": r["meeting_id"],
            "type": r["type"],
            "text": r["text"],
            "owner": r["owner"],
            "due": r["due"],
            "status": r["status"],
            "citations": cites,
            "created_at": r["created_at"],
        }
    finally:
        conn.close()


def update_item_status(item_id: str, status: str) -> dict[str, Any] | None:
    """Update status for an item. Returns the updated item or None if not found."""
    if status not in ("pending", "confirmed", "dismissed"):
        raise ValueError("invalid status")
    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                "UPDATE extracted_items SET status = ? WHERE id = ?",
                (status, item_id),
            )
            if cur.rowcount == 0:
                return None
        # Re-fetch to return fresh row
        return get_item(item_id)
    finally:
        conn.close()


# -------------------- Global Settings --------------------

def get_settings() -> dict[str, Any]:
    """Return the global application settings."""
    conn = _connect()
    try:
        r = conn.execute("SELECT service_mode, deepgram_api_key, groq_api_key FROM settings WHERE id = 1").fetchone()
        if r is None:
            # Should not happen due to INSERT OR IGNORE, but fallback safely
            return {"service_mode": "local", "deepgram_api_key": "", "groq_api_key": ""}
        return {
            "service_mode": r["service_mode"],
            "deepgram_api_key": r["deepgram_api_key"],
            "groq_api_key": r["groq_api_key"]
        }
    finally:
        conn.close()


def update_settings(service_mode: str, deepgram_api_key: str, groq_api_key: str) -> dict[str, Any]:
    """Update and return the global application settings."""
    if service_mode not in ("local", "cloud"):
        raise ValueError("service_mode must be 'local' or 'cloud'")
    conn = _connect()
    try:
        with conn:
            conn.execute(
                """
                UPDATE settings 
                SET service_mode = ?, deepgram_api_key = ?, groq_api_key = ? 
                WHERE id = 1
                """,
                (service_mode, deepgram_api_key, groq_api_key)
            )
        return get_settings()
    finally:
        conn.close()
