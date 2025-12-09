"""Folder watcher repository."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import uuid4

from src.storage.database import Database, get_database
from src.storage.models import FolderWatcherModel

logger = logging.getLogger(__name__)


class FolderWatcherRepository:
    """Repository for folder watcher persistence."""

    def __init__(self, database: Database | None = None):
        """Initialize repository.

        Args:
            database: Database instance.
        """
        self.db = database or get_database()

    def create_watcher(
        self,
        name: str,
        path: str,
        pocket_id: str,
        recursive: bool = False,
        file_patterns: list[str] | None = None,
        watcher_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new folder watcher.

        Args:
            name: Display name for the watcher.
            path: Absolute path to watch.
            pocket_id: Target RAG pocket ID.
            recursive: Watch subdirectories.
            file_patterns: List of glob patterns to match.
            watcher_id: Optional custom ID.

        Returns:
            Created watcher as dictionary.
        """
        watcher_id = watcher_id or str(uuid4())
        patterns = ",".join(file_patterns) if file_patterns else "*.txt,*.md,*.pdf,*.docx"

        with self.db.session_scope() as db_session:
            db_model = FolderWatcherModel(
                id=watcher_id,
                name=name,
                path=path,
                pocket_id=pocket_id,
                recursive=recursive,
                file_patterns=patterns,
            )
            db_session.add(db_model)
            db_session.flush()
            result = db_model.to_dict()

        logger.info(f"Created folder watcher: {name} -> {pocket_id}")
        return result

    def get_watcher(self, watcher_id: str) -> dict[str, Any] | None:
        """Get a watcher by ID.

        Args:
            watcher_id: Watcher ID.

        Returns:
            Watcher dictionary or None.
        """
        with self.db.session_scope() as db_session:
            db_model = db_session.query(FolderWatcherModel).filter_by(id=watcher_id).first()
            return db_model.to_dict() if db_model else None

    def list_watchers(
        self,
        pocket_id: str | None = None,
        active_only: bool = False,
    ) -> list[dict[str, Any]]:
        """List all watchers.

        Args:
            pocket_id: Filter by target pocket.
            active_only: Only return active watchers.

        Returns:
            List of watcher dictionaries.
        """
        with self.db.session_scope() as db_session:
            query = db_session.query(FolderWatcherModel)

            if pocket_id:
                query = query.filter_by(pocket_id=pocket_id)

            if active_only:
                query = query.filter_by(is_active=True)

            watchers = query.order_by(FolderWatcherModel.name).all()
            return [w.to_dict() for w in watchers]

    def update_watcher(
        self,
        watcher_id: str,
        name: str | None = None,
        path: str | None = None,
        pocket_id: str | None = None,
        recursive: bool | None = None,
        file_patterns: list[str] | None = None,
        is_active: bool | None = None,
    ) -> dict[str, Any] | None:
        """Update a watcher.

        Args:
            watcher_id: Watcher ID.
            name: New name.
            path: New path.
            pocket_id: New target pocket.
            recursive: New recursive setting.
            file_patterns: New file patterns.
            is_active: New active status.

        Returns:
            Updated watcher or None if not found.
        """
        with self.db.session_scope() as db_session:
            db_model = db_session.query(FolderWatcherModel).filter_by(id=watcher_id).first()

            if not db_model:
                return None

            if name is not None:
                db_model.name = name
            if path is not None:
                db_model.path = path
            if pocket_id is not None:
                db_model.pocket_id = pocket_id
            if recursive is not None:
                db_model.recursive = recursive
            if file_patterns is not None:
                db_model.file_patterns = ",".join(file_patterns)
            if is_active is not None:
                db_model.is_active = is_active

            db_model.updated_at = datetime.utcnow()
            db_session.flush()
            return db_model.to_dict()

    def delete_watcher(self, watcher_id: str) -> bool:
        """Delete a watcher.

        Args:
            watcher_id: Watcher ID.

        Returns:
            True if deleted, False if not found.
        """
        with self.db.session_scope() as db_session:
            db_model = db_session.query(FolderWatcherModel).filter_by(id=watcher_id).first()

            if not db_model:
                return False

            db_session.delete(db_model)
            logger.info(f"Deleted folder watcher: {watcher_id}")
            return True

    def update_scan_stats(
        self,
        watcher_id: str,
        file_count: int,
    ) -> bool:
        """Update watcher scan statistics.

        Args:
            watcher_id: Watcher ID.
            file_count: Number of files found.

        Returns:
            True if updated, False if not found.
        """
        with self.db.session_scope() as db_session:
            db_model = db_session.query(FolderWatcherModel).filter_by(id=watcher_id).first()

            if not db_model:
                return False

            db_model.last_scan_at = datetime.utcnow()
            db_model.file_count = file_count
            return True

    def get_active_watchers(self) -> list[dict[str, Any]]:
        """Get all active watchers.

        Returns:
            List of active watcher dictionaries.
        """
        return self.list_watchers(active_only=True)


# Global singleton
_watcher_repository: FolderWatcherRepository | None = None


def get_watcher_repository() -> FolderWatcherRepository:
    """Get the global watcher repository instance."""
    global _watcher_repository
    if _watcher_repository is None:
        _watcher_repository = FolderWatcherRepository()
    return _watcher_repository
