"""Project/Workspace repository."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import desc

from src.storage.database import Database, get_database
from src.storage.models import ProjectModel, ChatSessionModel

logger = logging.getLogger(__name__)


class ProjectRepository:
    """Repository for project/workspace persistence."""

    def __init__(self, database: Database | None = None):
        """Initialize repository."""
        self.db = database or get_database()

    def create_project(
        self,
        name: str,
        description: str | None = None,
        color: str = "#007AFF",
        icon: str = "folder",
        default_rag_pocket: str | None = None,
        system_prompt: str | None = None,
        settings: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a new project.

        Args:
            name: Project name.
            description: Project description.
            color: Hex color for the project.
            icon: Icon name.
            default_rag_pocket: Default RAG pocket for new chats.
            system_prompt: Project-wide system prompt.
            settings: Project-specific settings.

        Returns:
            Created project as dict.
        """
        project_id = str(uuid4())

        with self.db.session_scope() as db_session:
            project = ProjectModel(
                id=project_id,
                name=name,
                description=description,
                color=color,
                icon=icon,
                default_rag_pocket=default_rag_pocket,
                system_prompt=system_prompt,
                settings_json=json.dumps(settings) if settings else None,
            )
            db_session.add(project)
            db_session.flush()
            return project.to_dict()

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        """Get a project by ID."""
        with self.db.session_scope() as db_session:
            project = db_session.query(ProjectModel).filter_by(id=project_id).first()
            return project.to_dict() if project else None

    def list_projects(
        self,
        include_inactive: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List all projects.

        Args:
            include_inactive: Include inactive projects.
            limit: Maximum projects to return.
            offset: Offset for pagination.

        Returns:
            List of project dictionaries.
        """
        with self.db.session_scope() as db_session:
            query = db_session.query(ProjectModel)

            if not include_inactive:
                query = query.filter_by(is_active=True)

            projects = (
                query.order_by(
                    desc(ProjectModel.is_default),
                    desc(ProjectModel.updated_at),
                )
                .offset(offset)
                .limit(limit)
                .all()
            )
            return [p.to_dict() for p in projects]

    def update_project(
        self,
        project_id: str,
        name: str | None = None,
        description: str | None = None,
        color: str | None = None,
        icon: str | None = None,
        default_rag_pocket: str | None = None,
        system_prompt: str | None = None,
        settings: dict[str, Any] | None = None,
        is_active: bool | None = None,
        is_default: bool | None = None,
    ) -> dict[str, Any] | None:
        """Update a project.

        Args:
            project_id: Project ID.
            name: New name.
            description: New description.
            color: New color.
            icon: New icon.
            default_rag_pocket: New default RAG pocket.
            system_prompt: New system prompt.
            settings: New settings.
            is_active: New active status.
            is_default: Set as default project.

        Returns:
            Updated project as dict, or None if not found.
        """
        with self.db.session_scope() as db_session:
            project = db_session.query(ProjectModel).filter_by(id=project_id).first()
            if not project:
                return None

            if name is not None:
                project.name = name
            if description is not None:
                project.description = description
            if color is not None:
                project.color = color
            if icon is not None:
                project.icon = icon
            if default_rag_pocket is not None:
                project.default_rag_pocket = default_rag_pocket
            if system_prompt is not None:
                project.system_prompt = system_prompt
            if settings is not None:
                project.settings_json = json.dumps(settings)
            if is_active is not None:
                project.is_active = is_active
            if is_default is not None:
                if is_default:
                    # Unset other defaults
                    db_session.query(ProjectModel).filter(
                        ProjectModel.id != project_id
                    ).update({ProjectModel.is_default: False})
                project.is_default = is_default

            project.updated_at = datetime.utcnow()
            db_session.flush()
            return project.to_dict()

    def delete_project(self, project_id: str, move_sessions_to: str | None = None) -> bool:
        """Delete a project.

        Args:
            project_id: Project ID.
            move_sessions_to: Project ID to move sessions to (or None for no project).

        Returns:
            True if deleted, False if not found.
        """
        with self.db.session_scope() as db_session:
            project = db_session.query(ProjectModel).filter_by(id=project_id).first()
            if not project:
                return False

            # Move sessions to target project or unassign
            for session in project.sessions:
                session.project_id = move_sessions_to

            db_session.delete(project)
            logger.info(f"Deleted project: {project_id}")
            return True

    def get_default_project(self) -> dict[str, Any] | None:
        """Get the default project."""
        with self.db.session_scope() as db_session:
            project = db_session.query(ProjectModel).filter_by(
                is_default=True,
                is_active=True,
            ).first()
            return project.to_dict() if project else None

    def move_session_to_project(self, session_id: str, project_id: str | None) -> bool:
        """Move a session to a project (or remove from project if None).

        Args:
            session_id: Session ID.
            project_id: Project ID or None.

        Returns:
            True if successful, False if session not found.
        """
        with self.db.session_scope() as db_session:
            session = db_session.query(ChatSessionModel).filter_by(id=session_id).first()
            if not session:
                return False

            session.project_id = project_id
            session.updated_at = datetime.utcnow()
            return True

    def get_project_sessions(
        self,
        project_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Get sessions for a project.

        Args:
            project_id: Project ID.
            limit: Maximum sessions to return.
            offset: Offset for pagination.

        Returns:
            List of session dictionaries.
        """
        with self.db.session_scope() as db_session:
            sessions = (
                db_session.query(ChatSessionModel)
                .filter_by(project_id=project_id, is_archived=False)
                .order_by(
                    desc(ChatSessionModel.is_pinned),
                    desc(ChatSessionModel.updated_at),
                )
                .offset(offset)
                .limit(limit)
                .all()
            )
            return [s.to_dict() for s in sessions]


# Global singleton
_project_repository: ProjectRepository | None = None


def get_project_repository() -> ProjectRepository:
    """Get the global project repository instance."""
    global _project_repository
    if _project_repository is None:
        _project_repository = ProjectRepository()
    return _project_repository
