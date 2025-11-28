"""RAG retriever for knowledge-augmented responses."""

from __future__ import annotations

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

    def retrieve(
        self,
        query: str,
        k: int = 5,
    ) -> list[SearchResult]:
        """Retrieve relevant documents for a query.

        Args:
            query: Search query
            k: Number of results

        Returns:
            List of SearchResult objects
        """
        logger.info("Retrieving documents for query: %s", query[:50])
        return self.vector_store.search(query, k=k)

    def answer(
        self,
        query: str,
        k: int = 5,
        system_prompt: str | None = None,
    ) -> str:
        """Answer a question using RAG.

        Args:
            query: User question
            k: Number of documents to retrieve
            system_prompt: Optional system prompt override

        Returns:
            Answer text
        """
        logger.info("Answering question: %s", query[:50])

        # Retrieve relevant documents
        context = self.vector_store.search_with_context(query, k=k)

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
