"""Models API routes."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from src.core.models import ModelInfo, ModelSwitchRequest
from src.foundry.manager import FoundryManager, get_foundry_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=list[ModelInfo])
async def list_models(
    cached_only: bool = False,
    manager: FoundryManager = Depends(get_foundry_manager),
) -> list[ModelInfo]:
    """List available models.

    Args:
        cached_only: If True, only return downloaded models.

    Returns:
        List of ModelInfo objects.
    """
    if not manager.is_initialized:
        raise HTTPException(status_code=503, detail="Foundry not initialized")

    if cached_only:
        return manager.list_cached_models()
    return manager.list_catalog_models()


@router.get("/current")
async def get_current_model(
    manager: FoundryManager = Depends(get_foundry_manager),
) -> dict[str, Any]:
    """Get information about the currently loaded model."""
    if not manager.is_initialized:
        raise HTTPException(status_code=503, detail="Foundry not initialized")

    if not manager.current_model:
        return {"loaded": False, "model": None}

    info = manager.get_model_info(manager.current_model)
    return {
        "loaded": True,
        "model": info.model_dump() if info else None,
        "alias": manager.current_model,
        "id": manager.current_model_id,
    }


@router.get("/loaded", response_model=list[ModelInfo])
async def list_loaded_models(
    manager: FoundryManager = Depends(get_foundry_manager),
) -> list[ModelInfo]:
    """List all currently loaded models."""
    if not manager.is_initialized:
        raise HTTPException(status_code=503, detail="Foundry not initialized")

    return manager.list_loaded_models()


@router.get("/{model_alias}", response_model=ModelInfo)
async def get_model(
    model_alias: str,
    manager: FoundryManager = Depends(get_foundry_manager),
) -> ModelInfo:
    """Get information about a specific model."""
    if not manager.is_initialized:
        raise HTTPException(status_code=503, detail="Foundry not initialized")

    info = manager.get_model_info(model_alias)
    if not info:
        raise HTTPException(status_code=404, detail=f"Model '{model_alias}' not found")
    return info


@router.post("/switch", response_model=ModelInfo)
async def switch_model(
    request: ModelSwitchRequest,
    manager: FoundryManager = Depends(get_foundry_manager),
) -> ModelInfo:
    """Switch to a different model.

    This will unload the current model and load the requested one.
    If the model isn't downloaded, it will be downloaded first.
    """
    if not manager.is_initialized:
        raise HTTPException(status_code=503, detail="Foundry not initialized")

    try:
        logger.info(f"Switching to model: {request.model_alias}")
        return manager.switch_model(request.model_alias)
    except Exception as e:
        logger.error(f"Failed to switch model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/download/{model_alias}", response_model=ModelInfo)
async def download_model(
    model_alias: str,
    force: bool = False,
    manager: FoundryManager = Depends(get_foundry_manager),
) -> ModelInfo:
    """Download a model to local cache.

    Args:
        model_alias: Model alias or ID to download.
        force: Force re-download if already cached.
    """
    if not manager.is_initialized:
        raise HTTPException(status_code=503, detail="Foundry not initialized")

    try:
        logger.info(f"Downloading model: {model_alias}")
        return manager.download_model(model_alias, force=force)
    except Exception as e:
        logger.error(f"Failed to download model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/load/{model_alias}", response_model=ModelInfo)
async def load_model(
    model_alias: str,
    ttl: int = 3600,
    manager: FoundryManager = Depends(get_foundry_manager),
) -> ModelInfo:
    """Load a model into memory.

    Args:
        model_alias: Model alias or ID to load.
        ttl: Time-to-live in seconds (default: 1 hour).
    """
    if not manager.is_initialized:
        raise HTTPException(status_code=503, detail="Foundry not initialized")

    try:
        logger.info(f"Loading model: {model_alias} (TTL: {ttl}s)")
        return manager.load_model(model_alias, ttl=ttl)
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/unload/{model_alias}")
async def unload_model(
    model_alias: str,
    force: bool = False,
    manager: FoundryManager = Depends(get_foundry_manager),
) -> dict[str, str]:
    """Unload a model from memory.

    Args:
        model_alias: Model alias or ID to unload.
        force: Force unload even if TTL hasn't expired.
    """
    if not manager.is_initialized:
        raise HTTPException(status_code=503, detail="Foundry not initialized")

    try:
        logger.info(f"Unloading model: {model_alias}")
        manager.unload_model(model_alias, force=force)
        return {"status": "unloaded", "model": model_alias}
    except Exception as e:
        logger.error(f"Failed to unload model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh-ttl")
async def refresh_model_ttl(
    model_alias: str | None = None,
    ttl: int = 3600,
    manager: FoundryManager = Depends(get_foundry_manager),
) -> dict[str, Any]:
    """Refresh the TTL for a loaded model.

    Args:
        model_alias: Model to refresh. Uses current model if not provided.
        ttl: New TTL in seconds.
    """
    if not manager.is_initialized:
        raise HTTPException(status_code=503, detail="Foundry not initialized")

    try:
        manager.refresh_model_ttl(model_alias, ttl=ttl)
        return {
            "status": "refreshed",
            "model": model_alias or manager.current_model,
            "ttl": ttl,
        }
    except Exception as e:
        logger.error(f"Failed to refresh TTL: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cache/location")
async def get_cache_location(
    manager: FoundryManager = Depends(get_foundry_manager),
) -> dict[str, str]:
    """Get the model cache directory path."""
    if not manager.is_initialized:
        raise HTTPException(status_code=503, detail="Foundry not initialized")

    return {"path": manager.get_cache_location()}
