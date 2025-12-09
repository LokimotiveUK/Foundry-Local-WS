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
    Table,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""
    pass


# Junction table for chat sessions and tags (many-to-many)
chat_session_tags = Table(
    "chat_session_tags",
    Base.metadata,
    Column("session_id", String(36), ForeignKey("chat_sessions.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", String(36), ForeignKey("chat_tags.id", ondelete="CASCADE"), primary_key=True),
)


class ChatFolderModel(Base):
    """Chat folder for organizing sessions.

    Folders can be:
    - Global (project_id=None): Visible in all projects
    - Project-specific (project_id set): Only visible in that project
    """

    __tablename__ = "chat_folders"

    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    color = Column(String(7), default="#808080")  # Hex color
    icon = Column(String(50), default="folder")  # Icon name
    parent_id = Column(String(36), ForeignKey("chat_folders.id", ondelete="SET NULL"), nullable=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    sessions = relationship("ChatSessionModel", back_populates="folder")
    children = relationship("ChatFolderModel", backref="parent", remote_side=[id])
    project = relationship("ProjectModel", back_populates="folders")

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "color": self.color,
            "icon": self.icon,
            "parent_id": self.parent_id,
            "project_id": self.project_id,
            "sort_order": self.sort_order,
            "session_count": len(self.sessions) if self.sessions else 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ChatTagModel(Base):
    """Tag for labeling chat sessions."""

    __tablename__ = "chat_tags"

    id = Column(String(36), primary_key=True)
    name = Column(String(50), nullable=False, unique=True)
    color = Column(String(7), default="#007AFF")  # Hex color
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    sessions = relationship(
        "ChatSessionModel",
        secondary=chat_session_tags,
        back_populates="tags",
    )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "color": self.color,
            "session_count": len(self.sessions) if self.sessions else 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ChatSessionModel(Base):
    """Chat session database model."""

    __tablename__ = "chat_sessions"

    id = Column(String(36), primary_key=True)
    title = Column(String(255), default="New Chat")
    rag_pocket = Column(String(50), nullable=True)
    model = Column(String(100), nullable=False)
    folder_id = Column(String(36), ForeignKey("chat_folders.id", ondelete="SET NULL"), nullable=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    is_pinned = Column(Boolean, default=False)
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
    folder = relationship("ChatFolderModel", back_populates="sessions")
    tags = relationship(
        "ChatTagModel",
        secondary=chat_session_tags,
        back_populates="sessions",
    )
    project = relationship("ProjectModel", back_populates="sessions")

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "rag_pocket": self.rag_pocket,
            "model": self.model,
            "folder_id": self.folder_id,
            "project_id": self.project_id,
            "is_pinned": self.is_pinned,
            "message_count": len(self.messages) if self.messages else 0,
            "tags": [t.to_dict() for t in self.tags] if self.tags else [],
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


class FolderWatcherModel(Base):
    """Folder watcher for auto-ingesting documents."""

    __tablename__ = "folder_watchers"

    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    path = Column(Text, nullable=False)  # Absolute path to watched folder
    pocket_id = Column(String(50), nullable=False)  # Target RAG pocket
    recursive = Column(Boolean, default=False)  # Watch subdirectories
    file_patterns = Column(Text, default="*.txt,*.md,*.pdf,*.docx")  # Comma-separated patterns
    is_active = Column(Boolean, default=True)
    last_scan_at = Column(DateTime, nullable=True)
    file_count = Column(Integer, default=0)  # Number of files being watched
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "path": self.path,
            "pocket_id": self.pocket_id,
            "recursive": self.recursive,
            "file_patterns": self.file_patterns.split(",") if self.file_patterns else [],
            "is_active": self.is_active,
            "last_scan_at": self.last_scan_at.isoformat() if self.last_scan_at else None,
            "file_count": self.file_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ProjectModel(Base):
    """Project/Workspace for grouping chats, docs, and settings."""

    __tablename__ = "projects"

    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    color = Column(String(7), default="#007AFF")  # Hex color
    icon = Column(String(50), default="folder")  # Icon name
    default_rag_pocket = Column(String(50), nullable=True)  # Default pocket for new chats
    system_prompt = Column(Text, nullable=True)  # Project-wide system prompt
    settings_json = Column(Text, nullable=True)  # Project-specific settings as JSON
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)  # Default project for new chats
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    sessions = relationship("ChatSessionModel", back_populates="project")
    folders = relationship("ChatFolderModel", back_populates="project")

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        import json as json_module

        settings = None
        if self.settings_json:
            try:
                settings = json_module.loads(self.settings_json)
            except json_module.JSONDecodeError:
                pass

        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "color": self.color,
            "icon": self.icon,
            "default_rag_pocket": self.default_rag_pocket,
            "system_prompt": self.system_prompt,
            "settings": settings,
            "folder_count": len(self.folders) if self.folders else 0,
            "is_active": self.is_active,
            "is_default": self.is_default,
            "session_count": len(self.sessions) if self.sessions else 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
