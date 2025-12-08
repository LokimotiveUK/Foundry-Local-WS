"""SQLAlchemy models for Mac Assistant."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""
    pass


class ChatSessionModel(Base):
    """Chat session database model."""

    __tablename__ = "chat_sessions"

    id = Column(String(36), primary_key=True)
    title = Column(String(255), default="New Chat")
    rag_pocket = Column(String(50), nullable=True)
    model = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_archived = Column(Boolean, default=False)

    # Relationships
    messages = relationship(
        "ChatMessageModel",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessageModel.timestamp",
    )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "rag_pocket": self.rag_pocket,
            "model": self.model,
            "message_count": len(self.messages) if self.messages else 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "is_archived": self.is_archived,
        }


class ChatMessageModel(Base):
    """Chat message database model."""

    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("chat_sessions.id"), nullable=False)
    role = Column(String(20), nullable=False)  # system, user, assistant
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Metrics (optional, for assistant messages)
    tokens_generated = Column(Integer, nullable=True)
    tokens_per_second = Column(Float, nullable=True)
    total_time = Column(Float, nullable=True)

    # RAG sources (JSON string, optional)
    sources_json = Column(Text, nullable=True)

    # Relationships
    session = relationship("ChatSessionModel", back_populates="messages")

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        import json

        result = {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }

        if self.tokens_generated:
            result["metrics"] = {
                "tokens_generated": self.tokens_generated,
                "tokens_per_second": self.tokens_per_second,
                "total_time": self.total_time,
            }

        if self.sources_json:
            try:
                result["sources"] = json.loads(self.sources_json)
            except json.JSONDecodeError:
                pass

        return result


class DocumentModel(Base):
    """Ingested document database model."""

    __tablename__ = "documents"

    id = Column(String(36), primary_key=True)
    filename = Column(String(255), nullable=False)
    path = Column(Text, nullable=False)
    pocket_id = Column(String(50), nullable=False)
    file_type = Column(String(20), nullable=False)
    file_size = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)
    ingested_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Content hash for change detection
    content_hash = Column(String(64), nullable=True)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "filename": self.filename,
            "path": self.path,
            "pocket_id": self.pocket_id,
            "file_type": self.file_type,
            "file_size": self.file_size,
            "chunk_count": self.chunk_count,
            "ingested_at": self.ingested_at.isoformat() if self.ingested_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "content_hash": self.content_hash,
        }


class SettingModel(Base):
    """Application settings database model."""

    __tablename__ = "settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)
    value_type = Column(String(20), default="string")  # string, int, float, bool, json
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_typed_value(self):
        """Get value with proper type conversion."""
        import json

        if self.value_type == "int":
            return int(self.value)
        elif self.value_type == "float":
            return float(self.value)
        elif self.value_type == "bool":
            return self.value.lower() in ("true", "1", "yes")
        elif self.value_type == "json":
            return json.loads(self.value)
        else:
            return self.value


class ExportModel(Base):
    """Export history for backup tracking."""

    __tablename__ = "exports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(255), nullable=False)
    export_type = Column(String(50), nullable=False)  # full, chats, settings
    created_at = Column(DateTime, default=datetime.utcnow)
    size_bytes = Column(Integer, default=0)
    item_count = Column(Integer, default=0)
