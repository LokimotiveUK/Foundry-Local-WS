"""RAG API routes."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from src.core.config import Settings, get_settings
from src.core.models import RAGPocket
from src.rag.embeddings import EmbeddingService, get_embedding_service
from src.rag.ingest import IngestionResult, IngestionService, get_ingestion_service
from src.rag.pockets import PocketManager, get_pocket_manager
from src.rag.retriever import RAGResponse, RAGRetriever, get_retriever
from src.rag.vector_store import VectorStore, get_vector_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["rag"])


# Request/Response models
class PocketCreateRequest(BaseModel):
    """Request to create a new pocket."""

    id: str
    name: str
    description: str
    system_prompt: str | None = None
    chunk_size: int = 500
    chunk_overlap: int = 100
    color: str = "#808080"
    icon: str = "folder"


class PocketUpdateRequest(BaseModel):
    """Request to update a pocket."""

    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    chunk_size: int | None = None
    chunk_overlap: int | None = None
    color: str | None = None
    icon: str | None = None


class QueryRequest(BaseModel):
    """Request for RAG query."""

    query: str
    pocket_id: str
    top_k: int | None = None
    min_score: float | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    include_sources: bool = True


class SearchRequest(BaseModel):
    """Request for semantic search."""

    query: str
    pocket_id: str
    top_k: int | None = None
    min_score: float | None = None


class IngestRequest(BaseModel):
    """Request to ingest documents."""

    pocket_id: str
    force: bool = False


# Pocket management endpoints
@router.get("/pockets", response_model=list[RAGPocket])
async def list_pockets(
    pocket_manager: PocketManager = Depends(get_pocket_manager),
) -> list[RAGPocket]:
    """List all RAG pockets."""
    return pocket_manager.list_pockets()


@router.get("/pockets/{pocket_id}", response_model=RAGPocket)
async def get_pocket(
    pocket_id: str,
    pocket_manager: PocketManager = Depends(get_pocket_manager),
) -> RAGPocket:
    """Get a specific pocket."""
    try:
        return pocket_manager.get_pocket(pocket_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/pockets", response_model=RAGPocket)
async def create_pocket(
    request: PocketCreateRequest,
    pocket_manager: PocketManager = Depends(get_pocket_manager),
) -> RAGPocket:
    """Create a new pocket."""
    try:
        return pocket_manager.create_pocket(
            pocket_id=request.id,
            name=request.name,
            description=request.description,
            system_prompt=request.system_prompt,
            chunk_size=request.chunk_size,
            chunk_overlap=request.chunk_overlap,
            color=request.color,
            icon=request.icon,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/pockets/{pocket_id}", response_model=RAGPocket)
async def update_pocket(
    pocket_id: str,
    request: PocketUpdateRequest,
    pocket_manager: PocketManager = Depends(get_pocket_manager),
) -> RAGPocket:
    """Update a pocket."""
    try:
        return pocket_manager.update_pocket(
            pocket_id,
            **request.model_dump(exclude_unset=True),
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/pockets/{pocket_id}")
async def delete_pocket(
    pocket_id: str,
    delete_files: bool = False,
    pocket_manager: PocketManager = Depends(get_pocket_manager),
    vector_store: VectorStore = Depends(get_vector_store),
) -> dict[str, str]:
    """Delete a pocket."""
    try:
        # Delete vectors first
        vector_store.delete_collection(pocket_id)
        pocket_manager.delete_pocket(pocket_id, delete_files=delete_files)
        return {"status": "deleted", "pocket_id": pocket_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


# Document management endpoints
@router.get("/pockets/{pocket_id}/documents")
async def list_documents(
    pocket_id: str,
    pocket_manager: PocketManager = Depends(get_pocket_manager),
) -> list[dict[str, Any]]:
    """List documents in a pocket."""
    try:
        docs = pocket_manager.list_documents(pocket_id)
        return [
            {
                "name": d.name,
                "path": str(d),
                "size": d.stat().st_size,
                "type": d.suffix.lower(),
            }
            for d in docs
        ]
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/pockets/{pocket_id}/documents/upload")
async def upload_document(
    pocket_id: str,
    file: UploadFile = File(...),
    ingest: bool = True,
    pocket_manager: PocketManager = Depends(get_pocket_manager),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
) -> dict[str, Any]:
    """Upload a document to a pocket.

    Args:
        pocket_id: Target pocket.
        file: File to upload.
        ingest: Automatically ingest after upload.
    """
    try:
        pocket_path = pocket_manager.get_pocket_path(pocket_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Validate file type
    allowed_extensions = {".txt", ".md", ".pdf", ".docx"}
    file_ext = Path(file.filename).suffix.lower() if file.filename else ""

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}",
        )

    # Save file
    file_path = pocket_path / file.filename
    try:
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")

    result = {
        "filename": file.filename,
        "path": str(file_path),
        "size": len(content),
        "uploaded": True,
        "ingested": False,
    }

    # Optionally ingest
    if ingest:
        ingest_result = ingestion_service.ingest_file(file_path, pocket_id)
        result["ingested"] = ingest_result.success
        result["chunk_count"] = ingest_result.chunk_count
        if ingest_result.error:
            result["ingest_error"] = ingest_result.error

    return result


@router.delete("/pockets/{pocket_id}/documents/{filename}")
async def delete_document(
    pocket_id: str,
    filename: str,
    pocket_manager: PocketManager = Depends(get_pocket_manager),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
) -> dict[str, Any]:
    """Delete a document from a pocket."""
    try:
        pocket_path = pocket_manager.get_pocket_path(pocket_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

    file_path = pocket_path / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Document not found: {filename}")

    # Delete vectors
    vectors_deleted = ingestion_service.delete_document(pocket_id, str(file_path))

    # Delete file
    file_path.unlink()

    return {
        "filename": filename,
        "deleted": True,
        "vectors_deleted": vectors_deleted,
    }


# Ingestion endpoints
@router.post("/ingest")
async def ingest_documents(
    request: IngestRequest,
    ingestion_service: IngestionService = Depends(get_ingestion_service),
) -> dict[str, Any]:
    """Ingest all documents in a pocket."""
    try:
        results = ingestion_service.ingest_pocket(
            pocket_id=request.pocket_id,
            force=request.force,
            show_progress=False,  # No CLI progress bar in API
        )

        success_count = sum(1 for r in results if r.success)
        total_chunks = sum(r.chunk_count for r in results if r.success)

        return {
            "pocket_id": request.pocket_id,
            "documents_processed": len(results),
            "documents_successful": success_count,
            "total_chunks": total_chunks,
            "results": [
                {
                    "document": r.document_path.split("/")[-1],
                    "success": r.success,
                    "chunks": r.chunk_count,
                    "error": r.error,
                }
                for r in results
            ],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest/file")
async def ingest_file(
    pocket_id: str = Form(...),
    file_path: str = Form(...),
    force: bool = Form(False),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
) -> dict[str, Any]:
    """Ingest a specific file."""
    result = ingestion_service.ingest_file(
        file_path=file_path,
        pocket_id=pocket_id,
        force=force,
    )

    return {
        "document_id": result.document_id,
        "document_path": result.document_path,
        "pocket_id": result.pocket_id,
        "success": result.success,
        "chunk_count": result.chunk_count,
        "vector_count": len(result.vector_ids),
        "processing_time": result.processing_time,
        "error": result.error,
    }


@router.get("/ingest/status/{pocket_id}")
async def get_ingestion_status(
    pocket_id: str,
    ingestion_service: IngestionService = Depends(get_ingestion_service),
) -> dict[str, Any]:
    """Get ingestion status for a pocket."""
    try:
        return ingestion_service.get_ingestion_status(pocket_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


# Query and search endpoints
@router.post("/query")
async def query_rag(
    request: QueryRequest,
    retriever: RAGRetriever = Depends(get_retriever),
) -> dict[str, Any]:
    """Query a RAG pocket and get an AI-generated response.

    This retrieves relevant context from the pocket's documents
    and generates a response using the local LLM.
    """
    try:
        response = await retriever.generate_response_async(
            query=request.query,
            pocket_id=request.pocket_id,
            top_k=request.top_k,
            min_score=request.min_score,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            include_sources=request.include_sources,
        )

        return {
            "query": response.query,
            "answer": response.answer,
            "pocket_id": response.pocket_id,
            "sources": response.sources,
            "metrics": response.metrics.model_dump() if response.metrics else None,
            "retrieval_time": response.retrieval_time,
            "generation_time": response.generation_time,
        }

    except Exception as e:
        logger.error(f"RAG query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def search_documents(
    request: SearchRequest,
    retriever: RAGRetriever = Depends(get_retriever),
) -> dict[str, Any]:
    """Semantic search without AI response generation.

    Returns matching document chunks ranked by relevance.
    """
    try:
        results = retriever.search_only(
            query=request.query,
            pocket_id=request.pocket_id,
            top_k=request.top_k,
            min_score=request.min_score,
        )

        return {
            "query": request.query,
            "pocket_id": request.pocket_id,
            "result_count": len(results),
            "results": results,
        }

    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search/multi")
async def search_multi_pocket(
    query: str,
    pocket_ids: list[str],
    top_k: int = 5,
    min_score: float = 0.05,
    retriever: RAGRetriever = Depends(get_retriever),
) -> dict[str, Any]:
    """Search across multiple pockets."""
    try:
        results = retriever.multi_pocket_search(
            query=query,
            pocket_ids=pocket_ids,
            top_k=top_k,
            min_score=min_score,
        )

        return {
            "query": query,
            "pockets_searched": pocket_ids,
            "results": results,
        }

    except Exception as e:
        logger.error(f"Multi-pocket search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Stats and health endpoints
@router.get("/stats")
async def get_rag_stats(
    pocket_manager: PocketManager = Depends(get_pocket_manager),
    vector_store: VectorStore = Depends(get_vector_store),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
) -> dict[str, Any]:
    """Get overall RAG system statistics."""
    pockets = pocket_manager.list_pockets()
    collections = vector_store.list_collections()

    total_vectors = 0
    total_documents = 0

    pocket_stats = []
    for pocket in pockets:
        stats = vector_store.get_collection_stats(pocket.id)
        docs = pocket_manager.list_documents(pocket.id)
        total_vectors += stats.get("vector_count", 0)
        total_documents += len(docs)

        pocket_stats.append({
            "id": pocket.id,
            "name": pocket.name,
            "document_count": len(docs),
            "vector_count": stats.get("vector_count", 0),
        })

    return {
        "pocket_count": len(pockets),
        "collection_count": len(collections),
        "total_documents": total_documents,
        "total_vectors": total_vectors,
        "embedding_model": embedding_service.model_name,
        "embedding_dimension": embedding_service.dimension,
        "embedding_loaded": embedding_service.is_loaded(),
        "pockets": pocket_stats,
    }


@router.get("/stats/{pocket_id}")
async def get_pocket_stats(
    pocket_id: str,
    pocket_manager: PocketManager = Depends(get_pocket_manager),
    vector_store: VectorStore = Depends(get_vector_store),
) -> dict[str, Any]:
    """Get statistics for a specific pocket."""
    try:
        pocket = pocket_manager.get_pocket(pocket_id)
        stats = vector_store.get_collection_stats(pocket_id)
        docs = pocket_manager.list_documents(pocket_id)

        return {
            "pocket": pocket.model_dump(),
            "collection_stats": stats,
            "documents": [
                {
                    "name": d.name,
                    "size": d.stat().st_size,
                    "type": d.suffix.lower(),
                }
                for d in docs
            ],
        }

    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
