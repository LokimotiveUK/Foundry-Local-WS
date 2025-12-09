"""Chat folder and tag repository."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import desc
from sqlalchemy.orm import Session

from src.storage.database import Database, get_database
from src.storage.models import ChatFolderModel, ChatTagModel, ChatSessionModel, chat_session_tags

logger = logging.getLogger(__name__)


class FolderRepository:
    """Repository for chat folder and tag persistence."""

    def __init__(self, database: Database | None = None):
        """Initialize repository."""
        self.db = database or get_database()

    # === Folder Operations ===

    def create_folder(
        self,
        name: str,
        color: str = "#808080",
        icon: str = "folder",
        parent_id: str | None = None,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new folder.

        Args:
            name: Folder name
            color: Hex color code
            icon: Icon name
            parent_id: Parent folder ID (for nesting)
            project_id: Project ID (None = global folder visible everywhere)
        """
        folder_id = str(uuid4())

        with self.db.session_scope() as db_session:
            # Get max sort order for siblings
            query = db_session.query(ChatFolderModel)
            if parent_id:
                query = query.filter_by(parent_id=parent_id)
            else:
                query = query.filter(ChatFolderModel.parent_id.is_(None))

            max_order = query.count()

            folder = ChatFolderModel(
                id=folder_id,
                name=name,
                color=color,
                icon=icon,
                parent_id=parent_id,
                project_id=project_id,
                sort_order=max_order,
            )
            db_session.add(folder)
            db_session.flush()
            return folder.to_dict()

    def get_folder(self, folder_id: str) -> dict[str, Any] | None:
        """Get a folder by ID."""
        with self.db.session_scope() as db_session:
            folder = db_session.query(ChatFolderModel).filter_by(id=folder_id).first()
            return folder.to_dict() if folder else None

    def list_folders(
        self,
        parent_id: str | None = None,
        project_id: str | None = None,
        include_global: bool = True,
    ) -> list[dict[str, Any]]:
        """List folders, optionally filtered by parent and/or project.

        Args:
            parent_id: Filter by parent folder ID
            project_id: Filter by project ID. When set with include_global=True,
                        returns both project-specific and global folders.
            include_global: When project_id is set, also include global folders (project_id=None)
        """
        with self.db.session_scope() as db_session:
            query = db_session.query(ChatFolderModel)

            if parent_id:
                query = query.filter_by(parent_id=parent_id)
            else:
                query = query.filter(ChatFolderModel.parent_id.is_(None))

            # Project filtering
            if project_id is not None:
                if include_global:
                    # Show folders for this project OR global folders
                    from sqlalchemy import or_
                    query = query.filter(
                        or_(
                            ChatFolderModel.project_id == project_id,
                            ChatFolderModel.project_id.is_(None)
                        )
                    )
                else:
                    # Only show folders for this specific project
                    query = query.filter_by(project_id=project_id)

            folders = query.order_by(ChatFolderModel.sort_order).all()
            return [f.to_dict() for f in folders]

    def list_all_folders(self, project_id: str | None = None, include_global: bool = True) -> list[dict[str, Any]]:
        """List all folders in a flat list.

        Args:
            project_id: Filter by project ID
            include_global: When project_id is set, also include global folders
        """
        with self.db.session_scope() as db_session:
            query = db_session.query(ChatFolderModel)

            # Project filtering
            if project_id is not None:
                if include_global:
                    from sqlalchemy import or_
                    query = query.filter(
                        or_(
                            ChatFolderModel.project_id == project_id,
                            ChatFolderModel.project_id.is_(None)
                        )
                    )
                else:
                    query = query.filter_by(project_id=project_id)

            folders = query.order_by(
                ChatFolderModel.parent_id,
                ChatFolderModel.sort_order,
            ).all()
            return [f.to_dict() for f in folders]

    def update_folder(
        self,
        folder_id: str,
        name: str | None = None,
        color: str | None = None,
        icon: str | None = None,
        parent_id: str | None = None,
        sort_order: int | None = None,
        project_id: str | None = "__unset__",
    ) -> dict[str, Any] | None:
        """Update a folder.

        Args:
            project_id: Use "__unset__" to leave unchanged, None to make global,
                        or a string ID to assign to a project.
        """
        with self.db.session_scope() as db_session:
            folder = db_session.query(ChatFolderModel).filter_by(id=folder_id).first()
            if not folder:
                return None

            if name is not None:
                folder.name = name
            if color is not None:
                folder.color = color
            if icon is not None:
                folder.icon = icon
            if parent_id is not None:
                folder.parent_id = parent_id if parent_id else None
            if sort_order is not None:
                folder.sort_order = sort_order
            if project_id != "__unset__":
                folder.project_id = project_id

            folder.updated_at = datetime.utcnow()
            db_session.flush()
            return folder.to_dict()

    def assign_folder_to_project(self, folder_id: str, project_id: str | None) -> dict[str, Any] | None:
        """Assign a folder to a project or make it global.

        Args:
            folder_id: The folder to update
            project_id: Project ID to assign to, or None to make global
        """
        with self.db.session_scope() as db_session:
            folder = db_session.query(ChatFolderModel).filter_by(id=folder_id).first()
            if not folder:
                return None

            folder.project_id = project_id
            folder.updated_at = datetime.utcnow()
            db_session.flush()
            logger.info(f"Assigned folder {folder_id} to project {project_id or 'global'}")
            return folder.to_dict()

    def delete_folder(self, folder_id: str, move_sessions_to: str | None = None) -> bool:
        """Delete a folder, optionally moving its sessions to another folder."""
        with self.db.session_scope() as db_session:
            folder = db_session.query(ChatFolderModel).filter_by(id=folder_id).first()
            if not folder:
                return False

            # Move sessions to target folder or root (None)
            for session in folder.sessions:
                session.folder_id = move_sessions_to

            # Move child folders to parent
            for child in folder.children:
                child.parent_id = folder.parent_id

            db_session.delete(folder)
            logger.info(f"Deleted folder: {folder_id}")
            return True

    def reorder_folders(self, folder_ids: list[str]) -> bool:
        """Reorder folders by setting sort_order based on list position."""
        with self.db.session_scope() as db_session:
            for i, folder_id in enumerate(folder_ids):
                folder = db_session.query(ChatFolderModel).filter_by(id=folder_id).first()
                if folder:
                    folder.sort_order = i
            return True

    # === Tag Operations ===

    def create_tag(self, name: str, color: str = "#007AFF") -> dict[str, Any]:
        """Create a new tag."""
        tag_id = str(uuid4())

        with self.db.session_scope() as db_session:
            # Check if tag with same name exists
            existing = db_session.query(ChatTagModel).filter_by(name=name).first()
            if existing:
                return existing.to_dict()

            tag = ChatTagModel(
                id=tag_id,
                name=name,
                color=color,
            )
            db_session.add(tag)
            db_session.flush()
            return tag.to_dict()

    def get_tag(self, tag_id: str) -> dict[str, Any] | None:
        """Get a tag by ID."""
        with self.db.session_scope() as db_session:
            tag = db_session.query(ChatTagModel).filter_by(id=tag_id).first()
            return tag.to_dict() if tag else None

    def get_tag_by_name(self, name: str) -> dict[str, Any] | None:
        """Get a tag by name."""
        with self.db.session_scope() as db_session:
            tag = db_session.query(ChatTagModel).filter_by(name=name).first()
            return tag.to_dict() if tag else None

    def list_tags(self) -> list[dict[str, Any]]:
        """List all tags."""
        with self.db.session_scope() as db_session:
            tags = db_session.query(ChatTagModel).order_by(ChatTagModel.name).all()
            return [t.to_dict() for t in tags]

    def update_tag(
        self,
        tag_id: str,
        name: str | None = None,
        color: str | None = None,
    ) -> dict[str, Any] | None:
        """Update a tag."""
        with self.db.session_scope() as db_session:
            tag = db_session.query(ChatTagModel).filter_by(id=tag_id).first()
            if not tag:
                return None

            if name is not None:
                tag.name = name
            if color is not None:
                tag.color = color

            db_session.flush()
            return tag.to_dict()

    def delete_tag(self, tag_id: str) -> bool:
        """Delete a tag (removes from all sessions automatically via cascade)."""
        with self.db.session_scope() as db_session:
            tag = db_session.query(ChatTagModel).filter_by(id=tag_id).first()
            if not tag:
                return False

            db_session.delete(tag)
            logger.info(f"Deleted tag: {tag_id}")
            return True

    # === Session-Tag Operations ===

    def add_tag_to_session(self, session_id: str, tag_id: str) -> bool:
        """Add a tag to a session."""
        with self.db.session_scope() as db_session:
            session = db_session.query(ChatSessionModel).filter_by(id=session_id).first()
            tag = db_session.query(ChatTagModel).filter_by(id=tag_id).first()

            if not session or not tag:
                return False

            if tag not in session.tags:
                session.tags.append(tag)

            return True

    def remove_tag_from_session(self, session_id: str, tag_id: str) -> bool:
        """Remove a tag from a session."""
        with self.db.session_scope() as db_session:
            session = db_session.query(ChatSessionModel).filter_by(id=session_id).first()
            tag = db_session.query(ChatTagModel).filter_by(id=tag_id).first()

            if not session or not tag:
                return False

            if tag in session.tags:
                session.tags.remove(tag)

            return True

    def set_session_tags(self, session_id: str, tag_ids: list[str]) -> bool:
        """Set all tags for a session (replaces existing)."""
        with self.db.session_scope() as db_session:
            session = db_session.query(ChatSessionModel).filter_by(id=session_id).first()
            if not session:
                return False

            tags = db_session.query(ChatTagModel).filter(ChatTagModel.id.in_(tag_ids)).all()
            session.tags = tags
            return True

    def get_session_tags(self, session_id: str) -> list[dict[str, Any]]:
        """Get all tags for a session."""
        with self.db.session_scope() as db_session:
            session = db_session.query(ChatSessionModel).filter_by(id=session_id).first()
            if not session:
                return []
            return [t.to_dict() for t in session.tags]

    # === Session-Folder Operations ===

    def move_session_to_folder(self, session_id: str, folder_id: str | None) -> bool:
        """Move a session to a folder (or root if folder_id is None).

        When moving to a folder, the session inherits the folder's project_id.
        When moving to root (folder_id=None), the project_id is cleared.
        """
        with self.db.session_scope() as db_session:
            session = db_session.query(ChatSessionModel).filter_by(id=session_id).first()
            if not session:
                return False

            session.folder_id = folder_id

            # Inherit project from folder, or clear if moving to root
            if folder_id:
                folder = db_session.query(ChatFolderModel).filter_by(id=folder_id).first()
                if folder:
                    session.project_id = folder.project_id
            else:
                # Moving to root - clear project assignment
                session.project_id = None

            session.updated_at = datetime.utcnow()
            return True

    def set_session_pinned(self, session_id: str, is_pinned: bool) -> bool:
        """Set whether a session is pinned."""
        with self.db.session_scope() as db_session:
            session = db_session.query(ChatSessionModel).filter_by(id=session_id).first()
            if not session:
                return False

            session.is_pinned = is_pinned
            session.updated_at = datetime.utcnow()
            return True


# Global singleton
_folder_repository: FolderRepository | None = None


def get_folder_repository() -> FolderRepository:
    """Get the global folder repository instance."""
    global _folder_repository
    if _folder_repository is None:
        _folder_repository = FolderRepository()
    return _folder_repository
