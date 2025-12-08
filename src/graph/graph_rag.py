"""Hybrid GraphRAG retriever combining graph traversal and vector search."""

from __future__ import annotations

from typing import Any

from langchain_core.documents import Document

from ..rag.retriever import RAGRetriever
from ..utils.logger import get_logger
from .chemical_graph import ChemicalGraph
from .graph_queries import GraphQueryEngine

logger = get_logger(__name__)


class GraphRAGRetriever:
    """Hybrid retriever combining graph queries and vector search."""

    def __init__(self) -> None:
        """Initialize hybrid retriever."""
        self.graph = ChemicalGraph()
        self.query_engine = GraphQueryEngine()
        self.vector_retriever = RAGRetriever()

    def query(
        self,
        query: str,
        use_graph: bool = True,
        use_vector: bool = True,
        max_graph_depth: int = 2,
        top_k: int = 5,
    ) -> dict[str, Any]:
        """Execute hybrid query combining graph and vector retrieval.

        Args:
            query: Natural language query
            use_graph: Enable graph-based retrieval
            use_vector: Enable vector-based retrieval
            max_graph_depth: Maximum graph traversal depth
            top_k: Number of vector results

        Returns:
            Combined results with graph and vector contexts
        """
        results: dict[str, Any] = {
            "query": query,
            "graph_context": [],
            "vector_context": [],
            "combined_context": "",
        }

        # Extract CAS numbers from query (simple regex)
        cas_numbers = self._extract_cas_numbers(query)

        # Graph-based retrieval
        if use_graph and cas_numbers:
            logger.info(f"Graph retrieval for CAS: {cas_numbers}")
            for cas in cas_numbers:
                # Get incompatibilities
                incompatible = self.graph.find_incompatible_chemicals(
                    cas, max_depth=max_graph_depth
                )
                results["graph_context"].append(
                    {
                        "cas": cas,
                        "incompatibilities": incompatible,
                    }
                )

                # Get neighborhood
                neighborhood = self.query_engine.get_chemical_neighborhood(
                    cas, radius=max_graph_depth
                )
                results["graph_context"].append(
                    {
                        "cas": cas,
                        "neighborhood": neighborhood,
                    }
                )

        # Vector-based retrieval
        if use_vector:
            logger.info(f"Vector retrieval for query: {query}")
            try:
                vector_results = self.vector_retriever.retrieve(
                    query, top_k=top_k
                )
                results["vector_context"] = [
                    {
                        "content": doc.page_content,
                        "metadata": doc.metadata,
                        "score": score,
                    }
                    for doc, score in vector_results
                ]
            except Exception as e:
                logger.error(f"Vector retrieval failed: {e}")

        # Combine contexts
        results["combined_context"] = self._combine_contexts(results)

        return results

    def query_incompatibility_chain(
        self, cas: str, max_depth: int = 3
    ) -> dict[str, Any]:
        """Query for incompatibility chains starting from a chemical.

        Args:
            cas: Starting CAS number
            max_depth: Maximum chain depth

        Returns:
            Incompatibility chains with enriched context
        """
        # Get transitive incompatibilities
        incompatibilities = self.query_engine.find_transitive_incompatibilities(
            cas, max_depth
        )

        # Get reaction chains from graph
        chains = self.graph.find_reaction_chains(cas, max_depth)

        # Enrich with vector search for each chemical in chains
        enriched_chains = []
        for chain in chains[:5]:  # Limit to top 5 chains
            enriched = []
            for chemical_cas in chain:
                # Query vector DB for this chemical
                try:
                    docs = self.vector_retriever.retrieve(
                        f"safety information for CAS {chemical_cas}",
                        top_k=1,
                    )
                    context = docs[0][0].page_content if docs else ""
                except Exception:
                    context = ""

                enriched.append(
                    {
                        "cas": chemical_cas,
                        "context": context,
                    }
                )

            enriched_chains.append(enriched)

        return {
            "cas": cas,
            "transitive_incompatibilities": incompatibilities,
            "reaction_chains": chains,
            "enriched_chains": enriched_chains,
        }

    def query_hazardous_clusters(
        self, threshold: float = 100.0
    ) -> dict[str, Any]:
        """Find and enrich hazardous chemical clusters.

        Args:
            threshold: IDLH threshold

        Returns:
            Hazardous clusters with safety documentation
        """
        # Get hazardous clusters from graph query
        clusters = self.query_engine.find_hazardous_clusters(threshold)

        # Enrich each cluster with vector search
        enriched_clusters = []
        for cluster in clusters[:10]:  # Limit to top 10
            cas_a = cluster["cas_a"]
            cas_b = cluster["cas_b"]

            # Get safety docs for both chemicals
            try:
                docs_a = self.vector_retriever.retrieve(
                    f"safety hazards CAS {cas_a}", top_k=1
                )
                docs_b = self.vector_retriever.retrieve(
                    f"safety hazards CAS {cas_b}", top_k=1
                )

                cluster["safety_context_a"] = (
                    docs_a[0][0].page_content if docs_a else ""
                )
                cluster["safety_context_b"] = (
                    docs_b[0][0].page_content if docs_b else ""
                )
            except Exception as e:
                logger.error(f"Error enriching cluster: {e}")
                cluster["safety_context_a"] = ""
                cluster["safety_context_b"] = ""

            enriched_clusters.append(cluster)

        return {
            "threshold": threshold,
            "clusters": enriched_clusters,
        }

    def _extract_cas_numbers(self, query: str) -> list[str]:
        """Extract CAS numbers from query text.

        Args:
            query: Query text

        Returns:
            List of CAS numbers found
        """
        import re

        # CAS number pattern: XXX-XX-X or XXXXX-XX-X
        pattern = r"\b\d{2,7}-\d{2}-\d\b"
        matches = re.findall(pattern, query)
        return matches

    def _combine_contexts(self, results: dict[str, Any]) -> str:
        """Combine graph and vector contexts into unified context.

        Args:
            results: Results dict with graph and vector contexts

        Returns:
            Combined context string
        """
        combined = []

        # Add graph context
        if results["graph_context"]:
            combined.append("## Graph Context (Chemical Relationships)")
            for ctx in results["graph_context"]:
                if "incompatibilities" in ctx:
                    incomp = ctx["incompatibilities"]
                    if incomp:
                        combined.append(
                            f"CAS {ctx['cas']} has {len(incomp)} "
                            f"incompatibilities at various depths"
                        )

        # Add vector context
        if results["vector_context"]:
            combined.append("\n## Vector Context (Document Excerpts)")
            for i, ctx in enumerate(results["vector_context"], 1):
                combined.append(f"\n### Document {i}")
                combined.append(ctx["content"][:500])  # Truncate

        return "\n".join(combined)

    def get_enhanced_context_for_llm(
        self, query: str, cas_numbers: list[str] | None = None
    ) -> str:
        """Get enhanced context for LLM generation.

        Args:
            query: User query
            cas_numbers: Optional list of CAS numbers to focus on

        Returns:
            Rich context string for LLM
        """
        if cas_numbers is None:
            cas_numbers = self._extract_cas_numbers(query)

        context_parts = []

        # Get graph-based context
        for cas in cas_numbers:
            # Direct incompatibilities
            incomp = self.graph.find_incompatible_chemicals(cas, max_depth=1)
            if incomp:
                context_parts.append(
                    f"Chemical {cas} is directly incompatible with: "
                    f"{', '.join(c for c, _ in incomp[:5])}"
                )

            # Similar chemicals
            similar = self.graph.find_similar_chemicals(cas, by="ghs_class")
            if similar:
                context_parts.append(
                    f"Chemicals similar to {cas} (same GHS class): "
                    f"{', '.join(similar[:5])}"
                )

        # Get vector-based context
        try:
            vector_docs = self.vector_retriever.retrieve(query, top_k=3)
            for doc, score in vector_docs:
                context_parts.append(
                    f"[Relevance: {score:.2f}] {doc.page_content[:300]}"
                )
        except Exception as e:
            logger.error(f"Vector retrieval error: {e}")

        return "\n\n".join(context_parts)
