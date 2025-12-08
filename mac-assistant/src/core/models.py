"""Pydantic models for Mac Assistant."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    """Role of a chat message."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(BaseModel):
    """A single chat message."""
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    def to_openai_format(self) -> dict[str, str]:
        """Convert to OpenAI API format."""
        return {"role": self.role.value, "content": self.content}


class ChatRequest(BaseModel):
    """Request to send a chat message."""
    message: str
    session_id: str | None = None
    rag_pocket: str | None = None
    include_history: bool = True
    max_tokens: int | None = None
    temperature: float | None = None
    stream: bool = False


class ChatResponse(BaseModel):
    """Response from a chat request."""
    message: str
    session_id: str
    model: str
    rag_pocket: str | None = None
    sources: list[dict[str, Any]] = Field(default_factory=list)
    metrics: MetricsData | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class StreamChunk(BaseModel):
    """A single chunk from a streaming response."""
    content: str
    done: bool = False
    metrics: MetricsData | None = None


class ModelInfo(BaseModel):
    """Information about an AI model."""
    id: str
    alias: str
    version: str
    device_type: str
    execution_provider: str
    model_size: int
    supports_tool_calling: bool = False
    is_loaded: bool = False
    is_current: bool = False


class ModelSwitchRequest(BaseModel):
    """Request to switch models."""
    model_alias: str
    device: str | None = None


class MetricsData(BaseModel):
    """Performance metrics for a response."""
    tokens_generated: int = 0
    tokens_per_second: float = 0.0
    time_to_first_token: float = 0.0
    total_time: float = 0.0
    prompt_tokens: int = 0
    context_tokens: int = 0


class RAGPocket(BaseModel):
    """A RAG knowledge pocket configuration."""
    id: str
    name: str
    description: str
    icon: str = "folder"
    system_prompt: str
    chunk_size: int = 500
    chunk_overlap: int = 100
    color: str = "#808080"
    document_count: int = 0
    vector_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class DocumentInfo(BaseModel):
    """Information about an ingested document."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    filename: str
    path: str
    pocket_id: str
    chunk_count: int = 0
    file_size: int = 0
    file_type: str
    ingested_at: datetime = Field(default_factory=datetime.utcnow)


class ChatSession(BaseModel):
    """A chat session with history."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str = "New Chat"
    rag_pocket: str | None = None
    model: str
    messages: list[ChatMessage] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def add_message(self, role: MessageRole, content: str) -> ChatMessage:
        """Add a message to the session."""
        msg = ChatMessage(role=role, content=content)
        self.messages.append(msg)
        self.updated_at = datetime.utcnow()
        return msg

    def get_context_messages(self, max_messages: int = 20) -> list[dict[str, str]]:
        """Get recent messages in OpenAI format."""
        recent = self.messages[-max_messages:] if len(self.messages) > max_messages else self.messages
        return [m.to_openai_format() for m in recent]


class SettingsUpdate(BaseModel):
    """Request to update settings."""
    default_model: str | None = None
    context_window: int | None = None
    max_response_tokens: int | None = None
    temperature: float | None = None
    verbose_mode: bool | None = None
    save_chat_history: bool | None = None
    chunk_size: int | None = None
    chunk_overlap: int | None = None
    top_k: int | None = None


class HealthStatus(BaseModel):
    """Health check response."""
    status: str
    foundry_running: bool
    current_model: str | None = None
    qdrant_status: str
    version: str
