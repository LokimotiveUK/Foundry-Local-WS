"""Configuration management for Mac Assistant."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # Paths
    app_dir: Path = Field(default_factory=lambda: Path.home() / ".mac-assistant")
    data_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent / "data")

    # Foundry Local
    default_model: str = "qwen2.5-1.5b"
    model_ttl: int = 3600  # 1 hour

    # Context management
    context_window: int = 4096
    max_response_tokens: int = 2048
    temperature: float = 0.7

    # RAG settings
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    chunk_size: int = 500
    chunk_overlap: int = 100
    top_k: int = 5
    min_similarity: float = 0.05

    # Vector database (embedded Qdrant)
    qdrant_path: Path = Field(default_factory=lambda: Path.home() / ".mac-assistant" / "qdrant")

    # API settings
    api_host: str = "127.0.0.1"
    api_port: int = 8000

    # Features
    verbose_mode: bool = True
    save_chat_history: bool = True

    # Database
    db_path: Path = Field(default_factory=lambda: Path.home() / ".mac-assistant" / "assistant.db")

    class Config:
        env_prefix = "MAC_ASSISTANT_"
        env_file = ".env"

    def model_post_init(self, __context: Any) -> None:
        """Ensure directories exist after initialization."""
        self.app_dir.mkdir(parents=True, exist_ok=True)
        self.qdrant_path.mkdir(parents=True, exist_ok=True)

        # Ensure pockets directories exist
        pockets_dir = self.data_dir / "pockets"
        for pocket in ["medical", "finance", "study", "writing"]:
            (pockets_dir / pocket).mkdir(parents=True, exist_ok=True)

    def save(self) -> None:
        """Save current settings to config file."""
        config_file = self.app_dir / "config.json"
        config_data = {
            "default_model": self.default_model,
            "context_window": self.context_window,
            "max_response_tokens": self.max_response_tokens,
            "temperature": self.temperature,
            "embedding_model": self.embedding_model,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "top_k": self.top_k,
            "verbose_mode": self.verbose_mode,
            "save_chat_history": self.save_chat_history,
        }
        with open(config_file, "w") as f:
            json.dump(config_data, f, indent=2)

    @classmethod
    def load(cls) -> "Settings":
        """Load settings from config file if it exists."""
        settings = cls()
        config_file = settings.app_dir / "config.json"

        if config_file.exists():
            with open(config_file) as f:
                config_data = json.load(f)
                for key, value in config_data.items():
                    if hasattr(settings, key):
                        setattr(settings, key, value)

        return settings


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings.load()


# Default RAG pocket configurations
DEFAULT_POCKETS = {
    "medical": {
        "name": "Medical",
        "description": "Medical records, lab results, prescriptions, doctor notes",
        "icon": "heart.text.square",
        "system_prompt": """You are a helpful assistant analyzing personal healthcare documents.
Be precise with medical terminology and dates. If you're unsure about something, say so.
Never provide medical advice - only summarize and explain the documents provided.
Always cite which document information comes from.""",
        "chunk_size": 400,  # Smaller for precision
        "color": "#FF6B6B",
    },
    "finance": {
        "name": "Finance",
        "description": "Bank statements, tax returns, investment reports, receipts",
        "icon": "dollarsign.circle",
        "system_prompt": """You are a helpful assistant analyzing personal financial documents.
Be precise with numbers, dates, and account references. Always clarify which document a figure comes from.
Never provide financial advice - only summarize and explain the documents provided.
Format currency values consistently.""",
        "chunk_size": 600,  # Larger for context
        "color": "#4ECDC4",
    },
    "study": {
        "name": "Study",
        "description": "Textbooks, lecture notes, research papers, study guides",
        "icon": "book.closed",
        "system_prompt": """You are a knowledgeable study assistant helping understand academic materials.
Explain concepts clearly and relate them to the source materials.
Provide examples when helpful. If asked about topics not in the documents, say so.
Help connect ideas across different documents when relevant.""",
        "chunk_size": 500,
        "color": "#45B7D1",
    },
    "writing": {
        "name": "Writing",
        "description": "Manuscripts, drafts, reference materials, style guides",
        "icon": "pencil.and.outline",
        "system_prompt": """You are a thoughtful writing assistant with access to reference materials.
Help with consistency, continuity, and style based on the provided documents.
Reference specific passages when discussing the materials.
Maintain the author's voice and intentions.""",
        "chunk_size": 800,  # Larger for narrative flow
        "color": "#96CEB4",
    },
}
