"""Audio transcription service (Phase 3).

Supports dual-mode processing:
- Cloud Mode: uses Deepgram for fast transcription and diarization.
- Local Mode: uses WhisperX directly (small model, CPU).
  - Diarize via pyannote/speaker-diarization-3.1 (token from HF cache)
  - Align speakers to segments via assign_word_speakers (best-effort)

- Normalize to canonical TranscriptTurn[]:
    turn_id: "turn_000", "turn_001", ...
    speaker: stable label from diarization (e.g., SPEAKER_00) or fallback
    start_ms, end_ms: integer milliseconds
    text: normalized utterance text

Constraints (per plan):
- Do not persist raw audio; discard after transcription.
- Errors are raised as ValueError for the caller to map to 4xx/5xx.
- Runs asynchronously via background tasks to prevent blocking API.
"""

from __future__ import annotations

import gc
import logging
import os
import tempfile
import requests
from dataclasses import dataclass
from typing import Any

# NOTE: whisperx (and its torch stack) is imported lazily inside
# transcribe_and_diarize() so the API server can start and serve the
# text-transcript path without the audio dependencies installed.

from .models import TranscriptTurn
from .db import get_settings

log = logging.getLogger("backend.audio")

# Model / device selection (documented and verified locally):
# - Model: "small" (good balance for M1 Pro 16 GB; faster than medium on CPU)
# - Device: "cpu" (no CUDA; MPS is available but not used for stability here)
# - Compute: "int8" (quantized; matches Phase 0 verification)
WHISPER_MODEL = "small"
WHISPER_DEVICE = "cpu"
WHISPER_COMPUTE = "int8"

# Diarization model (user has accepted gated terms; token resolved from HF cache via token=True)
DIARIZE_MODEL = "pyannote/speaker-diarization-3.1"

# Conservative MVP limits (documented):
# - Max upload size: 25 MiB (covers ~10-25 min of typical speech depending on bitrate)
# - Processing is synchronous; callers should not send hour-long files.
MAX_AUDIO_BYTES = 25 * 1024 * 1024

# Allowed extensions / mimetypes (best-effort checks; do not trust client)
ALLOWED_AUDIO_EXTS = {".mp3", ".wav"}
ALLOWED_AUDIO_CTYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/x-pn-wav",
}


def _normalize_text(s: str) -> str:
    """Collapse internal whitespace and trim."""
    return " ".join((s or "").split())


def _to_ms(seconds: float) -> int:
    """Convert seconds (float) to integer milliseconds, with safe flooring."""
    if seconds is None:
        return 0
    ms = int(round(float(seconds) * 1000.0))
    return max(0, ms)


@dataclass
class _RawSegment:
    start: float
    end: float
    text: str
    speaker: str | None


def transcribe_and_diarize(audio_path: str) -> list[TranscriptTurn]:
    """Run WhisperX (transcribe + diarize) and return canonical TranscriptTurn list.

    Raises ValueError with a clear message on unrecoverable failures.
    The caller is responsible for cleaning up temp files.
    """
    if not audio_path or not os.path.exists(audio_path):
        raise ValueError("audio file not found")

    settings = get_settings()
    is_cloud = settings.get("service_mode") == "cloud"
    
    if is_cloud:
        dg_key = settings.get("deepgram_api_key", "").strip()
        if not dg_key:
            raise ValueError("Deepgram API key is not configured for cloud mode")
            
        url = "https://api.deepgram.com/v1/listen?model=nova-2&smart_format=true&diarize=true&utterances=true"
        headers = {
            "Authorization": f"Token {dg_key}"
        }
        
        try:
            with open(audio_path, "rb") as f:
                resp = requests.post(url, headers=headers, data=f, timeout=300)
        except Exception as exc:
            raise ValueError(f"transcription failed: connection to Deepgram failed - {exc}") from exc
            
        if resp.status_code != 200:
            raise ValueError(f"transcription failed: Deepgram returned {resp.status_code} - {resp.text}")
            
        data = resp.json()
        utterances = data.get("results", {}).get("utterances", [])
        
        if not utterances:
            # If no utterances, fallback to check paragraphs or just return empty
            return []
            
        turns: list[TranscriptTurn] = []
        for idx, u in enumerate(utterances):
            speaker = f"SPEAKER_{u.get('speaker', 0):02d}"
            start_ms = _to_ms(u.get("start", 0.0))
            end_ms = _to_ms(u.get("end", 0.0))
            if end_ms <= start_ms:
                end_ms = start_ms + 1000
            turns.append(
                TranscriptTurn(
                    turn_id=f"turn_{idx:03d}",
                    speaker=speaker,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    text=_normalize_text(u.get("transcript", "")),
                )
            )
        return turns

    # 0) Lazy import of the heavy audio stack (see module docstring/NOTE above).
    try:
        from whisperx.asr import load_model
        from whisperx.audio import load_audio
        from whisperx.diarize import DiarizationPipeline, assign_word_speakers
    except ImportError as exc:
        # Phrased to map to a 500 in the API layer: this is a server setup
        # problem, not a client error. See README audio setup.
        raise ValueError(
            "transcription failed: WhisperX is not installed in this environment; "
            "see README 'Local-Model Setup' for audio support"
        ) from exc

    # 1) Load audio into memory (WhisperX's load_audio returns 16 kHz mono float32 ndarray)
    try:
        audio = load_audio(audio_path)
    except Exception as exc:
        raise ValueError(f"failed to load audio: {exc}") from exc

    if audio is None or len(audio) == 0:
        raise ValueError("audio is empty or unreadable")

    duration_s = len(audio) / 16000.0

    # 2) Load ASR model (small/int8/cpu)
    model = None
    try:
        log.info("loading whisper model: %s device=%s compute=%s", WHISPER_MODEL, WHISPER_DEVICE, WHISPER_COMPUTE)
        model = load_model(
            WHISPER_MODEL,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE,
            threads=4,
        )

        # 3) Transcribe
        log.info("transcribing (duration~%.1fs)", duration_s)
        result: dict[str, Any] = model.transcribe(audio, batch_size=8)
    except Exception as exc:
        raise ValueError(f"transcription failed: {exc}") from exc
    finally:
        # Free ASR resources promptly
        if model is not None:
            try:
                del model
            except Exception:
                pass
        gc.collect()

    segments: list[dict[str, Any]] = result.get("segments", []) or []
    if not segments:
        # No speech detected; return empty list (caller may treat as 422)
        return []

    # 4) Diarize (best-effort). If this fails we still return turns with unknown speakers.
    diarize_df = None
    try:
        log.info("diarizing with %s", DIARIZE_MODEL)
        diarize_model = DiarizationPipeline(
            model_name=DIARIZE_MODEL,
            token=True,  # rely on cached HF token accepted by user
            device=WHISPER_DEVICE,
        )
        diarize_df = diarize_model(audio_path)
        # Assign speakers to words/segments (best-effort)
        result = assign_word_speakers(diarize_df, result)
        segments = result.get("segments", []) or segments
    except Exception as exc:
        # Non-fatal: proceed with speaker=None; caller will normalize to a stable label.
        log.warning("diarization failed or produced no labels: %s", exc)
    finally:
        try:
            if "diarize_model" in locals() and diarize_model is not None:
                del diarize_model
        except Exception:
            pass
        gc.collect()

    # 5) Normalize into raw segments
    raw: list[_RawSegment] = []
    for seg in segments:
        text = _normalize_text(seg.get("text", ""))
        if not text:
            continue
        spk = seg.get("speaker")
        # WhisperX may leave speaker as None if diarization didn't assign; keep as None here.
        raw.append(
            _RawSegment(
                start=float(seg.get("start", 0.0)),
                end=float(seg.get("end", 0.0)),
                text=text,
                speaker=str(spk) if spk else None,
            )
        )

    if not raw:
        return []

    # 6) Sort segments chronologically FIRST (defensive; whisper segments are
    # normally already ordered), then assign stable speaker labels and
    # deterministic turn_ids so id order always matches display order.
    raw.sort(key=lambda r: (r.start, r.end))
    turns: list[TranscriptTurn] = []
    for idx, r in enumerate(raw):
        speaker = r.speaker or "SPEAKER_00"
        start_ms = _to_ms(r.start)
        end_ms = _to_ms(r.end)
        if end_ms <= start_ms:
            # Ensure a minimal positive duration (1s) to satisfy non-empty turns
            end_ms = start_ms + 1000
        turns.append(
            TranscriptTurn(
                turn_id=f"turn_{idx:03d}",
                speaker=speaker,
                start_ms=start_ms,
                end_ms=end_ms,
                text=r.text,
            )
        )

    return turns


def allowed_audio_filename(name: str | None) -> bool:
    """Return True if filename extension is allowed (case-insensitive)."""
    if not name:
        return False
    base = name.replace("\\", "/").split("/")[-1]
    if "." not in base:
        return False
    ext = "." + base.rsplit(".", 1)[-1].lower()
    return ext in ALLOWED_AUDIO_EXTS


def allowed_audio_content_type(ct: str | None) -> bool:
    """Return True if content-type (if provided) is acceptable."""
    if not ct:
        return True  # be lenient when clients omit
    c = ct.lower().strip()
    # Some clients send charset or parameters; be tolerant
    c = c.split(";")[0].strip()
    return c in ALLOWED_AUDIO_CTYPES or c == ""  # empty handled as True above


def write_upload_to_temp(data: bytes, suffix: str) -> str:
    """Write bytes to a secure temp file and return its path.

    The caller MUST delete the file when done (success or failure).
    """
    if len(data) > MAX_AUDIO_BYTES:
        raise ValueError(f"audio exceeds {MAX_AUDIO_BYTES} bytes")

    # Use delete=False so caller controls lifetime; suffix helps tools that sniff extension.
    fd, path = tempfile.mkstemp(prefix="meet_audio_", suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        return path
    except Exception:
        # Ensure cleanup on failure to create/write
        try:
            os.unlink(path)
        except Exception:
            pass
        raise
