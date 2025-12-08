"""Custom exceptions for Mac Assistant."""

from __future__ import annotations


class MacAssistantError(Exception):
    """Base exception for Mac Assistant."""
    pass


class FoundryNotInstalledError(MacAssistantError):
    """Foundry Local is not installed."""
    def __init__(self) -> None:
        super().__init__(
            "Foundry Local is not installed. "
            "Install with: brew install microsoft/foundrylocal/foundrylocal"
        )


class FoundryServiceError(MacAssistantError):
    """Error with Foundry Local service."""
    pass


class ModelNotFoundError(MacAssistantError):
    """Requested model not found."""
    def __init__(self, model: str) -> None:
        self.model = model
        super().__init__(f"Model '{model}' not found in catalog or cache")


class ModelNotLoadedError(MacAssistantError):
    """Model is not currently loaded."""
    def __init__(self, model: str) -> None:
        self.model = model
        super().__init__(f"Model '{model}' is not loaded. Load it first.")


class RAGPocketNotFoundError(MacAssistantError):
    """RAG pocket not found."""
    def __init__(self, pocket: str) -> None:
        self.pocket = pocket
        super().__init__(f"RAG pocket '{pocket}' not found")


class DocumentIngestionError(MacAssistantError):
    """Error during document ingestion."""
    pass


class EmbeddingError(MacAssistantError):
    """Error generating embeddings."""
    pass


class VectorStoreError(MacAssistantError):
    """Error with vector store operations."""
    pass


class ChatSessionNotFoundError(MacAssistantError):
    """Chat session not found."""
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        super().__init__(f"Chat session '{session_id}' not found")
