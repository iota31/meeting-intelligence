"""Pydantic models for Phase 2 (Transcript Upload → Canonical Turns).

Only the minimal shapes required by the plan:
- TranscriptTurn: canonical turn model
- MeetingSummary, MeetingDetail: response shapes
- Upload response and error shapes
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TranscriptTurn(BaseModel):
    """Canonical turn model shared by all ingest paths (Phase 2+).

    Fields per IMPLEMENTATION_PLAN.md §3.1:
    - turn_id: stable identifier for the turn within a meeting
    - speaker: speaker label (as provided or normalized)
    - start_ms: start time in milliseconds
    - end_ms: end time in milliseconds
    - text: utterance text
    """

    turn_id: str
    speaker: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    text: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "turn_id": "turn_000",
                "speaker": "Alice",
                "start_ms": 0,
                "end_ms": 12500,
                "text": "Let's start with the Q3 numbers.",
            }
        }
    }


class MeetingSummary(BaseModel):
    """Summary row for GET /api/meetings."""

    id: str
    title: str
    created_at: str
    source_type: Literal["transcript", "audio"]
    source_meta: dict | None = None
    turn_count: int
    status: Literal["processing", "ready", "error"] = "ready"


class MeetingDetail(BaseModel):
    """Full detail for GET /api/meetings/{id} (Phase 2: turns only)."""

    id: str
    title: str
    created_at: str
    source_type: Literal["transcript", "audio"]
    source_meta: dict | None = None
    turn_count: int
    status: Literal["processing", "ready", "error"] = "ready"
    turns: list[TranscriptTurn]


class UploadTranscriptResponse(BaseModel):
    """Response for POST /api/meetings/upload/transcript."""

    meeting_id: str
    turn_count: int
    status: Literal["ok", "processing"] = "ok"


class ErrorDetail(BaseModel):
    """Consistent error envelope: { "error": { "code": "...", "message": "..." } }"""

    code: str
    message: str


class ErrorResponse(BaseModel):
    """Top-level error body."""

    error: ErrorDetail


# -------------------- Phase 6: Chat models --------------------

class ChatRequest(BaseModel):
    """Request body for POST /api/meetings/{id}/chat."""

    question: str = Field(min_length=1, max_length=2000)


class ChatCitation(BaseModel):
    """Citation derived deterministically from retrieved chunks (not model output)."""

    turn_id: str | None = None
    speaker: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)


class ChatResponse(BaseModel):
    """Response for POST /api/meetings/{id}/chat.

    - answer: model text or an explicit insufficient-evidence refusal
    - citations: deterministic speaker+timestamp citations from retrieval metadata
    """

    answer: str
    citations: list[ChatCitation]


# -------------------- Phase 5/7: Extraction models --------------------

class Citation(BaseModel):
    """Citation to a canonical turn within a meeting."""

    turn_id: str
    speaker: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)


class ExtractedItem(BaseModel):
    """A decision or action item extracted from a meeting, with citations."""

    id: str
    meeting_id: str
    type: Literal["decision", "action_item"]
    text: str
    owner: str | None = None
    due: str | None = None
    status: Literal["pending", "confirmed", "dismissed"] = "pending"
    citations: list[Citation]
    created_at: str


class ExtractResponse(BaseModel):
    """Response for POST /api/meetings/{id}/extract."""

    extracted: int
    items: list[ExtractedItem]


class PatchItemStatus(BaseModel):
    """Request body for PATCH /api/items/{id}."""

    status: Literal["confirmed", "dismissed"]


class MeetingDetailWithItems(MeetingDetail):
    """GET /api/meetings/{id} response that also includes extracted items."""

    items: list[ExtractedItem] = []


# -------------------- Global Settings --------------------

class SettingsResponse(BaseModel):
    service_mode: Literal["local", "cloud"]
    deepgram_api_key: str
    groq_api_key: str

class SettingsUpdate(BaseModel):
    service_mode: Literal["local", "cloud"]
    deepgram_api_key: str
    groq_api_key: str
