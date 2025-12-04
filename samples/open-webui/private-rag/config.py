# Private RAG Configuration
# All settings for local-only RAG processing

import json
import os
from pathlib import Path

# === Paths ===
BASE_DIR = Path(__file__).parent
DOCUMENTS_DIR = BASE_DIR / "documents"
CATEGORIES_FILE = BASE_DIR / "categories.json"

# Create documents directory if it doesn't exist
DOCUMENTS_DIR.mkdir(exist_ok=True)

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

# === Default Categories ===
DEFAULT_CATEGORIES = {
    "healthcare": {
        "description": "Medical records, lab results, prescriptions, doctor notes",
        "icon": "🏥",
        "system_prompt": """You are a helpful assistant analyzing personal healthcare documents.
Be precise with medical terminology and dates. If you're unsure about something, say so.
Never provide medical advice - only summarize and explain the documents provided."""
    },
    "finance": {
        "description": "Bank statements, tax returns, investment reports, receipts",
        "icon": "💰",
        "system_prompt": """You are a helpful assistant analyzing personal financial documents.
Be precise with numbers and dates. Always clarify which document a figure comes from.
Never provide financial advice - only summarize and explain the documents provided."""
    }
}


def load_categories() -> dict:
    """Load categories from JSON file, or return defaults if not found."""
    if CATEGORIES_FILE.exists():
        try:
            with open(CATEGORIES_FILE, "r", encoding="utf-8") as f:
                categories = json.load(f)
                # Add path for each category
                for name, info in categories.items():
                    info["path"] = DOCUMENTS_DIR / name
                    info["path"].mkdir(exist_ok=True)
                return categories
        except (json.JSONDecodeError, IOError):
            pass

    # Return defaults and save them
    save_categories(DEFAULT_CATEGORIES)
    return load_categories()


def save_categories(categories: dict) -> bool:
    """Save categories to JSON file."""
    try:
        # Remove path objects before saving (they're not JSON serializable)
        save_data = {}
        for name, info in categories.items():
            save_data[name] = {
                "description": info.get("description", ""),
                "icon": info.get("icon", "📁"),
                "system_prompt": info.get("system_prompt", "You are a helpful assistant analyzing documents.")
            }

        with open(CATEGORIES_FILE, "w", encoding="utf-8") as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False)
        return True
    except IOError:
        return False


def add_category(name: str, description: str, icon: str = "📁", system_prompt: str = None) -> bool:
    """Add a new category."""
    categories = load_categories()

    # Normalize name (lowercase, no spaces)
    name = name.lower().replace(" ", "-").replace("_", "-")

    if name in categories:
        return False  # Already exists

    # Create directory
    category_dir = DOCUMENTS_DIR / name
    category_dir.mkdir(exist_ok=True)

    # Add to categories
    if system_prompt is None:
        system_prompt = f"""You are a helpful assistant analyzing personal {name} documents.
Be precise with details and dates. Always clarify which document information comes from.
Only answer based on the provided context. If the answer isn't in the context, say so."""

    categories[name] = {
        "description": description,
        "icon": icon,
        "system_prompt": system_prompt,
        "path": category_dir
    }

    return save_categories(categories)


def delete_category(name: str) -> bool:
    """Delete a category (does not delete files)."""
    categories = load_categories()

    if name not in categories:
        return False

    del categories[name]
    return save_categories(categories)


def get_category_path(category_name: str) -> Path:
    """Get the path for a category."""
    return DOCUMENTS_DIR / category_name


# Load categories on module import
CATEGORIES = load_categories()

# Ensure all category directories exist
for name in CATEGORIES:
    (DOCUMENTS_DIR / name).mkdir(exist_ok=True)
