"""Document ingestion pipeline."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from tqdm import tqdm

from src.core.config import Settings, get_settings
from src.core.exceptions import DocumentIngestionError, RAGPocketNotFoundError
from src.core.models import DocumentInfo
from src.rag.chunker import Chunk, DocumentChunker
from src.rag.embeddings import EmbeddingService, get_embedding_service
from src.rag.pockets import PocketManager, get_pocket_manager
from src.rag.vector_store import VectorStore, get_vector_store

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    """Result of document ingestion."""

    document_id: str
    document_path: str
    pocket_id: str
    chunk_count: int
    vector_ids: list[str]
    success: bool
    error: str | None = None
    processing_time: float = 0.0


class IngestionService:
    """Service for ingesting documents into RAG pockets."""

    def __init__(
        self,
        pocket_manager: PocketManager | None = None,
        embedding_service: EmbeddingService | None = None,
        vector_store: VectorStore | None = None,
        settings: Settings | None = None,
    ):
        """Initialize ingestion service.

        Args:
            pocket_manager: Pocket manager instance.
            embedding_service: Embedding service instance.
            vector_store: Vector store instance.
            settings: Application settings.
        """
        self.settings = settings or get_settings()
        self._pocket_manager = pocket_manager
        self._embedding_service = embedding_service
        self._vector_store = vector_store

    @property
    def pocket_manager(self) -> PocketManager:
        """Get pocket manager."""
        if self._pocket_manager is None:
            self._pocket_manager = get_pocket_manager()
        return self._pocket_manager

    @property
    def embedding_service(self) -> EmbeddingService:
        """Get embedding service."""
        if self._embedding_service is None:
            self._embedding_service = get_embedding_service()
        return self._embedding_service

    @property
    def vector_store(self) -> VectorStore:
        """Get vector store."""
        if self._vector_store is None:
            self._vector_store = get_vector_store()
        return self._vector_store

    def ingest_file(
        self,
        file_path: Path | str,
        pocket_id: str,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        force: bool = False,
        progress_callback: Callable[[str, float], None] | None = None,
    ) -> IngestionResult:
        """Ingest a single file into a pocket.

        Args:
            file_path: Path to the file.
            pocket_id: Target pocket ID.
            chunk_size: Override chunk size.
            chunk_overlap: Override chunk overlap.
            force: Re-ingest even if already present.
            progress_callback: Optional callback for progress updates.

        Returns:
            IngestionResult with details.
        """
        import time

        start_time = time.time()
        file_path = Path(file_path)

        # Validate pocket exists
        try:
            pocket = self.pocket_manager.get_pocket(pocket_id)
        except RAGPocketNotFoundError:
            return IngestionResult(
                document_id="",
                document_path=str(file_path),
                pocket_id=pocket_id,
                chunk_count=0,
                vector_ids=[],
                success=False,
                error=f"Pocket '{pocket_id}' not found",
            )

        # Validate file exists
        if not file_path.exists():
            return IngestionResult(
                document_id="",
                document_path=str(file_path),
                pocket_id=pocket_id,
                chunk_count=0,
                vector_ids=[],
                success=False,
                error=f"File not found: {file_path}",
            )

        # Create chunker with pocket settings
        chunker = DocumentChunker(
            chunk_size=chunk_size or pocket.chunk_size,
            chunk_overlap=chunk_overlap or pocket.chunk_overlap,
        )

        document_id = chunker.generate_document_id(file_path)

        # Delete existing vectors if re-ingesting
        if force:
            self.vector_store.delete_by_document(pocket_id, document_id)

        if progress_callback:
            progress_callback("Extracting text", 0.1)

        # Extract and chunk text
        try:
            chunks = list(chunker.chunk_file(file_path))
        except Exception as e:
            return IngestionResult(
                document_id=document_id,
                document_path=str(file_path),
                pocket_id=pocket_id,
                chunk_count=0,
                vector_ids=[],
                success=False,
                error=f"Failed to extract text: {e}",
            )

        if not chunks:
            return IngestionResult(
                document_id=document_id,
                document_path=str(file_path),
                pocket_id=pocket_id,
                chunk_count=0,
                vector_ids=[],
                success=False,
                error="No text content extracted",
            )

        if progress_callback:
            progress_callback("Generating embeddings", 0.3)

        # Generate embeddings
        try:
            texts = [c.text for c in chunks]
            embeddings = self.embedding_service.embed_texts(texts)
        except Exception as e:
            return IngestionResult(
                document_id=document_id,
                document_path=str(file_path),
                pocket_id=pocket_id,
                chunk_count=len(chunks),
                vector_ids=[],
                success=False,
                error=f"Failed to generate embeddings: {e}",
            )

        if progress_callback:
            progress_callback("Storing vectors", 0.7)

        # Store in vector database
        try:
            metadatas = [c.to_metadata() for c in chunks]
            vector_ids = self.vector_store.add_vectors(
                pocket_id=pocket_id,
                vectors=embeddings,
                texts=texts,
                metadatas=metadatas,
            )
        except Exception as e:
            return IngestionResult(
                document_id=document_id,
                document_path=str(file_path),
                pocket_id=pocket_id,
                chunk_count=len(chunks),
                vector_ids=[],
                success=False,
                error=f"Failed to store vectors: {e}",
            )

        # Update pocket stats
        stats = self.vector_store.get_collection_stats(pocket_id)
        docs = self.pocket_manager.list_documents(pocket_id)
        self.pocket_manager.update_stats(
            pocket_id,
            document_count=len(docs),
            vector_count=stats.get("vector_count", 0),
        )

        if progress_callback:
            progress_callback("Complete", 1.0)

        processing_time = time.time() - start_time

        logger.info(
            f"Ingested {file_path.name}: {len(chunks)} chunks, "
            f"{len(vector_ids)} vectors in {processing_time:.2f}s"
        )

        return IngestionResult(
            document_id=document_id,
            document_path=str(file_path),
            pocket_id=pocket_id,
            chunk_count=len(chunks),
            vector_ids=vector_ids,
            success=True,
            processing_time=processing_time,
        )

    def ingest_directory(
        self,
        directory: Path | str,
        pocket_id: str,
        recursive: bool = False,
        force: bool = False,
        show_progress: bool = True,
    ) -> list[IngestionResult]:
        """Ingest all documents in a directory.

        Args:
            directory: Directory path.
            pocket_id: Target pocket ID.
            recursive: Search subdirectories.
            force: Re-ingest existing documents.
            show_progress: Show progress bar.

        Returns:
            List of IngestionResult for each file.
        """
        directory = Path(directory)

        if not directory.exists():
            raise DocumentIngestionError(f"Directory not found: {directory}")

        # Find supported files
        supported_extensions = {'.txt', '.md', '.pdf', '.docx'}
        files = []

        if recursive:
            for ext in supported_extensions:
                files.extend(directory.rglob(f"*{ext}"))
        else:
            for ext in supported_extensions:
                files.extend(directory.glob(f"*{ext}"))

        files = sorted(set(files))

        if not files:
            logger.warning(f"No supported files found in {directory}")
            return []

        results = []
        iterator = tqdm(files, desc="Ingesting") if show_progress else files

        for file_path in iterator:
            result = self.ingest_file(
                file_path=file_path,
                pocket_id=pocket_id,
                force=force,
            )
            results.append(result)

        # Summary
        success_count = sum(1 for r in results if r.success)
        total_chunks = sum(r.chunk_count for r in results if r.success)

        logger.info(
            f"Ingested {success_count}/{len(files)} files, "
            f"{total_chunks} total chunks"
        )

        return results

    def ingest_pocket(
        self,
        pocket_id: str,
        force: bool = False,
        show_progress: bool = True,
    ) -> list[IngestionResult]:
        """Ingest all documents in a pocket's directory.

        Args:
            pocket_id: Pocket ID to ingest.
            force: Re-ingest existing documents.
            show_progress: Show progress bar.

        Returns:
            List of IngestionResult for each file.
        """
        pocket_path = self.pocket_manager.get_pocket_path(pocket_id)

        return self.ingest_directory(
            directory=pocket_path,
            pocket_id=pocket_id,
            recursive=False,
            force=force,
            show_progress=show_progress,
        )

    def delete_document(self, pocket_id: str, document_path: str) -> int:
        """Delete a document and its vectors.

        Args:
            pocket_id: Pocket containing the document.
            document_path: Path to the document.

        Returns:
            Number of vectors deleted.
        """
        chunker = DocumentChunker()
        document_id = chunker.generate_document_id(document_path)

        deleted = self.vector_store.delete_by_document(pocket_id, document_id)

        # Update pocket stats
        stats = self.vector_store.get_collection_stats(pocket_id)
        docs = self.pocket_manager.list_documents(pocket_id)
        self.pocket_manager.update_stats(
            pocket_id,
            document_count=len(docs),
            vector_count=stats.get("vector_count", 0),
        )

        return deleted

    def get_ingestion_status(self, pocket_id: str) -> dict[str, Any]:
        """Get ingestion status for a pocket.

        Args:
            pocket_id: Pocket ID.

        Returns:
            Status dictionary.
        """
        pocket = self.pocket_manager.get_pocket(pocket_id)
        stats = self.vector_store.get_collection_stats(pocket_id)
        docs = self.pocket_manager.list_documents(pocket_id)

        return {
            "pocket_id": pocket_id,
            "document_count": len(docs),
            "vector_count": stats.get("vector_count", 0),
            "collection_exists": stats.get("exists", False),
            "collection_status": stats.get("status", "unknown"),
            "documents": [str(d.name) for d in docs],
        }


# Global singleton
_ingestion_service: IngestionService | None = None


def get_ingestion_service() -> IngestionService:
    """Get the global ingestion service instance."""
    global _ingestion_service
    if _ingestion_service is None:
        _ingestion_service = IngestionService()
    return _ingestion_service
