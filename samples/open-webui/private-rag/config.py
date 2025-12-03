# Private RAG Configuration
# All settings for local-only RAG processing

import os
from pathlib import Path

# === Paths ===
BASE_DIR = Path(__file__).parent
DOCUMENTS_DIR = BASE_DIR / "documents"
HEALTHCARE_DIR = DOCUMENTS_DIR / "healthcare"
FINANCE_DIR = DOCUMENTS_DIR / "finance"

# Create directories if they don't exist
DOCUMENTS_DIR.mkdir(exist_ok=True)
HEALTHCARE_DIR.mkdir(exist_ok=True)
FINANCE_DIR.mkdir(exist_ok=True)

# === Qdrant Vector Database ===
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
COLLECTION_NAME = "private_docs"

# === Embedding Model (runs locally) ===
# all-MiniLM-L6-v2: Fast, 384 dimensions, ~90MB
# all-mpnet-base-v2: Better quality, 768 dimensions, ~420MB
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
EMBEDDING_DIMENSION = 384  # Match the model above

# === Chunking Settings ===
CHUNK_SIZE = 500  # Words per chunk
CHUNK_OVERLAP = 100  # Overlap for context continuity

# === Retrieval Settings ===
TOP_K = 5  # Number of chunks to retrieve
MIN_SCORE = 0.3  # Minimum similarity score (0-1)

# === Foundry Local ===
# These are auto-detected by the foundry-local-sdk
FOUNDRY_MODEL = os.getenv("FOUNDRY_MODEL", "phi-3.5-mini")

# === RAG Server ===
RAG_SERVER_HOST = "0.0.0.0"
RAG_SERVER_PORT = 8000

# === Document Categories ===
# Used for filtering and organizing retrievals
CATEGORIES = {
    "healthcare": {
        "path": HEALTHCARE_DIR,
        "description": "Medical records, lab results, prescriptions, doctor notes",
        "system_prompt": """You are a helpful assistant analyzing personal healthcare documents.
Be precise with medical terminology and dates. If you're unsure about something, say so.
Never provide medical advice - only summarize and explain the documents provided."""
    },
    "finance": {
        "path": FINANCE_DIR,
        "description": "Bank statements, tax returns, investment reports, receipts",
        "system_prompt": """You are a helpful assistant analyzing personal financial documents.
Be precise with numbers and dates. Always clarify which document a figure comes from.
Never provide financial advice - only summarize and explain the documents provided."""
    }
}
