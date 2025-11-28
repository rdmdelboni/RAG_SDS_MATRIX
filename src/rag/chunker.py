"""Smart text chunking for RAG knowledge base."""

from __future__ import annotations

from dataclasses import dataclass

try:  # Prefer modular package if available
    from langchain_text_splitters import RecursiveCharacterTextSplitter  # type: ignore
except ImportError:  # Fallback to legacy import path
    from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from ..config.settings import get_settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ChunkConfig:
    """Configuration for text chunking."""

    chunk_size: int = 1000
    chunk_overlap: int = 200
    separators: list[str] | None = None

    def __post_init__(self) -> None:
        if self.separators is None:
            self.separators = [
                "\n\n",  # Paragraph breaks
                "\n",  # Line breaks
                " ",  # Space
                "",  # Character level
            ]


class TextChunker:
    """Smart text chunking for documents."""

    def __init__(self, config: ChunkConfig | None = None) -> None:
        """Initialize chunker.

        Args:
            config: ChunkConfig (uses settings default if None)
        """
        if config is None:
            settings = get_settings()
            config = ChunkConfig(
                chunk_size=settings.processing.chunk_size,
                chunk_overlap=settings.processing.chunk_overlap,
            )

        self.config = config
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
            separators=config.separators,
            length_function=len,
        )

    def chunk_documents(self, documents: list[Document]) -> list[Document]:
        """Chunk a list of documents.

        Args:
            documents: List of Document objects

        Returns:
            List of chunked documents
        """
        if not documents:
            return []

        chunked = []
        for doc in documents:
            chunks = self.chunk_document(doc)
            chunked.extend(chunks)

        logger.info("Split %d documents into %d chunks", len(documents), len(chunked))
        return chunked

    def chunk_document(self, document: Document) -> list[Document]:
        """Chunk a single document.

        Args:
            document: Document to chunk

        Returns:
            List of chunked documents
        """
        chunks = self.splitter.split_documents([document])

        # Preserve metadata and add chunk info
        for i, chunk in enumerate(chunks):
            chunk.metadata["chunk_index"] = i
            chunk.metadata["total_chunks"] = len(chunks)

        logger.debug(
            "Split document '%s' into %d chunks",
            document.metadata.get("title", "unknown"),
            len(chunks),
        )

        return chunks

    def chunk_text(self, text: str, metadata: dict | None = None) -> list[Document]:
        """Chunk raw text into documents.

        Args:
            text: Text to chunk
            metadata: Optional metadata to attach

        Returns:
            List of chunked documents
        """
        if not metadata:
            metadata = {}

        # Create initial document
        doc = Document(page_content=text, metadata=metadata)

        # Split and return
        return self.chunk_document(doc)
