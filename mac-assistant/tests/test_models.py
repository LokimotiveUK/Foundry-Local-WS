"""Tests for Pydantic models."""

from datetime import datetime

import pytest

from src.core.models import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatSession,
    MessageRole,
    MetricsData,
    ModelInfo,
    RAGPocket,
    StreamChunk,
)


class TestChatMessage:
    """Test ChatMessage model."""

    def test_create_user_message(self):
        """Test creating a user message."""
        msg = ChatMessage(role=MessageRole.USER, content="Hello!")

        assert msg.role == MessageRole.USER
        assert msg.content == "Hello!"
        assert msg.timestamp is not None

    def test_to_openai_format(self):
        """Test conversion to OpenAI format."""
        msg = ChatMessage(role=MessageRole.ASSISTANT, content="Hi there!")
        openai_format = msg.to_openai_format()

        assert openai_format == {"role": "assistant", "content": "Hi there!"}


class TestChatSession:
    """Test ChatSession model."""

    def test_create_session(self):
        """Test creating a chat session."""
        session = ChatSession(model="test-model")

        assert session.id is not None
        assert session.model == "test-model"
        assert len(session.messages) == 0

    def test_add_message(self):
        """Test adding messages to session."""
        session = ChatSession(model="test-model")

        session.add_message(MessageRole.USER, "Hello")
        session.add_message(MessageRole.ASSISTANT, "Hi!")

        assert len(session.messages) == 2
        assert session.messages[0].role == MessageRole.USER
        assert session.messages[1].role == MessageRole.ASSISTANT

    def test_get_context_messages(self):
        """Test getting context messages."""
        session = ChatSession(model="test-model")

        for i in range(25):
            session.add_message(MessageRole.USER, f"Message {i}")

        context = session.get_context_messages(max_messages=10)

        assert len(context) == 10
        assert context[0]["content"] == "Message 15"  # Should be the 16th message (0-indexed)


class TestStreamChunk:
    """Test StreamChunk model."""

    def test_basic_chunk(self):
        """Test basic chunk creation."""
        chunk = StreamChunk(content="Hello")

        assert chunk.content == "Hello"
        assert chunk.done is False
        assert chunk.metrics is None

    def test_final_chunk(self):
        """Test final chunk with metrics."""
        metrics = MetricsData(tokens_generated=100, tokens_per_second=42.0)
        chunk = StreamChunk(content="", done=True, metrics=metrics)

        assert chunk.done is True
        assert chunk.metrics.tokens_generated == 100


class TestModelInfo:
    """Test ModelInfo model."""

    def test_model_info(self):
        """Test ModelInfo creation."""
        info = ModelInfo(
            id="qwen2.5-1.5b-instruct-cpu:1",
            alias="qwen2.5-1.5b-instruct",
            version="1",
            device_type="CPU",
            execution_provider="CPUExecutionProvider",
            model_size=1500000000,
            supports_tool_calling=False,
            is_loaded=True,
            is_current=True,
        )

        assert info.alias == "qwen2.5-1.5b-instruct"
        assert info.is_loaded is True
        assert info.is_current is True


class TestRAGPocket:
    """Test RAGPocket model."""

    def test_rag_pocket(self):
        """Test RAGPocket creation."""
        pocket = RAGPocket(
            id="medical",
            name="Medical",
            description="Medical documents",
            system_prompt="You are a medical assistant.",
        )

        assert pocket.id == "medical"
        assert pocket.chunk_size == 500  # Default
        assert pocket.document_count == 0
