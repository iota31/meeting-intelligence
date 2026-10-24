"""FastAPI backend for Meeting Intelligence MVP.

Phase 2: Transcript Upload → Canonical Turns (SQLite).
- POST /api/meetings/upload/transcript
- GET /api/meetings
- GET /api/meetings/{id}

Design constraints (per plan):
- No ORM, no migrations, no repository pattern
- stdlib sqlite3 via backend/db.py
- Pydantic + FastAPI built-ins for validation/responses
- Conservative validation; consistent {error:{code,message}} errors
"""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import FastAPI, File, Form, Request, UploadFile, BackgroundTasks
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .audio import (
    MAX_AUDIO_BYTES,
    allowed_audio_content_type,
    allowed_audio_filename,
    transcribe_and_diarize,
    write_upload_to_temp,
)
from .db import (
    create_meeting,
    get_item,
    get_meeting,
    init_db,
    list_items_for_meeting,
    list_meetings,
    update_item_status,
    get_settings,
    update_settings,
    update_meeting_turns,
)
from .models import (
    ChatCitation,
    ChatRequest,
    ChatResponse,
    ErrorDetail,
    ErrorResponse,
    ExtractedItem,
    ExtractResponse,
    MeetingDetail,
    MeetingDetailWithItems,
    MeetingSummary,
    PatchItemStatus,
    TranscriptTurn,
    UploadTranscriptResponse,
    SettingsResponse,
    SettingsUpdate,
)
from .extract import run_extract_and_persist
from .rag import chat_answer, index_meeting
from .transcript import parse_transcript_text

# Logging: never log raw transcript content
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("backend")

app = FastAPI(title="Meeting Intelligence API", version="0.2.0")

# CORS: allow local frontend dev origin only (Vite default port 5173)
# Use existing local CORS config; extend only if truly necessary for dev.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Limits (conservative)
MAX_TRANSCRIPT_BYTES = 5 * 1024 * 1024  # 5 MiB
ALLOWED_CONTENT_TYPES = {"text/plain", "text/plain; charset=utf-8"}
ALLOWED_EXTENSIONS = {".txt"}

# Audio limit: MAX_AUDIO_BYTES (25 MiB) is imported from backend/audio.py.

# Ensure DB is initialized on import (idempotent)
init_db()


def _error(code: str, message: str, status_code: int = 400) -> JSONResponse:
    """Return a consistent error JSON body with given HTTP status."""
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(error=ErrorDetail(code=code, message=message)).model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def _validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Map FastAPI/Pydantic validation failures to the consistent error envelope.

    Without this, validation errors return FastAPI's default {"detail": [...]}
    shape, breaking the documented {error:{code,message}} contract.
    """
    message = "Invalid request"
    errors = exc.errors()
    if errors:
        first = errors[0]
        loc = ".".join(str(p) for p in first.get("loc", []) if p != "body")
        msg = str(first.get("msg", "invalid value"))
        message = f"{loc}: {msg}" if loc else msg
    return _error("validation_error", message, 422)


@app.exception_handler(StarletteHTTPException)
async def _http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Map framework HTTP errors (404 route not found, 405, etc.) to the error envelope."""
    code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
    return _error(code, str(exc.detail), exc.status_code)


def _sanitize_title(raw_title: str | None, fallback: str) -> str:
    """Sanitize an optional title for safe storage.

    - Strip control chars and surrounding whitespace
    - Collapse internal whitespace to single spaces
    - Enforce a reasonable length cap
    - Provide a safe fallback if empty
    - Never retain client filesystem paths (take basename only)
    """
    if not raw_title:
        return fallback
    # Remove ASCII control chars except tab/newline (then normalize whitespace)
    cleaned = "".join(ch for ch in raw_title if ch >= " " or ch in "\t\n")
    # Strip any client path components; keep only the basename
    cleaned = cleaned.replace("\\", "/").split("/")[-1]
    cleaned = " ".join(cleaned.split())
    if not cleaned:
        return fallback
    # Cap length
    if len(cleaned) > 200:
        cleaned = cleaned[:200].rstrip()
    return cleaned


def _safe_filename(name: str | None) -> str:
    """Return a safe display filename without directory components."""
    if not name:
        return "transcript.txt"
    # Take only the last path component if any path separators leaked in
    base = name.replace("\\", "/").split("/")[-1]
    # Strip control chars
    base = "".join(ch for ch in base if ch >= " " or ch in "\t\n")
    base = base.strip() or "transcript.txt"
    # Enforce a small length
    if len(base) > 120:
        base = base[:120]
    return base


@app.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint.

    Returns:
        JSON dict with status ok.
    """
    return {"status": "ok"}


def _mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "***"
    if key.startswith("gsk_"):
        return f"gsk_...{key[-4:]}"
    if key.startswith("dg_"):
        return f"dg_...{key[-4:]}"
    return f"...{key[-4:]}"

@app.get("/api/settings", response_model=SettingsResponse)
def get_settings_endpoint() -> SettingsResponse:
    """Get global settings."""
    settings = get_settings()
    settings["deepgram_api_key"] = _mask_key(settings["deepgram_api_key"])
    settings["groq_api_key"] = _mask_key(settings["groq_api_key"])
    return SettingsResponse.model_validate(settings)


@app.post("/api/settings", response_model=SettingsResponse)
def update_settings_endpoint(body: SettingsUpdate) -> SettingsResponse | JSONResponse:
    """Update global settings."""
    try:
        current = get_settings()
        dg_key = body.deepgram_api_key
        g_key = body.groq_api_key
        
        # If frontend sends back a masked key, keep the existing one
        if "..." in dg_key or dg_key == "***":
            dg_key = current["deepgram_api_key"]
        if "..." in g_key or g_key == "***":
            g_key = current["groq_api_key"]
            
        updated = update_settings(body.service_mode, dg_key, g_key)
        updated["deepgram_api_key"] = _mask_key(updated["deepgram_api_key"])
        updated["groq_api_key"] = _mask_key(updated["groq_api_key"])
        return SettingsResponse.model_validate(updated)
    except ValueError as ve:
        return _error("invalid_settings", str(ve), 400)
    except Exception as exc:
        log.exception("failed to update settings")
        return _error("settings_error", "Failed to update settings", 500)



@app.post("/api/meetings/upload/transcript", response_model=UploadTranscriptResponse)
async def upload_transcript(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
) -> UploadTranscriptResponse | JSONResponse:
    """Upload a text transcript and store canonical turns in SQLite.

    Multipart form:
    - file: text file (required)
    - title: optional meeting title (sanitized)

    Accepts:
    - .txt content-type text/plain (conservative allowlist)
    - UTF-8 decodable content

    Rejects:
    - Oversized files (> MAX_TRANSCRIPT_BYTES)
    - Disallowed extensions or content types
    - Non-UTF-8 content
    - Parse failures (missing/malformed timestamps or speakers)

    Returns 200 on success with {meeting_id, turn_count, status:"ok"}.
    Errors use {error:{code,message}} and appropriate 4xx status.
    """
    # Basic size guard (read up to limit + 1 to detect overflow)
    try:
        content = await file.read(MAX_TRANSCRIPT_BYTES + 1)
    except Exception as exc:
        log.warning("upload read error: %s", exc)
        return _error("upload_read_error", "Failed to read uploaded file", 400)

    if len(content) > MAX_TRANSCRIPT_BYTES:
        return _error("file_too_large", f"Transcript exceeds {MAX_TRANSCRIPT_BYTES} bytes", 413)

    # Extension + content-type checks (best-effort; clients may lie)
    filename = _safe_filename(file.filename)
    ext = ""
    if "." in filename:
        ext = "." + filename.rsplit(".", 1)[-1].lower()
    if ext and ext not in ALLOWED_EXTENSIONS:
        return _error("invalid_file_type", f"Only {sorted(ALLOWED_EXTENSIONS)} files are accepted", 415)

    # Be lenient on empty content_type (some clients omit), but if present it must be allowed
    ctype = (file.content_type or "").lower().strip()
    if ctype and ctype not in ALLOWED_CONTENT_TYPES:
        return _error("invalid_content_type", "Only text/plain transcripts are accepted", 415)

    # Decode as UTF-8 strictly
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return _error("invalid_encoding", "Transcript must be UTF-8 text", 415)

    # Sanitize metadata (never persist client filesystem paths)
    safe_title = _sanitize_title(title, fallback=filename.rsplit(".", 1)[0] or "Untitled Meeting")
    source_meta: dict[str, Any] = {
        "original_filename": filename,
        # Do not include client paths; only the basename
    }

    # Parse into canonical turns (raises ValueError on malformed)
    try:
        turns: list[TranscriptTurn] = parse_transcript_text(text)
    except ValueError as ve:
        # Map parse errors to 422 with explicit message
        return _error("parse_error", str(ve), 422)

    if not turns:
        return _error("parse_error", "No turns parsed from transcript", 422)

    # Convert to plain dicts for persistence (no client paths)
    turns_dicts = [t.model_dump() for t in turns]

    try:
        meeting_id = create_meeting(
            title=safe_title,
            source_type="transcript",
            source_meta=source_meta,
            turns=turns_dicts,
        )
    except Exception:
        # Do not leak internal details
        log.exception("create_meeting failed")
        return _error("storage_error", "Failed to persist meeting", 500)

    # Phase 4: index after successful persistence (never partial meetings).
    # Run in a worker thread: embedding makes sequential HTTP calls to Ollama
    # and must not block the event loop.
    try:
        await run_in_threadpool(index_meeting, meeting_id, turns)
    except Exception:
        # Indexing is best-effort for MVP; do not fail the upload on index issues.
        # The derived index can be rebuilt from SQLite later if needed.
        log.exception("index_meeting (transcript) failed; continuing without index")

    return UploadTranscriptResponse(meeting_id=meeting_id, turn_count=len(turns))


@app.get("/api/meetings", response_model=list[MeetingSummary])
def get_meetings() -> list[MeetingSummary]:
    """List all meetings (newest first)."""
    rows = list_meetings()
    return [MeetingSummary.model_validate(r) for r in rows]


# -------------------- Audio upload (Phase 3) + Phase 4 indexing --------------------

async def process_audio_background(meeting_id: str, tmp_path: str) -> None:
    """Background task to transcribe, diarize, persist turns, and index."""
    try:
        turns = await run_in_threadpool(transcribe_and_diarize, tmp_path)
        if not turns:
            log.warning("No turns extracted for meeting %s", meeting_id)
            update_meeting_turns(meeting_id, [], "error")
            return
            
        turns_dicts = [t.model_dump() for t in turns]
        update_meeting_turns(meeting_id, turns_dicts, "ready")
        
        try:
            await run_in_threadpool(index_meeting, meeting_id, turns)
        except Exception:
            log.exception("index_meeting (audio) failed; continuing without index")
    except Exception as exc:
        log.exception("async audio process failed %s", meeting_id)
        update_meeting_turns(meeting_id, [], "error")
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


@app.post("/api/meetings/upload/audio", response_model=UploadTranscriptResponse, status_code=202)
async def upload_audio(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
) -> JSONResponse:
    """Upload an audio file, persist meeting as 'processing', and offload transcription."""
    try:
        content = await file.read(MAX_AUDIO_BYTES + 1)
    except Exception as exc:
        log.warning("audio upload read error: %s", exc)
        return _error("upload_read_error", "Failed to read uploaded file", 400)

    if len(content) > MAX_AUDIO_BYTES:
        return _error("file_too_large", f"Audio exceeds {MAX_AUDIO_BYTES} bytes", 413)

    filename = _safe_filename(file.filename)
    if not allowed_audio_filename(filename):
        return _error("invalid_file_type", "Only .mp3 and .wav audio files are accepted", 415)

    ctype = file.content_type
    if not allowed_audio_content_type(ctype):
        return _error("invalid_content_type", "Only MP3 or WAV audio is accepted", 415)

    suffix = ""
    if "." in filename:
        ext = "." + filename.rsplit(".", 1)[-1].lower()
        if ext in {".mp3", ".wav"}:
            suffix = ext
    try:
        tmp_path = write_upload_to_temp(content, suffix=suffix or ".wav")
    except ValueError as ve:
        return _error("file_too_large", str(ve), 413)
    except Exception as exc:
        log.warning("failed to write temp audio: %s", exc)
        return _error("upload_write_error", "Failed to stage uploaded audio for processing", 500)

    safe_title = _sanitize_title(title, fallback=filename.rsplit(".", 1)[0] or "Untitled Meeting")
    source_meta = {"original_filename": filename}

    try:
        meeting_id = create_meeting(
            title=safe_title,
            source_type="audio",
            source_meta=source_meta,
            turns=[],
        )
    except Exception:
        log.exception("create_meeting (audio) failed")
        if tmp_path:
            os.unlink(tmp_path)
        return _error("storage_error", "Failed to persist meeting", 500)

    background_tasks.add_task(process_audio_background, meeting_id, tmp_path)

    return JSONResponse(
        status_code=202,
        content=UploadTranscriptResponse(meeting_id=meeting_id, turn_count=0, status="processing").model_dump()
    )


# -------------------- Phase 6: Grounded chat --------------------

@app.post(
    "/api/meetings/{meeting_id}/chat",
    response_model=ChatResponse,
)
def chat(meeting_id: str, body: ChatRequest) -> ChatResponse | JSONResponse:
    """Grounded chat over a single meeting's transcript.

    Body: { "question": str }
    - Non-empty and length-capped (enforced by ChatRequest).
    - Retrieval is strictly scoped to the requested meeting.
    - If retrieval is empty or weak (distance threshold), returns an explicit
      insufficient-evidence answer with empty citations and does NOT call the LLM.
    - Citations are built deterministically from retrieved chunk metadata
      (speaker + start/end ms). Model output is not trusted for citations.
    - Uses only local Ollama (llama3.2:3b). No external services.
    """
    # Ensure the meeting exists (fail fast with 404 for UX clarity)
    rec = get_meeting(meeting_id)
    if rec is None:
        return _error("not_found", "Meeting not found", 404)

    try:
        result = chat_answer(meeting_id, body.question)
    except Exception:
        log.exception("chat_answer failed")
        return _error("chat_error", "Chat failed", 500)

    # Map to response model
    citations = [ChatCitation.model_validate(c) for c in result.citations]
    return ChatResponse(answer=result.answer, citations=citations)


# -------------------- Phase 5/7: Extraction + Item status --------------------

async def extract_background(meeting_id: str) -> None:
    from .db import update_meeting_status_only
    try:
        # run_in_threadpool because run_extract_and_persist makes blocking DB and HTTP calls
        from fastapi.concurrency import run_in_threadpool
        await run_in_threadpool(run_extract_and_persist, meeting_id)
        update_meeting_status_only(meeting_id, "ready")
    except Exception as exc:
        log.exception("extract_background failed for %s", meeting_id)
        update_meeting_status_only(meeting_id, "error")


@app.post(
    "/api/meetings/{meeting_id}/extract",
    status_code=202,
)
def extract(meeting_id: str, background_tasks: BackgroundTasks) -> JSONResponse:
    """Extract decisions and action items for a meeting.

    Runs in the background. Sets status to 'processing'.
    """
    # Ensure meeting exists
    rec = get_meeting(meeting_id)
    if rec is None:
        return _error("not_found", "Meeting not found", 404)

    from .db import update_meeting_status_only
    update_meeting_status_only(meeting_id, "processing")
    background_tasks.add_task(extract_background, meeting_id)

    return JSONResponse(status_code=202, content={"message": "Extraction started", "status": "processing"})


@app.patch(
    "/api/items/{item_id}",
    response_model=ExtractedItem,
)
def patch_item(item_id: str, body: PatchItemStatus) -> ExtractedItem | JSONResponse:
    """Confirm or dismiss an extracted item.

    Body: { "status": "confirmed" | "dismissed" }
    """
    # Ensure item exists first for clearer 404
    existing = get_item(item_id)
    if existing is None:
        return _error("not_found", "Item not found", 404)

    try:
        updated = update_item_status(item_id, body.status)
    except ValueError:
        return _error("invalid_status", "Invalid status value", 400)
    except Exception:
        log.exception("update_item_status failed")
        return _error("update_error", "Failed to update item", 500)

    if updated is None:
        return _error("not_found", "Item not found", 404)

    return ExtractedItem.model_validate(updated)


@app.get("/api/meetings/{meeting_id}", response_model=MeetingDetailWithItems)
def get_meeting_by_id(meeting_id: str) -> MeetingDetailWithItems | JSONResponse:
    """Return a meeting with ordered normalized turns and extracted items (all statuses)."""
    rec = get_meeting(meeting_id)
    if rec is None:
        return _error("not_found", "Meeting not found", 404)

    items = list_items_for_meeting(meeting_id)
    rec["items"] = items  # extend with items for the enriched model
    detail = MeetingDetailWithItems.model_validate(rec)
    return detail


@app.delete("/api/meetings/{meeting_id}", response_model=None)
def delete_meeting_endpoint(meeting_id: str) -> dict[str, str] | JSONResponse:
    """Delete a meeting and its index."""
    from .db import delete_meeting
    from .rag import delete_meeting_index
    rec = get_meeting(meeting_id)
    if rec is None:
        return _error("not_found", "Meeting not found", 404)
        
    delete_meeting(meeting_id)
    try:
        delete_meeting_index(meeting_id)
    except Exception as exc:
        log.warning("failed to delete meeting index %s: %s", meeting_id, exc)
    return {"status": "ok"}
