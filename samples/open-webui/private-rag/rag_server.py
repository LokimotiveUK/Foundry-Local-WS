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


def get_foundry_endpoint() -> str:
    """Get the Foundry Local endpoint (auto-detects dynamic port).

    When running in Docker, we need to use host.docker.internal to reach
    Foundry Local running on the host machine.
    """
    # Check for environment variable override first
    env_endpoint = os.getenv("FOUNDRY_ENDPOINT")
    if env_endpoint:
        logger.info(f"Using FOUNDRY_ENDPOINT from environment: {env_endpoint}")
        return env_endpoint

    # Try auto-detection (only works when NOT in Docker)
    try:
        from foundry_local import FoundryLocalManager
        manager = FoundryLocalManager(bootstrap=False)
        if manager.is_service_running():
            endpoint = manager.endpoint
            # If we're in Docker, replace localhost with host.docker.internal
            if os.path.exists("/.dockerenv") or os.getenv("DOCKER_CONTAINER"):
                endpoint = endpoint.replace("localhost", "host.docker.internal")
                endpoint = endpoint.replace("127.0.0.1", "host.docker.internal")
            logger.info(f"Auto-detected Foundry endpoint: {endpoint}")
            return endpoint
    except Exception as e:
        logger.warning(f"Could not auto-detect Foundry endpoint: {e}")

    # Fallback - use host.docker.internal for Docker, localhost otherwise
    if os.path.exists("/.dockerenv") or os.getenv("DOCKER_CONTAINER"):
        return "http://host.docker.internal:5273/v1"
    return "http://localhost:5273/v1"


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
            max_tokens=2048  # Increased for longer responses
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
