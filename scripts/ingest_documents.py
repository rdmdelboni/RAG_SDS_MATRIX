#!/usr/bin/env python3
"""
Ingest documents (PDFs, XLSX) from input folder with multi-language support.

Supports Portuguese and English documents. Automatically detects language
and configures chunking/extraction accordingly.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from src.rag.ingestion_service import KnowledgeIngestionService
from src.utils.logger import get_logger

logger = get_logger("ingest_documents")


def detect_language(file_path: Path) -> str:
    """Detect document language (pt or en) from filename or content preview."""
    filename_lower = file_path.name.lower()

    # Portuguese indicators
    pt_keywords = [
        "português",
        "pt",
        "guia",
        "tabela",
        "incompatibilidade",
        "ufv",
        "cois",
        "cbpf",
    ]
    en_keywords = [
        "english",
        "en",
        "guide",
        "chart",
        "table",
        "incompatibility",
        "chemical",
    ]

    # Check filename
    for keyword in pt_keywords:
        if keyword in filename_lower:
            return "pt"

    for keyword in en_keywords:
        if keyword in filename_lower:
            return "en"

    # Default to Portuguese for Brazilian documents, English otherwise
    if any(
        x in filename_lower for x in ["ufv", "cbpf", "cois", "guia", "incompatibilidad"]
    ):
        return "pt"

    return "en"


def ingest_folder(
    folder_path: str | Path,
    file_extensions: list[str] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Ingest all documents from a folder.

    Args:
        folder_path: Path to folder containing documents
        file_extensions: List of extensions to ingest (default: [.pdf, .xlsx])
        dry_run: If True, only report what would be ingested

    Returns:
        Dictionary with ingestion statistics
    """
    folder_path = Path(folder_path)
    if not folder_path.exists():
        logger.error(f"Folder not found: {folder_path}")
        return {"error": "Folder not found"}

    if file_extensions is None:
        file_extensions = [".pdf", ".xlsx"]

    service = KnowledgeIngestionService()

    # Find all documents
    documents = []
    for ext in file_extensions:
        documents.extend(folder_path.glob(f"*{ext}"))

    documents = sorted(set(documents))  # Remove duplicates

    if not documents:
        logger.warning(f"No documents found in {folder_path}")
        return {"total": 0, "processed": 0, "skipped": 0, "errors": 0}

    logger.info(f"Found {len(documents)} documents")
    logger.info("=" * 70)

    stats = {
        "total": len(documents),
        "processed": 0,
        "skipped": 0,
        "errors": 0,
        "by_language": {"pt": 0, "en": 0},
        "details": [],
    }

    for doc_path in documents:
        lang = detect_language(doc_path)
        stats["by_language"][lang] += 1

        # Skip incomplete downloads
        if doc_path.suffix == ".crdownload":
            logger.debug(f"⊘ {doc_path.name} (incomplete download)")
            stats["skipped"] += 1
            stats["details"].append(
                {"file": doc_path.name, "status": "skipped", "reason": "incomplete"}
            )
            continue

        if dry_run:
            logger.info(f"[DRY-RUN] {doc_path.name} ({lang.upper()})")
            continue

        try:
            # Check file size (skip if > 50MB)
            file_size_mb = doc_path.stat().st_size / (1024 * 1024)
            if file_size_mb > 50:
                logger.warning(f"⊘ {doc_path.name} ({file_size_mb:.1f}MB - too large)")
                stats["skipped"] += 1
                stats["details"].append(
                    {"file": doc_path.name, "status": "skipped", "reason": "too_large"}
                )
                continue

            logger.info(
                f"Processing: {doc_path.name} ({lang.upper()}) [{file_size_mb:.1f}MB]"
            )

            result = service.ingest_local_files([doc_path])

            chunks_added = result.chunks_added
            logger.info(f"✓ {doc_path.name} - {chunks_added} chunks")
            stats["processed"] += 1
            stats["details"].append(
                {
                    "file": doc_path.name,
                    "language": lang,
                    "status": "success",
                    "chunks": chunks_added,
                }
            )

        except FileExistsError as e:
            if "already processed" in str(e):
                logger.debug(f"⊘ {doc_path.name} (already in vector store)")
                stats["skipped"] += 1
                stats["details"].append(
                    {
                        "file": doc_path.name,
                        "status": "skipped",
                        "reason": "already_processed",
                    }
                )
            else:
                logger.error(f"✗ {doc_path.name}: {str(e)[:80]}")
                stats["errors"] += 1
                stats["details"].append(
                    {"file": doc_path.name, "status": "error", "error": str(e)[:80]}
                )

        except Exception as e:
            logger.error(f"✗ {doc_path.name}: {str(e)[:80]}")
            stats["errors"] += 1
            stats["details"].append(
                {"file": doc_path.name, "status": "error", "error": str(e)[:80]}
            )

    logger.info("=" * 70)
    logger.info(
        f"SUMMARY: Processed={stats['processed']}, Skipped={stats['skipped']}, Errors={stats['errors']}"
    )
    logger.info(
        f"Languages: Portuguese={stats['by_language']['pt']}, English={stats['by_language']['en']}"
    )

    return stats


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Ingest documents from input folder")
    parser.add_argument(
        "--folder",
        type=str,
        default="data/input",
        help="Folder containing documents (default: data/input)",
    )
    parser.add_argument(
        "--extensions",
        type=str,
        default="pdf,xlsx",
        help="File extensions to ingest (comma-separated, default: pdf,xlsx)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be ingested without actually ingesting",
    )

    args = parser.parse_args()

    extensions = [f".{ext.strip()}" for ext in args.extensions.split(",")]

    print("\n" + "=" * 70)
    print("  Document Ingestion - Multi-Language Support")
    print("=" * 70)
    print(f"Folder: {args.folder}")
    print(f"Extensions: {', '.join(extensions)}")
    if args.dry_run:
        print("Mode: DRY-RUN (no actual ingestion)")
    print("=" * 70 + "\n")

    stats = ingest_folder(args.folder, extensions, dry_run=args.dry_run)

    # Print summary
    if "error" in stats:
        print(f"\n❌ Error: {stats['error']}")
        return 1

    print(f"\n📊 RESULTS:")
    print(f"  Total Documents: {stats['total']}")
    print(f"  Processed: {stats['processed']} ✓")
    print(f"  Skipped: {stats['skipped']} ⊘")
    print(f"  Errors: {stats['errors']} ✗")
    print(f"  Portuguese: {stats['by_language']['pt']}")
    print(f"  English: {stats['by_language']['en']}\n")

    return 0 if stats["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
