#!/usr/bin/env python3
"""
Private RAG Server

A FastAPI server that provides RAG capabilities for Open WebUI.
Connects to Qdrant for retrieval and Foundry Local for generation.
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional

import openai
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

import config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Global instances
embedding_model: SentenceTransformer = None
qdrant_client: QdrantClient = None
foundry_endpoint: str = None


class QueryRequest(BaseModel):
    """Request model for RAG queries."""
    query: str
    category: Optional[str] = None  # healthcare, finance, or None for all
    top_k: Optional[int] = None
    include_sources: Optional[bool] = True


class QueryResponse(BaseModel):
    """Response model for RAG queries."""
    answer: str
    sources: list[dict]
    category_used: Optional[str]


class SearchRequest(BaseModel):
    """Request model for semantic search only (no generation)."""
    query: str
    category: Optional[str] = None
    top_k: Optional[int] = None


class SearchResponse(BaseModel):
    """Response model for semantic search."""
    results: list[dict]


def get_foundry_endpoint() -> str:
    """Get the Foundry Local endpoint (auto-detects dynamic port)."""
    try:
        from foundry_local import FoundryLocalManager
        manager = FoundryLocalManager(bootstrap=False)
        if manager.is_service_running():
            return manager.endpoint
    except Exception as e:
        logger.warning(f"Could not auto-detect Foundry endpoint: {e}")

    # Fallback to default
    return "http://localhost:5273/v1"


def retrieve_context(query: str, category: Optional[str] = None, top_k: int = 5) -> list[dict]:
    """Retrieve relevant document chunks from Qdrant."""
    # Generate query embedding
    query_embedding = embedding_model.encode(query).tolist()

    # Build filter if category specified
    filter_condition = None
    if category and category in config.CATEGORIES:
        from qdrant_client.models import FieldCondition, Filter, MatchValue
        filter_condition = Filter(
            must=[FieldCondition(key="category", match=MatchValue(value=category))]
        )

    # Search Qdrant
    results = qdrant_client.search(
        collection_name=config.COLLECTION_NAME,
        query_vector=query_embedding,
        limit=top_k,
        score_threshold=config.MIN_SCORE,
        query_filter=filter_condition
    )

    # Format results
    chunks = []
    for result in results:
        chunks.append({
            "text": result.payload.get("text", ""),
            "document": result.payload.get("document", "unknown"),
            "document_path": result.payload.get("document_path", ""),
            "category": result.payload.get("category", "general"),
            "chunk_index": result.payload.get("chunk_index", 0),
            "score": result.score
        })

    return chunks


def generate_response(query: str, context_chunks: list[dict], category: Optional[str] = None) -> str:
    """Generate response using Foundry Local with retrieved context."""
    # Build context string
    context_parts = []
    for i, chunk in enumerate(context_chunks, 1):
        context_parts.append(f"[Source {i}: {chunk['document']}]\n{chunk['text']}")
    context = "\n\n".join(context_parts)

    # Get system prompt based on category
    if category and category in config.CATEGORIES:
        system_prompt = config.CATEGORIES[category]["system_prompt"]
    else:
        system_prompt = """You are a helpful assistant analyzing personal documents.
Be precise with details and dates. If information comes from multiple documents, cite which document.
Only answer based on the provided context. If the answer isn't in the context, say so."""

    # Build messages
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"""Based on the following documents, answer this question: {query}

Context from your documents:
{context}

Answer:"""}
    ]

    # Call Foundry Local
    client = openai.OpenAI(
        base_url=foundry_endpoint,
        api_key="local-key"
    )

    try:
        response = client.chat.completions.create(
            model=config.FOUNDRY_MODEL,
            messages=messages,
            temperature=0.3,  # Lower temperature for factual accuracy
            max_tokens=1024
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error calling Foundry Local: {e}")
        raise HTTPException(status_code=500, detail=f"LLM generation failed: {str(e)}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on startup."""
    global embedding_model, qdrant_client, foundry_endpoint

    logger.info("Starting Private RAG Server...")

    # Load embedding model
    logger.info(f"Loading embedding model: {config.EMBEDDING_MODEL}")
    embedding_model = SentenceTransformer(config.EMBEDDING_MODEL)

    # Connect to Qdrant
    logger.info(f"Connecting to Qdrant at {config.QDRANT_HOST}:{config.QDRANT_PORT}")
    qdrant_client = QdrantClient(host=config.QDRANT_HOST, port=config.QDRANT_PORT)

    # Verify collection exists
    collections = [c.name for c in qdrant_client.get_collections().collections]
    if config.COLLECTION_NAME not in collections:
        logger.warning(f"Collection '{config.COLLECTION_NAME}' not found. Run ingest.py first!")

    # Get Foundry endpoint
    foundry_endpoint = get_foundry_endpoint()
    logger.info(f"Using Foundry Local at: {foundry_endpoint}")

    logger.info("RAG Server ready!")
    yield

    # Cleanup
    logger.info("Shutting down...")


app = FastAPI(
    title="Private RAG API",
    description="Local RAG server for healthcare and finance documents",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "embedding_model": config.EMBEDDING_MODEL,
        "qdrant": f"{config.QDRANT_HOST}:{config.QDRANT_PORT}",
        "foundry_endpoint": foundry_endpoint
    }


@app.post("/query", response_model=QueryResponse)
async def query_rag(request: QueryRequest):
    """
    Query the RAG system.

    Retrieves relevant document chunks and generates an answer using Foundry Local.
    """
    top_k = request.top_k or config.TOP_K

    # Retrieve relevant chunks
    chunks = retrieve_context(request.query, request.category, top_k)

    if not chunks:
        return QueryResponse(
            answer="I couldn't find any relevant information in your documents for this query.",
            sources=[],
            category_used=request.category
        )

    # Generate response
    answer = generate_response(request.query, chunks, request.category)

    # Format sources
    sources = []
    if request.include_sources:
        for chunk in chunks:
            sources.append({
                "document": chunk["document"],
                "excerpt": chunk["text"][:200] + "..." if len(chunk["text"]) > 200 else chunk["text"],
                "relevance": round(chunk["score"], 3)
            })

    return QueryResponse(
        answer=answer,
        sources=sources,
        category_used=request.category
    )


@app.post("/search", response_model=SearchResponse)
async def search_documents(request: SearchRequest):
    """
    Semantic search only (no LLM generation).

    Returns relevant document chunks without generating an answer.
    """
    top_k = request.top_k or config.TOP_K
    chunks = retrieve_context(request.query, request.category, top_k)

    return SearchResponse(results=chunks)


@app.get("/categories")
async def list_categories():
    """List available document categories."""
    return {
        name: {
            "description": info["description"],
            "path": str(info["path"])
        }
        for name, info in config.CATEGORIES.items()
    }


@app.get("/stats")
async def get_stats():
    """Get collection statistics."""
    try:
        info = qdrant_client.get_collection(config.COLLECTION_NAME)
        return {
            "collection": config.COLLECTION_NAME,
            "vectors_count": info.vectors_count,
            "points_count": info.points_count,
            "status": info.status.name
        }
    except Exception as e:
        return {"error": str(e)}


@app.post("/ingest")
async def ingest_documents():
    """
    Trigger document ingestion.

    Re-indexes all documents in the documents folder.
    Called by the admin UI when new files are uploaded.
    """
    import subprocess
    import sys

    try:
        # Run ingest.py as subprocess
        result = subprocess.run(
            [sys.executable, "ingest.py"],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=config.BASE_DIR
        )

        if result.returncode == 0:
            return {"status": "success", "message": "Documents ingested successfully"}
        else:
            logger.error(f"Ingestion failed: {result.stderr}")
            raise HTTPException(status_code=500, detail=f"Ingestion failed: {result.stderr}")

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Ingestion timed out")
    except Exception as e:
        logger.error(f"Ingestion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/documents/{doc_path:path}")
async def delete_document(doc_path: str):
    """
    Delete a document from the vector store.

    Removes all chunks associated with the given document path.
    """
    from qdrant_client.models import Filter, FieldCondition, MatchValue

    try:
        qdrant_client.delete(
            collection_name=config.COLLECTION_NAME,
            points_selector=Filter(
                must=[FieldCondition(
                    key="document_path",
                    match=MatchValue(value=doc_path)
                )]
            )
        )
        return {"status": "success", "message": f"Deleted vectors for {doc_path}"}
    except Exception as e:
        logger.error(f"Delete error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(
        "rag_server:app",
        host=config.RAG_SERVER_HOST,
        port=config.RAG_SERVER_PORT,
        reload=True
    )
