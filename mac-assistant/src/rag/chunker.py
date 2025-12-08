"""Document chunking utilities."""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Generator

from src.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """A text chunk from a document."""

    text: str
    index: int
    document_id: str
    document_path: str
    start_char: int
    end_char: int

    @property
    def word_count(self) -> int:
        """Get word count of chunk."""
        return len(self.text.split())

    def to_metadata(self) -> dict:
        """Convert to metadata dict for vector store."""
        return {
            "chunk_index": self.index,
            "document_id": self.document_id,
            "document_path": self.document_path,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "word_count": self.word_count,
        }


class DocumentChunker:
    """Split documents into overlapping chunks."""

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 100,
        settings: Settings | None = None,
    ):
        """Initialize chunker.

        Args:
            chunk_size: Target words per chunk.
            chunk_overlap: Words to overlap between chunks.
            settings: Application settings.
        """
        self.settings = settings or get_settings()
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def generate_document_id(self, path: str | Path) -> str:
        """Generate a unique document ID.

        Args:
            path: Document path.

        Returns:
            MD5 hash of the path.
        """
        path_str = str(path)
        return hashlib.md5(path_str.encode()).hexdigest()[:16]

    def chunk_text(
        self,
        text: str,
        document_path: str,
        document_id: str | None = None,
    ) -> Generator[Chunk, None, None]:
        """Split text into overlapping chunks.

        Args:
            text: Text content to chunk.
            document_path: Source document path.
            document_id: Optional document ID. Generated if not provided.

        Yields:
            Chunk objects.
        """
        if not text.strip():
            return

        if document_id is None:
            document_id = self.generate_document_id(document_path)

        # Normalize whitespace but preserve paragraph structure
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)

        words = text.split()
        if not words:
            return

        chunk_index = 0
        start_word = 0
        start_char = 0

        while start_word < len(words):
            # Get chunk words
            end_word = min(start_word + self.chunk_size, len(words))
            chunk_words = words[start_word:end_word]
            chunk_text = ' '.join(chunk_words)

            # Calculate character positions
            end_char = start_char + len(chunk_text)

            yield Chunk(
                text=chunk_text,
                index=chunk_index,
                document_id=document_id,
                document_path=document_path,
                start_char=start_char,
                end_char=end_char,
            )

            chunk_index += 1

            # Move forward with overlap
            advance = self.chunk_size - self.chunk_overlap
            if advance <= 0:
                advance = max(1, self.chunk_size // 2)

            start_word += advance

            # Update start_char (approximate)
            if start_word < len(words):
                start_char = text.find(words[start_word], start_char)
                if start_char == -1:
                    start_char = end_char

    def chunk_file(self, file_path: Path) -> Generator[Chunk, None, None]:
        """Chunk a file based on its type.

        Args:
            file_path: Path to the file.

        Yields:
            Chunk objects.
        """
        text = self.extract_text(file_path)
        if text:
            yield from self.chunk_text(
                text=text,
                document_path=str(file_path),
            )

    def extract_text(self, file_path: Path) -> str:
        """Extract text from a file based on its type.

        Args:
            file_path: Path to the file.

        Returns:
            Extracted text content.
        """
        suffix = file_path.suffix.lower()

        try:
            if suffix in ('.txt', '.md'):
                return self._extract_text_file(file_path)
            elif suffix == '.pdf':
                return self._extract_pdf(file_path)
            elif suffix == '.docx':
                return self._extract_docx(file_path)
            else:
                logger.warning(f"Unsupported file type: {suffix}")
                return ""
        except Exception as e:
            logger.error(f"Failed to extract text from {file_path}: {e}")
            return ""

    def _extract_text_file(self, file_path: Path) -> str:
        """Extract text from plain text or markdown file."""
        encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']

        for encoding in encodings:
            try:
                return file_path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue

        logger.error(f"Could not decode {file_path} with any encoding")
        return ""

    def _extract_pdf(self, file_path: Path) -> str:
        """Extract text from PDF file."""
        try:
            from pypdf import PdfReader

            reader = PdfReader(file_path)
            text_parts = []

            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

            return '\n\n'.join(text_parts)

        except ImportError:
            logger.error("pypdf not installed. Install with: pip install pypdf")
            return ""
        except Exception as e:
            logger.error(f"Failed to extract PDF: {e}")
            return ""

    def _extract_docx(self, file_path: Path) -> str:
        """Extract text from Word document."""
        try:
            from docx import Document

            doc = Document(file_path)
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            return '\n\n'.join(paragraphs)

        except ImportError:
            logger.error("python-docx not installed. Install with: pip install python-docx")
            return ""
        except Exception as e:
            logger.error(f"Failed to extract DOCX: {e}")
            return ""

    def estimate_chunks(self, text: str) -> int:
        """Estimate number of chunks for text.

        Args:
            text: Text to estimate.

        Returns:
            Estimated chunk count.
        """
        words = len(text.split())
        if words <= self.chunk_size:
            return 1

        advance = self.chunk_size - self.chunk_overlap
        if advance <= 0:
            advance = max(1, self.chunk_size // 2)

        return max(1, (words - self.chunk_size) // advance + 1)
