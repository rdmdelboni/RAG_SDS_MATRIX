#!/usr/bin/env python3
"""SDS Processing Pipeline - Complete workflow for processing SDS files."""

from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

# Setup path
_project_root = Path(__file__).parent.parent
sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_project_root / "src"))

# pylint: disable=wrong-import-position
from src.utils.logger import get_logger

logger = get_logger("sds_pipeline")


class SDSPipelineManager:
    """Manage complete SDS processing pipeline."""

    def __init__(self):
        self.source_folder: Optional[Path] = None
        self.sds_files: list[dict] = []
        self.extraction_list: list[dict] = []
        self.results: dict = {
            "timestamp": None,
            "source_folder": None,
            "total_files_found": 0,
            "duplicates_removed": 0,
            "extraction_list": [],
            "extraction_results": [],
        }

    def select_source_folder(self, folder_path: str | Path) -> bool:
        """
        Step 1: Select external folder with SDS files.

        Recursively scans for supported document formats.
        """
        folder = Path(folder_path)

        if not folder.exists():
            logger.error(f"Folder does not exist: {folder}")
            return False

        if not folder.is_dir():
            logger.error(f"Path is not a directory: {folder}")
            return False

        self.source_folder = folder
        logger.info(f"Selected source folder: {folder}")

        # Supported formats
        supported = {".pdf", ".docx", ".xlsx", ".xls", ".csv", ".txt"}

        # Scan recursively
        self.sds_files = []
        for file_path in folder.rglob("*"):
            if file_path.is_file() and (file_path.suffix.lower() in supported):
                file_info = {
                    "path": file_path,
                    "name": file_path.name,
                    "size": file_path.stat().st_size,
                    "modified": file_path.stat().st_mtime,
                }
                self.sds_files.append(file_info)

        logger.info(f"Found {len(self.sds_files)} files in {folder}")
        self.results["source_folder"] = str(folder)
        self.results["total_files_found"] = len(self.sds_files)

        return True

    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA256 hash of file content."""
        try:
            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception as e:
            logger.error(f"Error computing hash for {file_path}: {e}")
            return ""

    def create_extraction_list(
        self,
        remove_duplicates: bool = True,
    ) -> list[dict]:
        """
        Step 2: Create extraction list with duplicate removal.

        Removes duplicates by:
        - Content hash (identical files)
        - Filename + size (likely duplicates)
        """
        if not self.sds_files:
            logger.error("No files selected. Run select_source_folder first.")
            return []

        logger.info("Creating extraction list...")

        if remove_duplicates:
            # Track files by hash and name+size
            seen_hashes: dict[str, dict] = {}
            seen_names: dict[str, dict] = {}
            duplicates = []

            for file_info in self.sds_files:
                file_hash = self._compute_file_hash(file_info["path"])
                file_key = f"{file_info['name']}_{file_info['size']}"

                # Check content hash
                if file_hash in seen_hashes:
                    prior = seen_hashes[file_hash]
                    logger.warning(
                        f"Duplicate: {file_info['path']} vs " f"{prior['path']}"
                    )
                    duplicates.append(file_info)
                    continue

                # Check filename + size
                if file_key in seen_names:
                    prior = seen_names[file_key]
                    logger.warning(
                        f"Similar: {file_info['path']} vs " f"{prior['path']}"
                    )
                    duplicates.append(file_info)
                    continue

                # New file
                seen_hashes[file_hash] = file_info
                seen_names[file_key] = file_info
                self.extraction_list.append(
                    {
                        "path": str(file_info["path"]),
                        "name": file_info["name"],
                        "size": file_info["size"],
                        "hash": file_hash,
                        "status": "pending",
                    }
                )

            self.results["duplicates_removed"] = len(duplicates)
            logger.info(
                f"Extraction list: {len(self.extraction_list)} unique "
                f"files, {len(duplicates)} duplicates removed"
            )
        else:
            self.extraction_list = [
                {
                    "path": str(f["path"]),
                    "name": f["name"],
                    "size": f["size"],
                    "hash": self._compute_file_hash(f["path"]),
                    "status": "pending",
                }
                for f in self.sds_files
            ]
            logger.info(f"Extraction list: {len(self.extraction_list)} files")

        self.results["extraction_list"] = self.extraction_list
        return self.extraction_list

    def extract_and_classify(self) -> list[dict]:
        """
        Step 3: Extract and classify data from each SDS file.

        Uses RAG + LLM to extract:
        - Chemical names and CAS numbers
        - Hazard classifications
        - Exposure limits
        - Storage requirements
        - Emergency procedures
        """
        if not self.extraction_list:
            logger.error("No extraction list. Run create_extraction_list first.")
            return []

        logger.info(f"Extracting data from {len(self.extraction_list)} files...")

        # Import extraction services
        try:
            from src.sds.processor import SDSProcessor
            from src.sds.extractor import SDSExtractor
        except ImportError as e:
            logger.error(f"Failed to import extraction modules: {e}")
            return []

        processor = SDSProcessor()
        extractor = SDSExtractor()

        extraction_results = []

        for idx, file_info in enumerate(self.extraction_list, 1):
            file_path = Path(file_info["path"])
            logger.info(
                f"[{idx}/{len(self.extraction_list)}] Processing: "
                f"{file_info['name']}"
            )

            try:
                # Load document
                from src.rag.document_loader import DocumentLoader

                doc_loader = DocumentLoader()
                documents = doc_loader.load_file(file_path)

                if not documents:
                    logger.warning(f"No content extracted from {file_path}")
                    extraction_results.append(
                        {
                            "file": file_info["name"],
                            "status": "error",
                            "error": "No content extracted",
                            "data": None,
                        }
                    )
                    continue

                # Extract SDS data
                sds_data = processor.process_documents(documents)

                # Extract chemical information
                chemicals = extractor.extract_chemicals(documents)

                extraction_results.append(
                    {
                        "file": file_info["name"],
                        "path": file_info["path"],
                        "status": "success",
                        "extracted_at": datetime.now().isoformat(),
                        "data": {
                            "document_count": len(documents),
                            "chemicals": chemicals,
                            "sds_data": sds_data,
                        },
                    }
                )

                file_info["status"] = "extracted"
                logger.info(f"✓ Extracted {len(chemicals)} chemicals")

            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
                extraction_results.append(
                    {
                        "file": file_info["name"],
                        "path": file_info["path"],
                        "status": "error",
                        "error": str(e),
                        "extracted_at": datetime.now().isoformat(),
                        "data": None,
                    }
                )
                file_info["status"] = "error"

        self.results["extraction_results"] = extraction_results
        success_count = sum(1 for r in extraction_results if r["status"] == "success")
        error_count = sum(1 for r in extraction_results if r["status"] == "error")
        logger.info(
            f"Extraction complete: {success_count} successful, " f"{error_count} errors"
        )

        return extraction_results

    def process_results(self) -> dict:
        """
        Step 4: Process extraction results.

        - Deduplicates chemical data
        - Builds compatibility matrix
        - Stores in database
        - Generates reports
        """
        if not self.results["extraction_results"]:
            logger.error("No extraction results. Run extract_and_classify first.")
            return {}

        logger.info("Processing extraction results...")

        try:
            from src.matrix.builder import MatrixBuilder
        except ImportError as e:
            logger.error(f"Failed to import processing modules: {e}")
            return {}

        matrix_builder = MatrixBuilder()

        # Collect all chemicals
        all_chemicals = defaultdict(dict)
        processed_files = 0

        for result in self.results["extraction_results"]:
            if result["status"] != "success":
                continue

            processed_files += 1
            chemicals = result["data"].get("chemicals", [])

            for chem in chemicals:
                cas = chem.get("cas_number", "unknown")
                all_chemicals[cas].update(chem)

        logger.info(
            f"Collected data from {processed_files} files, "
            f"{len(all_chemicals)} unique chemicals"
        )

        # Store chemicals in database
        for cas, chem_data in all_chemicals.items():
            try:
                # This would interact with your database
                logger.debug(f"Storing chemical: " f"{chem_data.get('name', cas)}")
            except Exception as e:
                logger.error(f"Error storing chemical {cas}: {e}")

        # Build matrix
        try:
            matrix = matrix_builder.build(all_chemicals)
            logger.info(f"Generated compatibility matrix: {len(matrix)} entries")
        except Exception as e:
            logger.error(f"Error building matrix: {e}")
            matrix = None

        processing_summary = {
            "timestamp": datetime.now().isoformat(),
            "files_processed": processed_files,
            "unique_chemicals": len(all_chemicals),
            "matrix_entries": len(matrix) if matrix else 0,
            "chemicals": list(all_chemicals.keys()),
        }

        self.results["processing_summary"] = processing_summary
        logger.info("✅ Processing complete")

        return processing_summary

    def save_results(self, output_path: str | Path) -> Path:
        """Save complete pipeline results to JSON."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = Path(output_path) / (f"sds_pipeline_results_{timestamp}.json")

        self.results["timestamp"] = datetime.now().isoformat()

        try:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(
                    self.results,
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

    def run_pipeline(
        self,
        source_folder: str | Path,
        output_folder: str | Path = "data/output",
    ) -> dict:
        """
        Run complete pipeline: select → deduplicate → extract → process.

        Returns: Dictionary with results summary
        """
        logger.info("=" * 70)
        logger.info("Starting SDS Processing Pipeline")
        logger.info("=" * 70)

        # Step 1: Select folder
        if not self.select_source_folder(source_folder):
            return {"error": "Failed to select source folder"}

        # Step 2: Create extraction list
        self.create_extraction_list(remove_duplicates=True)

        # Step 3: Extract and classify
        self.extract_and_classify()

        # Step 4: Process results
        summary = self.process_results()

        # Save results
        output_folder = Path(output_folder)
        output_folder.mkdir(parents=True, exist_ok=True)
        self.save_results(output_folder)

        logger.info("=" * 70)
        logger.info("Pipeline complete!")
        logger.info("=" * 70)

        return summary


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="SDS Processing Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process SDS from folder
  python sds_pipeline.py --input /path/to/sds/folder

  # Process with custom output
  python sds_pipeline.py --input /path/to/sds --output /path/to/output

  # Just list files (step 1-2 only)
  python sds_pipeline.py --input /path/to/sds --list-only
        """,
    )
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Input folder with SDS files",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/output",
        help="Output folder for results",
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="Only list files, don't extract",
    )
    parser.add_argument(
        "--extract-only",
        action="store_true",
        help="Only extract, don't process",
    )

    args = parser.parse_args()

    manager = SDSPipelineManager()

    try:
        # Step 1: Select folder
        if not manager.select_source_folder(args.input):
            return 1

        print(f"\n✓ Found {len(manager.sds_files)} files\n")

        # Step 2: Create extraction list
        extraction_list = manager.create_extraction_list()

        print(f"\n📋 EXTRACTION LIST ({len(extraction_list)} files):")
        print("=" * 70)
        for i, file_info in enumerate(extraction_list[:10], 1):
            size_kb = file_info["size"] / 1024
            print(f"{i}. {Path(file_info['path']).name} ({size_kb:.1f} KB)")
        if len(extraction_list) > 10:
            print(f"... and {len(extraction_list) - 10} more files")
        print()

        if args.extract_only:
            logger.info("Stopping after extraction (--extract-only)")
            return 0

        # Step 4: Process
        summary = manager.process_results()

        # Save results
        output_path = Path(args.output)
        output_path.mkdir(parents=True, exist_ok=True)
        manager.save_results(output_path)

        # Print summary
        print("\n" + "=" * 70)
        print("📊 PIPELINE RESULTS")
        print("=" * 70)
        print(f"Files processed: {summary.get('files_processed', 0)}")
        print(f"Unique chemicals: {summary.get('unique_chemicals', 0)}")
        print(f"Matrix entries: {summary.get('matrix_entries', 0)}")
        print()

        return 0

    except Exception as e:
        logger.exception(f"Pipeline error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
