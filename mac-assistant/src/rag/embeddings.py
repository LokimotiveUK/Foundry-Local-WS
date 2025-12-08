"""Embedding service using sentence-transformers."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import TYPE_CHECKING

import numpy as np

from src.core.config import Settings, get_settings
from src.core.exceptions import EmbeddingError

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Generate embeddings using sentence-transformers (runs locally)."""

    def __init__(self, settings: Settings | None = None):
        """Initialize embedding service.

        Args:
            settings: Application settings.
        """
        self.settings = settings or get_settings()
        self.model_name = self.settings.embedding_model
        self.dimension = self.settings.embedding_dimension
        self._model: "SentenceTransformer | None" = None

    def _load_model(self) -> "SentenceTransformer":
        """Load the embedding model (lazy loading)."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                logger.info(f"Loading embedding model: {self.model_name}")
                self._model = SentenceTransformer(self.model_name)

                # Verify dimension
                test_embedding = self._model.encode("test")
                actual_dim = len(test_embedding)
                if actual_dim != self.dimension:
                    logger.warning(
                        f"Model dimension ({actual_dim}) differs from config ({self.dimension}). "
                        f"Using actual dimension."
                    )
                    self.dimension = actual_dim

                logger.info(f"Embedding model loaded. Dimension: {self.dimension}")

            except ImportError:
                raise EmbeddingError(
                    "sentence-transformers not installed. "
                    "Install with: pip install sentence-transformers"
                )
            except Exception as e:
                raise EmbeddingError(f"Failed to load embedding model: {e}")

        return self._model

    @property
    def model(self) -> "SentenceTransformer":
        """Get the embedding model."""
        return self._load_model()

    def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Text to embed.

        Returns:
            Embedding vector as list of floats.
        """
        try:
            embedding = self.model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            raise EmbeddingError(f"Failed to generate embedding: {e}")

    def embed_texts(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed.
            batch_size: Batch size for encoding.

        Returns:
            List of embedding vectors.
        """
        if not texts:
            return []

        try:
            embeddings = self.model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=len(texts) > 10,
                convert_to_numpy=True,
            )
            return embeddings.tolist()
        except Exception as e:
            raise EmbeddingError(f"Failed to generate embeddings: {e}")

    def embed_query(self, query: str) -> list[float]:
        """Generate embedding for a search query.

        Some models have different encoding for queries vs documents.
        This method handles that if needed.

        Args:
            query: Search query text.

        Returns:
            Query embedding vector.
        """
        # For most sentence-transformers models, query and document
        # embeddings are the same. Override this for asymmetric models.
        return self.embed_text(query)

    def similarity(self, embedding1: list[float], embedding2: list[float]) -> float:
        """Calculate cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector.
            embedding2: Second embedding vector.

        Returns:
            Cosine similarity score (0-1).
        """
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)

        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    def get_dimension(self) -> int:
        """Get the embedding dimension.

        Loads the model if needed to verify dimension.
        """
        self._load_model()
        return self.dimension

    def is_loaded(self) -> bool:
        """Check if model is loaded."""
        return self._model is not None


# Global singleton
_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """Get the global embedding service instance."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
