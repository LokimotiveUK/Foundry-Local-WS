"""Models API routes."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from src.core.models import ModelInfo, ModelSwitchRequest
from src.foundry.manager import FoundryManager, get_foundry_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/models", tags=["models"])

# === Download State Management ===
# Track active downloads so frontend can poll status
_active_downloads: dict[str, dict[str, Any]] = {}

# === Simple Cache for Model Lists ===
_cache: dict[str, tuple[float, Any]] = {}
CACHE_TTL = 5.0  # Cache for 5 seconds


def _get_cached(key: str) -> Any | None:
    """Get cached value if not expired."""
    if key in _cache:
        timestamp, value = _cache[key]
        if time.time() - timestamp < CACHE_TTL:
            return value
    return None


def _set_cached(key: str, value: Any) -> None:
    """Set cached value with current timestamp."""
    _cache[key] = (time.time(), value)


def _clear_cache() -> None:
    """Clear all cached values."""
    _cache.clear()


def _get_folder_size(path: Path) -> int:
    """Get total size of a folder in bytes."""
    total = 0
    try:
        for entry in path.rglob("*"):
            if entry.is_file():
                total += entry.stat().st_size
    except Exception:
        pass
    return total


def _find_model_folder(cache_path: str, model_id: str) -> Path | None:
    """Find the folder for a model in the cache."""
    cache = Path(cache_path)
    if not cache.exists():
        return None

    # Model folders are in Microsoft subfolder with patterns like:
    # Phi-4-mini-instruct-generic-gpu-5, qwen2.5-1.5b-instruct-generic-gpu-4
    microsoft_folder = cache / "Microsoft"
    if not microsoft_folder.exists():
        return None

    # Try to find folder matching the model ID
    model_id_lower = model_id.lower()
    for folder in microsoft_folder.iterdir():
        if folder.is_dir():
            folder_lower = folder.name.lower()
            # Check if model ID matches folder name
            if model_id_lower.replace(":", "-").replace("/", "-") in folder_lower:
                return folder
            # Also check without version suffix
            if model_id_lower.split(":")[0].replace("-", "") in folder_lower.replace("-", ""):
                return folder
    return None


# === Download Background Task ===
def _download_model_task(
    alias: str,
    manager: FoundryManager,
    model_id: str,
    expected_size_mb: int,
    force: bool = False,
) -> None:
    """Background task to download a model."""
    try:
        cache_path = manager.get_cache_location()

        # Get initial folder size (in case of partial download)
        initial_size = 0
        model_folder = _find_model_folder(cache_path, model_id)
        if model_folder:
            initial_size = _get_folder_size(model_folder)

        _active_downloads[alias] = {
            "status": "downloading",
            "started_at": time.time(),
            "error": None,
            "model_id": model_id,
            "expected_size_mb": expected_size_mb,
            "expected_size_bytes": expected_size_mb * 1024 * 1024,
            "cache_path": cache_path,
            "initial_size_bytes": initial_size,
            "downloaded_bytes": 0,
            "progress_percent": 0,
        }
        logger.info(f"Starting background download: {alias} ({expected_size_mb} MB, initial: {initial_size // (1024*1024)} MB)")

        # This is blocking but runs in a thread
        manager.download_model(alias, force=force)

        _active_downloads[alias] = {
            "status": "completed",
            "completed_at": time.time(),
            "error": None,
        }
        _clear_cache()  # Clear cache so new model shows up
        logger.info(f"Download completed: {alias}")

    except Exception as e:
        logger.error(f"Download failed for {alias}: {e}")
        _active_downloads[alias] = {
            "status": "failed",
            "error": str(e),
        }


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

    cache_key = f"models_{'cached' if cached_only else 'all'}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    if cached_only:
        result = manager.list_cached_models()
    else:
        result = manager.list_catalog_models()

    _set_cached(cache_key, result)
    return result


@router.get("/current")
async def get_current_model(
    manager: FoundryManager = Depends(get_foundry_manager),
) -> dict[str, Any]:
    """Get information about the currently loaded model."""
    if not manager.is_initialized:
        raise HTTPException(status_code=503, detail="Foundry not initialized")

    if not manager.current_model:
        return {"loaded": False, "model": None}

    # Use cache for current model info
    cache_key = f"current_{manager.current_model}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    info = manager.get_model_info(manager.current_model)
    result = {
        "loaded": True,
        "model": info.model_dump() if info else None,
        "alias": manager.current_model,
        "id": manager.current_model_id,
        "model_size": info.model_size if info else 0,
    }
    _set_cached(cache_key, result)
    return result


@router.get("/loaded", response_model=list[ModelInfo])
async def list_loaded_models(
    manager: FoundryManager = Depends(get_foundry_manager),
) -> list[ModelInfo]:
    """List all currently loaded models."""
    if not manager.is_initialized:
        raise HTTPException(status_code=503, detail="Foundry not initialized")

    return manager.list_loaded_models()


@router.get("/downloads/status")
async def get_download_status() -> dict[str, Any]:
    """Get status of all active/recent downloads."""
    # Clean up old completed/failed downloads (older than 5 minutes)
    cutoff = time.time() - 300
    to_remove = []
    for alias, status in _active_downloads.items():
        if status.get("status") in ("completed", "failed"):
            completed_at = status.get("completed_at", 0)
            if completed_at and completed_at < cutoff:
                to_remove.append(alias)
    for alias in to_remove:
        del _active_downloads[alias]

    return {"downloads": _active_downloads}


@router.get("/downloads/{model_alias}/status")
async def get_model_download_status(model_alias: str) -> dict[str, Any]:
    """Get download status for a specific model with real-time progress."""
    if model_alias not in _active_downloads:
        return {"alias": model_alias, "status": "not_downloading"}

    status = _active_downloads[model_alias].copy()

    # Calculate real progress by checking folder size delta
    if status.get("status") == "downloading":
        cache_path = status.get("cache_path")
        model_id = status.get("model_id")
        expected_bytes = status.get("expected_size_bytes", 0)
        initial_bytes = status.get("initial_size_bytes", 0)

        if cache_path and model_id and expected_bytes > 0:
            model_folder = _find_model_folder(cache_path, model_id)
            if model_folder:
                current_bytes = _get_folder_size(model_folder)
                # Calculate new bytes downloaded since we started
                new_bytes = max(0, current_bytes - initial_bytes)
                # Progress is based on new bytes vs expected total
                # Cap at 95% since we can't detect exact completion
                progress_percent = min(95, int((new_bytes / expected_bytes) * 100))
                status["downloaded_bytes"] = current_bytes
                status["new_bytes"] = new_bytes
                status["progress_percent"] = progress_percent
                status["downloaded_mb"] = round(current_bytes / (1024 * 1024), 1)
                status["new_mb"] = round(new_bytes / (1024 * 1024), 1)

    return {"alias": model_alias, **status}


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
        result = manager.switch_model(request.model_alias)
        _clear_cache()  # Clear cache after switch
        return result
    except Exception as e:
        logger.error(f"Failed to switch model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/download/{model_alias}")
async def download_model(
    model_alias: str,
    background_tasks: BackgroundTasks,
    force: bool = False,
    blocking: bool = False,
    manager: FoundryManager = Depends(get_foundry_manager),
) -> dict[str, Any]:
    """Download a model to local cache.

    Args:
        model_alias: Model alias or ID to download.
        force: Force re-download if already cached.
        blocking: If True, wait for download to complete (default: False for async).
    """
    if not manager.is_initialized:
        raise HTTPException(status_code=503, detail="Foundry not initialized")

    # Check if already downloading
    if model_alias in _active_downloads:
        status = _active_downloads[model_alias]
        if status.get("status") == "downloading":
            return {
                "status": "already_downloading",
                "alias": model_alias,
                "message": "Download already in progress",
            }

    # Get model info for tracking progress
    model_info = manager.get_model_info(model_alias)
    model_id = model_info.id if model_info else model_alias
    expected_size_mb = model_info.model_size if model_info else 0

    if blocking:
        # Original blocking behavior
        try:
            logger.info(f"Downloading model (blocking): {model_alias}")
            result = manager.download_model(model_alias, force=force)
            _clear_cache()
            return {"status": "completed", "alias": model_alias, "model": result.model_dump()}
        except Exception as e:
            logger.error(f"Failed to download model: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    else:
        # Non-blocking: start background download
        logger.info(f"Starting async download: {model_alias} (ID: {model_id}, Size: {expected_size_mb} MB)")

        # Run in thread pool since the SDK is blocking
        loop = asyncio.get_event_loop()
        loop.run_in_executor(
            None,
            _download_model_task,
            model_alias,
            manager,
            model_id,
            expected_size_mb,
            force,
        )

        return {
            "status": "started",
            "alias": model_alias,
            "model_id": model_id,
            "expected_size_mb": expected_size_mb,
            "message": "Download started in background. Poll /models/downloads/{alias}/status for progress.",
        }


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
        result = manager.load_model(model_alias, ttl=ttl)
        _clear_cache()
        return result
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
        _clear_cache()
        return {"status": "unloaded", "model": model_alias}
    except Exception as e:
        logger.error(f"Failed to unload model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cache/{model_alias}")
async def delete_cached_model(
    model_alias: str,
    manager: FoundryManager = Depends(get_foundry_manager),
) -> dict[str, Any]:
    """Delete a cached model from disk.

    This removes the model files from the cache directory.
    The model must be unloaded first if it's currently loaded.

    Args:
        model_alias: Model alias or ID to delete.
    """
    if not manager.is_initialized:
        raise HTTPException(status_code=503, detail="Foundry not initialized")

    try:
        # Get model info to find the model ID
        model_info = manager.get_model_info(model_alias)
        if not model_info:
            raise HTTPException(status_code=404, detail=f"Model '{model_alias}' not found")

        # Check if model is loaded - unload it first
        loaded_models = manager.list_loaded_models()
        for loaded in loaded_models:
            if loaded.alias == model_alias or loaded.id == model_info.id:
                logger.info(f"Unloading model before deletion: {model_alias}")
                manager.unload_model(model_alias, force=True)
                break

        # Find and delete the model folder
        cache_path = manager.get_cache_location()
        model_folder = _find_model_folder(cache_path, model_info.id)

        if not model_folder or not model_folder.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Model cache folder not found for '{model_alias}'",
            )

        # Get folder size before deletion for response
        folder_size = _get_folder_size(model_folder)
        folder_size_mb = round(folder_size / (1024 * 1024), 1)

        # Delete the folder
        logger.info(f"Deleting model cache: {model_folder} ({folder_size_mb} MB)")
        shutil.rmtree(model_folder)

        _clear_cache()  # Clear API cache
        return {
            "status": "deleted",
            "model": model_alias,
            "path": str(model_folder),
            "freed_mb": folder_size_mb,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete model: {e}")
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


@router.post("/cache/clear")
async def clear_api_cache() -> dict[str, str]:
    """Clear the API response cache."""
    _clear_cache()
    return {"status": "cleared"}
