"""Chemical knowledge graph for relationship-based queries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import networkx as nx

from ..database import get_db_manager
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class GraphNode:
    """Node in the chemical graph."""

    id: str
    type: str  # chemical, hazard, supplier, ghs_class, document
    properties: dict[str, Any]


@dataclass
class GraphEdge:
    """Edge in the chemical graph."""

    source: str
    target: str
    type: str  # incompatible_with, has_hazard, belongs_to, manufactured_by
    properties: dict[str, Any]


class ChemicalGraph:
    """Knowledge graph for chemical relationships and safety data."""

    def __init__(self) -> None:
        """Initialize chemical graph."""
        self.db = get_db_manager()
        self.graph = nx.MultiDiGraph()
        self._initialized = False

    def build_graph(self) -> None:
        """Build graph from database tables (includes enriched Phase 1-3 data)."""
        logger.info("Building chemical knowledge graph...")

        # Clear existing graph
        self.graph.clear()

        # Add chemical nodes
        self._add_chemical_nodes()

        # Phase 1a: Add incompatibility edges
        self._add_incompatibility_edges()

        # Phase 1b: Add hazard classifications and P-statements
        self._add_hazard_edges()
        self._add_hazard_classifications()
        self._add_p_statements()

        # Add GHS classification edges
        self._add_ghs_edges()

        # Phase 2a: Add manufacturer relationships
        self._add_manufacturer_edges()

        # Phase 2b: Add product family relationships
        self._add_product_family_edges()

        # Phase 3: Add chemical similarity edges
        self._add_similarity_edges()

        self._initialized = True
        logger.info(
            f"Graph built: {self.graph.number_of_nodes()} nodes, "
            f"{self.graph.number_of_edges()} edges (enriched with Phases 1-3)"
        )

    def _add_chemical_nodes(self) -> None:
        """Add chemical nodes from extraction results."""
        results = self.db.fetch_results()

        for result in results:
            cas = result.get("cas_number")
            if not cas:
                continue

            self.graph.add_node(
                cas,
                type="chemical",
                product_name=result.get("product_name"),
                molecular_formula=result.get("molecular_formula"),
                molecular_weight=result.get("molecular_weight"),
                supplier=result.get("supplier"),
                confidence=result.get("confidence_score", 0.0),
            )

    def _add_incompatibility_edges(self) -> None:
        """Add incompatibility edges from rules table."""
        conn = self.db.conn
        query = """
            SELECT cas_a, cas_b, rule, source, justification, 
                   group_a, group_b, indexed_at
            FROM rag_incompatibilities
        """

        try:
            cursor = conn.execute(query)
            for row in cursor.fetchall():
                cas_a, cas_b, rule, source, justification, group_a, group_b, indexed_at = row

                # Ensure both nodes exist
                if cas_a not in self.graph:
                    self.graph.add_node(cas_a, type="chemical")
                if cas_b not in self.graph:
                    self.graph.add_node(cas_b, type="chemical")

                # Add edge
                self.graph.add_edge(
                    cas_a,
                    cas_b,
                    type="incompatible_with",
                    rule=rule,
                    source=source,
                    justification=justification,
                    group_a=group_a,
                    group_b=group_b,
                    indexed_at=indexed_at,
                )

                # Add reverse edge (incompatibility is bidirectional)
                self.graph.add_edge(
                    cas_b,
                    cas_a,
                    type="incompatible_with",
                    rule=rule,
                    source=source,
                    justification=justification,
                    group_a=group_b,
                    group_b=group_a,
                    indexed_at=indexed_at,
                )

        except Exception as e:
            logger.error(f"Error adding incompatibility edges: {e}")

    def _add_hazard_edges(self) -> None:
        """Add hazard nodes and edges."""
        conn = self.db.conn
        query = """
            SELECT cas, hazard_flags, env_risk, idlh, pel, rel, source
            FROM rag_hazards
        """

        try:
            cursor = conn.execute(query)
            for row in cursor.fetchall():
                cas, hazard_flags, env_risk, idlh, pel, rel, source = row

                if cas not in self.graph:
                    self.graph.add_node(cas, type="chemical")

                # Add hazard as node attribute instead of separate node
                if hazard_flags:
                    self.graph.nodes[cas]["hazard_flags"] = hazard_flags
                if env_risk is not None:
                    self.graph.nodes[cas]["env_risk"] = env_risk
                if idlh is not None:
                    self.graph.nodes[cas]["idlh"] = idlh
                if pel is not None:
                    self.graph.nodes[cas]["pel"] = pel
                if rel is not None:
                    self.graph.nodes[cas]["rel"] = rel

        except Exception as e:
            logger.error(f"Error adding hazard edges: {e}")

    def _add_ghs_edges(self) -> None:
        """Add GHS classification edges."""
        results = self.db.fetch_results()

        for result in results:
            cas = result.get("cas_number")
            hazard_class = result.get("hazard_class")

            if cas and hazard_class and cas in self.graph:
                # Add GHS class as node property
                self.graph.nodes[cas]["ghs_class"] = hazard_class

    def _add_hazard_classifications(self) -> None:
        """Add hazard classifications from Phase 1b enrichment."""
        conn = self.db.conn
        query = "SELECT cas_number, ghs_class FROM hazard_classifications"

        try:
            cursor = conn.execute(query)
            for row in cursor.fetchall():
                cas, hazard_class = row

                if cas not in self.graph:
                    self.graph.add_node(cas, type="chemical")

                # Add hazard classification to node
                if not self.graph.nodes[cas].get("hazard_classes"):
                    self.graph.nodes[cas]["hazard_classes"] = []
                self.graph.nodes[cas]["hazard_classes"].append(hazard_class)

        except Exception as e:
            logger.error(f"Error adding hazard classifications: {e}")

    def _add_p_statements(self) -> None:
        """Add P-statements from Phase 1b enrichment."""
        conn = self.db.conn
        query = "SELECT cas_number, p_code FROM chemical_p_statements"

        try:
            cursor = conn.execute(query)
            for row in cursor.fetchall():
                cas, p_code = row

                if cas not in self.graph:
                    self.graph.add_node(cas, type="chemical")

                # Add P-statement to node
                if not self.graph.nodes[cas].get("p_statements"):
                    self.graph.nodes[cas]["p_statements"] = []
                self.graph.nodes[cas]["p_statements"].append(p_code)

        except Exception as e:
            logger.error(f"Error adding P-statements: {e}")

    def _add_manufacturer_edges(self) -> None:
        """Add manufacturer relationships from Phase 2a enrichment."""
        conn = self.db.conn
        query = "SELECT cas_number, manufacturer_name FROM chemical_manufacturers"

        try:
            cursor = conn.execute(query)
            for row in cursor.fetchall():
                cas, manufacturer = row

                if cas not in self.graph:
                    self.graph.add_node(cas, type="chemical")

                # Create or update manufacturer node
                mfg_id = f"mfg:{manufacturer}"
                if mfg_id not in self.graph:
                    self.graph.add_node(mfg_id, type="manufacturer", name=manufacturer)

                # Add edge from chemical to manufacturer
                self.graph.add_edge(
                    cas,
                    mfg_id,
                    type="manufactured_by",
                    manufacturer=manufacturer
                )

        except Exception as e:
            logger.error(f"Error adding manufacturer edges: {e}")

    def _add_product_family_edges(self) -> None:
        """Add product family relationships from Phase 2b enrichment."""
        conn = self.db.conn
        query = "SELECT cas_a, cas_b FROM product_families"

        try:
            cursor = conn.execute(query)
            for row in cursor.fetchall():
                cas_a, cas_b = row

                # Ensure both nodes exist
                if cas_a not in self.graph:
                    self.graph.add_node(cas_a, type="chemical")
                if cas_b not in self.graph:
                    self.graph.add_node(cas_b, type="chemical")

                # Add bidirectional edges (same manufacturer = compatible)
                self.graph.add_edge(
                    cas_a,
                    cas_b,
                    type="product_family",
                    relationship="same_manufacturer"
                )
                self.graph.add_edge(
                    cas_b,
                    cas_a,
                    type="product_family",
                    relationship="same_manufacturer"
                )

        except Exception as e:
            logger.error(f"Error adding product family edges: {e}")

    def _add_similarity_edges(self) -> None:
        """Add chemical similarity edges from Phase 3 enrichment."""
        conn = self.db.conn
        query = "SELECT cas_a, cas_b, similarity_score, similarity_type FROM chemical_similarity"

        try:
            cursor = conn.execute(query)
            for row in cursor.fetchall():
                cas_a, cas_b, score, sim_type = row

                # Ensure both nodes exist
                if cas_a not in self.graph:
                    self.graph.add_node(cas_a, type="chemical")
                if cas_b not in self.graph:
                    self.graph.add_node(cas_b, type="chemical")

                # Add bidirectional similarity edges
                self.graph.add_edge(
                    cas_a,
                    cas_b,
                    type="similar_to",
                    similarity_score=score,
                    similarity_type=sim_type
                )
                self.graph.add_edge(
                    cas_b,
                    cas_a,
                    type="similar_to",
                    similarity_score=score,
                    similarity_type=sim_type
                )

        except Exception as e:
            logger.error(f"Error adding similarity edges: {e}")

    def find_incompatible_chemicals(
        self, cas: str, max_depth: int = 1
    ) -> list[tuple[str, int]]:
        """Find chemicals incompatible with given CAS (with depth).

        Args:
            cas: CAS number to query
            max_depth: Maximum traversal depth (1=direct, 2=transitive, etc.)

        Returns:
            List of (cas_number, depth) tuples
        """
        if not self._initialized:
            self.build_graph()

        if cas not in self.graph:
            logger.warning(f"CAS {cas} not found in graph")
            return []

        incompatible = []

        try:
            # BFS traversal limited by depth
            for node, depth in nx.bfs_edges(self.graph, cas, depth_limit=max_depth):
                if depth <= max_depth:
                    # Check if edge is incompatibility
                    edges = self.graph.get_edge_data(cas, node)
                    if edges:
                        for edge_data in edges.values():
                            if edge_data.get("type") == "incompatible_with":
                                incompatible.append((node, depth))
                                break

        except Exception as e:
            logger.error(f"Error finding incompatible chemicals: {e}")

        return incompatible

    def find_reaction_chains(
        self, cas: str, max_depth: int = 3
    ) -> list[list[str]]:
        """Find reaction chains starting from a chemical.

        Uses a DFS traversal following only 'incompatible_with' edges to
        efficiently discover reaction chains without exploring unrelated relationships.

        Args:
            cas: Starting CAS number
            max_depth: Maximum chain length

        Returns:
            List of paths (each path is a list of CAS numbers)
        """
        if not self._initialized:
            self.build_graph()

        if cas not in self.graph:
            return []

        chains = []

        def dfs(current_path: list[str], current_depth: int) -> None:
            if current_depth >= max_depth:
                return

            current_node = current_path[-1]

            # Get neighbors connected via incompatibility edges
            for neighbor in self.graph.neighbors(current_node):
                if neighbor in current_path:  # Avoid cycles
                    continue

                edges = self.graph.get_edge_data(current_node, neighbor)
                is_incompatible = False

                # Check if any edge between these nodes is an incompatibility
                if edges:
                    for edge_data in edges.values():
                        if edge_data.get("type") == "incompatible_with":
                            is_incompatible = True
                            break

                if is_incompatible:
                    new_path = current_path + [neighbor]
                    chains.append(new_path)
                    dfs(new_path, current_depth + 1)

        # Start DFS from the source chemical
        dfs([cas], 0)

        return chains

    def find_chemicals_by_hazard(self, hazard_flag: str) -> list[str]:
        """Find chemicals with specific hazard flag.

        Args:
            hazard_flag: Hazard flag key (e.g., 'dangerous', 'toxic')

        Returns:
            List of CAS numbers
        """
        if not self._initialized:
            self.build_graph()

        chemicals = []

        for node, data in self.graph.nodes(data=True):
            if data.get("type") == "chemical":
                hazard_flags = data.get("hazard_flags", {})
                if isinstance(hazard_flags, dict) and hazard_flags.get(hazard_flag):
                    chemicals.append(node)

        return chemicals

    def find_similar_chemicals(
        self, cas: str, by: str = "ghs_class"
    ) -> list[str]:
        """Find chemicals similar to given CAS.

        Args:
            cas: CAS number to query
            by: Similarity criterion ('ghs_class', 'supplier', 'hazard_profile')

        Returns:
            List of similar CAS numbers
        """
        if not self._initialized:
            self.build_graph()

        if cas not in self.graph:
            return []

        node_data = self.graph.nodes[cas]
        similar = []

        if by == "ghs_class":
            target_class = node_data.get("ghs_class")
            if target_class:
                for node, data in self.graph.nodes(data=True):
                    if (
                        node != cas
                        and data.get("type") == "chemical"
                        and data.get("ghs_class") == target_class
                    ):
                        similar.append(node)

        elif by == "supplier":
            target_supplier = node_data.get("supplier")
            if target_supplier:
                for node, data in self.graph.nodes(data=True):
                    if (
                        node != cas
                        and data.get("type") == "chemical"
                        and data.get("supplier") == target_supplier
                    ):
                        similar.append(node)

        elif by == "hazard_profile":
            target_hazards = node_data.get("hazard_flags", {})
            if target_hazards:
                for node, data in self.graph.nodes(data=True):
                    if node != cas and data.get("type") == "chemical":
                        other_hazards = data.get("hazard_flags", {})
                        # Simple Jaccard similarity
                        if other_hazards and self._hazard_similarity(
                            target_hazards, other_hazards
                        ) > 0.5:
                            similar.append(node)

        return similar

    def _hazard_similarity(self, h1: dict, h2: dict) -> float:
        """Calculate Jaccard similarity between hazard profiles."""
        if not h1 or not h2:
            return 0.0

        keys1 = set(k for k, v in h1.items() if v)
        keys2 = set(k for k, v in h2.items() if v)

        if not keys1 and not keys2:
            return 0.0

        intersection = len(keys1 & keys2)
        union = len(keys1 | keys2)

        return intersection / union if union > 0 else 0.0

    def get_subgraph(self, cas_list: list[str]) -> nx.MultiDiGraph:
        """Extract subgraph for specific chemicals.

        Args:
            cas_list: List of CAS numbers to include

        Returns:
            NetworkX subgraph
        """
        if not self._initialized:
            self.build_graph()

        return self.graph.subgraph(cas_list).copy()

    def get_graph_stats(self) -> dict[str, Any]:
        """Get graph statistics."""
        if not self._initialized:
            self.build_graph()

        stats = {
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
            "chemicals": sum(
                1 for _, d in self.graph.nodes(data=True) if d.get("type") == "chemical"
            ),
            "avg_degree": (
                sum(dict(self.graph.degree()).values()) / self.graph.number_of_nodes()
                if self.graph.number_of_nodes() > 0
                else 0
            ),
            "density": nx.density(self.graph),
        }

        # Count edge types
        edge_types = {}
        for _, _, data in self.graph.edges(data=True):
            edge_type = data.get("type", "unknown")
            edge_types[edge_type] = edge_types.get(edge_type, 0) + 1

        stats["edge_types"] = edge_types

        return stats

    def find_similar_by_hazard_profile(self, cas: str, threshold: float = 0.7) -> list[tuple[str, float]]:
        """Find chemicals with similar hazard profiles (Phase 3 enrichment).

        Args:
            cas: CAS number to query
            threshold: Minimum similarity score (0.0-1.0)

        Returns:
            List of (cas_number, similarity_score) tuples
        """
        if not self._initialized:
            self.build_graph()

        if cas not in self.graph:
            return []

        similar = []
        for neighbor in self.graph.neighbors(cas):
            edges = self.graph.get_edge_data(cas, neighbor)
            if edges:
                for edge_data in edges.values():
                    if edge_data.get("type") == "similar_to":
                        score = edge_data.get("similarity_score", 0.0)
                        if score >= threshold:
                            similar.append((neighbor, score))
                            break

        # Sort by similarity score descending
        similar.sort(key=lambda x: x[1], reverse=True)
        return similar

    def find_by_manufacturer(self, manufacturer: str) -> list[str]:
        """Find all chemicals from a specific manufacturer (Phase 2a enrichment).

        Args:
            manufacturer: Manufacturer name

        Returns:
            List of CAS numbers
        """
        if not self._initialized:
            self.build_graph()

        chemicals = []
        mfg_id = f"mfg:{manufacturer}"

        if mfg_id in self.graph:
            # Find all chemicals connected to this manufacturer
            for predecessor in self.graph.predecessors(mfg_id):
                node_data = self.graph.nodes[predecessor]
                if node_data.get("type") == "chemical":
                    chemicals.append(predecessor)

        return chemicals

    def find_product_family(self, cas: str) -> list[str]:
        """Find product family members (same manufacturer) for a chemical (Phase 2b).

        Args:
            cas: CAS number to query

        Returns:
            List of CAS numbers in the same product family
        """
        if not self._initialized:
            self.build_graph()

        if cas not in self.graph:
            return []

        family = []
        for neighbor in self.graph.neighbors(cas):
            edges = self.graph.get_edge_data(cas, neighbor)
            if edges:
                for edge_data in edges.values():
                    if edge_data.get("type") == "product_family":
                        family.append(neighbor)
                        break

        return family

    def get_enriched_stats(self) -> dict[str, Any]:
        """Get enriched graph statistics including Phase 1-3 data."""
        if not self._initialized:
            self.build_graph()

        base_stats = self.get_graph_stats()

        # Count manufacturers
        manufacturers = sum(
            1 for _, d in self.graph.nodes(data=True) if d.get("type") == "manufacturer"
        )

        # Count chemicals with hazard classifications
        chemicals_with_hazards = sum(
            1 for _, d in self.graph.nodes(data=True)
            if d.get("type") == "chemical" and d.get("hazard_classes")
        )

        # Count chemicals with P-statements
        chemicals_with_p_statements = sum(
            1 for _, d in self.graph.nodes(data=True)
            if d.get("type") == "chemical" and d.get("p_statements")
        )

        # Count chemicals with similarity links
        chemicals_with_similarity = sum(
            1 for node in self.graph.nodes()
            if self.graph.nodes[node].get("type") == "chemical"
            and any(
                edge_data.get("type") == "similar_to"
                for _, _, edge_data in self.graph.edges(node, data=True)
            )
        )

        enriched_stats = {
            **base_stats,
            "manufacturers": manufacturers,
            "chemicals_with_hazards": chemicals_with_hazards,
            "chemicals_with_p_statements": chemicals_with_p_statements,
            "chemicals_with_similarity": chemicals_with_similarity,
            "enrichment_coverage": {
                "hazards": f"{chemicals_with_hazards}/{base_stats['chemicals']}",
                "p_statements": f"{chemicals_with_p_statements}/{base_stats['chemicals']}",
                "similarity": f"{chemicals_with_similarity}/{base_stats['chemicals']}",
            }
        }

        return enriched_stats
