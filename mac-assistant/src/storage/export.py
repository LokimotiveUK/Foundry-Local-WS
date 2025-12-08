"""Export and import functionality for Mac Assistant data."""

from __future__ import annotations

import json
import logging
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from src.core.config import Settings, get_settings
from src.storage.chats import ChatRepository, get_chat_repository
from src.storage.database import Database, get_database
from src.storage.documents import DocumentRepository, get_document_repository
from src.storage.models import ExportModel
from src.storage.settings import SettingsRepository, get_settings_repository

logger = logging.getLogger(__name__)


class ExportService:
    """Service for exporting and importing Mac Assistant data."""

    def __init__(
        self,
        settings: Settings | None = None,
        database: Database | None = None,
        chat_repo: ChatRepository | None = None,
        doc_repo: DocumentRepository | None = None,
        settings_repo: SettingsRepository | None = None,
    ):
        """Initialize export service.

        Args:
            settings: Application settings.
            database: Database instance.
            chat_repo: Chat repository.
            doc_repo: Document repository.
            settings_repo: Settings repository.
        """
        self.settings = settings or get_settings()
        self.db = database or get_database()
        self.chat_repo = chat_repo or get_chat_repository()
        self.doc_repo = doc_repo or get_document_repository()
        self.settings_repo = settings_repo or get_settings_repository()

        self.export_dir = self.settings.app_dir / "exports"
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def export_all(self, filename: str | None = None) -> Path:
        """Export all data to a JSON file.

        Args:
            filename: Optional custom filename.

        Returns:
            Path to the exported file.
        """
        if not filename:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"mac_assistant_export_{timestamp}.json"

        export_path = self.export_dir / filename

        # Gather all data
        export_data = {
            "export_type": "full",
            "version": "1.0",
            "exported_at": datetime.utcnow().isoformat(),
            "settings": self.settings_repo.get_all(),
            "chat_sessions": self.chat_repo.export_all_sessions(),
            "documents": self.doc_repo.list_documents(),
        }

        # Write to file
        with open(export_path, "w") as f:
            json.dump(export_data, f, indent=2, default=str)

        # Record export
        self._record_export(
            filename=filename,
            export_type="full",
            size_bytes=export_path.stat().st_size,
            item_count=len(export_data["chat_sessions"]) + len(export_data["documents"]),
        )

        logger.info(f"Exported all data to: {export_path}")
        return export_path

    def export_chats(self, filename: str | None = None) -> Path:
        """Export only chat sessions.

        Args:
            filename: Optional custom filename.

        Returns:
            Path to the exported file.
        """
        if not filename:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"mac_assistant_chats_{timestamp}.json"

        export_path = self.export_dir / filename

        export_data = {
            "export_type": "chats",
            "version": "1.0",
            "exported_at": datetime.utcnow().isoformat(),
            "chat_sessions": self.chat_repo.export_all_sessions(),
        }

        with open(export_path, "w") as f:
            json.dump(export_data, f, indent=2, default=str)

        self._record_export(
            filename=filename,
            export_type="chats",
            size_bytes=export_path.stat().st_size,
            item_count=len(export_data["chat_sessions"]),
        )

        logger.info(f"Exported chats to: {export_path}")
        return export_path

    def export_settings(self, filename: str | None = None) -> Path:
        """Export only settings.

        Args:
            filename: Optional custom filename.

        Returns:
            Path to the exported file.
        """
        if not filename:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"mac_assistant_settings_{timestamp}.json"

        export_path = self.export_dir / filename

        export_data = self.settings_repo.export_settings()
        export_data["export_type"] = "settings"
        export_data["version"] = "1.0"

        with open(export_path, "w") as f:
            json.dump(export_data, f, indent=2, default=str)

        self._record_export(
            filename=filename,
            export_type="settings",
            size_bytes=export_path.stat().st_size,
            item_count=len(export_data.get("settings", [])),
        )

        logger.info(f"Exported settings to: {export_path}")
        return export_path

    def export_pocket_documents(
        self,
        pocket_id: str,
        include_files: bool = False,
        filename: str | None = None,
    ) -> Path:
        """Export documents from a specific pocket.

        Args:
            pocket_id: Pocket ID to export.
            include_files: Include actual document files in a ZIP.
            filename: Optional custom filename.

        Returns:
            Path to the exported file.
        """
        if not filename:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            ext = ".zip" if include_files else ".json"
            filename = f"mac_assistant_pocket_{pocket_id}_{timestamp}{ext}"

        docs = self.doc_repo.list_documents(pocket_id=pocket_id)

        if include_files:
            export_path = self.export_dir / filename

            with zipfile.ZipFile(export_path, "w", zipfile.ZIP_DEFLATED) as zf:
                # Add metadata
                metadata = {
                    "export_type": "pocket_documents",
                    "version": "1.0",
                    "exported_at": datetime.utcnow().isoformat(),
                    "pocket_id": pocket_id,
                    "documents": docs,
                }
                zf.writestr("metadata.json", json.dumps(metadata, indent=2, default=str))

                # Add files
                for doc in docs:
                    file_path = Path(doc["path"])
                    if file_path.exists():
                        zf.write(file_path, f"documents/{file_path.name}")

            logger.info(f"Exported pocket {pocket_id} with files to: {export_path}")
        else:
            export_path = self.export_dir / filename

            export_data = {
                "export_type": "pocket_documents",
                "version": "1.0",
                "exported_at": datetime.utcnow().isoformat(),
                "pocket_id": pocket_id,
                "documents": docs,
            }

            with open(export_path, "w") as f:
                json.dump(export_data, f, indent=2, default=str)

            logger.info(f"Exported pocket {pocket_id} metadata to: {export_path}")

        return export_path

    def import_data(
        self,
        file_path: Path | str,
        overwrite_settings: bool = True,
        skip_existing_chats: bool = False,
    ) -> dict[str, Any]:
        """Import data from an export file.

        Args:
            file_path: Path to the export file.
            overwrite_settings: Overwrite existing settings.
            skip_existing_chats: Skip chats that already exist.

        Returns:
            Import summary.
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"Import file not found: {file_path}")

        if file_path.suffix == ".zip":
            return self._import_zip(file_path)

        with open(file_path) as f:
            data = json.load(f)

        export_type = data.get("export_type", "unknown")
        summary = {
            "file": str(file_path),
            "export_type": export_type,
            "settings_imported": 0,
            "chats_imported": 0,
            "errors": [],
        }

        # Import settings
        if "settings" in data and export_type in ("full", "settings"):
            try:
                if export_type == "settings":
                    count = self.settings_repo.import_settings(data, overwrite=overwrite_settings)
                else:
                    for key, value in data["settings"].items():
                        if overwrite_settings or self.settings_repo.get(key) is None:
                            self.settings_repo.set(key, value)
                            summary["settings_imported"] += 1
            except Exception as e:
                summary["errors"].append(f"Settings import error: {e}")

        # Import chat sessions
        if "chat_sessions" in data and export_type in ("full", "chats"):
            for session_data in data["chat_sessions"]:
                try:
                    session_info = session_data.get("session", {})
                    session_id = session_info.get("id")

                    if skip_existing_chats:
                        existing = self.chat_repo.get_session(session_id)
                        if existing:
                            continue

                    # Create session
                    self.chat_repo.create_session(
                        model=session_info.get("model", "unknown"),
                        rag_pocket=session_info.get("rag_pocket"),
                        title=session_info.get("title", "Imported Chat"),
                        session_id=session_id,
                    )

                    # Add messages
                    for msg in session_data.get("messages", []):
                        from src.core.models import MessageRole
                        self.chat_repo.add_message(
                            session_id=session_id,
                            role=MessageRole(msg["role"]),
                            content=msg["content"],
                        )

                    summary["chats_imported"] += 1

                except Exception as e:
                    summary["errors"].append(f"Chat import error: {e}")

        logger.info(f"Import complete: {summary}")
        return summary

    def _import_zip(self, zip_path: Path) -> dict[str, Any]:
        """Import data from a ZIP file.

        Args:
            zip_path: Path to the ZIP file.

        Returns:
            Import summary.
        """
        summary = {
            "file": str(zip_path),
            "export_type": "pocket_documents",
            "documents_imported": 0,
            "errors": [],
        }

        with zipfile.ZipFile(zip_path, "r") as zf:
            # Read metadata
            if "metadata.json" in zf.namelist():
                metadata = json.loads(zf.read("metadata.json"))
                pocket_id = metadata.get("pocket_id")

                if pocket_id:
                    # Extract documents to pocket directory
                    pocket_dir = self.settings.data_dir / "pockets" / pocket_id
                    pocket_dir.mkdir(parents=True, exist_ok=True)

                    for name in zf.namelist():
                        if name.startswith("documents/"):
                            filename = Path(name).name
                            if filename:
                                zf.extract(name, pocket_dir.parent.parent)
                                # Move from documents/ to pocket dir
                                extracted = pocket_dir.parent.parent / name
                                target = pocket_dir / filename
                                if extracted.exists():
                                    extracted.rename(target)
                                    summary["documents_imported"] += 1

        logger.info(f"ZIP import complete: {summary}")
        return summary

    def _record_export(
        self,
        filename: str,
        export_type: str,
        size_bytes: int,
        item_count: int,
    ) -> None:
        """Record an export in the database.

        Args:
            filename: Export filename.
            export_type: Type of export.
            size_bytes: File size.
            item_count: Number of items exported.
        """
        with self.db.session_scope() as db_session:
            export = ExportModel(
                filename=filename,
                export_type=export_type,
                size_bytes=size_bytes,
                item_count=item_count,
            )
            db_session.add(export)

    def list_exports(self) -> list[dict[str, Any]]:
        """List all exports in the export directory.

        Returns:
            List of export information.
        """
        exports = []

        for file in self.export_dir.iterdir():
            if file.suffix in (".json", ".zip"):
                exports.append({
                    "filename": file.name,
                    "path": str(file),
                    "size_bytes": file.stat().st_size,
                    "created_at": datetime.fromtimestamp(file.stat().st_ctime).isoformat(),
                })

        return sorted(exports, key=lambda x: x["created_at"], reverse=True)

    def delete_export(self, filename: str) -> bool:
        """Delete an export file.

        Args:
            filename: Export filename.

        Returns:
            True if deleted, False if not found.
        """
        export_path = self.export_dir / filename

        if not export_path.exists():
            return False

        export_path.unlink()
        logger.info(f"Deleted export: {filename}")
        return True


# Global singleton
_export_service: ExportService | None = None


def get_export_service() -> ExportService:
    """Get the global export service instance."""
    global _export_service
    if _export_service is None:
        _export_service = ExportService()
    return _export_service
