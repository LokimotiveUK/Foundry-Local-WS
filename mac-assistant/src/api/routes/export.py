"""Export/Import API routes."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src.core.config import Settings, get_settings
from src.storage.export import ExportService, get_export_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/export", tags=["export"])


class ImportOptions(BaseModel):
    """Options for importing data."""

    overwrite_settings: bool = True
    skip_existing_chats: bool = False


# Export endpoints
@router.post("/all")
async def export_all(
    export_service: ExportService = Depends(get_export_service),
) -> dict[str, Any]:
    """Export all data (settings, chats, documents)."""
    try:
        export_path = export_service.export_all()
        return {
            "success": True,
            "filename": export_path.name,
            "path": str(export_path),
            "size_bytes": export_path.stat().st_size,
        }
    except Exception as e:
        logger.error(f"Export failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chats")
async def export_chats(
    export_service: ExportService = Depends(get_export_service),
) -> dict[str, Any]:
    """Export only chat sessions."""
    try:
        export_path = export_service.export_chats()
        return {
            "success": True,
            "filename": export_path.name,
            "path": str(export_path),
            "size_bytes": export_path.stat().st_size,
        }
    except Exception as e:
        logger.error(f"Export failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/settings")
async def export_settings(
    export_service: ExportService = Depends(get_export_service),
) -> dict[str, Any]:
    """Export only settings."""
    try:
        export_path = export_service.export_settings()
        return {
            "success": True,
            "filename": export_path.name,
            "path": str(export_path),
            "size_bytes": export_path.stat().st_size,
        }
    except Exception as e:
        logger.error(f"Export failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pocket/{pocket_id}")
async def export_pocket(
    pocket_id: str,
    include_files: bool = False,
    export_service: ExportService = Depends(get_export_service),
) -> dict[str, Any]:
    """Export documents from a specific pocket.

    Args:
        pocket_id: Pocket ID to export.
        include_files: Include actual document files in a ZIP.
    """
    try:
        export_path = export_service.export_pocket_documents(
            pocket_id=pocket_id,
            include_files=include_files,
        )
        return {
            "success": True,
            "filename": export_path.name,
            "path": str(export_path),
            "size_bytes": export_path.stat().st_size,
            "includes_files": include_files,
        }
    except Exception as e:
        logger.error(f"Export failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download/{filename}")
async def download_export(
    filename: str,
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    """Download an export file."""
    export_path = settings.app_dir / "exports" / filename

    if not export_path.exists():
        raise HTTPException(status_code=404, detail="Export file not found")

    media_type = "application/zip" if filename.endswith(".zip") else "application/json"

    return FileResponse(
        path=export_path,
        filename=filename,
        media_type=media_type,
    )


@router.get("/list")
async def list_exports(
    export_service: ExportService = Depends(get_export_service),
) -> list[dict[str, Any]]:
    """List all available exports."""
    return export_service.list_exports()


@router.delete("/{filename}")
async def delete_export(
    filename: str,
    export_service: ExportService = Depends(get_export_service),
) -> dict[str, str]:
    """Delete an export file."""
    if export_service.delete_export(filename):
        return {"status": "deleted", "filename": filename}
    raise HTTPException(status_code=404, detail="Export file not found")


# Import endpoints
@router.post("/import")
async def import_data(
    file: UploadFile = File(...),
    options: ImportOptions = Depends(),
    export_service: ExportService = Depends(get_export_service),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Import data from an uploaded file."""
    # Save uploaded file temporarily
    temp_path = settings.app_dir / "exports" / f"import_{file.filename}"

    try:
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # Import the data
        summary = export_service.import_data(
            file_path=temp_path,
            overwrite_settings=options.overwrite_settings,
            skip_existing_chats=options.skip_existing_chats,
        )

        return summary

    except Exception as e:
        logger.error(f"Import failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # Clean up temp file
        if temp_path.exists():
            temp_path.unlink()


@router.post("/import/file")
async def import_from_path(
    file_path: str,
    options: ImportOptions = Depends(),
    export_service: ExportService = Depends(get_export_service),
) -> dict[str, Any]:
    """Import data from a file path on disk."""
    try:
        summary = export_service.import_data(
            file_path=file_path,
            overwrite_settings=options.overwrite_settings,
            skip_existing_chats=options.skip_existing_chats,
        )
        return summary

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        logger.error(f"Import failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
