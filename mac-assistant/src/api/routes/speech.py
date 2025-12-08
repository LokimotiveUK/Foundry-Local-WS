"""Speech-to-text API routes using Whisper."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from src.speech.transcriber import (
    WhisperTranscriber,
    get_transcriber,
    TranscriptionResult,
    WHISPER_MODELS,
    DEFAULT_MODEL,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/speech", tags=["speech"])


class TranscribeRequest(BaseModel):
    """Request model for transcription settings."""

    language: str | None = None
    task: str = "transcribe"
    beam_size: int = 5
    vad_filter: bool = True


class TranscriptionResponse(BaseModel):
    """Response model for transcription."""

    text: str
    language: str
    language_probability: float
    duration: float
    processing_time: float
    words_per_minute: float
    segments: list[dict[str, Any]] | None = None


class ModelInfo(BaseModel):
    """Information about the Whisper model."""

    model_size: str
    device: str
    compute_type: str
    is_initialized: bool
    model_info: dict[str, str]


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    file: UploadFile = File(..., description="Audio file to transcribe"),
    language: str | None = Form(None, description="Language code (e.g., 'en', 'es'). Auto-detect if not specified."),
    task: str = Form("transcribe", description="'transcribe' or 'translate' (to English)"),
    include_segments: bool = Form(False, description="Include segment-level timestamps"),
    transcriber: WhisperTranscriber = Depends(get_transcriber),
) -> TranscriptionResponse:
    """Transcribe an uploaded audio file to text.

    Supports common audio formats: WAV, MP3, M4A, FLAC, OGG, WEBM.

    Args:
        file: Audio file to transcribe.
        language: Optional language code for faster processing.
        task: 'transcribe' keeps original language, 'translate' converts to English.
        include_segments: Whether to include segment-level timestamps.

    Returns:
        Transcription result with text and metadata.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    # Validate file type
    allowed_extensions = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm", ".mp4"}
    file_ext = Path(file.filename).suffix.lower()

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio format: {file_ext}. Supported: {', '.join(allowed_extensions)}",
        )

    # Save to temp file
    with tempfile.NamedTemporaryFile(suffix=file_ext, delete=False) as temp_file:
        temp_path = Path(temp_file.name)
        content = await file.read()
        temp_file.write(content)

    try:
        # Initialize transcriber if needed
        if not transcriber.is_initialized:
            transcriber.initialize()

        # Transcribe
        result = transcriber.transcribe(
            audio_path=temp_path,
            language=language,
            task=task,
            vad_filter=True,
        )

        return TranscriptionResponse(
            text=result.text,
            language=result.language,
            language_probability=result.language_probability,
            duration=result.duration,
            processing_time=result.processing_time,
            words_per_minute=result.words_per_minute,
            segments=[s.__dict__ for s in result.segments] if include_segments else None,
        )

    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

    finally:
        # Cleanup temp file
        temp_path.unlink(missing_ok=True)


@router.post("/transcribe/base64", response_model=TranscriptionResponse)
async def transcribe_base64(
    audio_base64: str = Form(..., description="Base64-encoded audio data"),
    filename: str = Form("audio.wav", description="Original filename for format detection"),
    language: str | None = Form(None),
    task: str = Form("transcribe"),
    include_segments: bool = Form(False),
    transcriber: WhisperTranscriber = Depends(get_transcriber),
) -> TranscriptionResponse:
    """Transcribe base64-encoded audio data.

    Useful for web clients that capture audio as base64.
    """
    import base64

    try:
        audio_bytes = base64.b64decode(audio_base64)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid base64 data: {e}")

    file_ext = Path(filename).suffix.lower() or ".wav"

    with tempfile.NamedTemporaryFile(suffix=file_ext, delete=False) as temp_file:
        temp_path = Path(temp_file.name)
        temp_file.write(audio_bytes)

    try:
        if not transcriber.is_initialized:
            transcriber.initialize()

        result = transcriber.transcribe(
            audio_path=temp_path,
            language=language,
            task=task,
            vad_filter=True,
        )

        return TranscriptionResponse(
            text=result.text,
            language=result.language,
            language_probability=result.language_probability,
            duration=result.duration,
            processing_time=result.processing_time,
            words_per_minute=result.words_per_minute,
            segments=[s.__dict__ for s in result.segments] if include_segments else None,
        )

    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

    finally:
        temp_path.unlink(missing_ok=True)


@router.get("/models", response_model=dict[str, dict])
async def list_whisper_models() -> dict[str, dict]:
    """List available Whisper models and their characteristics.

    Returns information about model sizes, speeds, and quality levels.
    """
    return {
        "models": WHISPER_MODELS,
        "default": DEFAULT_MODEL,
        "recommended": {
            "fast": "tiny",
            "balanced": "base",
            "quality": "small",
            "best": "large-v3",
        },
    }


@router.get("/status", response_model=ModelInfo)
async def get_transcriber_status(
    transcriber: WhisperTranscriber = Depends(get_transcriber),
) -> ModelInfo:
    """Get current transcriber status and model information."""
    info = transcriber.get_model_info()
    return ModelInfo(**info)


@router.post("/initialize")
async def initialize_transcriber(
    model_size: str = Form(DEFAULT_MODEL, description="Whisper model size to load"),
    transcriber: WhisperTranscriber = Depends(get_transcriber),
) -> dict[str, Any]:
    """Pre-initialize the Whisper model.

    Call this to load the model before first transcription,
    avoiding delay on first use.
    """
    if model_size not in WHISPER_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown model size: {model_size}. Available: {list(WHISPER_MODELS.keys())}",
        )

    if transcriber.is_initialized and transcriber.model_size == model_size:
        return {
            "status": "already_initialized",
            "model": model_size,
        }

    try:
        # Create new transcriber with requested model
        global _transcriber
        from src.speech.transcriber import _transcriber

        new_transcriber = WhisperTranscriber(model_size=model_size)
        new_transcriber.initialize()

        # Update global singleton (not ideal but works for now)
        import src.speech.transcriber as speech_module
        speech_module._transcriber = new_transcriber

        return {
            "status": "initialized",
            "model": model_size,
            "info": new_transcriber.get_model_info(),
        }

    except Exception as e:
        logger.error(f"Failed to initialize Whisper: {e}")
        raise HTTPException(status_code=500, detail=f"Initialization failed: {str(e)}")


@router.get("/languages")
async def list_supported_languages() -> dict[str, list[str]]:
    """List languages supported by Whisper.

    Whisper supports 99 languages. Common ones listed here.
    """
    return {
        "common": [
            "en",  # English
            "es",  # Spanish
            "fr",  # French
            "de",  # German
            "it",  # Italian
            "pt",  # Portuguese
            "ru",  # Russian
            "zh",  # Chinese
            "ja",  # Japanese
            "ko",  # Korean
            "ar",  # Arabic
            "hi",  # Hindi
            "nl",  # Dutch
            "pl",  # Polish
            "tr",  # Turkish
            "vi",  # Vietnamese
            "th",  # Thai
            "id",  # Indonesian
        ],
        "note": "Whisper auto-detects language if not specified. Pass language code for faster processing.",
    }
