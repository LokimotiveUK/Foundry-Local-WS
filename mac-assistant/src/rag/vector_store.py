"""Vector store using Qdrant (embedded mode - no Docker required)."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from src.core.config import Settings, get_settings
from src.core.exceptions import VectorStoreError

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A single search result from the vector store."""

    id: str
    score: float
    text: str
    metadata: dict[str, Any]

    @property
    def document_id(self) -> str:
        """Get the source document ID."""
        return self.metadata.get("document_id", "")

    @property
    def document_path(self) -> str:
        """Get the source document path."""
        return self.metadata.get("document_path", "")

    @property
    def chunk_index(self) -> int:
        """Get the chunk index within the document."""
        return self.metadata.get("chunk_index", 0)

    @property
    def pocket_id(self) -> str:
        """Get the pocket this chunk belongs to."""
        return self.metadata.get("pocket_id", "")


class VectorStore:
    """Vector database using Qdrant in embedded mode.

    Qdrant runs in-process with data persisted to disk.
    No Docker or external services required.
    """

    def __init__(self, settings: Settings | None = None):
        """Initialize vector store.

        Args:
            settings: Application settings.
        """
        self.settings = settings or get_settings()
        self.storage_path = str(self.settings.qdrant_path)
        self.dimension = self.settings.embedding_dimension
        self._client = None

    def _get_client(self):
        """Get or create Qdrant client (lazy initialization)."""
        if self._client is None:
            try:
                from qdrant_client import QdrantClient

                logger.info(f"Initializing Qdrant at: {self.storage_path}")
                self._client = QdrantClient(path=self.storage_path)
                logger.info("Qdrant initialized successfully")

            except ImportError:
                raise VectorStoreError(
                    "qdrant-client not installed. "
                    "Install with: pip install qdrant-client"
                )
            except Exception as e:
                raise VectorStoreError(f"Failed to initialize Qdrant: {e}")

        return self._client

    @property
    def client(self):
        """Get the Qdrant client."""
        return self._get_client()

    def _get_collection_name(self, pocket_id: str) -> str:
        """Get collection name for a pocket."""
        return f"pocket_{pocket_id}"

    def ensure_collection(self, pocket_id: str) -> None:
        """Ensure a collection exists for a pocket.

        Args:
            pocket_id: Pocket identifier.
        """
        from qdrant_client.models import Distance, VectorParams

        collection_name = self._get_collection_name(pocket_id)

        try:
            collections = self.client.get_collections().collections
            exists = any(c.name == collection_name for c in collections)

            if not exists:
                logger.info(f"Creating collection: {collection_name}")
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=self.dimension,
                        distance=Distance.COSINE,
                    ),
                )
        except Exception as e:
            raise VectorStoreError(f"Failed to ensure collection: {e}")

    def add_vectors(
        self,
        pocket_id: str,
        vectors: list[list[float]],
        texts: list[str],
        metadatas: list[dict[str, Any]],
        ids: list[str] | None = None,
    ) -> list[str]:
        """Add vectors to the store.

        Args:
            pocket_id: Pocket to add to.
            vectors: List of embedding vectors.
            texts: List of text chunks.
            metadatas: List of metadata dicts.
            ids: Optional list of IDs. Generated if not provided.

        Returns:
            List of vector IDs.
        """
        from qdrant_client.models import PointStruct

        if not vectors:
            return []

        # Ensure collection exists
        self.ensure_collection(pocket_id)
        collection_name = self._get_collection_name(pocket_id)

        # Generate IDs if not provided
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in vectors]

        # Build points
        points = []
        for i, (vec, text, meta) in enumerate(zip(vectors, texts, metadatas)):
            payload = {
                "text": text,
                "pocket_id": pocket_id,
                **meta,
            }
            points.append(
                PointStruct(
                    id=ids[i],
                    vector=vec,
                    payload=payload,
                )
            )

        try:
            self.client.upsert(
                collection_name=collection_name,
                points=points,
            )
            logger.info(f"Added {len(points)} vectors to {collection_name}")
            return ids

        except Exception as e:
            raise VectorStoreError(f"Failed to add vectors: {e}")

    def search(
        self,
        pocket_id: str,
        query_vector: list[float],
        limit: int = 5,
        min_score: float = 0.0,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Search for similar vectors.

        Args:
            pocket_id: Pocket to search in.
            query_vector: Query embedding vector.
            limit: Maximum results to return.
            min_score: Minimum similarity score.
            filter_metadata: Optional metadata filter.

        Returns:
            List of SearchResult objects.
        """
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        collection_name = self._get_collection_name(pocket_id)

        # Check if collection exists
        try:
            collections = self.client.get_collections().collections
            if not any(c.name == collection_name for c in collections):
                logger.warning(f"Collection {collection_name} does not exist")
                return []
        except Exception:
            return []

        # Build filter if metadata provided
        query_filter = None
        if filter_metadata:
            conditions = []
            for key, value in filter_metadata.items():
                conditions.append(
                    FieldCondition(
                        key=key,
                        match=MatchValue(value=value),
                    )
                )
            query_filter = Filter(must=conditions)

        try:
            # Use query_points (newer Qdrant API) instead of deprecated search
            response = self.client.query_points(
                collection_name=collection_name,
                query=query_vector,
                limit=limit,
                query_filter=query_filter,
                score_threshold=min_score if min_score > 0 else None,
                with_payload=True,
            )

            return [
                SearchResult(
                    id=str(r.id),
                    score=r.score,
                    text=r.payload.get("text", ""),
                    metadata={k: v for k, v in r.payload.items() if k != "text"},
                )
                for r in response.points
            ]

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def delete_by_document(self, pocket_id: str, document_id: str) -> int:
        """Delete all vectors for a document.

        Args:
            pocket_id: Pocket containing the document.
            document_id: Document ID to delete.

        Returns:
            Number of vectors deleted.
        """
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        collection_name = self._get_collection_name(pocket_id)

        try:
            # First count how many we're deleting
            count_before = self.get_collection_stats(pocket_id).get("vector_count", 0)

            self.client.delete(
                collection_name=collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=document_id),
                        )
                    ]
                ),
            )

            count_after = self.get_collection_stats(pocket_id).get("vector_count", 0)
            deleted = count_before - count_after

            logger.info(f"Deleted {deleted} vectors for document {document_id}")
            return deleted

        except Exception as e:
            logger.error(f"Failed to delete vectors: {e}")
            return 0

    def delete_collection(self, pocket_id: str) -> None:
        """Delete an entire collection.

        Args:
            pocket_id: Pocket whose collection to delete.
        """
        collection_name = self._get_collection_name(pocket_id)

        try:
            self.client.delete_collection(collection_name)
            logger.info(f"Deleted collection: {collection_name}")
        except Exception as e:
            logger.error(f"Failed to delete collection: {e}")

    def get_collection_stats(self, pocket_id: str) -> dict[str, Any]:
        """Get statistics for a collection.

        Args:
            pocket_id: Pocket to get stats for.

        Returns:
            Dictionary with collection statistics.
        """
        collection_name = self._get_collection_name(pocket_id)

        try:
            collections = self.client.get_collections().collections
            if not any(c.name == collection_name for c in collections):
                return {"exists": False, "vector_count": 0}

            info = self.client.get_collection(collection_name)
            # Use points_count (newer API) with fallback to vectors_count (older API)
            vector_count = getattr(info, "points_count", None) or getattr(info, "vectors_count", 0)
            return {
                "exists": True,
                "vector_count": vector_count,
                "indexed_vectors_count": getattr(info, "indexed_vectors_count", 0),
                "status": info.status.value if info.status else "unknown",
            }

        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"exists": False, "error": str(e)}

    def list_collections(self) -> list[str]:
        """List all collections."""
        try:
            collections = self.client.get_collections().collections
            return [c.name for c in collections]
        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            return []

    def is_initialized(self) -> bool:
        """Check if vector store is initialized."""
        return self._client is not None


# Global singleton
_vector_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """Get the global vector store instance."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
