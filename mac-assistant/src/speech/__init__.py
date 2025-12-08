"""Speech module for Mac Assistant - Whisper-based speech-to-text."""

from src.speech.transcriber import WhisperTranscriber, get_transcriber, TranscriptionResult

__all__ = [
    "WhisperTranscriber",
    "get_transcriber",
    "TranscriptionResult",
]
