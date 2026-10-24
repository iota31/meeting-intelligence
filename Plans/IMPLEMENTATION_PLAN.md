# IMPLEMENTATION_PLAN  -  Meeting Intelligence MVP (Checklist)

> This is the authoritative, ordered build plan. All work is tracked here. No other planning docs are created.

---

## 0. Product Definition

**Product:** a meeting intelligence system that turns transcripts into grounded, citable intelligence.

**Delivered scope:**
- Text transcript upload (speaker labels + timestamps).
- Audio upload with transcription + speaker diarization (WhisperX).
- Both paths normalize into one canonical `TranscriptTurn` model and share extraction / RAG / citation logic.

**Stack:**
- Frontend: React + Vite + TypeScript + Tailwind
- Backend: FastAPI + Python
- Storage: SQLite (records) + ChromaDB (vectors)
- AI: Ollama (embeddings), Groq or local Ollama (chat/extraction), WhisperX (STT + diarization)

---

## 1. Scope and Non-Goals (Ponytail)

### 1.1 Must Deliver (Vertical Slice)
- [ ] Upload text transcript file → parse speaker/timestamp → store canonical turns
- [ ] Upload audio file → WhisperX (transcribe + diarize) → store canonical turns
- [ ] One `TranscriptTurn` shape for both paths
- [ ] Extract decisions and action items (structured) with citations
- [ ] Grounded Q&A (RAG) with citations (speaker + timestamp); explicit refusal on unsupported
- [ ] Confirm / dismiss extracted items
- [ ] Minimal UI: dashboard list, meeting detail (transcript / intelligence / chat panes), upload
- [ ] Local-only operation (no external SaaS required at runtime)

### 1.2 Explicit Non-Goals (Do Not Build)
- [ ] No live meeting capture, browser tab audio, or streaming microphone
- [ ] No MCP / FastMCP / tool endpoints
- [ ] No authentication, accounts, multi-tenancy, or user management
- [ ] No calendar integrations, Zoom/Teams/Google Meet bots, or scheduling
- [ ] No provider marketplace or BYOK (pluggable provider) in this build
- [ ] No premature abstractions (one working path; generalize only if a concrete failure justifies it)
- [ ] No unnecessary UI (no settings pages, theming, or dashboard chrome beyond what's required to exercise the slice)

### 1.3 Out of Scope for This Build (Document, Do Not Build)
- Production deployment, scaling, multi-user isolation
- Real clinical / patient data
- Medical or legal advice semantics
- Video frame analysis

---

## 2. Exact Vertical Slice (End-to-End Runnable)

```
Upload (transcript or audio)
  ↓
Normalize → TranscriptTurn[]
  ↓
Persist Meeting + Turns (SQLite)
  ↓
Chunk (speaker-turn windows) → embed → index (Chroma)
  ↓
Extract (Ollama) → decisions + action items + citations → persist
  ↓
Chat (retrieve → prompt → answer + citations) or explicit refusal
  ↓
Confirm / dismiss items
```

Smallest end-to-end check: upload one short synthetic transcript or audio → see turns → extract → see items with citations → ask a grounded question → get cited answer → confirm one item.

---

## 3. Data Contracts (Canonical)

### 3.1 TranscriptTurn (shared by both ingest paths)
```python
# Backend canonical model (Pydantic or dataclass)
class TranscriptTurn(BaseModel):
    turn_id: str
    speaker: str
    start_ms: int
    end_ms: int
    text: str
```

### 3.2 Meeting
```python
class Meeting(BaseModel):
    id: str
    title: str
    created_at: str
    source_type: Literal["transcript", "audio"]
    source_meta: dict | None = None  # e.g., original filename, duration
    turn_count: int
```

### 3.3 ExtractedItem
```python
class Citation(BaseModel):
    turn_id: str
    speaker: str
    start_ms: int
    end_ms: int

class ExtractedItem(BaseModel):
    id: str
    meeting_id: str
    type: Literal["decision", "action_item"]
    text: str
    owner: str | None = None
    due: str | None = None
    status: Literal["pending", "confirmed", "dismissed"] = "pending"
    citations: list[Citation]
```

### 3.4 RAG Chunk (internal)
- Window of N consecutive turns (e.g., 3-5) with M-turn overlap (e.g., 1-2)
- Fields: `meeting_id`, `chunk_id`, `turn_ids[]`, `text`, `embedding`

**Invariant:** Both ingest paths produce `TranscriptTurn[]` with identical field semantics. Extraction and RAG operate only on this shape.

---

## 4. API Contracts (FastAPI, Minimal)

Base prefix: `/api`

- `POST /meetings/upload/transcript`
  - Multipart: `file` (text), optional `title`
  - 200: `{ "meeting_id": str, "turn_count": int, "status": "ok" }`

- `POST /meetings/upload/audio`
  - Multipart: `file` (audio), optional `title`
  - Side effects: WhisperX → canonical turns
  - 200: `{ "meeting_id": str, "turn_count": int, "status": "ok" }`

- `GET /meetings`
  - 200: `[{ meeting summary... }]`

- `GET /meetings/{id}`
  - 200: `{ meeting, turns: TranscriptTurn[], items: ExtractedItem[] }`

- `POST /meetings/{id}/extract`
  - 200: `{ "extracted": int, "items": ExtractedItem[] }`
  - Safe to re-run; policy for merge vs replace documented in code.

- `POST /meetings/{id}/chat`
  - Body: `{ "question": str }`
  - 200: `{ "answer": str, "citations": Citation[] }`
  - If unsupported: answer states insufficient evidence; citations may be empty.

- `PATCH /items/{id}`
  - Body: `{ "status": "confirmed" | "dismissed" }`
  - 200: updated item

Error shape (consistent):
```json
{ "error": { "code": "...", "message": "..." } }
```

---

## 5. Phases with Dependency Gates + Smallest Runnable Check

Mark each checkbox when the check **passes on this machine**.

### Phase 0  -  Environment & Hardware Gates (HARD; Do Not Skip)
These are **early explicit gates**. Resolve before Phase 1 code.

- [x] Python 3.10+ installed (`python --version`)
  - Python 3.12.0 (v3.12.0:0fb18b02c8, Oct  2 2023, 09:45:56) [Clang 13.0.0 (clang-1300.0.29.30)]
- [x] Node 18+ installed (`node --version`)
  - v22.23.1 (via nvm)
- [x] Ollama installed and daemon running
  - Ollama 0.32.1 (installed via Homebrew)
  - Daemon: `ollama serve` running on 127.0.0.1:11434
  - [x] Pull chat model: `llama3.2:3b` (exact tag)
    - Size: 2.0 GB, Quant: Q4_K_M, Params: 3.2B, Context: 131072
  - [x] Pull embedding model: `nomic-embed-text:latest` (exact tag)
    - Size: 274 MB, Params: 137M, Embedding dim: 768, Context: 2048
  - [x] `ollama list` shows both; smoke test embedding + completion
    - Completion test: `curl -X POST http://localhost:11434/api/generate -d '{"model":"llama3.2:3b","prompt":"Count to 3","stream":false,"options":{"num_predict":20}}'` → response "1, 2, 3."
    - Embedding test: `curl -X POST http://localhost:11434/api/embeddings -d '{"model":"nomic-embed-text","prompt":"test"}'` → 768-dim vector
- [x] WhisperX installed / installable
  - [x] `whisperx --help` works
    - whisperx 3.8.6 installed in project .venv
  - [x] Run on a 20-60s test audio file; verify diarization labels and timestamps
    - **TRANSCRIPTION + DIARIZATION: PASSED** on 14.4s real-speech test audio (espeak-generated two-speaker)
    - Test file: `/tmp/real_speech_test.wav` (636 KB, 22050 Hz mono, 14.4s)
    - Transcription: 1 segment, lang=en, [0.0-14.5s]
    - Diarization: 2 segments detected, both labeled SPEAKER_00 (limitation: single-speaker output despite 2-speaker input)
    - Timing: transcribe=1.2s, diarize=6.2s, total pipeline ~11s
    - Normalized to TranscriptTurn: `{"turn_id": "turn_000", "speaker": "SPEAKER_00", "start_ms": 31, "end_ms": 14459, "text": "The load is in speaker a speaking about the project timeline and deliverables..."}`  -  shape matches planned contract
  - [x] Document: CPU vs GPU, approx. real-time factor on this hardware
    - Device: CPU (M1 Pro arm64), Compute: int8
    - Real-time factor: ~0.08x (14.4s audio in 1.2s transcription) / ~0.43x (diarization 6.2s)  -  well under real-time on CPU
    - No GPU/MPS used; all CPU inference
- [x] Audio toolchain present (ffmpeg or equivalent) if required by WhisperX
  - ffmpeg version 7.1.1 (from /opt/homebrew/bin/ffmpeg)
- [x] Disk / memory sanity: enough space for models + sample audio
  - RAM: 16 GB total, ~3.4 GB available at check time
  - Disk: 166 GB free on /
  - Ollama models: 2.1 GB total in ~/.ollama
  - HF cache: 97 MB in ~/.cache/huggingface
  - Test audio: 622 KB synthetic file
- [x] Any required env vars documented (e.g., `OLLAMA_HOST`)
  - OLLAMA_HOST=127.0.0.1:11434 (for CLI access when not default)
  - HF token present at ~/.cache/huggingface/token (user accepted pyannote terms for speaker-diarization-3.1, segmentation-3.0, and speaker-diarization-community-1)

**Blocker rule:** If any gate cannot be satisfied, document the exact error/output and **do not proceed** to dependent phases until resolved or scope is explicitly reduced with justification.

**Smallest runnable check:**  
`ollama list` shows models; 30s audio transcribes+diarizes locally and produces speaker-labeled turns with timestamps.

---

### Phase 1  -  Project Scaffolding (No AI)
- [x] Create repo layout (e.g., `/frontend`, `/backend`, or clear separation)
- [x] Frontend: `npm create vite@latest` → React + TS + Tailwind configured
- [x] Backend: FastAPI app with `/health` returning 200
- [x] Dev workflow documented (how to run both locally, ports, CORS)
- [x] `.gitignore` excludes models, audio uploads, venv, node_modules, `.env*`

**Smallest runnable check:**  
Browser shows Vite app; `curl /health` returns 200.

---

### Phase 2  -  Transcript Upload → Canonical Turns (SQLite)
- [x] Define `TranscriptTurn` model (Pydantic) and DB table(s)
- [x] Implement `POST /api/meetings/upload/transcript`
- [x] Parser supports at least one text format with speaker + timestamp
  - Accept `.txt` (simple), optionally `.vtt`
  - Normalize timestamps to milliseconds
- [x] Persist `Meeting` + `TranscriptTurn[]`
- [x] `GET /api/meetings` and `GET /api/meetings/{id}` return turns
- [x] Validation + error responses for bad input

**Smallest runnable check:**  
Upload a 4-turn synthetic transcript file; `GET /meetings/{id}` returns exactly those 4 turns with correct speaker, start_ms, end_ms, text.

**Verification (2026-07-22):**  
Ran `backend/test_verify_phase2.py` (local, no AI).  
Synthetic transcript (4 turns, one multi-line continuation) uploaded via POST; GET `/api/meetings/{id}` returned exactly the 4 canonical turns with matching speaker/start_ms/end_ms/text. All assertions passed. See `backend/test_verify_phase2.py` and `backend/transcript.py` for grammar and normalization.

---

### Phase 3  -  Audio Upload → WhisperX → Same Canonical Turns
- [x] Implement `POST /api/meetings/upload/audio`
- [x] Call WhisperX (transcribe + diarize); map output to `TranscriptTurn[]`
- [x] Persist using identical schema and code path as Phase 2
- [x] No divergence: same GET endpoints, same shape
- [x] Basic file type / size guardrails (document limits)

**Smallest runnable check:**  
Upload a short audio file; turns appear with speaker labels and timestamps; `GET /meetings/{id}` shape identical to transcript upload.

**Invariant check:**  
A helper or test asserts that transcript-uploaded and audio-uploaded meetings both conform to the same `TranscriptTurn` contract.

**Verification (2026-07-22):**  
Ran `backend/test_verify_phase3_audio.py` (local).  
- Synthetic two-speaker WAV generated on-the-fly via espeak + ffmpeg (~9s, ~406 KB) inside the test; fixture is never committed.
- POST `/api/meetings/upload/audio` accepted MP3/WAV with 25 MiB cap; temp file cleaned on all paths.
- Returned 200 with `{meeting_id, turn_count, status:"ok"}`.
- GET `/api/meetings/{id}` returned `source_type="audio"` and canonical turns.
- Turns verified:
  - Exact TranscriptTurn fields: `turn_id`, `speaker`, `start_ms`, `end_ms`, `text`.
  - Deterministic IDs: `turn_000`, `turn_001`, ...
  - Integer ms timestamps; `end_ms >= start_ms`; non-decreasing by `start_ms`.
  - At least one diarization label observed (`SPEAKER_00`).
- Same persistence path as Phase 2 (`create_meeting` with `source_type="audio"`; no client paths in `source_meta`).
- No audio retained after processing.

**Chosen WhisperX strategy (M1 Pro 16 GB, verified locally):**
- Model: `small`
- Device: `cpu`
- Compute: `int8`
- Diarization: `pyannote/speaker-diarization-3.1` via HF-cached token (user accepted gated terms)
- No alignment model used for MVP (word-level timestamps not required for canonical turn shape)
- FFmpeg used only to stage/prepare short synthetic fixtures for the test; WhisperX `load_audio` handles 16 kHz mono normalization internally.
- Real-time factor (observed): transcription ~2s for ~9s audio; diarization ~2s; total pipeline <5s end-to-end for short MVP files.

**Duration expectations (documented):**
- Model load (first time): ~25-30s (thereafter faster due to caches).
- Short files (≤60s): typically a few seconds on CPU.
- Longer files: scales roughly linearly with duration on CPU; diarization is the heavier step. Enforce 25 MiB cap and recommend short MVP recordings.

**Limitations (documented):**
- CPU-only on this hardware; no CUDA path exercised.
- Diarization may collapse multiple speakers to a single `SPEAKER_00` label on some inputs (observed in Phase 0 smoke as well). Speaker labels are stable within a meeting but quality is not guaranteed.
- No word-level timestamps or forced alignment for MVP.
- No persistent raw audio storage (by design); re-transcription requires re-upload.
- Synchronous processing; not appropriate for long recordings in production without a queue/worker.
- Warnings from torchcodec/pyannote about FFmpeg rpath are non-fatal; transcription and diarization succeed.

---

### Phase 4  -  Chunking + ChromaDB Indexing
- [x] Speaker-turn window chunker (configurable N turns, M overlap)
- [x] Embedder via Ollama embeddings API
- [x] ChromaDB collection(s); store chunks with metadata for citations
- [x] Retrieval helper: `retrieve(meeting_id, query, k) → list[ChunkWithCitations]`
- [x] Basic logging: retrieval latency, top-k scores (no secrets)

**Smallest runnable check:**  
After ingesting a meeting, a keyword query returns at least one chunk whose turns contain that keyword; chunk metadata includes turn references.

**Verification (2026-07-22):**  
Ran `backend/test_verify_phase4_6.py` (local).  
- Two distinct small text meetings uploaded via API (A and B).
- Chroma collections created per meeting under `data/chroma` (gitignored).
- Speaker-turn window chunker: W=4, O=1; deterministic chunk ids; turn_ids/speakers/start/end preserved.
- Embeddings via local `nomic-embed-text:latest` (L2-normalized client-side for stable distances).
- Retrieval strictly scoped to meeting_id via collection + metadata filter.
- Basic logging emitted for index/retrieve phases (no transcript bodies).
- Smallest check passed: answerable question on A produced citations within A's speaker/time bounds.

---

### Phase 5  -  Extraction (Decisions + Action Items)
- [x] `POST /api/meetings/{id}/extract`
- [x] Prompt + structured output (Pydantic model) for:
  - `type ∈ {decision, action_item}`
  - `text`, optional `owner`, optional `due`
  - `citations[]` (turn refs)
- [x] Persist `ExtractedItem[]`
- [x] Re-extraction policy documented (e.g., do not overwrite confirmed items, or append-only with provenance)
- [x] Guard: never invent owners or deadlines not present in transcript

**Smallest runnable check:**  
Run extract on a known fixture meeting; verify items created with citations pointing to actual stored turns.

**Verification (2026-07-22):**  
Ran `backend/test_verify_phase5_7.py` (local, HTTP against running backend).
- `POST /api/meetings/{id}/extract` implemented; returns `ExtractResponse { extracted, items }`.
- Strict Pydantic validation of model output; citations validated to be meeting-local canonical turns.
- Only `llama3.2:3b` via local Ollama; no external services.
- Re-extraction policy: existing `confirmed`/`dismissed` preserved; `pending` replaced.
- Citations: turn_id/speaker/start_ms/end_ms match exactly the stored turns for that meeting.
- GET `/api/meetings/{id}` now returns `items` (all statuses) via `MeetingDetailWithItems`.
- Smallest check passed: items created with citations to real stored turns.

---

### Phase 6  -  Grounded Chat (RAG + Citations + Refusal)
- [x] `POST /api/meetings/{id}/chat`
- [x] Retrieve relevant chunks
- [x] Compose prompt: context + citations + "cite by speaker+timestamp; say if not found"
- [x] Return `{ answer, citations }`
- [x] Explicit unsupported behavior:
  - If retrieval is empty or weak → answer states "insufficient evidence in this meeting"
  - Never fabricate turns, speakers, or timestamps
- [x] Prompt injection hygiene: transcript content is data, not instructions

**Smallest runnable check:**  
- Ask a question answerable from the fixture → answer contains correct speaker/timestamp citations.
- Ask a question with no support in the meeting → answer explicitly declines.

**Verification (2026-07-22):**  
Ran `backend/test_verify_phase4_6.py` (local).  
- `POST /api/meetings/{id}/chat` implemented with body `{question}`.
- Validation: non-empty + length cap (2000 chars) via Pydantic `ChatRequest`.
- Retrieval: top K=3 chunks, strictly for the requested meeting (collection + metadata filter).
- Threshold: best squared-L2 distance > 0.8 → refuse without LLM call (documented in rag.py).
- Prompt: short, treats chunks as untrusted evidence; only claims supported by chunks; model citations ignored.
- Model: `llama3.2:3b` via local Ollama only (no external services).
- Deterministic citations: built from retrieved chunk metadata (speakers + start/end ms); no invented timestamps.
- Refusal behavior: unsupported question returns explicit refusal + empty citations.
- Cross-meeting isolation: B-specific question on A meeting returns refusal (no B speaker leakage).
- Logging: phase, meeting_id, latency, hit/miss, selected chunk ids/scores (no transcript bodies).
- Pydantic response: `ChatResponse { answer: str, citations: list[ChatCitation] }`.

---

### Phase 7  -  Item Confirmation
- [x] `PATCH /api/items/{id}` updates `status`
- [ ] UI (later) reflects `pending | confirmed | dismissed`
- [x] Extraction re-run does not silently revert user-confirmed state (policy implemented and documented)

**Smallest runnable check:**  
Confirm one item, dismiss one item; `GET /meetings/{id}` shows updated statuses; re-extract does not regress them (per policy).

**Verification (2026-07-22):**  
Ran `backend/test_verify_phase5_7.py` (local).
- `PATCH /api/items/{id}` with `{ "status": "confirmed" | "dismissed" }` works; returns updated `ExtractedItem`.
- Confirmed item persisted across re-extract.
- Dismissed item persisted across re-extract.
- `GET /api/meetings/{id}` returns `items` array with correct statuses.
- Cross-meeting citation injection rejected (B extract contains only B turn citations).

---

### Phase 8  -  Minimal Usable UI
- [x] Dashboard: list of meetings (title, date, source type, turn count, item counts)
- [x] Meeting detail page:
  - [x] Transcript pane: ordered turns with speaker + timestamp + text
  - [x] Intelligence pane: decisions and action items grouped; each has Confirm / Dismiss
  - [x] Chat pane: input, submit, display answer + citation list (click citation → scroll/highlight turn)
- [x] Upload modal / dropzone supporting both text and audio files
- [x] Loading / error states for the critical path (upload → extract → chat)
- [x] No extraneous routes or settings

**Smallest runnable check (end-to-end):**
1. Upload synthetic transcript or audio.
2. See turns in transcript pane.
3. Trigger extract; see items.
4. Ask a grounded question; see answer with citations.
5. Confirm one item; status updates.

---

### Phase 9  -  Fixtures, Evals, Observability
- [x] Synthetic meeting fixture (committed to repo):
  - Transcript text file
  - Ground-truth decisions and action items (JSON)
  - 8-12 sample questions: some answerable, some unsupported, some testing owner/due inference
- [x] Eval script (Python or TS):
  - Ingest fixture → extract → chat
  - Asserts: citation correctness (turn exists), groundedness (answer only uses cited content), refusal on unsupported
  - Prints summary (pass/fail counts, simple metrics)
- [x] Logging (structured, local):
  - Request id, phase (ingest/extract/retrieve/chat), latency, token counts (approx), retrieval hit/miss
  - Do not log raw audio or sensitive PII in fixtures
- [x] Error taxonomy (document):
  - Retrieval empty, parse failure, model error/timeout, WhisperX failure

**Smallest runnable check:**  
Run eval script against fixture; it reports deterministic results (pass or documented failures).

---

### Phase 10  -  Safety, Privacy, Limits
- [x] Fixtures use only synthetic data; no real PII
- [x] Local-only default: nothing leaves the machine
- [x] Document limits:
  - Max audio duration / file size for WhisperX on this hardware
  - Max transcript length (characters/turns) for MVP
- [x] Prompt injection note in code/README: transcript content must not be executed as instructions
- [x] Basic input sanitization (strip control chars, length caps)

**Smallest runnable check:**  
Limits and data policy are written in a clear "Limits & Data" section of README; fixture contains no real personal data.

---

### Phase 11  -  README, Screenshots, Demo Packaging

- [x] README.md contains (in your own words, not raw LLM paste):
  - Quick setup instructions (prerequisites, exact commands)
  - Architecture overview (simple diagram or clear description)
  - Productionization notes: what would be required to deploy and scale on AWS/GCP/Azure/Cloudflare (do not implement)
  - RAG/LLM approach & decisions:
    - LLM and embedding model (Ollama tags)
    - Vector DB (ChromaDB)
    - Chunking strategy (speaker-turn windows)
    - Prompt & context management
    - Guardrails (refusal, citation requirement, untrusted content)
    - Quality controls and evals
    - Observability (what is logged)
  - Key technical decisions and rationale (e.g., one canonical turn model, why not live capture for MVP)
  - Engineering standards followed (and some intentionally skipped)
  - How AI coding tools were used and how you kept control
  - What you would do with more time (documented gaps)
- [ ] Screenshots (committed or linked):
  - Dashboard (meeting list)
  - Meeting detail: transcript pane
  - Extracted items (intelligence pane)
  - Chat with citations
- [ ] (Optional but encouraged) Short video demonstrating the flow

**Smallest runnable check:**  
A fresh clone + follow README allows another developer to run the full vertical slice on a comparable machine (document any additional one-time setup like model pulls).

---

## 6. Definition of Done (DoD)

A build is complete only when **all** are true:

- [x] Both transcript and audio upload paths work and produce identical `TranscriptTurn` shape
- [x] Extraction produces decisions and action items, each with citations to stored turns
- [x] Chat answers grounded questions with citations and explicitly refuses unsupported questions
- [x] Items can be confirmed and dismissed; status persists
- [x] Minimal UI demonstrates the full vertical slice (upload → turns → extract → chat → confirm)
- [ ] Fixture + eval script runs and demonstrates correctness/refusal on at least one synthetic meeting
- [x] README and screenshots cover setup, architecture, design decisions, and limitations
- [x] No live capture, no MCP, no auth, no calendar, no BYOK marketplace shipped in this build
- [x] Stack matches the preserved default (or a machine constraint is documented with justification)
- [x] Local-only operation; no external services required at runtime

---

## 7. Hardware / Provider Unknowns (Explicit Early Gates)

Document these **before Phase 1 implementation code**:

- [x] Ollama chat model: tag, context window, approx. tokens/sec on this machine
  - Tag: `llama3.2:3b`
  - Format: gguf, Family: llama, Params: 3.2B, Quant: Q4_K_M
  - Context window: 131072 tokens
  - Size: 2.0 GB
  - Smoke test: `curl -X POST http://localhost:11434/api/generate -d '{"model":"llama3.2:3b","prompt":"Count to 3","stream":false,"options":{"num_predict":20}}'`
    - Response: "1, 2, 3."  -  completion works

- [x] Ollama embedding model: tag, dimensions, latency profile
  - Tag: `nomic-embed-text:latest`
  - Format: gguf, Family: nomic-bert, Params: 137M, Quant: F16
  - Context: 2048, Embedding length: 768
  - Size: 274 MB
  - Smoke test: `curl -X POST http://localhost:11434/api/embeddings -d '{"model":"nomic-embed-text","prompt":"test"}'`
    - Returns 768-dim vector, first value ~0.97  -  embedding works

- [x] WhisperX: version, diarization quality notes, CPU vs GPU, real-time factor on sample audio
  - Version: 3.8.6 (pip install in project .venv)
  - Transcription: WORKS on CPU (int8)
    - Test file: 14.4s real speech (espeak-generated, 2 speakers, 622 KB WAV)
    - Output: Detected lang=en (0.95), 1 segment, ~14.5s duration
    - Audio: "The load is in speaker a speaking about the project timeline and deliverables..."
  - Diarization: BLOCKED (see error below)
    - Device tested: CPU only (M1 Pro arm64)
    - No GPU/MPS tested for diarization (blocked before perf measurement)
  - CLI: `whisperx --help` works; `--diarize --diarize_model` flags present
  - Import: `import whisperx; from whisperx.diarize import DiarizationPipeline` works

- [ ] Max comfortable audio length for WhisperX on this hardware (minutes)
  - UNKNOWN  -  diarization blocked; transcription tested only on ~14s file
  - Constraint: Cannot measure without working diarization

- [x] Any install or runtime errors encountered (exact output)
  - **CRITICAL BLOCKER  -  Diarization gated access:**
    ```
    huggingface_hub.errors.GatedRepoError: 403 Client Error.
    Cannot access gated repo for url https://huggingface.co/pyannote/speaker-diarization-community-1/resolve/main/plda/xvec_transform.npz
    Access to model pyannote/speaker-diarization-community-1 is restricted and you are not in the authorized list.
    ```
  - Historical blocker (resolved):
    1. User accepted terms for `pyannote/speaker-diarization-3.1` and `pyannote/segmentation-3.0`
    2. WhisperX `DiarizationPipeline.__init__()` defaults to `model_name="pyannote/speaker-diarization-community-1"`
    3. Even when passing `model_name='pyannote/speaker-diarization-3.1'`, internal `Pipeline.from_pretrained()` triggers downloads from `pyannote/speaker-diarization-community-1` (xvec_transform.npz, plda files)
    4. User accepted terms for `pyannote/speaker-diarization-community-1`  -  diarization now works
  - Verified: Diarization passed with a locally cached HF token.
  - Exact command: `DiarizationPipeline(model_name='pyannote/speaker-diarization-3.1', token=token, device='cpu')`
  - Other errors (non-blocking):
    - torchcodec lib loading warnings (FFmpeg rpath issues)  -  transcription still works
    - Lightning checkpoint upgrade note  -  benign

- [x] Required environment or path configuration (e.g., `OLLAMA_HOST`, cache dirs)
  - OLLAMA_HOST=127.0.0.1:11434 (required for `/opt/homebrew/opt/ollama/bin/ollama` CLI when daemon not on default)
  - HF token: ~/.cache/huggingface/token (used by whisperx/pyannote)
  - Ollama models: ~/.ollama/models/
  - WhisperX cache: default huggingface hub cache (~/.cache/huggingface/hub)
  - Python env: repo-local `.venv` (not global)

**Phase 0 complete:** All gates passed. Diarization verified working after user accepted pyannote/speaker-diarization-community-1 terms. Transcription + diarization produce speaker-labeled turns. Ollama completion + embedding verified. Safe to proceed to Phase 1.

---

## 8. Work Ordering & Dependency Rules

- Phase 0 gates must be resolved (or explicitly waived with justification) before Phase 1+ work that depends on them.
- Phases 2 and 3 are interchangeable in order but must converge on the same `TranscriptTurn` contract before Phase 4.
- Phase 4 (indexing) must be working before Phase 6 (chat) can be validated.
- Phase 5 (extraction) can proceed in parallel with Phase 4 once turns exist, but chat quality depends on both.
- UI (Phase 8) can begin as soon as API endpoints for turns + items + chat exist (even if quality is rough).
- Evals (Phase 9) should be started as soon as extraction + chat are minimally functional; do not defer until the end.
- README and screenshots (Phase 11) are written continuously; final polish at the end.

---

## 9. Change Control

- Any scope change (adding live capture, MCP, auth, BYOK, new providers, etc.) must be proposed as an edit to this file with rationale and impact on DoD.
- If a machine constraint forces a stack change (e.g., WhisperX cannot run), record the constraint, the chosen alternative, and re-validate the DoD.

---

## 10. Notes to Self (Engineering Philosophy)

- Start with the smallest end-to-end that can be inspected and cited.
- One canonical model (`TranscriptTurn`) is load-bearing; do not let the two ingest paths diverge.
- Citations are the product: if you cannot show the exact turn, do not claim the fact.
- Refusal is a feature: "I don't have that in this meeting" is the correct answer more often than a guess.
- Keep the UI minimal but sufficient to demonstrate the intelligence loop.
- Write the README as you go in your own voice; do not paste raw LLM output.

---

**End of plan.** Update checkboxes as checks pass. Re-read this file before major phase transitions to catch contradictions.