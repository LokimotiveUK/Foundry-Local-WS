"""RAG (Retrieval-Augmented Generation) module for Mac Assistant."""

from src.rag.pockets import PocketManager, get_pocket_manager
from src.rag.embeddings import EmbeddingService, get_embedding_service
from src.rag.vector_store import VectorStore, get_vector_store
from src.rag.chunker import DocumentChunker
from src.rag.ingest import IngestionService, get_ingestion_service
from src.rag.retriever import RAGRetriever, get_retriever

__all__ = [
    "PocketManager",
    "get_pocket_manager",
    "EmbeddingService",
    "get_embedding_service",
    "VectorStore",
    "get_vector_store",
    "DocumentChunker",
    "IngestionService",
    "get_ingestion_service",
    "RAGRetriever",
    "get_retriever",
]
