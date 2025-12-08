"""Models API routes."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import time
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException

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
    """Background task to download a model with real-time progress tracking.

    This calls the Foundry service directly and parses streaming progress updates
    rather than relying on file system monitoring.
    """
    try:
        # Initialize download state
        _active_downloads[alias] = {
            "status": "downloading",
            "started_at": time.time(),
            "error": None,
            "model_id": model_id,
            "expected_size_mb": expected_size_mb,
            "progress_percent": 0,
            "downloaded_mb": 0,
        }
        logger.info(f"Starting streaming download: {alias} ({expected_size_mb} MB)")

        # Get full model info from SDK for proper download body format
        sdk_model_info = manager.sdk.get_model_info(alias)
        if not sdk_model_info:
            raise RuntimeError(f"Model {alias} not found in catalog")

        # Build request body using SDK's format
        download_body = {
            "model": sdk_model_info.to_download_body(),
            "token": None,
            "IgnorePipeReport": True,
        }

        # Stream directly from Foundry service to get real-time progress
        service_uri = manager.endpoint.replace("/v1", "")  # Get base URI

        # Use extended timeouts for large model downloads (can take 30+ minutes)
        download_timeout = httpx.Timeout(
            connect=30.0,      # 30s to connect
            read=600.0,        # 10 min read timeout (reset on each chunk)
            write=30.0,        # 30s write timeout
            pool=30.0,         # 30s pool timeout
        )

        with httpx.Client(timeout=download_timeout) as client:
            with client.stream("POST", f"{service_uri}/openai/download", json=download_body) as response:
                # Check response status
                if response.status_code != 200:
                    raise RuntimeError(f"Download request failed with status {response.status_code}")

                final_json = ""

                for line in response.iter_lines():
                    # Skip empty lines
                    if not line:
                        continue

                    # Check if this is the final JSON response
                    if final_json or line.startswith("{"):
                        final_json += line
                        continue

                    # Parse progress percentage from lines like "50.5%" or "Downloading: 50.5%"
                    if match := re.search(r"(\d+(?:\.\d+)?)%", line):
                        percent = min(float(match.group(1)), 100.0)
                        downloaded_mb = (percent / 100.0) * expected_size_mb

                        # Update progress state
                        _active_downloads[alias].update({
                            "progress_percent": round(percent, 1),
                            "downloaded_mb": round(downloaded_mb, 1),
                        })

                        if int(percent) % 10 == 0:  # Log every 10%
                            logger.debug(f"Download progress {alias}: {percent:.1f}%")

                # Parse final response
                if final_json:
                    try:
                        result = json.loads(final_json)
                        if not result.get("success", False):
                            raise RuntimeError(result.get("errorMessage", "Download failed"))
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse final JSON: {e}")
                        # If we got progress to 100%, consider it successful
                        if _active_downloads.get(alias, {}).get("progress_percent", 0) < 95:
                            raise RuntimeError("Download ended unexpectedly")

        # Mark as completed
        _active_downloads[alias] = {
            "status": "completed",
            "completed_at": time.time(),
            "progress_percent": 100,
            "downloaded_mb": expected_size_mb,
            "error": None,
        }
        _clear_cache()  # Clear cache so new model shows up
        logger.info(f"Download completed: {alias}")

    except Exception as e:
        logger.error(f"Download failed for {alias}: {e}")
        _active_downloads[alias] = {
            "status": "failed",
            "error": str(e),
            "progress_percent": _active_downloads.get(alias, {}).get("progress_percent", 0),
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
    """Get download status for a specific model with real-time progress.

    Progress is tracked directly from the Foundry service streaming response,
    providing accurate real-time download progress.
    """
    if model_alias not in _active_downloads:
        return {"alias": model_alias, "status": "not_downloading"}

    status = _active_downloads[model_alias].copy()
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
    if not model_info:
        raise HTTPException(status_code=404, detail=f"Model '{model_alias}' not found in catalog")

    model_id = model_info.id
    expected_size_mb = model_info.model_size or 0

    # Check if already cached (unless force=True)
    if model_info.is_cached and not force:
        return {
            "status": "already_cached",
            "alias": model_alias,
            "model_id": model_id,
            "message": "Model is already downloaded. Use force=true to re-download.",
        }

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
