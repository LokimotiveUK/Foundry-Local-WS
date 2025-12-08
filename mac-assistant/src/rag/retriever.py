"""RAG retriever for query and context building."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from src.core.config import Settings, get_settings
from src.core.models import MetricsData
from src.foundry.manager import FoundryManager, get_foundry_manager
from src.foundry.metrics import MetricsTracker
from src.foundry.streaming import StreamingHandler
from src.rag.embeddings import EmbeddingService, get_embedding_service
from src.rag.pockets import PocketManager, get_pocket_manager
from src.rag.vector_store import SearchResult, VectorStore, get_vector_store

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """Result of a retrieval operation."""

    query: str
    pocket_id: str
    chunks: list[SearchResult]
    context: str
    retrieval_time: float = 0.0


@dataclass
class RAGResponse:
    """Complete RAG response with answer and sources."""

    query: str
    answer: str
    pocket_id: str
    sources: list[dict[str, Any]]
    metrics: MetricsData | None = None
    retrieval_time: float = 0.0
    generation_time: float = 0.0


class RAGRetriever:
    """Retrieve relevant context and generate RAG responses."""

    def __init__(
        self,
        pocket_manager: PocketManager | None = None,
        embedding_service: EmbeddingService | None = None,
        vector_store: VectorStore | None = None,
        foundry_manager: FoundryManager | None = None,
        settings: Settings | None = None,
    ):
        """Initialize retriever.

        Args:
            pocket_manager: Pocket manager instance.
            embedding_service: Embedding service instance.
            vector_store: Vector store instance.
            foundry_manager: Foundry manager instance.
            settings: Application settings.
        """
        self.settings = settings or get_settings()
        self._pocket_manager = pocket_manager
        self._embedding_service = embedding_service
        self._vector_store = vector_store
        self._foundry_manager = foundry_manager

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

    @property
    def foundry_manager(self) -> FoundryManager:
        """Get Foundry manager."""
        if self._foundry_manager is None:
            self._foundry_manager = get_foundry_manager()
        return self._foundry_manager

    def retrieve(
        self,
        query: str,
        pocket_id: str,
        top_k: int | None = None,
        min_score: float | None = None,
    ) -> RetrievalResult:
        """Retrieve relevant chunks for a query.

        Args:
            query: Search query.
            pocket_id: Pocket to search in.
            top_k: Number of results to return.
            min_score: Minimum similarity score.

        Returns:
            RetrievalResult with chunks and context.
        """
        import time

        start_time = time.time()

        top_k = top_k or self.settings.top_k
        min_score = min_score if min_score is not None else self.settings.min_similarity

        # Generate query embedding
        query_embedding = self.embedding_service.embed_query(query)

        # Search vector store
        chunks = self.vector_store.search(
            pocket_id=pocket_id,
            query_vector=query_embedding,
            limit=top_k,
            min_score=min_score,
        )

        # Build context string
        context = self._build_context(chunks)

        retrieval_time = time.time() - start_time

        logger.debug(
            f"Retrieved {len(chunks)} chunks for query in {retrieval_time:.3f}s"
        )

        return RetrievalResult(
            query=query,
            pocket_id=pocket_id,
            chunks=chunks,
            context=context,
            retrieval_time=retrieval_time,
        )

    def _build_context(self, chunks: list[SearchResult]) -> str:
        """Build context string from retrieved chunks.

        Args:
            chunks: Retrieved search results.

        Returns:
            Formatted context string.
        """
        if not chunks:
            return ""

        context_parts = []

        for i, chunk in enumerate(chunks, 1):
            # Include source info for citation
            source = chunk.document_path.split("/")[-1] if chunk.document_path else "unknown"
            context_parts.append(
                f"[Source {i}: {source}]\n{chunk.text}"
            )

        return "\n\n---\n\n".join(context_parts)

    def generate_response(
        self,
        query: str,
        pocket_id: str,
        top_k: int | None = None,
        min_score: float | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        include_sources: bool = True,
    ) -> RAGResponse:
        """Generate a complete RAG response.

        Args:
            query: User's question.
            pocket_id: Pocket to search in.
            top_k: Number of chunks to retrieve.
            min_score: Minimum similarity score.
            temperature: LLM temperature.
            max_tokens: Maximum response tokens.
            include_sources: Include source citations.

        Returns:
            RAGResponse with answer and sources.
        """
        import time

        # Retrieve relevant context
        retrieval = self.retrieve(
            query=query,
            pocket_id=pocket_id,
            top_k=top_k,
            min_score=min_score,
        )

        if not retrieval.chunks:
            return RAGResponse(
                query=query,
                answer="I couldn't find any relevant information in the documents to answer your question.",
                pocket_id=pocket_id,
                sources=[],
                retrieval_time=retrieval.retrieval_time,
            )

        # Get pocket configuration
        pocket = self.pocket_manager.get_pocket(pocket_id)

        # Build messages
        messages = [
            {
                "role": "system",
                "content": pocket.system_prompt,
            },
            {
                "role": "user",
                "content": self._build_prompt(query, retrieval.context),
            },
        ]

        # Generate response
        gen_start = time.time()

        handler = StreamingHandler(
            client=self.foundry_manager.client,
            model_id=self.foundry_manager.current_model_id,
            verbose=self.settings.verbose_mode,
        )

        answer, metrics = handler.complete_chat(
            messages=messages,
            temperature=temperature or self.settings.temperature,
            max_tokens=max_tokens or self.settings.max_response_tokens,
        )

        generation_time = time.time() - gen_start

        # Build sources list
        sources = []
        if include_sources:
            for i, chunk in enumerate(retrieval.chunks):
                sources.append({
                    "index": i + 1,
                    "document": chunk.document_path.split("/")[-1] if chunk.document_path else "unknown",
                    "document_path": chunk.document_path,
                    "score": round(chunk.score, 4),
                    "chunk_index": chunk.chunk_index,
                    "text_preview": chunk.text[:200] + "..." if len(chunk.text) > 200 else chunk.text,
                })

        return RAGResponse(
            query=query,
            answer=answer,
            pocket_id=pocket_id,
            sources=sources,
            metrics=metrics,
            retrieval_time=retrieval.retrieval_time,
            generation_time=generation_time,
        )

    async def generate_response_async(
        self,
        query: str,
        pocket_id: str,
        top_k: int | None = None,
        min_score: float | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        include_sources: bool = True,
    ) -> RAGResponse:
        """Async version of generate_response."""
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.generate_response(
                query=query,
                pocket_id=pocket_id,
                top_k=top_k,
                min_score=min_score,
                temperature=temperature,
                max_tokens=max_tokens,
                include_sources=include_sources,
            ),
        )

    def _build_prompt(self, query: str, context: str) -> str:
        """Build the user prompt with context.

        Args:
            query: User's question.
            context: Retrieved context.

        Returns:
            Formatted prompt.
        """
        return f"""Based on the following context, please answer the question. If the answer cannot be found in the context, say so clearly.

Context:
{context}

Question: {query}

Answer:"""

    def search_only(
        self,
        query: str,
        pocket_id: str,
        top_k: int | None = None,
        min_score: float | None = None,
    ) -> list[dict[str, Any]]:
        """Search without generating a response.

        Useful for semantic search or when you want to handle
        the response generation yourself.

        Args:
            query: Search query.
            pocket_id: Pocket to search in.
            top_k: Number of results.
            min_score: Minimum score threshold.

        Returns:
            List of search results as dictionaries.
        """
        retrieval = self.retrieve(
            query=query,
            pocket_id=pocket_id,
            top_k=top_k,
            min_score=min_score,
        )

        return [
            {
                "id": chunk.id,
                "score": round(chunk.score, 4),
                "text": chunk.text,
                "document_path": chunk.document_path,
                "document_id": chunk.document_id,
                "chunk_index": chunk.chunk_index,
            }
            for chunk in retrieval.chunks
        ]

    def multi_pocket_search(
        self,
        query: str,
        pocket_ids: list[str],
        top_k: int | None = None,
        min_score: float | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """Search across multiple pockets.

        Args:
            query: Search query.
            pocket_ids: List of pockets to search.
            top_k: Number of results per pocket.
            min_score: Minimum score threshold.

        Returns:
            Dictionary mapping pocket_id to search results.
        """
        results = {}

        for pocket_id in pocket_ids:
            try:
                results[pocket_id] = self.search_only(
                    query=query,
                    pocket_id=pocket_id,
                    top_k=top_k,
                    min_score=min_score,
                )
            except Exception as e:
                logger.error(f"Search failed for pocket {pocket_id}: {e}")
                results[pocket_id] = []

        return results


# Global singleton
_retriever: RAGRetriever | None = None


def get_retriever() -> RAGRetriever:
    """Get the global retriever instance."""
    global _retriever
    if _retriever is None:
        _retriever = RAGRetriever()
    return _retriever
