"""RAG retriever for knowledge-augmented responses."""

from __future__ import annotations

import hashlib
from functools import lru_cache

from ..models import get_ollama_client
from ..utils.logger import get_logger
from .vector_store import SearchResult, get_vector_store

logger = get_logger(__name__)


class RAGRetriever:
    """Retrieve and answer questions using RAG."""

    def __init__(self, vector_store=None, ollama_client=None) -> None:
        """Initialize retriever.

        Args:
            vector_store: VectorStore instance (uses default if None)
            ollama_client: OllamaClient instance (uses default if None)
        """
        self.vector_store = vector_store or get_vector_store()
        self.ollama = ollama_client or get_ollama_client()
        # Cache for RAG search results (up to 256 queries)
        self._search_cache: dict[str, list[SearchResult]] = {}
        self._cache_max_size = 256

    def _get_cache_key(self, query: str, k: int) -> str:
        """Generate cache key for a search query."""
        # Use hash to keep keys short and handle special characters
        content = f"{query}:{k}"
        return hashlib.sha256(content.encode()).hexdigest()

    def _update_cache(self, key: str, result: list[SearchResult]) -> None:
        """Update cache with LRU eviction policy."""
        if len(self._search_cache) >= self._cache_max_size:
            # Remove first (oldest) entry
            self._search_cache.pop(next(iter(self._search_cache)))
        self._search_cache[key] = result

    def retrieve(
        self,
        query: str,
        k: int = 5,
    ) -> list[SearchResult]:
        """Retrieve relevant documents for a query with result caching.

        Caches search results to avoid redundant vector store queries (1-2s savings
        for repeated queries over the same knowledge base).

        Args:
            query: Search query
            k: Number of results

        Returns:
            List of SearchResult objects
        """
        # Check cache first
        cache_key = self._get_cache_key(query, k)
        if cache_key in self._search_cache:
            logger.debug("Cache hit for RAG query: %s", query[:50])
            return self._search_cache[cache_key]

        logger.info("Retrieving documents for query: %s", query[:50])
        results = self.vector_store.search(query, k=k)
        
        # Update cache
        self._update_cache(cache_key, results)
        
        return results

    def answer(
        self,
        query: str,
        k: int = 5,
        system_prompt: str | None = None,
    ) -> str:
        """Answer a question using RAG with cached retrieval.

        Args:
            query: User question
            k: Number of documents to retrieve
            system_prompt: Optional system prompt override

        Returns:
            Answer text (or notice if RAG unavailable)
        """
        logger.info("Answering question: %s", query[:50])

        # Use retrieve() which includes caching
        search_results = self.retrieve(query, k=k)
        
        # Check if RAG is available
        if not search_results:
            logger.warning(
                "No RAG results available. Vector store may be disabled. "
                "Answering without RAG context."
            )
            return (
                "I don't have access to the knowledge base to answer this question. "
                "The RAG system may not be configured or the embedding model is unavailable."
            )
        
        # Convert search results to context string
        context = "\n---\n".join(
            f"{result.source}:\n{result.content}" for result in search_results
        )

        if not context:
            logger.warning("No relevant documents found")
            return "No relevant information found in the knowledge base."

        # Generate answer with context
        prompt = f"""Based on the following context, answer the question.

Context:
{context}

Question: {query}

Answer:"""

        default_system = (
            "You are a helpful assistant specialized in chemical safety and SDS analysis. "
            "Answer questions based on the provided context. "
            "If the context doesn't contain the answer, say so clearly."
        )

        answer = self.ollama.chat(
            message=prompt,
            system_prompt=system_prompt or default_system,
        )

        return answer

    def get_knowledge_base_stats(self) -> dict[str, str | int]:
        """Get statistics about the knowledge base.

        Returns:
            Statistics dictionary
        """
        return self.vector_store.get_collection_stats()

    def clear_knowledge_base(self) -> None:
        """Clear all documents from knowledge base."""
        logger.warning("Clearing knowledge base")
        self.vector_store.clear()
