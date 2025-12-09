"""Folder watcher API routes."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.services.watcher import FolderWatcherService, get_watcher_service
from src.storage.watchers import FolderWatcherRepository, get_watcher_repository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/watchers", tags=["watchers"])


# Request/Response models
class CreateWatcherRequest(BaseModel):
    """Request to create a folder watcher."""
    name: str
    path: str
    pocket_id: str
    recursive: bool = False
    file_patterns: list[str] | None = None
    initial_scan: bool = True


class UpdateWatcherRequest(BaseModel):
    """Request to update a watcher."""
    name: str | None = None
    path: str | None = None
    pocket_id: str | None = None
    recursive: bool | None = None
    file_patterns: list[str] | None = None
    is_active: bool | None = None


class ToggleActiveRequest(BaseModel):
    """Request to toggle watcher active state."""
    is_active: bool


# Endpoints
@router.get("")
async def list_watchers(
    pocket_id: str | None = None,
    active_only: bool = False,
    repository: FolderWatcherRepository = Depends(get_watcher_repository),
) -> list[dict[str, Any]]:
    """List all folder watchers."""
    return repository.list_watchers(pocket_id=pocket_id, active_only=active_only)


@router.get("/status")
async def get_watcher_status(
    service: FolderWatcherService = Depends(get_watcher_service),
) -> dict[str, Any]:
    """Get watcher service status."""
    return service.get_status()


@router.post("")
async def create_watcher(
    request: CreateWatcherRequest,
    service: FolderWatcherService = Depends(get_watcher_service),
) -> dict[str, Any]:
    """Create a new folder watcher."""
    try:
        return service.create_watcher(
            name=request.name,
            path=request.path,
            pocket_id=request.pocket_id,
            recursive=request.recursive,
            file_patterns=request.file_patterns,
            initial_scan=request.initial_scan,
        )
    except Exception as e:
        logger.error(f"Failed to create watcher: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{watcher_id}")
async def get_watcher(
    watcher_id: str,
    repository: FolderWatcherRepository = Depends(get_watcher_repository),
) -> dict[str, Any]:
    """Get a specific watcher."""
    watcher = repository.get_watcher(watcher_id)
    if not watcher:
        raise HTTPException(status_code=404, detail="Watcher not found")
    return watcher


@router.patch("/{watcher_id}")
async def update_watcher(
    watcher_id: str,
    request: UpdateWatcherRequest,
    service: FolderWatcherService = Depends(get_watcher_service),
) -> dict[str, Any]:
    """Update a watcher."""
    watcher = service.update_watcher(
        watcher_id,
        **request.model_dump(exclude_unset=True),
    )
    if not watcher:
        raise HTTPException(status_code=404, detail="Watcher not found")
    return watcher


@router.delete("/{watcher_id}")
async def delete_watcher(
    watcher_id: str,
    service: FolderWatcherService = Depends(get_watcher_service),
) -> dict[str, str]:
    """Delete a watcher."""
    if not service.delete_watcher(watcher_id):
        raise HTTPException(status_code=404, detail="Watcher not found")
    return {"status": "deleted", "watcher_id": watcher_id}


@router.put("/{watcher_id}/active")
async def toggle_watcher_active(
    watcher_id: str,
    request: ToggleActiveRequest,
    service: FolderWatcherService = Depends(get_watcher_service),
) -> dict[str, Any]:
    """Toggle watcher active state."""
    watcher = service.toggle_watcher(watcher_id, request.is_active)
    if not watcher:
        raise HTTPException(status_code=404, detail="Watcher not found")
    return watcher


@router.post("/{watcher_id}/scan")
async def scan_watcher(
    watcher_id: str,
    service: FolderWatcherService = Depends(get_watcher_service),
) -> dict[str, Any]:
    """Trigger manual scan and ingestion for a watcher."""
    result = service.scan_watcher(watcher_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/start")
async def start_watcher_service(
    service: FolderWatcherService = Depends(get_watcher_service),
) -> dict[str, str]:
    """Start the folder watcher service."""
    service.start()
    return {"status": "started"}


@router.post("/stop")
async def stop_watcher_service(
    service: FolderWatcherService = Depends(get_watcher_service),
) -> dict[str, str]:
    """Stop the folder watcher service."""
    service.stop()
    return {"status": "stopped"}
