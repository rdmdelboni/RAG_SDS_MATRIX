#!/usr/bin/env python3
"""
View RAG ingestion status and content.

Shows what documents have been ingested into the RAG knowledge base,
including source types, document counts, and metadata.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

try:
    import duckdb
    import json
except ImportError as e:
    print(f"Error: Missing required library: {e}")
    sys.exit(1)

from src.utils.logger import get_logger

logger = get_logger("rag_status")


class RAGStatusViewer:
    """Utility to view RAG ingestion status."""

    def __init__(self, db_path: str = "data/duckdb/extractions.db"):
        self.db_path = db_path
        try:
            self.conn = duckdb.connect(db_path, read_only=True)
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    def get_overall_stats(self) -> dict:
        """Get overall ingestion statistics."""
        try:
            total_docs = self.conn.execute(
                "SELECT COUNT(*) FROM rag_documents"
            ).fetchall()[0][0]

            source_types = self.conn.execute(
                """
                SELECT source_type, COUNT(*) as count
                FROM rag_documents
                GROUP BY source_type
                ORDER BY count DESC
                """
            ).fetchall()

            total_chunks = self.conn.execute(
                "SELECT SUM(chunk_count) FROM rag_documents"
            ).fetchall()[0][0]

            return {
                "total_documents": total_docs,
                "total_chunks": total_chunks or 0,
                "source_types": source_types,
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}

    def list_documents(
        self,
        source_type: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """List ingested documents."""
        try:
            if source_type:
                query = f"""
                    SELECT 
                        id,
                        source_type,
                        title,
                        chunk_count,
                        indexed_at,
                        source_url
                    FROM rag_documents
                    WHERE source_type = '{source_type}'
                    ORDER BY indexed_at DESC
                    LIMIT {limit}
                """
            else:
                query = f"""
                    SELECT 
                        id,
                        source_type,
                        title,
                        chunk_count,
                        indexed_at,
                        source_url
                    FROM rag_documents
                    ORDER BY indexed_at DESC
                    LIMIT {limit}
                """

            results = self.conn.execute(query).fetchall()

            documents = []
            for row in results:
                documents.append(
                    {
                        "id": row[0],
                        "source_type": row[1],
                        "title": row[2],
                        "chunk_count": row[3],
                        "indexed_at": row[4],
                        "source_url": row[5],
                    }
                )

            return documents
        except Exception as e:
            logger.error(f"Error listing documents: {e}")
            return []

    def get_document_details(self, doc_id: int) -> dict | None:
        """Get detailed information about a specific document."""
        try:
            result = self.conn.execute(
                f"""
                SELECT 
                    id,
                    source_type,
                    title,
                    chunk_count,
                    indexed_at,
                    source_url,
                    metadata
                FROM rag_documents
                WHERE id = {doc_id}
                """
            ).fetchall()

            if not result:
                return None

            row = result[0]
            metadata = {}
            if row[6]:
                try:
                    metadata = json.loads(row[6])
                except json.JSONDecodeError:
                    metadata = {"raw": row[6]}

            return {
                "id": row[0],
                "source_type": row[1],
                "title": row[2],
                "chunk_count": row[3],
                "indexed_at": row[4],
                "source_url": row[5],
                "metadata": metadata,
            }
        except Exception as e:
            logger.error(f"Error getting document details: {e}")
            return None

    def get_by_source_type(self) -> dict[str, list]:
        """Get documents grouped by source type."""
        try:
            results = self.conn.execute(
                """
                SELECT source_type
                FROM rag_documents
                GROUP BY source_type
                ORDER BY source_type
                """
            ).fetchall()

            grouped = {}
            for (source_type,) in results:
                docs = self.list_documents(source_type=source_type, limit=100)
                grouped[source_type] = docs

            return grouped
        except Exception as e:
            logger.error(f"Error grouping by source: {e}")
            return {}

    def get_incompatibilities(self) -> dict:
        """Get incompatibility ingestion status."""
        try:
            count = self.conn.execute(
                "SELECT COUNT(*) FROM rag_incompatibilities"
            ).fetchall()[0][0]

            if count == 0:
                return {"count": 0, "samples": []}

            samples = self.conn.execute(
                """
                SELECT cas_a, cas_b, rule, source
                FROM rag_incompatibilities
                LIMIT 10
                """
            ).fetchall()

            return {
                "count": count,
                "samples": [
                    {
                        "cas_a": s[0],
                        "cas_b": s[1],
                        "rule": s[2],
                        "source": s[3],
                    }
                    for s in samples
                ],
            }
        except Exception as e:
            logger.error(f"Error getting incompatibilities: {e}")
            return {"count": 0}

    def get_hazards(self) -> dict:
        """Get hazard ingestion status."""
        try:
            count = self.conn.execute("SELECT COUNT(*) FROM rag_hazards").fetchall()[0][
                0
            ]

            if count == 0:
                return {"count": 0, "samples": []}

            samples = self.conn.execute(
                """
                SELECT cas, hazard_flags, idlh, source
                FROM rag_hazards
                LIMIT 10
                """
            ).fetchall()

            return {
                "count": count,
                "samples": [
                    {
                        "cas": s[0],
                        "hazard_flags": s[1],
                        "idlh": s[2],
                        "source": s[3],
                    }
                    for s in samples
                ],
            }
        except Exception as e:
            logger.error(f"Error getting hazards: {e}")
            return {"count": 0}

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()


def print_stats(viewer: RAGStatusViewer):
    """Print overall statistics."""
    stats = viewer.get_overall_stats()

    print("\n" + "=" * 70)
    print("📊 RAG INGESTION STATUS")
    print("=" * 70)
    print(f"Total Documents:        {stats.get('total_documents', 0)}")
    print(f"Total Chunks:           {stats.get('total_chunks', 0)}")

    print("\nBreakdown by Source Type:")
    for source_type, count in stats.get("source_types", []):
        print(f"  • {source_type:20s} {count:6d} documents")

    print("=" * 70)


def print_documents(viewer: RAGStatusViewer, source_type: str | None = None):
    """Print document list."""
    docs = viewer.list_documents(source_type=source_type, limit=20)

    if source_type:
        print(f"\n📄 Documents from '{source_type}':")
    else:
        print("\n📄 Recently Ingested Documents:")

    print("-" * 70)

    for doc in docs:
        source_label = doc["source_url"] or doc["source_type"]
        print(
            f"ID: {doc['id']:5d} | Chunks: {doc['chunk_count']:4d} | "
            f"{doc['title'][:40]}"
        )
        print(f"      Source: {source_label[:60]}")
        print()


def print_grouped(viewer: RAGStatusViewer):
    """Print documents grouped by source."""
    grouped = viewer.get_by_source_type()

    print("\n📦 INGESTION BY SOURCE TYPE")
    print("=" * 70)

    for source_type, docs in sorted(grouped.items()):
        print(f"\n{source_type.upper()} ({len(docs)} documents)")
        print("-" * 70)

        for doc in docs[:5]:  # Show first 5 of each type
            print(f"  • {doc['title'][:55]} ({doc['chunk_count']} chunks)")

        if len(docs) > 5:
            print(f"  ... and {len(docs) - 5} more")


def print_structured_data(viewer: RAGStatusViewer):
    """Print structured data (incompatibilities and hazards)."""
    print("\n" + "=" * 70)
    print("🧪 STRUCTURED DATA")
    print("=" * 70)

    # Incompatibilities
    incomp = viewer.get_incompatibilities()
    print(f"\nChemical Incompatibilities: {incomp['count']} total")
    if incomp.get("samples"):
        print("Sample rules:")
        for sample in incomp["samples"][:3]:
            print(
                f"  • {sample['cas_a']} + {sample['cas_b']} "
                f"→ {sample['rule']} ({sample['source']})"
            )

    # Hazards
    hazards = viewer.get_hazards()
    print(f"\nChemical Hazards: {hazards['count']} total")
    if hazards.get("samples"):
        print("Sample hazards:")
        for sample in hazards["samples"][:3]:
            print(f"  • CAS {sample['cas']}: {sample['source']}")


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="View RAG ingestion status and content",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show overall status
  python rag_status.py

  # List documents from specific source
  python rag_status.py --source pdf

  # Show grouped view
  python rag_status.py --grouped

  # Show document details
  python rag_status.py --detail 1

  # Show all PDFs
  python rag_status.py --source pdf --list
        """,
    )
    parser.add_argument(
        "--db",
        type=str,
        default="data/duckdb/extractions.db",
        help="Path to DuckDB database",
    )
    parser.add_argument(
        "--source",
        type=str,
        help="Filter by source type (pdf, cameo_chemical, file, etc.)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List documents",
    )
    parser.add_argument(
        "--grouped",
        action="store_true",
        help="Show grouped by source type",
    )
    parser.add_argument(
        "--detail",
        type=int,
        help="Show details for specific document ID",
    )
    parser.add_argument(
        "--structured",
        action="store_true",
        help="Show structured data (incompatibilities, hazards)",
    )

    args = parser.parse_args()

    try:
        viewer = RAGStatusViewer(args.db)

        if args.detail:
            # Show document details
            doc = viewer.get_document_details(args.detail)
            if doc:
                print("\n" + "=" * 70)
                print(f"📋 DOCUMENT DETAILS (ID: {args.detail})")
                print("=" * 70)
                print(f"Title:        {doc['title']}")
                print(f"Source Type:  {doc['source_type']}")
                print(f"Chunks:       {doc['chunk_count']}")
                print(f"Indexed:      {doc['indexed_at']}")
                if doc["source_url"]:
                    print(f"URL:          {doc['source_url']}")
                if doc["metadata"]:
                    print("Metadata:")
                    print(json.dumps(doc["metadata"], indent=2))
                print("=" * 70)
            else:
                print(f"Document {args.detail} not found")

        elif args.grouped:
            print_grouped(viewer)

        elif args.structured:
            print_structured_data(viewer)

        elif args.list:
            print_documents(viewer, source_type=args.source)

        else:
            # Default: show stats
            print_stats(viewer)

            if args.source:
                print_documents(viewer, source_type=args.source)
            else:
                print_documents(viewer)
                print_structured_data(viewer)

        viewer.close()

    except Exception as e:
        logger.exception(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())
