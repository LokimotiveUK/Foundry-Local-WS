"""Chat session and message repository."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import desc
from sqlalchemy.orm import Session

from src.core.models import ChatMessage, ChatSession, MessageRole, MetricsData
from src.storage.database import Database, get_database
from src.storage.models import ChatMessageModel, ChatSessionModel

logger = logging.getLogger(__name__)


class ChatRepository:
    """Repository for chat session and message persistence."""

    def __init__(self, database: Database | None = None):
        """Initialize repository.

        Args:
            database: Database instance.
        """
        self.db = database or get_database()

    def create_session(
        self,
        model: str,
        rag_pocket: str | None = None,
        title: str = "New Chat",
        session_id: str | None = None,
    ) -> ChatSession:
        """Create a new chat session.

        Args:
            model: Model name.
            rag_pocket: Optional RAG pocket ID.
            title: Session title.
            session_id: Optional custom session ID.

        Returns:
            Created ChatSession.
        """
        session_id = session_id or str(uuid4())

        with self.db.session_scope() as db_session:
            db_model = ChatSessionModel(
                id=session_id,
                title=title,
                model=model,
                rag_pocket=rag_pocket,
            )
            db_session.add(db_model)

        return ChatSession(
            id=session_id,
            title=title,
            model=model,
            rag_pocket=rag_pocket,
        )

    def get_session(self, session_id: str) -> ChatSession | None:
        """Get a chat session by ID.

        Args:
            session_id: Session ID.

        Returns:
            ChatSession or None if not found.
        """
        with self.db.session_scope() as db_session:
            db_model = db_session.query(ChatSessionModel).filter_by(id=session_id).first()

            if not db_model:
                return None

            # Build ChatSession with messages
            session = ChatSession(
                id=db_model.id,
                title=db_model.title,
                model=db_model.model,
                rag_pocket=db_model.rag_pocket,
                created_at=db_model.created_at,
                updated_at=db_model.updated_at,
            )

            # Load messages
            for msg in db_model.messages:
                session.messages.append(
                    ChatMessage(
                        role=MessageRole(msg.role),
                        content=msg.content,
                        timestamp=msg.timestamp,
                    )
                )

            return session

    def get_or_create_session(
        self,
        session_id: str | None,
        model: str,
        rag_pocket: str | None = None,
    ) -> ChatSession:
        """Get existing session or create new one.

        Args:
            session_id: Optional session ID.
            model: Model name.
            rag_pocket: Optional RAG pocket.

        Returns:
            ChatSession.
        """
        if session_id:
            session = self.get_session(session_id)
            if session:
                return session

        return self.create_session(
            model=model,
            rag_pocket=rag_pocket,
            session_id=session_id,
        )

    def add_message(
        self,
        session_id: str,
        role: MessageRole,
        content: str,
        metrics: MetricsData | None = None,
        sources: list[dict[str, Any]] | None = None,
    ) -> ChatMessage:
        """Add a message to a session.

        Args:
            session_id: Session ID.
            role: Message role.
            content: Message content.
            metrics: Optional metrics data.
            sources: Optional RAG sources.

        Returns:
            Created ChatMessage.
        """
        with self.db.session_scope() as db_session:
            # Verify session exists
            session = db_session.query(ChatSessionModel).filter_by(id=session_id).first()
            if not session:
                raise ValueError(f"Session {session_id} not found")

            db_message = ChatMessageModel(
                session_id=session_id,
                role=role.value,
                content=content,
            )

            if metrics:
                db_message.tokens_generated = metrics.tokens_generated
                db_message.tokens_per_second = metrics.tokens_per_second
                db_message.total_time = metrics.total_time

            if sources:
                db_message.sources_json = json.dumps(sources)

            db_session.add(db_message)

            # Update session timestamp
            session.updated_at = datetime.utcnow()

            # Generate title from first user message if needed
            if session.title == "New Chat" and role == MessageRole.USER:
                session.title = content[:50] + ("..." if len(content) > 50 else "")

        return ChatMessage(role=role, content=content)

    def list_sessions(
        self,
        limit: int = 50,
        offset: int = 0,
        rag_pocket: str | None = None,
        include_archived: bool = False,
    ) -> list[dict[str, Any]]:
        """List chat sessions.

        Args:
            limit: Maximum sessions to return.
            offset: Offset for pagination.
            rag_pocket: Filter by RAG pocket.
            include_archived: Include archived sessions.

        Returns:
            List of session dictionaries.
        """
        with self.db.session_scope() as db_session:
            query = db_session.query(ChatSessionModel)

            if not include_archived:
                query = query.filter_by(is_archived=False)

            if rag_pocket:
                query = query.filter_by(rag_pocket=rag_pocket)

            sessions = (
                query.order_by(desc(ChatSessionModel.updated_at))
                .offset(offset)
                .limit(limit)
                .all()
            )

            return [s.to_dict() for s in sessions]

    def update_session(
        self,
        session_id: str,
        title: str | None = None,
        is_archived: bool | None = None,
    ) -> bool:
        """Update session properties.

        Args:
            session_id: Session ID.
            title: New title.
            is_archived: Archive status.

        Returns:
            True if updated, False if not found.
        """
        with self.db.session_scope() as db_session:
            session = db_session.query(ChatSessionModel).filter_by(id=session_id).first()

            if not session:
                return False

            if title is not None:
                session.title = title
            if is_archived is not None:
                session.is_archived = is_archived

            session.updated_at = datetime.utcnow()
            return True

    def delete_session(self, session_id: str) -> bool:
        """Delete a chat session and all its messages.

        Args:
            session_id: Session ID.

        Returns:
            True if deleted, False if not found.
        """
        with self.db.session_scope() as db_session:
            session = db_session.query(ChatSessionModel).filter_by(id=session_id).first()

            if not session:
                return False

            db_session.delete(session)
            logger.info(f"Deleted session: {session_id}")
            return True

    def clear_sessions(self, rag_pocket: str | None = None) -> int:
        """Clear all sessions.

        Args:
            rag_pocket: Optional filter by pocket.

        Returns:
            Number of sessions deleted.
        """
        with self.db.session_scope() as db_session:
            query = db_session.query(ChatSessionModel)

            if rag_pocket:
                query = query.filter_by(rag_pocket=rag_pocket)

            count = query.count()
            query.delete()

            logger.info(f"Cleared {count} sessions")
            return count

    def get_session_messages(
        self,
        session_id: str,
        limit: int = 100,
        before_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get messages for a session.

        Args:
            session_id: Session ID.
            limit: Maximum messages.
            before_id: Get messages before this ID (for pagination).

        Returns:
            List of message dictionaries.
        """
        with self.db.session_scope() as db_session:
            query = db_session.query(ChatMessageModel).filter_by(session_id=session_id)

            if before_id:
                query = query.filter(ChatMessageModel.id < before_id)

            messages = (
                query.order_by(desc(ChatMessageModel.id))
                .limit(limit)
                .all()
            )

            # Reverse to get chronological order
            return [m.to_dict() for m in reversed(messages)]

    def search_messages(
        self,
        query: str,
        rag_pocket: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Search messages by content.

        Args:
            query: Search query.
            rag_pocket: Filter by RAG pocket.
            limit: Maximum results.

        Returns:
            List of matching messages with session info.
        """
        with self.db.session_scope() as db_session:
            db_query = (
                db_session.query(ChatMessageModel)
                .join(ChatSessionModel)
                .filter(ChatMessageModel.content.ilike(f"%{query}%"))
            )

            if rag_pocket:
                db_query = db_query.filter(ChatSessionModel.rag_pocket == rag_pocket)

            messages = (
                db_query.order_by(desc(ChatMessageModel.timestamp))
                .limit(limit)
                .all()
            )

            results = []
            for msg in messages:
                result = msg.to_dict()
                result["session_title"] = msg.session.title
                result["session_model"] = msg.session.model
                results.append(result)

            return results

    def export_session(self, session_id: str) -> dict[str, Any] | None:
        """Export a session with all messages.

        Args:
            session_id: Session ID.

        Returns:
            Complete session data or None.
        """
        with self.db.session_scope() as db_session:
            session = db_session.query(ChatSessionModel).filter_by(id=session_id).first()

            if not session:
                return None

            return {
                "session": session.to_dict(),
                "messages": [m.to_dict() for m in session.messages],
            }

    def export_all_sessions(self) -> list[dict[str, Any]]:
        """Export all sessions.

        Returns:
            List of complete session data.
        """
        with self.db.session_scope() as db_session:
            sessions = db_session.query(ChatSessionModel).all()

            return [
                {
                    "session": s.to_dict(),
                    "messages": [m.to_dict() for m in s.messages],
                }
                for s in sessions
            ]


# Global singleton
_chat_repository: ChatRepository | None = None


def get_chat_repository() -> ChatRepository:
    """Get the global chat repository instance."""
    global _chat_repository
    if _chat_repository is None:
        _chat_repository = ChatRepository()
    return _chat_repository
