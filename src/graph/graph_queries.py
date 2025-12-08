"""Graph-based query engine using DuckDB recursive CTEs."""

from __future__ import annotations

from typing import Any

from ..database import get_db_manager
from ..utils.logger import get_logger

logger = get_logger(__name__)


class GraphQueryEngine:
    """Execute graph queries using DuckDB recursive CTEs."""

    def __init__(self) -> None:
        """Initialize query engine."""
        self.db = get_db_manager()

    def find_transitive_incompatibilities(
        self, cas: str, max_depth: int = 3
    ) -> list[dict[str, Any]]:
        """Find transitive incompatibilities using recursive CTE.

        Args:
            cas: Starting CAS number
            max_depth: Maximum traversal depth

        Returns:
            List of incompatibility records with depth
        """
        conn = self.db.conn

        query = f"""
            WITH RECURSIVE reaction_chain AS (
                -- Base case: direct incompatibilities
                SELECT
                    cas_a,
                    cas_b,
                    rule,
                    source,
                    justification,
                    1 as depth
                FROM rag_incompatibilities
                WHERE cas_a = ?

                UNION ALL

                -- Recursive case: follow incompatibility chains
                SELECT
                    r.cas_a,
                    r.cas_b,
                    r.rule,
                    r.source,
                    r.justification,
                    rc.depth + 1
                FROM rag_incompatibilities r
                JOIN reaction_chain rc ON r.cas_a = rc.cas_b
                WHERE rc.depth < ?
            )
            SELECT DISTINCT * FROM reaction_chain
            ORDER BY depth, cas_b;
        """

        try:
            cursor = conn.execute(query, (cas, max_depth))
            rows = cursor.fetchall()

            results = []
            for row in rows:
                results.append(
                    {
                        "cas_a": row[0],
                        "cas_b": row[1],
                        "rule": row[2],
                        "source": row[3],
                        "justification": row[4],
                        "depth": row[5],
                    }
                )

            return results

        except Exception as e:
            logger.error(f"Error in transitive incompatibility query: {e}")
            return []

    def find_chemical_clusters(
        self, min_connections: int = 2
    ) -> list[dict[str, Any]]:
        """Find clusters of highly connected chemicals.

        Args:
            min_connections: Minimum incompatibility connections

        Returns:
            List of chemical groups
        """
        conn = self.db.conn

        query = f"""
            WITH connection_counts AS (
                SELECT
                    cas_a,
                    COUNT(DISTINCT cas_b) as connection_count
                FROM rag_incompatibilities
                GROUP BY cas_a
                HAVING COUNT(DISTINCT cas_b) >= ?
            )
            SELECT
                cc.cas_a,
                cc.connection_count,
                ARRAY_AGG(DISTINCT ri.cas_b) as connected_to
            FROM connection_counts cc
            JOIN rag_incompatibilities ri ON cc.cas_a = ri.cas_a
            GROUP BY cc.cas_a, cc.connection_count
            ORDER BY cc.connection_count DESC;
        """

        try:
            cursor = conn.execute(query, (min_connections,))
            rows = cursor.fetchall()

            results = []
            for row in rows:
                results.append(
                    {
                        "cas": row[0],
                        "connection_count": row[1],
                        "connected_to": row[2],
                    }
                )

            return results

        except Exception as e:
            logger.error(f"Error in cluster query: {e}")
            return []

    def find_shared_incompatibilities(
        self, cas1: str, cas2: str
    ) -> list[dict[str, Any]]:
        """Find chemicals incompatible with both cas1 and cas2.

        Args:
            cas1: First CAS number
            cas2: Second CAS number

        Returns:
            List of shared incompatibilities
        """
        conn = self.db.conn

        query = """
            SELECT DISTINCT
                r1.cas_b as shared_incompatible,
                r1.rule as rule1,
                r2.rule as rule2,
                r1.source as source1,
                r2.source as source2
            FROM rag_incompatibilities r1
            JOIN rag_incompatibilities r2
                ON r1.cas_b = r2.cas_b
            WHERE r1.cas_a = ? AND r2.cas_a = ?
            ORDER BY r1.cas_b;
        """

        try:
            cursor = conn.execute(query, (cas1, cas2))
            rows = cursor.fetchall()

            results = []
            for row in rows:
                results.append(
                    {
                        "shared_incompatible": row[0],
                        "rule1": row[1],
                        "rule2": row[2],
                        "source1": row[3],
                        "source2": row[4],
                    }
                )

            return results

        except Exception as e:
            logger.error(f"Error in shared incompatibilities query: {e}")
            return []

    def find_hazardous_clusters(
        self, hazard_threshold: float = 100.0
    ) -> list[dict[str, Any]]:
        """Find groups of incompatible chemicals with high hazard levels.

        Args:
            hazard_threshold: Minimum IDLH threshold

        Returns:
            List of hazardous chemical groups
        """
        conn = self.db.conn

        query = f"""
            WITH hazardous_chemicals AS (
                SELECT cas, idlh, hazard_flags
                FROM rag_hazards
                WHERE idlh IS NOT NULL AND idlh >= ?
            ),
            hazardous_pairs AS (
                SELECT
                    ri.cas_a,
                    ri.cas_b,
                    ri.rule,
                    h1.idlh as idlh_a,
                    h2.idlh as idlh_b,
                    h1.hazard_flags as flags_a,
                    h2.hazard_flags as flags_b
                FROM rag_incompatibilities ri
                JOIN hazardous_chemicals h1 ON ri.cas_a = h1.cas
                JOIN hazardous_chemicals h2 ON ri.cas_b = h2.cas
            )
            SELECT * FROM hazardous_pairs
            ORDER BY idlh_a DESC, idlh_b DESC;
        """

        try:
            cursor = conn.execute(query, (hazard_threshold,))
            rows = cursor.fetchall()

            results = []
            for row in rows:
                results.append(
                    {
                        "cas_a": row[0],
                        "cas_b": row[1],
                        "rule": row[2],
                        "idlh_a": row[3],
                        "idlh_b": row[4],
                        "hazard_flags_a": row[5],
                        "hazard_flags_b": row[6],
                    }
                )

            return results

        except Exception as e:
            logger.error(f"Error in hazardous clusters query: {e}")
            return []

    def find_chemicals_by_ghs_path(
        self, start_ghs: str, target_ghs: str
    ) -> list[dict[str, Any]]:
        """Find incompatibility paths between GHS classes.

        Args:
            start_ghs: Starting GHS class
            target_ghs: Target GHS class

        Returns:
            List of paths connecting the classes
        """
        conn = self.db.conn

        query = """
            WITH chemicals_by_ghs AS (
                SELECT DISTINCT
                    cas_number,
                    product_name,
                    hazard_class
                FROM extraction_results
                WHERE hazard_class IN (?, ?)
            ),
            ghs_incompatibilities AS (
                SELECT
                    ri.cas_a,
                    ri.cas_b,
                    ri.rule,
                    c1.hazard_class as ghs_a,
                    c2.hazard_class as ghs_b
                FROM rag_incompatibilities ri
                JOIN chemicals_by_ghs c1 ON ri.cas_a = c1.cas_number
                JOIN chemicals_by_ghs c2 ON ri.cas_b = c2.cas_number
                WHERE c1.hazard_class = ? AND c2.hazard_class = ?
            )
            SELECT * FROM ghs_incompatibilities;
        """

        try:
            cursor = conn.execute(
                query, (start_ghs, target_ghs, start_ghs, target_ghs)
            )
            rows = cursor.fetchall()

            results = []
            for row in rows:
                results.append(
                    {
                        "cas_a": row[0],
                        "cas_b": row[1],
                        "rule": row[2],
                        "ghs_a": row[3],
                        "ghs_b": row[4],
                    }
                )

            return results

        except Exception as e:
            logger.error(f"Error in GHS path query: {e}")
            return []

    def get_chemical_neighborhood(
        self, cas: str, radius: int = 1
    ) -> dict[str, Any]:
        """Get full neighborhood around a chemical.

        Args:
            cas: CAS number
            radius: Neighborhood radius

        Returns:
            Dictionary with nodes and edges in neighborhood
        """
        # Get incompatibilities
        incompatibilities = self.find_transitive_incompatibilities(cas, radius)

        # Get chemical details
        conn = self.db.conn
        chem_query = """
            SELECT cas_number, product_name, hazard_class, supplier
            FROM extraction_results
            WHERE cas_number IN (
                SELECT DISTINCT cas_b FROM (
                    SELECT cas_b FROM rag_incompatibilities WHERE cas_a = ?
                    UNION
                    SELECT ? as cas_b
                )
            )
        """

        try:
            cursor = conn.execute(chem_query, (cas, cas))
            rows = cursor.fetchall()

            chemicals = {}
            for row in rows:
                chemicals[row[0]] = {
                    "product_name": row[1],
                    "hazard_class": row[2],
                    "supplier": row[3],
                }

            return {
                "center": cas,
                "radius": radius,
                "chemicals": chemicals,
                "incompatibilities": incompatibilities,
            }

        except Exception as e:
            logger.error(f"Error getting neighborhood: {e}")
            return {}
