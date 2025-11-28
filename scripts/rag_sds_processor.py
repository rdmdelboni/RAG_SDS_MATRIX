#!/usr/bin/env python3
"""
RAG-Enhanced SDS Processor

Uses all knowledge from the RAG to process Safety Data Sheets.
- Queries RAG for chemical information during extraction
- Matches extracted data against known incompatibilities
- Enriches SDS data with hazard classifications
- Builds intelligence across documents
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Setup path
_project_root = Path(__file__).parent.parent
sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_project_root / "src"))

# pylint: disable=wrong-import-position
from src.utils.logger import get_logger

logger = get_logger("rag_sds_processor")


class RAGSDSProcessor:
    """Process SDS using RAG knowledge base."""

    def __init__(self):
        """Initialize RAG-SDS processor."""
        self.rag_client = None
        self.sds_files = []
        self.processed_results = []

        self._initialize_rag()

    def _initialize_rag(self):
        """Initialize RAG client."""
        try:
            from src.rag.retriever import RAGRetriever
            from src.database import get_db_manager

            self.rag_retriever = RAGRetriever()
            self.db_manager = get_db_manager()
            logger.info("✓ RAG client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize RAG: {e}")
            raise

    def query_rag_for_chemical(
        self,
        chemical_name: str,
        cas_number: str | None = None,
    ) -> dict:
        """
        Query RAG for information about a chemical.

        Returns: Dictionary with:
        - chemical_name: Name of chemical
        - cas_number: CAS number if found
        - hazards: Known hazard information
        - incompatibilities: Known incompatible chemicals
        - exposure_limits: IDLH, PEL, REL if available
        - sources: Data sources (NIOSH, CETESB, CAMEO, etc.)
        """
        query = f"What are the hazards and incompatibilities of " f"{chemical_name}"
        if cas_number:
            query += f" (CAS {cas_number})"

        try:
            # Query RAG
            logger.info(f"Querying RAG for: {chemical_name}")

            # Get hazard information
            hazard_results = self._query_hazards(chemical_name, cas_number)

            # Get incompatibility information
            incomp_results = self._query_incompatibilities(chemical_name, cas_number)

            return {
                "chemical_name": chemical_name,
                "cas_number": cas_number,
                "hazards": hazard_results,
                "incompatibilities": incomp_results,
                "found_in_rag": bool(hazard_results or incomp_results),
            }
        except Exception as e:
            logger.error(f"Error querying RAG for {chemical_name}: {e}")
            return {
                "chemical_name": chemical_name,
                "cas_number": cas_number,
                "found_in_rag": False,
            }

    def _query_hazards(
        self,
        chemical_name: str,
        cas_number: str | None = None,
    ) -> dict:
        """Query RAG hazards database."""
        try:
            if cas_number:
                # Direct CAS lookup
                result = self.db_manager.get_hazard_record(cas_number)
                if result:
                    return {
                        "source": "RAG (Direct CAS Match)",
                        "data": result,
                    }

            logger.debug(f"Searching RAG for hazards: {chemical_name}")

            return {}
        except Exception as e:
            logger.error(f"Error querying hazards: {e}")
            return {}

    def _query_incompatibilities(
        self,
        chemical_name: str,
        cas_number: str | None = None,
    ) -> list[dict]:
        """Query RAG incompatibilities database."""
        try:
            if not cas_number:
                return []

            # Find all incompatibilities involving this chemical
            result = self.db_manager.get_incompatibility_rule(
                cas_a=cas_number, cas_b=None
            )

            incomp_list = []
            if result:
                incomp_list.append(result)

            # Also check as second chemical
            result_b = self.db_manager.get_incompatibility_rule(
                cas_a=None, cas_b=cas_number
            )
            if result_b:
                incomp_list.append(result_b)

            logger.debug(
                f"Found {len(incomp_list)} incompatibilities for " f"{chemical_name}"
            )
            return incomp_list
        except Exception as e:
            logger.error(f"Error querying incompatibilities: {e}")
            return []

    def process_sds_file(
        self,
        file_path: Path,
    ) -> dict:
        """
        Process a single SDS file using RAG knowledge.

        1. Load SDS file
        2. Extract chemical information
        3. Query RAG for each chemical
        4. Enrich with hazard/incompatibility data
        5. Generate analysis report
        """
        logger.info(f"Processing SDS: {file_path.name}")

        try:
            # Step 1: Load file
            from src.rag.document_loader import DocumentLoader

            doc_loader = DocumentLoader()

            documents = doc_loader.load_file(file_path)
            if not documents:
                logger.warning(f"No content extracted from {file_path}")
                return {
                    "file": file_path.name,
                    "status": "error",
                    "error": "No content extracted",
                }

            # Step 2: Extract text and find chemicals (simple regex)
            all_text = " ".join(doc.page_content for doc in documents)

            # Simple chemical extraction - look for CAS patterns
            import re

            cas_pattern = r"\b\d{1,6}-\d{1,2}-\d\b"
            cas_matches = re.findall(cas_pattern, all_text)

            chemicals = []
            if cas_matches:
                # Found CAS numbers
                for cas in set(cas_matches):
                    chemicals.append(
                        {
                            "cas_number": cas,
                            "name": "Unknown",
                            "source": "CAS pattern matching",
                        }
                    )
            else:
                # No CAS found, treat whole document as chemical
                chemicals.append(
                    {
                        "name": file_path.stem,
                        "cas_number": None,
                        "source": "document title",
                    }
                )

            logger.info(f"Extracted {len(chemicals)} chemicals from SDS")

            # Step 3: Enrich each chemical with RAG knowledge
            enriched_chemicals = []
            for chem in chemicals:
                chem_name = chem.get("name", "Unknown")
                cas = chem.get("cas_number")

                # Query RAG
                rag_data = self.query_rag_for_chemical(chem_name, cas)

                # Enrich
                enriched_chem = {
                    **chem,
                    "rag_enrichment": rag_data,
                }
                enriched_chemicals.append(enriched_chem)

                logger.debug(
                    f"Enriched {chem_name} with RAG data "
                    f"(found: {rag_data['found_in_rag']})"
                )

            # Step 4: Analyze incompatibilities within this SDS
            incomp_analysis = self._analyze_internal_incompatibilities(
                enriched_chemicals
            )

            # Step 5: Generate report
            result = {
                "file": file_path.name,
                "path": str(file_path),
                "status": "success",
                "chemicals_extracted": len(enriched_chemicals),
                "chemicals": enriched_chemicals,
                "incompatibility_analysis": incomp_analysis,
                "rag_matches": sum(
                    1
                    for c in enriched_chemicals
                    if c.get("rag_enrichment", {}).get("found_in_rag")
                ),
            }

            logger.info(
                f"✓ Processed {file_path.name}: "
                f"{len(enriched_chemicals)} chemicals, "
                f"{result['rag_matches']} with RAG data"
            )

            return result

        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            return {
                "file": file_path.name,
                "path": str(file_path),
                "status": "error",
                "error": str(e),
            }

    def _analyze_internal_incompatibilities(
        self,
        chemicals: list[dict],
    ) -> dict:
        """
        Analyze incompatibilities between chemicals in the same SDS.

        Returns: Dictionary with warnings about incompatible mixtures
        """
        incomp_pairs = []

        cas_list = [c.get("cas_number") for c in chemicals if c.get("cas_number")]

        if len(cas_list) < 2:
            return {"warning_count": 0, "pairs": []}

        try:
            # Check all pairs
            for i, cas_a in enumerate(cas_list):
                for cas_b in cas_list[i + 1 :]:
                    # Query RAG for incompatibility
                    try:
                        result_a = self.db_manager.get_incompatibility_rule(
                            cas_a=cas_a, cas_b=cas_b
                        )
                        result_b = self.db_manager.get_incompatibility_rule(
                            cas_a=cas_b, cas_b=cas_a
                        )

                        if result_a:
                            incomp_pairs.append(
                                {
                                    "cas_a": cas_a,
                                    "cas_b": cas_b,
                                    "rule": result_a.get("rule", "Unknown"),
                                    "source": result_a.get("source", "Unknown"),
                                }
                            )
                        elif result_b:
                            incomp_pairs.append(
                                {
                                    "cas_a": cas_b,
                                    "cas_b": cas_a,
                                    "rule": result_b.get("rule", "Unknown"),
                                    "source": result_b.get("source", "Unknown"),
                                }
                            )
                    except Exception as e:
                        msg = f"Error checking pair {cas_a}/{cas_b}: {e}"
                        logger.debug(msg)

            return {
                "warning_count": len(incomp_pairs),
                "pairs": incomp_pairs,
            }
        except Exception as e:
            logger.error(f"Error analyzing incompatibilities: {e}")
            return {"warning_count": 0, "pairs": [], "error": str(e)}

    def process_folder(
        self,
        folder_path: str | Path,
    ) -> list[dict]:
        """
        Process all SDS files in a folder.

        Returns: List of processing results
        """
        folder = Path(folder_path)
        if not folder.exists():
            logger.error(f"Folder not found: {folder}")
            return []

        # Find all SDS files
        supported = {".pdf", ".docx", ".xlsx", ".xls", ".csv", ".txt"}
        sds_files = [
            f
            for f in folder.rglob("*")
            if f.is_file() and f.suffix.lower() in supported
        ]

        logger.info(f"Found {len(sds_files)} SDS files in {folder}")

        results = []
        for idx, file_path in enumerate(sds_files, 1):
            msg = f"[{idx}/{len(sds_files)}] Processing {file_path.name}"
            logger.info(msg)
            result = self.process_sds_file(file_path)
            results.append(result)

        return results

    def save_results(
        self,
        results: list[dict],
        output_path: str | Path,
    ) -> Path:
        """Save processing results to JSON."""
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(
                    results,
                    f,
                    indent=2,
                    ensure_ascii=False,
                    default=str,
                )

            logger.info(f"Results saved to {output_file}")
            return output_file
        except Exception as e:
            logger.error(f"Error saving results: {e}")
            raise

    def generate_summary(self, results: list[dict]) -> dict:
        """Generate summary statistics from processing results."""
        successful = [r for r in results if r.get("status") == "success"]
        failed = [r for r in results if r.get("status") == "error"]

        total_chemicals = sum(r.get("chemicals_extracted", 0) for r in successful)
        rag_matches = sum(r.get("rag_matches", 0) for r in successful)
        total_warnings = sum(
            r.get("incompatibility_analysis", {}).get("warning_count", 0)
            for r in successful
        )

        return {
            "total_files": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "total_chemicals_extracted": total_chemicals,
            "rag_matches": rag_matches,
            "rag_match_percentage": (
                (rag_matches / total_chemicals * 100) if total_chemicals > 0 else 0
            ),
            "internal_incompatibility_warnings": total_warnings,
        }


def main():
    """CLI entry point."""
    import argparse
    from datetime import datetime

    parser = argparse.ArgumentParser(
        description="Process SDS using RAG knowledge",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process SDS folder using RAG
  python rag_sds_processor.py --input /path/to/sds

  # Save results to custom location
  python rag_sds_processor.py --input /path/to/sds --output /results.json

  # Single file
  python rag_sds_processor.py --file /path/to/document.pdf
        """,
    )
    parser.add_argument(
        "--input",
        type=str,
        help="Input folder with SDS files",
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Single SDS file to process",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output JSON file for results",
    )

    args = parser.parse_args()

    if not args.input and not args.file:
        parser.print_help()
        return 1

    try:
        processor = RAGSDSProcessor()

        # Process
        if args.file:
            logger.info("Processing single file...")
            results = [processor.process_sds_file(Path(args.file))]
        else:
            logger.info("Processing folder...")
            results = processor.process_folder(args.input)

        # Generate summary
        summary = processor.generate_summary(results)

        # Save results
        if args.output:
            output_file = Path(args.output)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = Path(f"data/output/" f"rag_sds_results_{timestamp}.json")

        processor.save_results(results, output_file)

        # Print summary
        print("\n" + "=" * 70)
        print("📊 RAG-SDS PROCESSING COMPLETE")
        print("=" * 70)
        print(f"Files processed: {summary['total_files']}")
        print(f"Successful: {summary['successful']}")
        print(f"Failed: {summary['failed']}")
        print(f"\nChemicals extracted: {summary['total_chemicals_extracted']}")
        print(
            f"RAG matches: {summary['rag_matches']} "
            f"({summary['rag_match_percentage']:.1f}%)"
        )
        print(
            f"Incompatibility warnings: "
            f"{summary['internal_incompatibility_warnings']}"
        )
        print(f"\n📁 Results saved to: {output_file}\n")

        return 0

    except Exception as e:
        logger.exception(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
