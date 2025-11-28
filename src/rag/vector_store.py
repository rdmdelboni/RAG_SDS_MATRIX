"""ChromaDB vector store for RAG knowledge base."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langchain_chroma import Chroma
from langchain_core.documents import Document

from ..config.settings import get_settings
from ..models import get_ollama_client
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SearchResult:
    """Result from vector store search."""

    content: str
    metadata: dict[str, Any]
    score: float
    source: str = ""

    def __post_init__(self) -> None:
        self.source = self.metadata.get("source", "unknown")


class VectorStore:
    """ChromaDB vector store for RAG knowledge base.

    Uses Ollama embeddings (qwen3-embedding:4b) for document embedding
    and similarity search.
    """

    COLLECTION_NAME = "sds_knowledge_base"

    def __init__(self, persist_directory: Path | None = None) -> None:
        """Initialize vector store.

        Args:
            persist_directory: Path to ChromaDB storage (uses settings default if None)
        """
        self.persist_directory = persist_directory or get_settings().paths.chroma_db
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        # Get embeddings from Ollama client (lazy - don't call yet)
        self.ollama = get_ollama_client()
        self._embeddings = None  # Lazy load embeddings
        self._embeddings_initialized = False

        # Initialize ChromaDB
        self._db: Chroma | None = None

        logger.info("VectorStore initialized at: %s", self.persist_directory)

    @property
    def embeddings(self):
        """Get embeddings (lazy initialization)."""
        if not self._embeddings_initialized:
            try:
                self._embeddings = self.ollama.get_embeddings()
                self._embeddings_initialized = True
            except Exception as e:
                logger.error("Failed to initialize embeddings: %s", e)
                self._embeddings_initialized = True
        return self._embeddings

    @property
    def db(self) -> Chroma:
        """Get or create ChromaDB instance (lazy initialization)."""
        if self._db is None:
            self._db = Chroma(
                collection_name=self.COLLECTION_NAME,
                embedding_function=self.embeddings,
                persist_directory=str(self.persist_directory),
            )
        return self._db

    # === Health/Readiness ===

    def ensure_ready(self) -> bool:
        """Ensure the underlying vector store is ready.

        Returns:
            True if ready, False otherwise (after attempting re-init)
        """
        try:
            # Try a lightweight call to ensure the collection is accessible
            _ = self.db._collection.count()  # type: ignore[attr-defined]
            return True
        except Exception as e:
            logger.warning("Vector store not ready, reinitializing: %s", e)
            self._db = None
            try:
                _ = self.db._collection.count()  # type: ignore[attr-defined]
                logger.info("Vector store reinitialized successfully")
                return True
            except Exception as e2:
                logger.error("Vector store reinit failed: %s", e2)
                return False

    # === Document Operations ===

    def add_documents(
        self,
        documents: list[Document],
        batch_size: int = 100,
    ) -> int:
        """Add documents to the vector store.

        Args:
            documents: List of LangChain Document objects
            batch_size: Number of documents to add per batch

        Returns:
            Number of documents added
        """
        if not documents:
            return 0

        total_added = 0

        # Process in batches to avoid memory issues
        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]

            try:
                if not self.ensure_ready():
                    raise RuntimeError("vector store unavailable")
                self.db.add_documents(batch)
                total_added += len(batch)
                logger.debug(
                    "Added batch of %d documents (%d/%d)",
                    len(batch),
                    total_added,
                    len(documents),
                )
            except Exception as e:
                logger.error("Failed to add batch starting at %d: %s", i, e)
                raise

        logger.info("Added %d documents to vector store", total_added)
        return total_added

    def add_texts(
        self,
        texts: list[str],
        metadatas: list[dict[str, Any]] | None = None,
        ids: list[str] | None = None,
    ) -> list[str]:
        """Add raw texts to the vector store.

        Args:
            texts: List of text strings
            metadatas: Optional metadata for each text
            ids: Optional IDs for each text

        Returns:
            List of document IDs
        """
        if not texts:
            return []

        try:
            doc_ids = self.db.add_texts(
                texts=texts,
                metadatas=metadatas,
                ids=ids,
            )
            logger.info("Added %d texts to vector store", len(texts))
            return doc_ids
        except Exception as e:
            logger.error("Failed to add texts: %s", e)
            raise

    # === Search Operations ===

    def search(
        self,
        query: str,
        k: int = 5,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Search for similar documents.

        Args:
            query: Search query text
            k: Number of results to return
            filter_metadata: Optional metadata filter

        Returns:
            List of SearchResult objects
        """
        try:
            if not self.ensure_ready():
                raise RuntimeError("vector store unavailable")
            # Use similarity search with scores
            results = self.db.similarity_search_with_relevance_scores(
                query=query,
                k=k,
                filter=filter_metadata,
            )

            search_results = []
            for doc, score in results:
                search_results.append(
                    SearchResult(
                        content=doc.page_content,
                        metadata=doc.metadata,
                        score=score,
                    )
                )

            logger.debug(
                "Search for '%s' returned %d results", query[:50], len(search_results)
            )
            return search_results

        except Exception as e:
            logger.error("Search failed: %s", e)
            return []

    def search_with_context(
        self,
        query: str,
        k: int = 5,
        context_window: int = 1,
    ) -> str:
        """Search and return formatted context for RAG.

        Args:
            query: Search query
            k: Number of results
            context_window: Number of adjacent chunks to include

        Returns:
            Formatted context string for LLM
        """
        results = self.search(query, k=k)

        if not results:
            return ""

        context_parts = []
        for i, result in enumerate(results, 1):
            source = result.metadata.get("source", "Unknown")
            title = result.metadata.get("title", "")

            header = f"[Source {i}: {title or source}]"
            context_parts.append(f"{header}\n{result.content}\n")

        return "\n---\n".join(context_parts)

    # === Collection Management ===

    def get_collection_stats(self) -> dict[str, Any]:
        """Get statistics about the vector store collection."""
        try:
            if not self.ensure_ready():
                return {"error": "vector store unavailable"}
            collection = self.db._collection
            count = collection.count()

            return {
                "name": self.COLLECTION_NAME,
                "document_count": count,
                "chunk_count": count,
                "persist_directory": str(self.persist_directory),
            }
        except Exception as e:
            logger.error("Failed to get collection stats: %s", e)
            return {"error": str(e)}

    def get_statistics(self) -> dict[str, Any]:
        """Return collection statistics (UI compatibility wrapper)."""
        return self.get_collection_stats()

    def clear(self) -> None:
        """Clear all documents from the vector store."""
        try:
            # Delete and recreate collection
            if self._db is not None:
                self._db.delete_collection()
                self._db = None

            # Recreate
            _ = self.db  # Triggers lazy initialization

            logger.info("Vector store cleared")
        except Exception as e:
            logger.error("Failed to clear vector store: %s", e)
            raise

    def delete_by_source(self, source: str) -> int:
        """Delete all documents from a specific source.

        Args:
            source: Source identifier to delete

        Returns:
            Number of documents deleted (approximate)
        """
        try:
            # Get documents with this source
            results = self.db.get(where={"source": source})

            if results and results.get("ids"):
                ids_to_delete = results["ids"]
                self.db.delete(ids=ids_to_delete)
                logger.info(
                    "Deleted %d documents from source: %s", len(ids_to_delete), source
                )
                return len(ids_to_delete)

            return 0
        except Exception as e:
            logger.error("Failed to delete by source: %s", e)
            return 0

    def delete_collection(self) -> None:
        """Completely delete the collection and its data."""
        try:
            if self.persist_directory.exists():
                shutil.rmtree(self.persist_directory)
                self.persist_directory.mkdir(parents=True, exist_ok=True)

            self._db = None
            logger.info("Collection deleted")
        except Exception as e:
            logger.error("Failed to delete collection: %s", e)
            raise


# Singleton instance
_vector_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """Get cached vector store instance."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
