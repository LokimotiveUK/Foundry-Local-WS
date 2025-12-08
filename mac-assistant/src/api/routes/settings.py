"""Settings API routes."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends

from src.core.config import DEFAULT_POCKETS, Settings, get_settings
from src.core.models import SettingsUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
async def get_all_settings(
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Get all current settings."""
    return {
        "default_model": settings.default_model,
        "context_window": settings.context_window,
        "max_response_tokens": settings.max_response_tokens,
        "temperature": settings.temperature,
        "embedding_model": settings.embedding_model,
        "chunk_size": settings.chunk_size,
        "chunk_overlap": settings.chunk_overlap,
        "top_k": settings.top_k,
        "verbose_mode": settings.verbose_mode,
        "save_chat_history": settings.save_chat_history,
        "api_host": settings.api_host,
        "api_port": settings.api_port,
    }


@router.put("")
async def update_settings(
    update: SettingsUpdate,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Update settings.

    Only provided fields will be updated.
    Settings are persisted to config file.
    """
    update_dict = update.model_dump(exclude_unset=True)

    for key, value in update_dict.items():
        if hasattr(settings, key) and value is not None:
            setattr(settings, key, value)
            logger.info(f"Updated setting: {key} = {value}")

    # Persist to file
    settings.save()

    return await get_all_settings(settings)


@router.get("/paths")
async def get_paths(
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    """Get configured paths."""
    return {
        "app_dir": str(settings.app_dir),
        "data_dir": str(settings.data_dir),
        "qdrant_path": str(settings.qdrant_path),
        "db_path": str(settings.db_path),
    }


@router.get("/pockets")
async def get_rag_pockets() -> dict[str, Any]:
    """Get configured RAG pocket definitions."""
    return DEFAULT_POCKETS


@router.get("/pockets/{pocket_id}")
async def get_rag_pocket(pocket_id: str) -> dict[str, Any]:
    """Get a specific RAG pocket configuration."""
    if pocket_id not in DEFAULT_POCKETS:
        return {"error": f"Pocket '{pocket_id}' not found"}
    return {pocket_id: DEFAULT_POCKETS[pocket_id]}
