"""Matrix building and compatibility analysis for SDS data."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from ..config.settings import get_settings
from ..database import get_db_manager
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class MatrixStats:
    """Statistics for a chemical compatibility matrix."""

    total_chemicals: int
    incompatibility_pairs: int
    hazard_distribution: dict[str, int]
    processing_status: dict[str, int]  # success/warning/failed counts
    avg_completeness: float
    avg_confidence: float


@dataclass
class CompatibilityResult:
    """Result of checking chemical compatibility."""

    product1: str
    product2: str
    compatible: bool
    incompatibilities: list[str] = field(default_factory=list)
    confidence: float = 0.0
    hazard_class1: str | None = None
    hazard_class2: str | None = None


class MatrixBuilder:
    """Build chemical compatibility and hazard matrices from SDS extractions."""

    def __init__(self) -> None:
        """Initialize matrix builder."""
        self.db = get_db_manager()
        self.hazard_idlh_threshold = get_settings().hazard_idlh_threshold

    def build_incompatibility_matrix(
        self,
        filters: dict[str, Any] | None = None,
    ) -> pd.DataFrame:
        """Build a matrix of chemical incompatibilities.

        Args:
            filters: Optional filters (hazard_class, validation_status, etc.)

        Returns:
            DataFrame with chemicals as rows/columns, incompatibilities as values
        """
        try:
            # Get all documents/chemicals
            results = self.db.fetch_results()

            if not results:
                logger.warning("No documents found for matrix building")
                return pd.DataFrame()

            # Create product list
            products = {}
            for result in results:
                doc_id = result["id"]
                product_name = result.get("product_name", "Unknown")
                if product_name and doc_id not in products:
                    products[doc_id] = {
                        "name": product_name,
                        "hazard_class": result.get("hazard_class", "Unknown"),
                        "incompatibilities": result.get("incompatibilities", ""),
                        "cas": result.get("cas_number"),
                    }

            if not products:
                return pd.DataFrame()

            # Build matrix
            product_names = [p["name"] for p in products.values()]
            matrix = pd.DataFrame(
                index=product_names,
                columns=product_names,
                dtype=object,
            )

            # Fill matrix
            for doc_id, product_data in products.items():
                prod_name = product_data["name"]
                incomp_str = product_data.get("incompatibilities", "") or ""
                cas_a = product_data.get("cas")
                incomp_list = [i.strip() for i in incomp_str.split(",") if i.strip()]

                for other_doc_id, other_data in products.items():
                    other_name = other_data["name"]
                    if prod_name == other_name:
                        matrix.loc[prod_name, other_name] = "Self"
                    else:
                        # Prefer structured incompatibility rules by CAS
                        other_cas = products[other_doc_id].get("cas")
                        rule = (
                            self.db.get_incompatibility_rule(cas_a, other_cas)
                            if cas_a or other_cas
                            else None
                        )

                        if rule and rule.get("rule") == "I":
                            matrix.loc[prod_name, other_name] = "Incompatible"
                        elif rule and rule.get("rule") == "R":
                            matrix.loc[prod_name, other_name] = "Restricted"
                            self._log_decision(
                                prod_name,
                                other_name,
                                cas_a,
                                other_cas,
                                "R",
                                source_layer="structured_rule",
                                rule_source=rule.get("source"),
                                justification=rule.get("justification"),
                            )
                        elif any(
                            incomp.lower() in other_name.lower()
                            for incomp in incomp_list
                        ):
                            matrix.loc[prod_name, other_name] = "Incompatible"
                            self._log_decision(
                                prod_name,
                                other_name,
                                cas_a,
                                other_cas,
                                "I",
                                source_layer="text_incompatibility",
                                rule_source=None,
                                justification="Name match from SDS incompatibilities",
                            )
                        else:
                            # Elevate compatibility if hazard flags indicate higher risk
                            if self._should_elevate_due_to_hazard(cas_a, other_cas):
                                matrix.loc[prod_name, other_name] = "Restricted"
                                self._log_decision(
                                    prod_name,
                                    other_name,
                                    cas_a,
                                    other_cas,
                                    "R",
                                    source_layer="hazard_flags",
                                    rule_source=None,
                                    justification="Elevated by hazard flags/IDLH/env risk",
                                )
                            else:
                                matrix.loc[prod_name, other_name] = "Compatible"

            # Fill empty cells
            matrix = matrix.fillna("Unknown")

            logger.debug(
                "Built incompatibility matrix (%dx%d)", len(products), len(products)
            )
            return matrix

        except Exception as e:
            logger.error("Failed to build incompatibility matrix: %s", e)
            return pd.DataFrame()

    def build_hazard_matrix(
        self,
        filters: dict[str, Any] | None = None,
    ) -> pd.DataFrame:
        """Build a matrix of chemical hazard classes.

        Args:
            filters: Optional filters

        Returns:
            DataFrame with chemicals and their hazard classifications
        """
        try:
            results = self.db.fetch_results()

            if not results:
                return pd.DataFrame()

            data = []
            for result in results:
                data.append(
                    {
                        "Product": result.get("product_name", "Unknown"),
                        "Manufacturer": result.get("manufacturer", ""),
                        "Hazard Class": result.get("hazard_class", "Unknown"),
                        "UN Number": result.get("un_number", ""),
                        "CAS Number": result.get("cas_number", ""),
                        "Packing Group": result.get("packing_group", ""),
                        "H Statements": result.get("h_statements", ""),
                        "P Statements": result.get("p_statements", ""),
                        "Completeness": result.get("completeness", 0.0),
                        "Confidence": result.get("confidence", 0.0),
                    }
                )

            df = pd.DataFrame(data)
            logger.debug("Built hazard matrix with %d chemicals", len(df))
            return df

        except Exception as e:
            logger.error("Failed to build hazard matrix: %s", e)
            return pd.DataFrame()

    def check_compatibility(
        self,
        product1: str,
        product2: str,
        check_database: bool = True,
    ) -> CompatibilityResult:
        """Check compatibility between two chemicals.

        Args:
            product1: First chemical name
            product2: Second chemical name
            check_database: Whether to check database for stored incompatibilities

        Returns:
            CompatibilityResult with compatibility status
        """
        try:
            if check_database:
                # Query database for stored incompatibilities
                results = self.db.fetch_results()

                product1_data = None
                product2_data = None

                for result in results:
                    if product1.lower() in result.get("product_name", "").lower():
                        product1_data = result
                    if product2.lower() in result.get("product_name", "").lower():
                        product2_data = result

                if product1_data and product2_data:
                    incomp_str = product1_data.get("incompatibilities", "")
                    incompatibilities = [
                        i.strip() for i in incomp_str.split(",") if i.strip()
                    ]

                    is_compatible = not any(
                        inc.lower() in product2.lower() for inc in incompatibilities
                    )

                    return CompatibilityResult(
                        product1=product1,
                        product2=product2,
                        compatible=is_compatible,
                        incompatibilities=incompatibilities,
                        confidence=product1_data.get("confidence", 0.0),
                        hazard_class1=product1_data.get("hazard_class"),
                        hazard_class2=(
                            product2_data.get("hazard_class") if product2_data else None
                        ),
                    )

            # Fallback: assume compatible if not found
            return CompatibilityResult(
                product1=product1,
                product2=product2,
                compatible=True,
                incompatibilities=[],
                confidence=0.0,
            )

        except Exception as e:
            logger.error("Compatibility check failed: %s", e)
            return CompatibilityResult(
                product1=product1,
                product2=product2,
                compatible=True,
                incompatibilities=[],
            )

    def get_matrix_statistics(
        self,
        filters: dict[str, Any] | None = None,
    ) -> MatrixStats:
        """Calculate statistics for the chemical matrix.

        Args:
            filters: Optional filters

        Returns:
            MatrixStats with aggregate metrics
        """
        try:
            results = self.db.fetch_results()

            if not results:
                return MatrixStats(
                    total_chemicals=0,
                    incompatibility_pairs=0,
                    hazard_distribution={},
                    processing_status={},
                    avg_completeness=0.0,
                    avg_confidence=0.0,
                )

            hazard_dist: dict[str, int] = {}
            status_dist: dict[str, int] = {}
            total_completeness = 0.0
            total_confidence = 0.0
            incomp_count = 0
            unique_incomp_pairs = set()

            for result in results:
                # Hazard distribution
                hazard = result.get("hazard_class", "Unknown")
                hazard_dist[hazard] = hazard_dist.get(hazard, 0) + 1

                # Status distribution
                status = result.get("validation_status", "unknown")
                status_dist[status] = status_dist.get(status, 0) + 1

                # Completeness and confidence
                total_completeness += result.get("completeness", 0.0)
                total_confidence += result.get("confidence", 0.0)

                # Incompatibilities
                incomp_str = result.get("incompatibilities", "")
                if incomp_str:
                    incomp_list = [
                        i.strip() for i in incomp_str.split(",") if i.strip()
                    ]
                    incomp_count += len(incomp_list)

                    product = result.get("product_name", "Unknown")
                    for incomp in incomp_list:
                        pair = tuple(sorted([product, incomp]))
                        unique_incomp_pairs.add(pair)

            avg_completeness = total_completeness / len(results) if results else 0.0
            avg_confidence = total_confidence / len(results) if results else 0.0

            stats = MatrixStats(
                total_chemicals=len(results),
                incompatibility_pairs=len(unique_incomp_pairs),
                hazard_distribution=hazard_dist,
                processing_status=status_dist,
                avg_completeness=avg_completeness,
                avg_confidence=avg_confidence,
            )

            logger.info(
                "Matrix stats: %d chemicals, %d incompatibility pairs, %.1f%% avg completeness",
                stats.total_chemicals,
                stats.incompatibility_pairs,
                stats.avg_completeness * 100,
            )

            return stats

        except Exception as e:
            logger.error("Failed to calculate matrix statistics: %s", e)
            return MatrixStats(
                total_chemicals=0,
                incompatibility_pairs=0,
                hazard_distribution={},
                processing_status={},
                avg_completeness=0.0,
                avg_confidence=0.0,
            )

    def get_dangerous_chemicals(
        self,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Get list of dangerous chemicals.

        Args:
            filters: Optional additional filters

        Returns:
            List of dangerous chemical records
        """
        try:
            # Get all results and filter for dangerous ones
            results = self.db.fetch_results()
            results = [r for r in results if r.get("is_dangerous", False)]

            logger.info("Found %d dangerous chemicals", len(results))
            return results
        except Exception as e:
            logger.error("Failed to get dangerous chemicals: %s", e)
            return []

    def _should_elevate_due_to_hazard(
        self, cas_a: str | None, cas_b: str | None
    ) -> bool:
        """Determine if compatibility should be elevated based on hazard flags."""
        for cas in (cas_a, cas_b):
            if not cas:
                continue
            hazard = self.db.get_hazard_record(cas)
            if not hazard:
                continue

            # Consider env_risk or explicit hazard_flags marker as dangerous
            if hazard.get("env_risk"):
                return True

            flags = hazard.get("hazard_flags") or {}
            if isinstance(flags, dict) and flags.get("dangerous"):
                return True

            idlh = hazard.get("idlh")
            if idlh is not None and idlh <= self.hazard_idlh_threshold:
                return True

        return False

    def _log_decision(
        self,
        product_a: str,
        product_b: str,
        cas_a: str | None,
        cas_b: str | None,
        decision: str,
        source_layer: str,
        rule_source: str | None = None,
        justification: str | None = None,
    ) -> None:
        """Persist matrix decision for audit."""
        try:
            self.db.store_matrix_decision(
                product_a=product_a,
                product_b=product_b,
                cas_a=cas_a,
                cas_b=cas_b,
                decision=decision,
                source_layer=source_layer,
                rule_source=rule_source,
                justification=justification,
            )
        except Exception as exc:  # pragma: no cover - audit best-effort
            logger.debug("Failed to log matrix decision: %s", exc)

    def get_processing_summary(self) -> dict[str, Any]:
        """Get summary of all processed documents.

        Returns:
            Dictionary with processing statistics
        """
        try:
            stats = self.db.get_statistics()

            return {
                "total_documents": stats.get("total_documents", 0),
                "successful": stats.get("successful_documents", 0),
                "failed": stats.get("failed_documents", 0),
                "dangerous_count": stats.get("dangerous_count", 0),
                "avg_completeness": stats.get("avg_completeness", 0.0),
                "avg_confidence": stats.get("avg_confidence", 0.0),
                "total_fields_extracted": stats.get("total_fields_extracted", 0),
            }

        except Exception as e:
            logger.error("Failed to get processing summary: %s", e)
            return {}
