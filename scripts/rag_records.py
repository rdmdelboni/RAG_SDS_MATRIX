#!/usr/bin/env python3
"""
View RAG records and search the vector store.

Query and display actual documents, chunks, and structured data
from the RAG knowledge base.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

try:
    import duckdb
except ImportError as e:
    print(f"Error: Missing required library: {e}")
    sys.exit(1)

from src.utils.logger import get_logger

logger = get_logger("rag_records")


class RAGRecordViewer:
    """View actual records from RAG knowledge base."""

    def __init__(self, db_path: str = "data/duckdb/extractions.db"):
        self.db_path = Path(db_path)
        self.conn = self._connect_with_fallback()

    def _connect_with_fallback(self):
        """Connect to DuckDB, falling back to a temp copy if locked."""
        try:
            return duckdb.connect(str(self.db_path), read_only=True)
        except duckdb.IOException as exc:
            # DuckDB forbids concurrent readers when another process holds a write lock.
            if "Could not set lock" not in str(exc):
                logger.error("Failed to connect to database: %s", exc)
                raise

            try:
                tmp_dir = Path(tempfile.mkdtemp(prefix="rag_records_db_"))
                copy_path = tmp_dir / self.db_path.name
                shutil.copy2(self.db_path, copy_path)
                logger.warning(
                    "Database locked; using read-only copy at %s. Source: %s",
                    copy_path,
                    self.db_path,
                )
                return duckdb.connect(str(copy_path), read_only=True)
            except Exception as copy_exc:
                logger.error(
                    "Failed to open fallback copy: %s (original error: %s)",
                    copy_exc,
                    exc,
                )
                raise
        except Exception as exc:
            logger.error("Failed to connect to database: %s", exc)
            raise

    def search_incompatibilities(
        self,
        cas_a: str | None = None,
        cas_b: str | None = None,
        rule: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Search chemical incompatibilities."""
        try:
            where_clauses = []
            params: list[str | int] = []
            if cas_a:
                where_clauses.append("r.cas_a = ?")
                params.append(cas_a)
            if cas_b:
                where_clauses.append("r.cas_b = ?")
                params.append(cas_b)
            if rule:
                where_clauses.append("r.rule = ?")
                params.append(rule.upper())

            query = """
                SELECT 
                    r.cas_a,
                    h1.metadata AS meta_a,
                    r.cas_b,
                    h2.metadata AS meta_b,
                    r.rule,
                    r.source,
                    r.justification,
                    r.group_a,
                    r.group_b,
                    r.metadata
                FROM rag_incompatibilities r
                LEFT JOIN rag_hazards h1 ON h1.cas = r.cas_a
                LEFT JOIN rag_hazards h2 ON h2.cas = r.cas_b
            """

            if where_clauses:
                query += "\nWHERE " + " AND ".join(where_clauses)

            query += "\nLIMIT ?"
            params.append(limit)

            results = self.conn.execute(query, params).fetchall()

            records = []
            for row in results:
                meta_a = {}
                if row[1]:
                    try:
                        meta_a = json.loads(row[1])
                    except json.JSONDecodeError:
                        pass

                meta_b = {}
                if row[3]:
                    try:
                        meta_b = json.loads(row[3])
                    except json.JSONDecodeError:
                        pass

                metadata = {}
                if row[9]:
                    try:
                        metadata = json.loads(row[9])
                    except json.JSONDecodeError:
                        pass

                records.append(
                    {
                        "cas_a": row[0],
                        "name_a": meta_a.get("name"),
                        "cas_b": row[2],
                        "name_b": meta_b.get("name"),
                        "rule": row[4],
                        "source": row[5],
                        "justification": row[6],
                        "group_a": row[7],
                        "group_b": row[8],
                        "metadata": metadata,
                    }
                )

            return records
        except Exception as e:
            logger.error(f"Error searching incompatibilities: {e}")
            return []

    def search_hazards(
        self,
        cas: str | None = None,
        source: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Search chemical hazards."""
        try:
            where_clauses = []
            params: list[str | int] = []
            if cas:
                where_clauses.append("cas = ?")
                params.append(cas)
            if source:
                where_clauses.append("source = ?")
                params.append(source)

            query = """
                SELECT 
                    cas,
                    hazard_flags,
                    idlh,
                    pel,
                    rel,
                    env_risk,
                    source,
                    metadata
                FROM rag_hazards
            """

            if where_clauses:
                query += "\nWHERE " + " AND ".join(where_clauses)

            query += "\nLIMIT ?"
            params.append(limit)

            results = self.conn.execute(query, params).fetchall()

            records = []
            for row in results:
                hazard_flags = {}
                if row[1]:
                    try:
                        hazard_flags = json.loads(row[1])
                    except json.JSONDecodeError:
                        pass

                metadata = {}
                if row[7]:
                    try:
                        metadata = json.loads(row[7])
                    except json.JSONDecodeError:
                        pass

                records.append(
                    {
                        "cas": row[0],
                        "name": metadata.get("name"),
                        "hazard_flags": hazard_flags,
                        "idlh": row[2],
                        "pel": row[3],
                        "rel": row[4],
                        "env_risk": row[5],
                        "source": row[6],
                        "metadata": metadata,
                    }
                )

            return records
        except Exception as e:
            logger.error(f"Error searching hazards: {e}")
            return []

    def list_all_incompatibilities(self) -> list[dict]:
        """List all incompatibilities."""
        return self.search_incompatibilities(limit=1000)

    def list_all_hazards(self) -> list[dict]:
        """List all hazards."""
        return self.search_hazards(limit=1000)

    def get_cameo_chemicals(self, limit: int = 50) -> list[dict]:
        """Get CAMEO chemicals from documents."""
        try:
            query = f"""
                SELECT 
                    id,
                    title,
                    chunk_count,
                    source_url,
                    metadata
                FROM rag_documents
                WHERE source_type = 'cameo_chemical'
                LIMIT {limit}
            """

            results = self.conn.execute(query).fetchall()

            records = []
            for row in results:
                metadata = {}
                if row[4]:
                    try:
                        metadata = json.loads(row[4])
                    except json.JSONDecodeError:
                        pass

                records.append(
                    {
                        "id": row[0],
                        "title": row[1],
                        "chunk_count": row[2],
                        "url": row[3],
                        "metadata": metadata,
                    }
                )

            return records
        except Exception as e:
            logger.error(f"Error getting CAMEO chemicals: {e}")
            return []

    def get_file_documents(self, limit: int = 50) -> list[dict]:
        """Get file-based documents (PDFs, Excel, etc.)."""
        try:
            query = f"""
                SELECT 
                    id,
                    title,
                    chunk_count,
                    source_path,
                    source_url,
                    metadata
                FROM rag_documents
                WHERE source_type = 'file'
                LIMIT {limit}
            """

            results = self.conn.execute(query).fetchall()

            records = []
            for row in results:
                metadata = {}
                if row[5]:
                    try:
                        metadata = json.loads(row[5])
                    except json.JSONDecodeError:
                        pass

                records.append(
                    {
                        "id": row[0],
                        "title": row[1],
                        "chunk_count": row[2],
                        "path": row[3],
                        "url": row[4],
                        "metadata": metadata,
                    }
                )

            return records
        except Exception as e:
            logger.error(f"Error getting file documents: {e}")
            return []

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()


def print_incompatibilities(records: list[dict]):
    """Print incompatibility records."""
    if not records:
        print("No incompatibilities found.")
        return

    print("\n" + "=" * 90)
    print("🧪 CHEMICAL INCOMPATIBILITIES")
    print("=" * 90)

    for i, record in enumerate(records, 1):
        name_a = f" ({record['name_a']})" if record.get("name_a") else ""
        name_b = f" ({record['name_b']})" if record.get("name_b") else ""
        print(f"\n[{i}] {record['cas_a']}{name_a}  +  {record['cas_b']}{name_b}")
        print(f"    Rule: {record['rule']}")
        print(f"    Source: {record['source']}")
        if record["justification"]:
            justif = record["justification"][:70]
            print(f"    Justification: {justif}...")
        if record["metadata"]:
            print(f"    Metadata: {record['metadata']}")


def print_hazards(records: list[dict]):
    """Print hazard records."""
    if not records:
        print("No hazards found.")
        return

    print("\n" + "=" * 90)
    print("⚠️  CHEMICAL HAZARDS")
    print("=" * 90)

    for i, record in enumerate(records, 1):
        name = f" ({record['name']})" if record.get("name") else ""
        print(f"\n[{i}] CAS {record['cas']}{name}")
        print(f"    Source: {record['source']}")

        if record["hazard_flags"]:
            flags = ", ".join(f"{k}={v}" for k, v in record["hazard_flags"].items())
            print(f"    Flags: {flags}")

        if record["idlh"]:
            print(f"    IDLH: {record['idlh']} ppm")
        if record["pel"]:
            print(f"    PEL: {record['pel']} ppm")
        if record["rel"]:
            print(f"    REL: {record['rel']} ppm")

        env_risk = "Yes" if record["env_risk"] else "No"
        print(f"    Environmental Risk: {env_risk}")

        if record["metadata"]:
            meta_str = json.dumps(record["metadata"], indent=6)
            print(f"    Metadata:\n{meta_str}")


def print_cameo_chemicals(records: list[dict]):
    """Print CAMEO chemical records."""
    if not records:
        print("No CAMEO chemicals found.")
        return

    print("\n" + "=" * 90)
    print("🧪 CAMEO CHEMICALS")
    print("=" * 90)

    for i, record in enumerate(records, 1):
        print(f"\n[{i}] {record['title']}")
        print(f"    ID: {record['id']}")
        print(f"    Chunks: {record['chunk_count']}")
        print(f"    URL: {record['url']}")

        if record["metadata"]:
            meta = record["metadata"]
            if "chemical_id" in meta:
                print(f"    Chemical ID: {meta['chemical_id']}")
            if "cas_number" in meta:
                print(f"    CAS: {meta['cas_number']}")
            if "hazards" in meta:
                print(f"    Hazards: {meta['hazards']}")


def print_file_documents(records: list[dict]):
    """Print file document records."""
    if not records:
        print("No file documents found.")
        return

    print("\n" + "=" * 90)
    print("📄 FILE DOCUMENTS (PDFs, Excel, etc.)")
    print("=" * 90)

    for i, record in enumerate(records, 1):
        print(f"\n[{i}] {record['title']}")
        print(f"    ID: {record['id']}")
        print(f"    Chunks: {record['chunk_count']}")

        if record["path"]:
            print(f"    Path: {record['path']}")

        if record["metadata"]:
            meta = record["metadata"]
            if "sheet" in meta:
                print(f"    Sheet: {meta['sheet']}")
            if "rows" in meta:
                print(f"    Rows: {meta['rows']}")
            if "pages" in meta:
                print(f"    Pages: {meta['pages']}")


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="View RAG records and data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all incompatibilities
  python rag_records.py --incompatibilities

  # Find incompatibilities involving water
  python rag_records.py --incompatibilities --cas-b 7732-18-5

  # List all hazards
  python rag_records.py --hazards

  # Find hazards for specific CAS number
  python rag_records.py --hazards --cas 50-00-0

  # List CAMEO chemicals
  python rag_records.py --cameo --limit 20

  # List PDF/Excel files
  python rag_records.py --files
        """,
    )
    parser.add_argument(
        "--db",
        type=str,
        default="data/duckdb/extractions.db",
        help="Path to DuckDB database",
    )
    parser.add_argument(
        "--incompatibilities",
        action="store_true",
        help="Show chemical incompatibilities",
    )
    parser.add_argument(
        "--hazards",
        action="store_true",
        help="Show chemical hazards",
    )
    parser.add_argument(
        "--cameo",
        action="store_true",
        help="Show CAMEO chemicals",
    )
    parser.add_argument(
        "--files",
        action="store_true",
        help="Show file documents",
    )
    parser.add_argument(
        "--cas",
        type=str,
        help="Filter by CAS number",
    )
    parser.add_argument(
        "--cas-a",
        type=str,
        help="Filter incompatibilities by first CAS",
    )
    parser.add_argument(
        "--cas-b",
        type=str,
        help="Filter incompatibilities by second CAS",
    )
    parser.add_argument(
        "--rule",
        type=str,
        choices=["I", "R", "C"],
        help="Filter by incompatibility rule",
    )
    parser.add_argument(
        "--source",
        type=str,
        help="Filter by source",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum records to show",
    )

    args = parser.parse_args()

    try:
        viewer = RAGRecordViewer(args.db)

        if not (args.incompatibilities or args.hazards or args.cameo or args.files):
            # Show all by default
            args.incompatibilities = True
            args.hazards = True

        if args.incompatibilities:
            records = viewer.search_incompatibilities(
                cas_a=args.cas_a,
                cas_b=args.cas_b,
                rule=args.rule,
                limit=args.limit,
            )
            print_incompatibilities(records)

        if args.hazards:
            records = viewer.search_hazards(
                cas=args.cas,
                source=args.source,
                limit=args.limit,
            )
            print_hazards(records)

        if args.cameo:
            records = viewer.get_cameo_chemicals(limit=args.limit)
            print_cameo_chemicals(records)

        if args.files:
            records = viewer.get_file_documents(limit=args.limit)
            print_file_documents(records)

        viewer.close()

    except Exception as e:
        logger.exception(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())
