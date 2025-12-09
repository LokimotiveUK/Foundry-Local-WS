"""Folder and tag management API routes."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.storage.folders import FolderRepository, get_folder_repository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/organize", tags=["organize"])


# === Request Models ===

class CreateFolderRequest(BaseModel):
    """Request to create a folder."""
    name: str
    color: str = "#808080"
    icon: str = "folder"
    parent_id: str | None = None
    project_id: str | None = None  # None = global folder


class UpdateFolderRequest(BaseModel):
    """Request to update a folder."""
    name: str | None = None
    color: str | None = None
    icon: str | None = None
    parent_id: str | None = None
    sort_order: int | None = None
    project_id: str | None = None  # Set to assign to project


class AssignFolderToProjectRequest(BaseModel):
    """Request to assign folder to a project."""
    project_id: str | None = None  # None = make global


class CreateTagRequest(BaseModel):
    """Request to create a tag."""
    name: str
    color: str = "#007AFF"


class UpdateTagRequest(BaseModel):
    """Request to update a tag."""
    name: str | None = None
    color: str | None = None


class SetSessionTagsRequest(BaseModel):
    """Request to set tags for a session."""
    tag_ids: list[str]


class MoveSessionRequest(BaseModel):
    """Request to move a session to a folder."""
    folder_id: str | None = None


class ReorderFoldersRequest(BaseModel):
    """Request to reorder folders."""
    folder_ids: list[str]


# === Folder Endpoints ===

@router.get("/folders")
async def list_folders(
    parent_id: str | None = None,
    project_id: str | None = None,
    include_global: bool = True,
    flat: bool = False,
    repo: FolderRepository = Depends(get_folder_repository),
) -> list[dict[str, Any]]:
    """List folders, optionally filtered by parent, project, or as flat list.

    Args:
        parent_id: Filter by parent folder ID
        project_id: Filter by project ID. When set with include_global=True,
                    returns both project-specific and global folders.
        include_global: When project_id is set, also include global folders
        flat: Return all folders in a flat list instead of hierarchical
    """
    if flat:
        return repo.list_all_folders(project_id=project_id, include_global=include_global)
    return repo.list_folders(parent_id=parent_id, project_id=project_id, include_global=include_global)


@router.post("/folders")
async def create_folder(
    request: CreateFolderRequest,
    repo: FolderRepository = Depends(get_folder_repository),
) -> dict[str, Any]:
    """Create a new folder."""
    return repo.create_folder(
        name=request.name,
        color=request.color,
        icon=request.icon,
        parent_id=request.parent_id,
        project_id=request.project_id,
    )


@router.get("/folders/{folder_id}")
async def get_folder(
    folder_id: str,
    repo: FolderRepository = Depends(get_folder_repository),
) -> dict[str, Any]:
    """Get a folder by ID."""
    folder = repo.get_folder(folder_id)
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    return folder


@router.patch("/folders/{folder_id}")
async def update_folder(
    folder_id: str,
    request: UpdateFolderRequest,
    repo: FolderRepository = Depends(get_folder_repository),
) -> dict[str, Any]:
    """Update a folder."""
    folder = repo.update_folder(
        folder_id=folder_id,
        name=request.name,
        color=request.color,
        icon=request.icon,
        parent_id=request.parent_id,
        sort_order=request.sort_order,
    )
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    return folder


@router.delete("/folders/{folder_id}")
async def delete_folder(
    folder_id: str,
    move_sessions_to: str | None = None,
    repo: FolderRepository = Depends(get_folder_repository),
) -> dict[str, str]:
    """Delete a folder, optionally moving sessions to another folder."""
    if not repo.delete_folder(folder_id, move_sessions_to=move_sessions_to):
        raise HTTPException(status_code=404, detail="Folder not found")
    return {"status": "deleted", "folder_id": folder_id}


@router.put("/folders/{folder_id}/project")
async def assign_folder_to_project(
    folder_id: str,
    request: AssignFolderToProjectRequest,
    repo: FolderRepository = Depends(get_folder_repository),
) -> dict[str, Any]:
    """Assign a folder to a project or make it global.

    Set project_id to null/None to make the folder global (visible everywhere).
    Set project_id to a valid project ID to make it project-specific.
    """
    folder = repo.assign_folder_to_project(folder_id, request.project_id)
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    return folder


@router.post("/folders/reorder")
async def reorder_folders(
    request: ReorderFoldersRequest,
    repo: FolderRepository = Depends(get_folder_repository),
) -> dict[str, str]:
    """Reorder folders by setting sort_order based on list position."""
    repo.reorder_folders(request.folder_ids)
    return {"status": "reordered"}


# === Tag Endpoints ===

@router.get("/tags")
async def list_tags(
    repo: FolderRepository = Depends(get_folder_repository),
) -> list[dict[str, Any]]:
    """List all tags."""
    return repo.list_tags()


@router.post("/tags")
async def create_tag(
    request: CreateTagRequest,
    repo: FolderRepository = Depends(get_folder_repository),
) -> dict[str, Any]:
    """Create a new tag (or return existing if name matches)."""
    return repo.create_tag(name=request.name, color=request.color)


@router.get("/tags/{tag_id}")
async def get_tag(
    tag_id: str,
    repo: FolderRepository = Depends(get_folder_repository),
) -> dict[str, Any]:
    """Get a tag by ID."""
    tag = repo.get_tag(tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    return tag


@router.patch("/tags/{tag_id}")
async def update_tag(
    tag_id: str,
    request: UpdateTagRequest,
    repo: FolderRepository = Depends(get_folder_repository),
) -> dict[str, Any]:
    """Update a tag."""
    tag = repo.update_tag(
        tag_id=tag_id,
        name=request.name,
        color=request.color,
    )
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    return tag


@router.delete("/tags/{tag_id}")
async def delete_tag(
    tag_id: str,
    repo: FolderRepository = Depends(get_folder_repository),
) -> dict[str, str]:
    """Delete a tag."""
    if not repo.delete_tag(tag_id):
        raise HTTPException(status_code=404, detail="Tag not found")
    return {"status": "deleted", "tag_id": tag_id}


# === Session Organization Endpoints ===

@router.get("/sessions/{session_id}/tags")
async def get_session_tags(
    session_id: str,
    repo: FolderRepository = Depends(get_folder_repository),
) -> list[dict[str, Any]]:
    """Get all tags for a session."""
    return repo.get_session_tags(session_id)


@router.put("/sessions/{session_id}/tags")
async def set_session_tags(
    session_id: str,
    request: SetSessionTagsRequest,
    repo: FolderRepository = Depends(get_folder_repository),
) -> dict[str, str]:
    """Set all tags for a session (replaces existing)."""
    if not repo.set_session_tags(session_id, request.tag_ids):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "updated", "session_id": session_id}


@router.post("/sessions/{session_id}/tags/{tag_id}")
async def add_tag_to_session(
    session_id: str,
    tag_id: str,
    repo: FolderRepository = Depends(get_folder_repository),
) -> dict[str, str]:
    """Add a tag to a session."""
    if not repo.add_tag_to_session(session_id, tag_id):
        raise HTTPException(status_code=404, detail="Session or tag not found")
    return {"status": "added", "session_id": session_id, "tag_id": tag_id}


@router.delete("/sessions/{session_id}/tags/{tag_id}")
async def remove_tag_from_session(
    session_id: str,
    tag_id: str,
    repo: FolderRepository = Depends(get_folder_repository),
) -> dict[str, str]:
    """Remove a tag from a session."""
    if not repo.remove_tag_from_session(session_id, tag_id):
        raise HTTPException(status_code=404, detail="Session or tag not found")
    return {"status": "removed", "session_id": session_id, "tag_id": tag_id}


@router.put("/sessions/{session_id}/folder")
async def move_session_to_folder(
    session_id: str,
    request: MoveSessionRequest,
    repo: FolderRepository = Depends(get_folder_repository),
) -> dict[str, str]:
    """Move a session to a folder (or root if folder_id is null)."""
    if not repo.move_session_to_folder(session_id, request.folder_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "moved", "session_id": session_id, "folder_id": request.folder_id}


class SetPinnedRequest(BaseModel):
    """Request to pin/unpin a session."""
    is_pinned: bool = True


@router.put("/sessions/{session_id}/pin")
async def set_session_pinned(
    session_id: str,
    request: SetPinnedRequest,
    repo: FolderRepository = Depends(get_folder_repository),
) -> dict[str, str]:
    """Pin or unpin a session."""
    if not repo.set_session_pinned(session_id, request.is_pinned):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "updated", "session_id": session_id, "is_pinned": str(request.is_pinned)}
