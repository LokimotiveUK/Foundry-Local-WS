"""Document metadata repository."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import desc

from src.storage.database import Database, get_database
from src.storage.models import DocumentModel

logger = logging.getLogger(__name__)


class DocumentRepository:
    """Repository for document metadata persistence."""

    def __init__(self, database: Database | None = None):
        """Initialize repository.

        Args:
            database: Database instance.
        """
        self.db = database or get_database()

    def _compute_hash(self, file_path: Path) -> str:
        """Compute SHA-256 hash of file content.

        Args:
            file_path: Path to file.

        Returns:
            Hex digest of hash.
        """
        sha256 = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception:
            return ""

    def add_document(
        self,
        document_id: str,
        filename: str,
        path: str,
        pocket_id: str,
        file_type: str,
        file_size: int = 0,
        chunk_count: int = 0,
    ) -> dict[str, Any]:
        """Add or update a document record.

        Args:
            document_id: Document ID.
            filename: File name.
            path: Full file path.
            pocket_id: RAG pocket ID.
            file_type: File extension.
            file_size: File size in bytes.
            chunk_count: Number of chunks created.

        Returns:
            Document dictionary.
        """
        content_hash = self._compute_hash(Path(path)) if Path(path).exists() else ""

        with self.db.session_scope() as db_session:
            # Check if exists
            existing = db_session.query(DocumentModel).filter_by(id=document_id).first()

            if existing:
                existing.filename = filename
                existing.path = path
                existing.pocket_id = pocket_id
                existing.file_type = file_type
                existing.file_size = file_size
                existing.chunk_count = chunk_count
                existing.content_hash = content_hash
                existing.updated_at = datetime.utcnow()
                return existing.to_dict()
            else:
                doc = DocumentModel(
                    id=document_id,
                    filename=filename,
                    path=path,
                    pocket_id=pocket_id,
                    file_type=file_type,
                    file_size=file_size,
                    chunk_count=chunk_count,
                    content_hash=content_hash,
                )
                db_session.add(doc)
                logger.info(f"Added document: {filename} to pocket {pocket_id}")
                return doc.to_dict()

    def get_document(self, document_id: str) -> dict[str, Any] | None:
        """Get a document by ID.

        Args:
            document_id: Document ID.

        Returns:
            Document dictionary or None.
        """
        with self.db.session_scope() as db_session:
            doc = db_session.query(DocumentModel).filter_by(id=document_id).first()
            return doc.to_dict() if doc else None

    def get_document_by_path(self, path: str) -> dict[str, Any] | None:
        """Get a document by path.

        Args:
            path: File path.

        Returns:
            Document dictionary or None.
        """
        with self.db.session_scope() as db_session:
            doc = db_session.query(DocumentModel).filter_by(path=path).first()
            return doc.to_dict() if doc else None

    def list_documents(
        self,
        pocket_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List documents.

        Args:
            pocket_id: Optional filter by pocket.
            limit: Maximum documents.
            offset: Offset for pagination.

        Returns:
            List of document dictionaries.
        """
        with self.db.session_scope() as db_session:
            query = db_session.query(DocumentModel)

            if pocket_id:
                query = query.filter_by(pocket_id=pocket_id)

            docs = (
                query.order_by(desc(DocumentModel.ingested_at))
                .offset(offset)
                .limit(limit)
                .all()
            )

            return [d.to_dict() for d in docs]

    def delete_document(self, document_id: str) -> bool:
        """Delete a document record.

        Args:
            document_id: Document ID.

        Returns:
            True if deleted, False if not found.
        """
        with self.db.session_scope() as db_session:
            doc = db_session.query(DocumentModel).filter_by(id=document_id).first()

            if not doc:
                return False

            db_session.delete(doc)
            logger.info(f"Deleted document record: {document_id}")
            return True

    def delete_by_pocket(self, pocket_id: str) -> int:
        """Delete all documents in a pocket.

        Args:
            pocket_id: Pocket ID.

        Returns:
            Number of documents deleted.
        """
        with self.db.session_scope() as db_session:
            count = (
                db_session.query(DocumentModel)
                .filter_by(pocket_id=pocket_id)
                .delete()
            )
            logger.info(f"Deleted {count} documents from pocket {pocket_id}")
            return count

    def get_pocket_stats(self, pocket_id: str) -> dict[str, Any]:
        """Get statistics for a pocket.

        Args:
            pocket_id: Pocket ID.

        Returns:
            Statistics dictionary.
        """
        with self.db.session_scope() as db_session:
            docs = db_session.query(DocumentModel).filter_by(pocket_id=pocket_id).all()

            total_size = sum(d.file_size for d in docs)
            total_chunks = sum(d.chunk_count for d in docs)

            return {
                "pocket_id": pocket_id,
                "document_count": len(docs),
                "total_size_bytes": total_size,
                "total_chunks": total_chunks,
                "file_types": list(set(d.file_type for d in docs)),
            }

    def check_needs_reindex(self, document_id: str, path: str) -> bool:
        """Check if a document needs to be re-indexed.

        Compares stored hash with current file hash.

        Args:
            document_id: Document ID.
            path: Current file path.

        Returns:
            True if re-indexing is needed.
        """
        with self.db.session_scope() as db_session:
            doc = db_session.query(DocumentModel).filter_by(id=document_id).first()

            if not doc:
                return True  # Not indexed yet

            if not Path(path).exists():
                return False  # File doesn't exist

            current_hash = self._compute_hash(Path(path))
            return doc.content_hash != current_hash

    def get_all_stats(self) -> dict[str, Any]:
        """Get statistics for all documents.

        Returns:
            Overall statistics.
        """
        with self.db.session_scope() as db_session:
            docs = db_session.query(DocumentModel).all()

            pockets = {}
            for doc in docs:
                if doc.pocket_id not in pockets:
                    pockets[doc.pocket_id] = {
                        "document_count": 0,
                        "chunk_count": 0,
                        "total_size": 0,
                    }
                pockets[doc.pocket_id]["document_count"] += 1
                pockets[doc.pocket_id]["chunk_count"] += doc.chunk_count
                pockets[doc.pocket_id]["total_size"] += doc.file_size

            return {
                "total_documents": len(docs),
                "total_chunks": sum(d.chunk_count for d in docs),
                "total_size_bytes": sum(d.file_size for d in docs),
                "pockets": pockets,
            }


# Global singleton
_document_repository: DocumentRepository | None = None


def get_document_repository() -> DocumentRepository:
    """Get the global document repository instance."""
    global _document_repository
    if _document_repository is None:
        _document_repository = DocumentRepository()
    return _document_repository
