"""Tests for configuration."""

import tempfile
from pathlib import Path

import pytest

from src.core.config import Settings, DEFAULT_POCKETS


class TestSettings:
    """Test Settings class."""

    def test_default_values(self):
        """Test default setting values."""
        settings = Settings()

        assert settings.default_model == "qwen2.5-1.5b-instruct"
        assert settings.context_window == 4096
        assert settings.temperature == 0.7
        assert settings.verbose_mode is True

    def test_embedding_settings(self):
        """Test embedding-related settings."""
        settings = Settings()

        assert settings.embedding_model == "all-MiniLM-L6-v2"
        assert settings.embedding_dimension == 384
        assert settings.chunk_size == 500
        assert settings.chunk_overlap == 100

    def test_paths_created(self):
        """Test that app directories are created."""
        settings = Settings()

        assert settings.app_dir.exists()
        assert settings.qdrant_path.exists()


class TestDefaultPockets:
    """Test default RAG pocket configurations."""

    def test_required_pockets(self):
        """Test that required pockets exist."""
        required = ["medical", "finance", "study", "writing"]

        for pocket in required:
            assert pocket in DEFAULT_POCKETS

    def test_pocket_structure(self):
        """Test pocket configuration structure."""
        for name, config in DEFAULT_POCKETS.items():
            assert "name" in config
            assert "description" in config
            assert "system_prompt" in config
            assert "chunk_size" in config
            assert isinstance(config["chunk_size"], int)

    def test_medical_pocket(self):
        """Test medical pocket configuration."""
        medical = DEFAULT_POCKETS["medical"]

        assert "medical" in medical["description"].lower()
        assert medical["chunk_size"] == 400  # Smaller for precision
        assert "advice" in medical["system_prompt"].lower()

    def test_finance_pocket(self):
        """Test finance pocket configuration."""
        finance = DEFAULT_POCKETS["finance"]

        assert "finance" in finance["description"].lower() or "bank" in finance["description"].lower()
        assert finance["chunk_size"] == 600  # Larger for context
