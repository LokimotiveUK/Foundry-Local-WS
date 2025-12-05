#!/usr/bin/env python3
"""
Private RAG Server

A FastAPI server that provides RAG capabilities for Open WebUI.
Connects to Qdrant for retrieval and Foundry Local for generation.
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

import openai
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
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
    query: str = Field(..., description="The question to ask about your documents")
    category: Optional[str] = Field(None, description="Filter by category: 'healthcare', 'finance', 'job-search', or any custom category")
    top_k: Optional[int] = Field(5, description="Number of document chunks to retrieve")
    include_sources: Optional[bool] = Field(True, description="Include source documents in response")


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


import http.client
import time

# Cache for Foundry port detection
_foundry_port_cache = None
_foundry_port_cache_time = 0
_FOUNDRY_CACHE_TTL = 30  # Re-detect every 30 seconds


def _probe_foundry_port(host: str, port: int) -> bool:
    """Check if Foundry is responding on a specific port."""
    try:
        conn = http.client.HTTPConnection(host, port, timeout=2)
        conn.request("GET", "/v1/models")
        response = conn.getresponse()
        data = response.read().decode()
        conn.close()
        return "model" in data.lower()
    except:
        return False


def _detect_foundry_port(host: str) -> int:
    """Detect Foundry's dynamic port by probing common ranges."""
    global _foundry_port_cache, _foundry_port_cache_time

    # Check cached port first
    if _foundry_port_cache and _probe_foundry_port(host, _foundry_port_cache):
        return _foundry_port_cache

    # Probe common Foundry port ranges
    probe_ranges = [
        range(50400, 50450),   # Common range
        range(50000, 50050),
        range(51400, 51450),
        range(62800, 62900),
        range(5273, 5280),     # Default range
    ]

    for port_range in probe_ranges:
        for port in port_range:
            if _probe_foundry_port(host, port):
                _foundry_port_cache = port
                _foundry_port_cache_time = time.time()
                logger.info(f"Found Foundry on port {port}")
                return port

    return None


def get_foundry_endpoint(refresh: bool = False) -> str:
    """Get the Foundry Local endpoint (auto-detects dynamic port).

    When running in Docker, we need to use host.docker.internal to reach
    Foundry Local running on the host machine.

    Args:
        refresh: If True, ignore cached endpoint and re-detect
    """
    global foundry_endpoint, _foundry_port_cache, _foundry_port_cache_time

    # Determine host based on environment
    is_docker = os.path.exists("/.dockerenv") or os.getenv("DOCKER_CONTAINER")
    host = "host.docker.internal" if is_docker else "localhost"

    # Check for environment variable override first (but verify it works)
    env_endpoint = os.getenv("FOUNDRY_ENDPOINT")
    if env_endpoint and not refresh:
        # Verify the endpoint is actually responding
        try:
            # Extract port from endpoint
            import re
            match = re.search(r':(\d+)', env_endpoint)
            if match:
                port = int(match.group(1))
                if _probe_foundry_port(host, port):
                    return env_endpoint
                else:
                    logger.warning(f"FOUNDRY_ENDPOINT {env_endpoint} not responding, auto-detecting...")
        except:
            pass

    # Return cached endpoint if valid, recent, and still working
    if not refresh and foundry_endpoint and (time.time() - _foundry_port_cache_time) < _FOUNDRY_CACHE_TTL:
        return foundry_endpoint

    # Auto-detect Foundry port by probing
    logger.info("Auto-detecting Foundry port...")
    port = _detect_foundry_port(host)

    if port:
        endpoint = f"http://{host}:{port}/v1"
        logger.info(f"Using Foundry endpoint: {endpoint}")
        return endpoint

    # Fallback to env or default
    if env_endpoint:
        logger.warning(f"Could not detect Foundry, falling back to FOUNDRY_ENDPOINT: {env_endpoint}")
        return env_endpoint

    default = f"http://{host}:5273/v1"
    logger.warning(f"Could not detect Foundry, using default: {default}")
    return default


def retrieve_context(query: str, category: Optional[str] = None, top_k: int = 5) -> list[dict]:
    """Retrieve relevant document chunks from Qdrant."""
    # Generate query embedding
    query_embedding = embedding_model.encode(query).tolist()

    # Build filter if category specified
    filter_condition = None
    if category:
        # Reload categories to get latest
        categories = config.load_categories()
        if category in categories:
            from qdrant_client.models import FieldCondition, Filter, MatchValue
            filter_condition = Filter(
                must=[FieldCondition(key="category", match=MatchValue(value=category))]
            )

    # Search Qdrant using query_points (newer API)
    try:
        results = qdrant_client.query_points(
            collection_name=config.COLLECTION_NAME,
            query=query_embedding,
            limit=top_k,
            score_threshold=config.MIN_SCORE,
            query_filter=filter_condition
        )
        points = results.points
    except AttributeError:
        # Fallback for older qdrant-client versions
        results = qdrant_client.search(
            collection_name=config.COLLECTION_NAME,
            query_vector=query_embedding,
            limit=top_k,
            score_threshold=config.MIN_SCORE,
            query_filter=filter_condition
        )
        points = results

    # Format results
    chunks = []
    for result in points:
        chunks.append({
            "text": result.payload.get("text", ""),
            "document": result.payload.get("document", "unknown"),
            "document_path": result.payload.get("document_path", ""),
            "category": result.payload.get("category", "general"),
            "chunk_index": result.payload.get("chunk_index", 0),
            "score": result.score
        })

    return chunks


def generate_response(query: str, context_chunks: list[dict], category: Optional[str] = None, retry_on_fail: bool = True) -> str:
    """Generate response using Foundry Local with retrieved context.

    Args:
        query: The user's question
        context_chunks: Retrieved document chunks
        category: Optional category for system prompt selection
        retry_on_fail: If True, retry once with refreshed endpoint on connection failure
    """
    global foundry_endpoint

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
            max_tokens=2048  # Increased for longer responses
        )
        return response.choices[0].message.content
    except Exception as e:
        error_str = str(e).lower()
        is_connection_error = any(x in error_str for x in ["connection", "refused", "timeout", "unreachable"])

        if retry_on_fail and is_connection_error:
            # Foundry might have restarted with new port - try to refresh
            logger.warning(f"Connection failed to {foundry_endpoint}, attempting to refresh endpoint...")
            new_endpoint = get_foundry_endpoint(refresh=True)
            if new_endpoint != foundry_endpoint:
                logger.info(f"Foundry endpoint changed: {foundry_endpoint} -> {new_endpoint}")
                foundry_endpoint = new_endpoint
                return generate_response(query, context_chunks, category, retry_on_fail=False)

        logger.error(f"Error calling Foundry Local at {foundry_endpoint}: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"LLM generation failed. Foundry Local may not be running. Error: {str(e)}"
        )


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
    description="""Local RAG server for searching private documents.

Use this API to search your personal documents including:
- **Healthcare**: Medical records, lab results, prescriptions
- **Finance**: Bank statements, tax returns, investments
- **Job Search**: Resumes, cover letters, applications
- **Custom categories**: Any category you create

All processing happens locally - no data leaves your device.""",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware for Open WebUI access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for local development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    # Test if Foundry is actually reachable
    foundry_status = "unknown"
    try:
        client = openai.OpenAI(base_url=foundry_endpoint, api_key="local-key")
        models = client.models.list()
        foundry_status = "connected"
    except Exception as e:
        foundry_status = f"unreachable: {str(e)[:50]}"

    return {
        "status": "healthy",
        "embedding_model": config.EMBEDDING_MODEL,
        "qdrant": f"{config.QDRANT_HOST}:{config.QDRANT_PORT}",
        "foundry_endpoint": foundry_endpoint,
        "foundry_status": foundry_status,
        "model": config.FOUNDRY_MODEL
    }


@app.post("/refresh-foundry")
async def refresh_foundry_endpoint():
    """Force refresh of Foundry endpoint detection.

    Use this if Foundry Local has restarted and the port has changed.
    """
    global foundry_endpoint
    old_endpoint = foundry_endpoint
    new_endpoint = get_foundry_endpoint(refresh=True)
    foundry_endpoint = new_endpoint

    return {
        "status": "refreshed",
        "old_endpoint": old_endpoint,
        "new_endpoint": new_endpoint,
        "changed": old_endpoint != new_endpoint
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
    # Reload categories to get latest
    categories = config.load_categories()
    return {
        name: {
            "description": info.get("description", ""),
            "icon": info.get("icon", "📁"),
            "path": f"documents/{name}/"
        }
        for name, info in categories.items()
    }


@app.post("/categories")
async def create_category(name: str, description: str, icon: str = "📁", system_prompt: str = None):
    """Create a new document category."""
    if config.add_category(name, description, icon, system_prompt):
        return {"status": "success", "message": f"Created category: {name}"}
    else:
        raise HTTPException(status_code=400, detail=f"Category '{name}' already exists")


@app.delete("/categories/{name}")
async def delete_category_endpoint(name: str):
    """Delete a document category."""
    if config.delete_category(name):
        return {"status": "success", "message": f"Deleted category: {name}"}
    else:
        raise HTTPException(status_code=404, detail=f"Category '{name}' not found")


@app.get("/stats")
async def get_stats():
    """Get collection statistics."""
    try:
        info = qdrant_client.get_collection(config.COLLECTION_NAME)
        # Handle different qdrant-client versions
        vectors_count = getattr(info, 'vectors_count', None)
        if vectors_count is None:
            vectors_count = getattr(info, 'points_count', 0)
        points_count = getattr(info, 'points_count', vectors_count)
        status = getattr(info.status, 'name', str(info.status))
        return {
            "collection": config.COLLECTION_NAME,
            "vectors_count": vectors_count,
            "points_count": points_count,
            "status": status
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
