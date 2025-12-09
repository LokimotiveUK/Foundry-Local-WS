"""Project/Workspace management API routes."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.storage.projects import ProjectRepository, get_project_repository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["projects"])


# === Request Models ===

class CreateProjectRequest(BaseModel):
    """Request to create a project."""
    name: str
    description: str | None = None
    color: str = "#007AFF"
    icon: str = "folder"
    default_rag_pocket: str | None = None
    system_prompt: str | None = None
    settings: dict[str, Any] | None = None


class UpdateProjectRequest(BaseModel):
    """Request to update a project."""
    name: str | None = None
    description: str | None = None
    color: str | None = None
    icon: str | None = None
    default_rag_pocket: str | None = None
    system_prompt: str | None = None
    settings: dict[str, Any] | None = None
    is_active: bool | None = None
    is_default: bool | None = None


class MoveSessionRequest(BaseModel):
    """Request to move a session to a project."""
    project_id: str | None = None


# === Project Endpoints ===

@router.get("")
async def list_projects(
    include_inactive: bool = False,
    limit: int = 50,
    offset: int = 0,
    repo: ProjectRepository = Depends(get_project_repository),
) -> list[dict[str, Any]]:
    """List all projects."""
    return repo.list_projects(
        include_inactive=include_inactive,
        limit=limit,
        offset=offset,
    )


@router.post("")
async def create_project(
    request: CreateProjectRequest,
    repo: ProjectRepository = Depends(get_project_repository),
) -> dict[str, Any]:
    """Create a new project."""
    return repo.create_project(
        name=request.name,
        description=request.description,
        color=request.color,
        icon=request.icon,
        default_rag_pocket=request.default_rag_pocket,
        system_prompt=request.system_prompt,
        settings=request.settings,
    )


@router.get("/default")
async def get_default_project(
    repo: ProjectRepository = Depends(get_project_repository),
) -> dict[str, Any] | None:
    """Get the default project."""
    return repo.get_default_project()


@router.get("/{project_id}")
async def get_project(
    project_id: str,
    repo: ProjectRepository = Depends(get_project_repository),
) -> dict[str, Any]:
    """Get a project by ID."""
    project = repo.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/{project_id}")
async def update_project(
    project_id: str,
    request: UpdateProjectRequest,
    repo: ProjectRepository = Depends(get_project_repository),
) -> dict[str, Any]:
    """Update a project."""
    project = repo.update_project(
        project_id=project_id,
        name=request.name,
        description=request.description,
        color=request.color,
        icon=request.icon,
        default_rag_pocket=request.default_rag_pocket,
        system_prompt=request.system_prompt,
        settings=request.settings,
        is_active=request.is_active,
        is_default=request.is_default,
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    move_sessions_to: str | None = None,
    repo: ProjectRepository = Depends(get_project_repository),
) -> dict[str, str]:
    """Delete a project, optionally moving sessions to another project."""
    if not repo.delete_project(project_id, move_sessions_to=move_sessions_to):
        raise HTTPException(status_code=404, detail="Project not found")
    return {"status": "deleted", "project_id": project_id}


# === Session-Project Endpoints ===

@router.get("/{project_id}/sessions")
async def get_project_sessions(
    project_id: str,
    limit: int = 50,
    offset: int = 0,
    repo: ProjectRepository = Depends(get_project_repository),
) -> list[dict[str, Any]]:
    """Get sessions for a project."""
    project = repo.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return repo.get_project_sessions(project_id, limit=limit, offset=offset)


@router.put("/sessions/{session_id}")
async def move_session_to_project(
    session_id: str,
    request: MoveSessionRequest,
    repo: ProjectRepository = Depends(get_project_repository),
) -> dict[str, str]:
    """Move a session to a project (or remove from project if project_id is null)."""
    if not repo.move_session_to_project(session_id, request.project_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "status": "moved",
        "session_id": session_id,
        "project_id": request.project_id or "none",
    }
