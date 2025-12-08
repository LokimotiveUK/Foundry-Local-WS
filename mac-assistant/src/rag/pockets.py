"""RAG Pocket management system."""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from src.core.config import DEFAULT_POCKETS, Settings, get_settings
from src.core.exceptions import RAGPocketNotFoundError
from src.core.models import DocumentInfo, RAGPocket

logger = logging.getLogger(__name__)


class PocketManager:
    """Manage RAG pockets (knowledge bases)."""

    def __init__(self, settings: Settings | None = None):
        """Initialize pocket manager.

        Args:
            settings: Application settings.
        """
        self.settings = settings or get_settings()
        self.pockets_dir = self.settings.data_dir / "pockets"
        self.config_file = self.settings.app_dir / "pockets.json"
        self._pockets: dict[str, RAGPocket] = {}
        self._load_pockets()

    def _load_pockets(self) -> None:
        """Load pocket configurations from disk."""
        # Ensure directories exist
        self.pockets_dir.mkdir(parents=True, exist_ok=True)

        # Load saved configurations
        if self.config_file.exists():
            try:
                with open(self.config_file) as f:
                    saved = json.load(f)
                    for pocket_id, data in saved.items():
                        self._pockets[pocket_id] = RAGPocket(
                            id=pocket_id,
                            **data,
                        )
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load pockets config: {e}")

        # Ensure default pockets exist
        for pocket_id, config in DEFAULT_POCKETS.items():
            if pocket_id not in self._pockets:
                self._pockets[pocket_id] = RAGPocket(
                    id=pocket_id,
                    name=config["name"],
                    description=config["description"],
                    icon=config.get("icon", "folder"),
                    system_prompt=config["system_prompt"],
                    chunk_size=config.get("chunk_size", 500),
                    chunk_overlap=config.get("chunk_overlap", 100),
                    color=config.get("color", "#808080"),
                )

            # Ensure directory exists
            pocket_dir = self.pockets_dir / pocket_id
            pocket_dir.mkdir(parents=True, exist_ok=True)

        self._save_pockets()

    def _save_pockets(self) -> None:
        """Save pocket configurations to disk."""
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            data = {}
            for pocket_id, pocket in self._pockets.items():
                data[pocket_id] = {
                    "name": pocket.name,
                    "description": pocket.description,
                    "icon": pocket.icon,
                    "system_prompt": pocket.system_prompt,
                    "chunk_size": pocket.chunk_size,
                    "chunk_overlap": pocket.chunk_overlap,
                    "color": pocket.color,
                    "document_count": pocket.document_count,
                    "vector_count": pocket.vector_count,
                    "created_at": pocket.created_at.isoformat(),
                    "updated_at": pocket.updated_at.isoformat(),
                }
            with open(self.config_file, "w") as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            logger.error(f"Failed to save pockets config: {e}")

    def list_pockets(self) -> list[RAGPocket]:
        """List all pockets."""
        return list(self._pockets.values())

    def get_pocket(self, pocket_id: str) -> RAGPocket:
        """Get a specific pocket.

        Args:
            pocket_id: Pocket identifier.

        Returns:
            RAGPocket configuration.

        Raises:
            RAGPocketNotFoundError: If pocket doesn't exist.
        """
        if pocket_id not in self._pockets:
            raise RAGPocketNotFoundError(pocket_id)
        return self._pockets[pocket_id]

    def create_pocket(
        self,
        pocket_id: str,
        name: str,
        description: str,
        system_prompt: str | None = None,
        icon: str = "folder",
        chunk_size: int = 500,
        chunk_overlap: int = 100,
        color: str = "#808080",
    ) -> RAGPocket:
        """Create a new pocket.

        Args:
            pocket_id: Unique identifier (lowercase, no spaces).
            name: Display name.
            description: Pocket description.
            system_prompt: Custom system prompt for this pocket.
            icon: SF Symbol name for icon.
            chunk_size: Words per chunk.
            chunk_overlap: Overlap between chunks.
            color: Hex color for UI.

        Returns:
            Created RAGPocket.
        """
        # Normalize ID
        pocket_id = pocket_id.lower().replace(" ", "-").replace("_", "-")

        if pocket_id in self._pockets:
            raise ValueError(f"Pocket '{pocket_id}' already exists")

        # Default system prompt
        if not system_prompt:
            system_prompt = f"""You are a helpful assistant with access to {name} documents.
Answer questions based on the provided context. If the answer isn't in the context, say so.
Be precise and cite which document information comes from when relevant."""

        # Create pocket
        pocket = RAGPocket(
            id=pocket_id,
            name=name,
            description=description,
            icon=icon,
            system_prompt=system_prompt,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            color=color,
        )

        # Create directory
        pocket_dir = self.pockets_dir / pocket_id
        pocket_dir.mkdir(parents=True, exist_ok=True)

        self._pockets[pocket_id] = pocket
        self._save_pockets()

        logger.info(f"Created pocket: {pocket_id}")
        return pocket

    def update_pocket(
        self,
        pocket_id: str,
        **kwargs,
    ) -> RAGPocket:
        """Update pocket configuration.

        Args:
            pocket_id: Pocket to update.
            **kwargs: Fields to update.

        Returns:
            Updated RAGPocket.
        """
        pocket = self.get_pocket(pocket_id)

        for key, value in kwargs.items():
            if hasattr(pocket, key) and value is not None:
                setattr(pocket, key, value)

        pocket.updated_at = datetime.utcnow()
        self._save_pockets()

        return pocket

    def delete_pocket(self, pocket_id: str, delete_files: bool = False) -> None:
        """Delete a pocket.

        Args:
            pocket_id: Pocket to delete.
            delete_files: Also delete document files.
        """
        if pocket_id not in self._pockets:
            raise RAGPocketNotFoundError(pocket_id)

        # Prevent deleting default pockets
        if pocket_id in DEFAULT_POCKETS:
            raise ValueError(f"Cannot delete default pocket: {pocket_id}")

        if delete_files:
            pocket_dir = self.pockets_dir / pocket_id
            if pocket_dir.exists():
                shutil.rmtree(pocket_dir)

        del self._pockets[pocket_id]
        self._save_pockets()

        logger.info(f"Deleted pocket: {pocket_id}")

    def get_pocket_path(self, pocket_id: str) -> Path:
        """Get the file path for a pocket.

        Args:
            pocket_id: Pocket identifier.

        Returns:
            Path to pocket's document directory.
        """
        self.get_pocket(pocket_id)  # Validate exists
        return self.pockets_dir / pocket_id

    def list_documents(self, pocket_id: str) -> list[Path]:
        """List all documents in a pocket.

        Args:
            pocket_id: Pocket identifier.

        Returns:
            List of document paths.
        """
        pocket_path = self.get_pocket_path(pocket_id)
        supported_extensions = {".txt", ".md", ".pdf", ".docx"}

        documents = []
        for file in pocket_path.iterdir():
            if file.is_file() and file.suffix.lower() in supported_extensions:
                documents.append(file)

        return sorted(documents)

    def update_stats(
        self,
        pocket_id: str,
        document_count: int | None = None,
        vector_count: int | None = None,
    ) -> None:
        """Update pocket statistics.

        Args:
            pocket_id: Pocket to update.
            document_count: Number of documents.
            vector_count: Number of vectors.
        """
        pocket = self.get_pocket(pocket_id)

        if document_count is not None:
            pocket.document_count = document_count
        if vector_count is not None:
            pocket.vector_count = vector_count

        pocket.updated_at = datetime.utcnow()
        self._save_pockets()


# Global singleton
_pocket_manager: PocketManager | None = None


def get_pocket_manager() -> PocketManager:
    """Get the global pocket manager instance."""
    global _pocket_manager
    if _pocket_manager is None:
        _pocket_manager = PocketManager()
    return _pocket_manager
