"""Tests for RAG components."""

import tempfile
from pathlib import Path

import pytest

from src.core.config import DEFAULT_POCKETS
from src.rag.chunker import Chunk, DocumentChunker


class TestDocumentChunker:
    """Test DocumentChunker functionality."""

    def test_basic_chunking(self):
        """Test basic text chunking."""
        chunker = DocumentChunker(chunk_size=10, chunk_overlap=2)

        text = " ".join([f"word{i}" for i in range(25)])  # 25 words
        chunks = list(chunker.chunk_text(text, "/test/doc.txt"))

        assert len(chunks) >= 2
        assert all(isinstance(c, Chunk) for c in chunks)

    def test_chunk_metadata(self):
        """Test chunk metadata."""
        chunker = DocumentChunker(chunk_size=50, chunk_overlap=10)

        text = "This is a test document with some content."
        chunks = list(chunker.chunk_text(text, "/test/doc.txt", "doc123"))

        assert len(chunks) == 1
        chunk = chunks[0]

        assert chunk.document_id == "doc123"
        assert chunk.document_path == "/test/doc.txt"
        assert chunk.index == 0

        meta = chunk.to_metadata()
        assert meta["document_id"] == "doc123"
        assert meta["chunk_index"] == 0

    def test_overlap(self):
        """Test that chunks overlap correctly."""
        chunker = DocumentChunker(chunk_size=5, chunk_overlap=2)

        text = "word1 word2 word3 word4 word5 word6 word7 word8 word9 word10"
        chunks = list(chunker.chunk_text(text, "/test/doc.txt"))

        # With 5 words, 2 overlap, advance is 3
        # Chunk 1: word1-5, Chunk 2: word4-8, Chunk 3: word7-10
        assert len(chunks) >= 2

    def test_empty_text(self):
        """Test handling of empty text."""
        chunker = DocumentChunker()
        chunks = list(chunker.chunk_text("", "/test/doc.txt"))
        assert len(chunks) == 0

    def test_document_id_generation(self):
        """Test document ID generation is consistent."""
        chunker = DocumentChunker()

        id1 = chunker.generate_document_id("/path/to/doc.txt")
        id2 = chunker.generate_document_id("/path/to/doc.txt")
        id3 = chunker.generate_document_id("/path/to/other.txt")

        assert id1 == id2  # Same path = same ID
        assert id1 != id3  # Different path = different ID

    def test_estimate_chunks(self):
        """Test chunk estimation."""
        chunker = DocumentChunker(chunk_size=100, chunk_overlap=20)

        # Short text
        assert chunker.estimate_chunks("hello world") == 1

        # Long text
        long_text = " ".join(["word"] * 500)
        estimate = chunker.estimate_chunks(long_text)
        assert estimate > 1

    def test_text_file_extraction(self):
        """Test text file extraction."""
        chunker = DocumentChunker()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Test content for extraction.")
            temp_path = Path(f.name)

        try:
            text = chunker.extract_text(temp_path)
            assert "Test content" in text
        finally:
            temp_path.unlink()


class TestDefaultPockets:
    """Test default pocket configurations."""

    def test_all_pockets_have_system_prompts(self):
        """Test all pockets have system prompts."""
        for pocket_id, config in DEFAULT_POCKETS.items():
            assert "system_prompt" in config
            assert len(config["system_prompt"]) > 0

    def test_all_pockets_have_chunk_sizes(self):
        """Test all pockets have chunk sizes."""
        for pocket_id, config in DEFAULT_POCKETS.items():
            assert "chunk_size" in config
            assert config["chunk_size"] > 0

    def test_pocket_chunk_sizes_differ(self):
        """Test pocket chunk sizes are customized."""
        sizes = [config["chunk_size"] for config in DEFAULT_POCKETS.values()]
        # At least some pockets should have different sizes
        assert len(set(sizes)) > 1


class TestChunk:
    """Test Chunk dataclass."""

    def test_word_count(self):
        """Test word count property."""
        chunk = Chunk(
            text="This is a test with five words extra.",
            index=0,
            document_id="doc1",
            document_path="/test.txt",
            start_char=0,
            end_char=100,
        )
        assert chunk.word_count == 8

    def test_to_metadata(self):
        """Test metadata conversion."""
        chunk = Chunk(
            text="Test text",
            index=5,
            document_id="doc123",
            document_path="/path/to/doc.txt",
            start_char=100,
            end_char=200,
        )

        meta = chunk.to_metadata()

        assert meta["chunk_index"] == 5
        assert meta["document_id"] == "doc123"
        assert meta["document_path"] == "/path/to/doc.txt"
        assert meta["start_char"] == 100
        assert meta["end_char"] == 200
        assert meta["word_count"] == 2
