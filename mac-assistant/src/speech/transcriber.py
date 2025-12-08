"""Whisper-based speech-to-text transcription service."""

from __future__ import annotations

import io
import logging
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, Iterator

import numpy as np
import soundfile as sf

logger = logging.getLogger(__name__)

# Whisper model sizes and their characteristics
WHISPER_MODELS = {
    "tiny": {"size": "~75MB", "speed": "fastest", "quality": "lowest"},
    "base": {"size": "~150MB", "speed": "fast", "quality": "good"},
    "small": {"size": "~500MB", "speed": "medium", "quality": "better"},
    "medium": {"size": "~1.5GB", "speed": "slow", "quality": "high"},
    "large-v3": {"size": "~3GB", "speed": "slowest", "quality": "best"},
}

# Default model - good balance for local use
DEFAULT_MODEL = "base"


@dataclass
class TranscriptionSegment:
    """A segment of transcribed audio."""

    text: str
    start: float
    end: float
    confidence: float = 0.0


@dataclass
class TranscriptionResult:
    """Result of a transcription operation."""

    text: str
    segments: list[TranscriptionSegment] = field(default_factory=list)
    language: str = "en"
    language_probability: float = 0.0
    duration: float = 0.0
    processing_time: float = 0.0

    @property
    def words_per_minute(self) -> float:
        """Calculate speaking rate."""
        if self.duration <= 0:
            return 0.0
        word_count = len(self.text.split())
        return (word_count / self.duration) * 60

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "text": self.text,
            "segments": [
                {
                    "text": s.text,
                    "start": s.start,
                    "end": s.end,
                    "confidence": s.confidence,
                }
                for s in self.segments
            ],
            "language": self.language,
            "language_probability": self.language_probability,
            "duration": self.duration,
            "processing_time": self.processing_time,
            "words_per_minute": self.words_per_minute,
        }


class WhisperTranscriber:
    """Speech-to-text transcription using faster-whisper.

    Uses OpenAI's Whisper model running locally via faster-whisper,
    which is optimized for CPU/GPU inference.
    """

    def __init__(
        self,
        model_size: str = DEFAULT_MODEL,
        device: str = "auto",
        compute_type: str = "auto",
    ):
        """Initialize the transcriber.

        Args:
            model_size: Whisper model size (tiny, base, small, medium, large-v3).
            device: Device to run on ('cpu', 'cuda', 'auto').
            compute_type: Compute precision ('int8', 'float16', 'float32', 'auto').
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None
        self._is_initialized = False

    @property
    def is_initialized(self) -> bool:
        """Check if model is loaded."""
        return self._is_initialized

    def initialize(self) -> None:
        """Load the Whisper model.

        This is called lazily on first transcription or can be called
        explicitly to pre-load the model.
        """
        if self._is_initialized:
            return

        try:
            from faster_whisper import WhisperModel

            logger.info(f"Loading Whisper model: {self.model_size}")
            start_time = time.time()

            # Determine device and compute type
            device = self.device
            compute_type = self.compute_type

            if device == "auto":
                # On macOS, use CPU with int8 for best compatibility
                # faster-whisper doesn't support MPS directly
                device = "cpu"

            if compute_type == "auto":
                compute_type = "int8" if device == "cpu" else "float16"

            self._model = WhisperModel(
                self.model_size,
                device=device,
                compute_type=compute_type,
            )

            load_time = time.time() - start_time
            self._is_initialized = True
            logger.info(f"Whisper model loaded in {load_time:.2f}s")

        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            raise RuntimeError(f"Whisper initialization failed: {e}") from e

    def transcribe(
        self,
        audio_path: str | Path,
        language: str | None = None,
        task: str = "transcribe",
        beam_size: int = 5,
        vad_filter: bool = True,
        word_timestamps: bool = False,
    ) -> TranscriptionResult:
        """Transcribe an audio file.

        Args:
            audio_path: Path to audio file (WAV, MP3, etc.).
            language: Language code (e.g., 'en', 'es'). None for auto-detect.
            task: 'transcribe' or 'translate' (to English).
            beam_size: Beam size for decoding (higher = better but slower).
            vad_filter: Apply voice activity detection to filter silence.
            word_timestamps: Include word-level timestamps.

        Returns:
            TranscriptionResult with text and metadata.
        """
        if not self._is_initialized:
            self.initialize()

        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        logger.info(f"Transcribing: {audio_path.name}")
        start_time = time.time()

        try:
            segments_iter, info = self._model.transcribe(
                str(audio_path),
                language=language,
                task=task,
                beam_size=beam_size,
                vad_filter=vad_filter,
                word_timestamps=word_timestamps,
            )

            # Collect segments
            segments = []
            full_text_parts = []

            for segment in segments_iter:
                segments.append(
                    TranscriptionSegment(
                        text=segment.text.strip(),
                        start=segment.start,
                        end=segment.end,
                        confidence=segment.avg_logprob if hasattr(segment, "avg_logprob") else 0.0,
                    )
                )
                full_text_parts.append(segment.text.strip())

            processing_time = time.time() - start_time
            full_text = " ".join(full_text_parts)

            result = TranscriptionResult(
                text=full_text,
                segments=segments,
                language=info.language,
                language_probability=info.language_probability,
                duration=info.duration,
                processing_time=processing_time,
            )

            logger.info(
                f"Transcription complete: {len(full_text)} chars, "
                f"{info.duration:.1f}s audio in {processing_time:.2f}s"
            )

            return result

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise RuntimeError(f"Transcription failed: {e}") from e

    def transcribe_bytes(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
        **kwargs,
    ) -> TranscriptionResult:
        """Transcribe audio from bytes.

        Args:
            audio_data: Raw audio bytes (WAV format preferred).
            sample_rate: Sample rate of the audio.
            **kwargs: Additional arguments passed to transcribe().

        Returns:
            TranscriptionResult with text and metadata.
        """
        # Write to temporary file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = Path(f.name)

            # Try to parse as WAV first
            try:
                # If already WAV, write directly
                f.write(audio_data)
            except Exception:
                # Convert raw PCM to WAV
                audio_array = np.frombuffer(audio_data, dtype=np.int16)
                audio_float = audio_array.astype(np.float32) / 32768.0
                sf.write(f.name, audio_float, sample_rate)

        try:
            return self.transcribe(temp_path, **kwargs)
        finally:
            # Cleanup
            temp_path.unlink(missing_ok=True)

    def transcribe_file_object(
        self,
        file_obj: BinaryIO,
        filename: str = "audio.wav",
        **kwargs,
    ) -> TranscriptionResult:
        """Transcribe audio from a file-like object.

        Args:
            file_obj: File-like object with audio data.
            filename: Original filename (for extension detection).
            **kwargs: Additional arguments passed to transcribe().

        Returns:
            TranscriptionResult with text and metadata.
        """
        # Determine suffix from filename
        suffix = Path(filename).suffix or ".wav"

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            temp_path = Path(f.name)
            f.write(file_obj.read())

        try:
            return self.transcribe(temp_path, **kwargs)
        finally:
            temp_path.unlink(missing_ok=True)

    def stream_transcribe(
        self,
        audio_path: str | Path,
        **kwargs,
    ) -> Iterator[TranscriptionSegment]:
        """Stream transcription results segment by segment.

        Useful for real-time display of transcription progress.

        Args:
            audio_path: Path to audio file.
            **kwargs: Additional arguments passed to transcribe().

        Yields:
            TranscriptionSegment objects as they're processed.
        """
        if not self._is_initialized:
            self.initialize()

        audio_path = Path(audio_path)

        segments_iter, info = self._model.transcribe(
            str(audio_path),
            **kwargs,
        )

        for segment in segments_iter:
            yield TranscriptionSegment(
                text=segment.text.strip(),
                start=segment.start,
                end=segment.end,
                confidence=segment.avg_logprob if hasattr(segment, "avg_logprob") else 0.0,
            )

    def get_available_models(self) -> dict:
        """Get information about available Whisper models."""
        return WHISPER_MODELS.copy()

    def get_model_info(self) -> dict:
        """Get information about the currently loaded model."""
        return {
            "model_size": self.model_size,
            "device": self.device,
            "compute_type": self.compute_type,
            "is_initialized": self._is_initialized,
            "model_info": WHISPER_MODELS.get(self.model_size, {}),
        }


# Global singleton
_transcriber: WhisperTranscriber | None = None


def get_transcriber(
    model_size: str = DEFAULT_MODEL,
    initialize: bool = False,
) -> WhisperTranscriber:
    """Get the global transcriber instance.

    Args:
        model_size: Whisper model size to use.
        initialize: Whether to initialize immediately.

    Returns:
        WhisperTranscriber instance.
    """
    global _transcriber

    if _transcriber is None:
        _transcriber = WhisperTranscriber(model_size=model_size)

    if initialize and not _transcriber.is_initialized:
        _transcriber.initialize()

    return _transcriber
