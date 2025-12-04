#!/usr/bin/env python3
"""
Document Ingestion for Private RAG

Processes documents from the documents/ folder and stores embeddings in Qdrant.
All processing is done locally - no data leaves your device.
"""

import hashlib
import re
from pathlib import Path
from typing import Generator

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

import config


def extract_text_from_file(file_path: Path) -> str:
    """Extract text content from various file types."""
    suffix = file_path.suffix.lower()

    if suffix in [".txt", ".md"]:
        return file_path.read_text(encoding="utf-8")

    elif suffix == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(file_path))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except ImportError:
            print(f"  [!] Install pypdf to process PDF files: pip install pypdf")
            return ""

    elif suffix == ".docx":
        try:
            from docx import Document
            doc = Document(str(file_path))
            return "\n".join(para.text for para in doc.paragraphs)
        except ImportError:
            print(f"  [!] Install python-docx to process Word files: pip install python-docx")
            return ""

    else:
        print(f"  [!] Unsupported file type: {suffix}")
        return ""


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> Generator[str, None, None]:
    """Split text into overlapping chunks by word count."""
    words = text.split()
    if not words:
        return

    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        if chunk.strip():
            yield chunk
        start = end - overlap
        if start < 0:
            start = 0
        if end >= len(words):
            break


def generate_chunk_id(doc_path: str, chunk_index: int) -> str:
    """Generate a unique ID for a document chunk."""
    content = f"{doc_path}:{chunk_index}"
    return hashlib.md5(content.encode()).hexdigest()


def get_category_from_path(file_path: Path) -> str:
    """Determine document category from file path."""
    path_str = str(file_path).lower()
    for category in config.CATEGORIES:
        if category in path_str:
            return category
    return "general"


def ingest_documents():
    """Main ingestion function - processes all documents and stores in Qdrant."""
    print("=" * 60)
    print("Private RAG Document Ingestion")
    print("=" * 60)
    print(f"\nConfiguration:")
    print(f"  Embedding model: {config.EMBEDDING_MODEL}")
    print(f"  Chunk size: {config.CHUNK_SIZE} words")
    print(f"  Chunk overlap: {config.CHUNK_OVERLAP} words")
    print(f"  Qdrant: {config.QDRANT_HOST}:{config.QDRANT_PORT}")
    print(f"  Collection: {config.COLLECTION_NAME}")

    # Initialize embedding model (downloads on first run)
    print(f"\nLoading embedding model '{config.EMBEDDING_MODEL}'...")
    model = SentenceTransformer(config.EMBEDDING_MODEL)
    print("  Model loaded successfully!")

    # Connect to Qdrant
    print(f"\nConnecting to Qdrant...")
    client = QdrantClient(host=config.QDRANT_HOST, port=config.QDRANT_PORT)

    # Create or recreate collection
    collections = [c.name for c in client.get_collections().collections]
    if config.COLLECTION_NAME in collections:
        print(f"  Collection '{config.COLLECTION_NAME}' exists - will add/update documents")
    else:
        print(f"  Creating collection '{config.COLLECTION_NAME}'...")
        client.create_collection(
            collection_name=config.COLLECTION_NAME,
            vectors_config=VectorParams(
                size=config.EMBEDDING_DIMENSION,
                distance=Distance.COSINE
            )
        )

    # Find all documents
    supported_extensions = [".txt", ".md", ".pdf", ".docx"]
    documents = []
    for ext in supported_extensions:
        documents.extend(config.DOCUMENTS_DIR.rglob(f"*{ext}"))

    if not documents:
        print(f"\n[!] No documents found in {config.DOCUMENTS_DIR}")
        print(f"    Add .txt, .md, .pdf, or .docx files to category folders:")
        for cat_name in config.CATEGORIES:
            print(f"    - documents/{cat_name}/")
        return

    print(f"\nFound {len(documents)} documents to process:")
    for doc in documents:
        print(f"  - {doc.relative_to(config.BASE_DIR)}")

    # Process each document
    all_points = []
    total_chunks = 0

    print(f"\nProcessing documents...")
    for doc_path in tqdm(documents, desc="Documents"):
        # Extract text
        text = extract_text_from_file(doc_path)
        if not text.strip():
            print(f"  [!] No text extracted from {doc_path.name}")
            continue

        # Get category
        category = get_category_from_path(doc_path)

        # Chunk the document
        chunks = list(chunk_text(text, config.CHUNK_SIZE, config.CHUNK_OVERLAP))

        # Generate embeddings and create points
        for i, chunk in enumerate(chunks):
            # Generate embedding
            embedding = model.encode(chunk).tolist()

            # Create point with metadata
            point_id = generate_chunk_id(str(doc_path), i)
            point = PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "text": chunk,
                    "document": doc_path.name,
                    "document_path": str(doc_path.relative_to(config.BASE_DIR)),
                    "category": category,
                    "chunk_index": i,
                    "total_chunks": len(chunks)
                }
            )
            all_points.append(point)

        total_chunks += len(chunks)

    # Upsert all points to Qdrant
    if all_points:
        print(f"\nStoring {len(all_points)} chunks in Qdrant...")
        # Batch upsert in groups of 100
        batch_size = 100
        for i in range(0, len(all_points), batch_size):
            batch = all_points[i:i + batch_size]
            client.upsert(
                collection_name=config.COLLECTION_NAME,
                points=batch
            )
        print("  Done!")

    # Summary
    print(f"\n" + "=" * 60)
    print("Ingestion Complete!")
    print("=" * 60)
    print(f"  Documents processed: {len(documents)}")
    print(f"  Total chunks created: {total_chunks}")
    print(f"  Vectors stored in: {config.COLLECTION_NAME}")
    print(f"\nYou can now run: python rag_server.py")


if __name__ == "__main__":
    ingest_documents()
