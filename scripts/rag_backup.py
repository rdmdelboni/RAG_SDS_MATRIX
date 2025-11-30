#!/usr/bin/env python3
"""
Backup RAG ingested data to external folder.

Exports all documents, incompatibilities, hazards, and metadata
to JSON/CSV for archival and sharing.
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime
from pathlib import Path

try:
    import duckdb
except ImportError as e:
    print(f"Error: Missing required library: {e}")
    sys.exit(1)

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from src.utils.logger import get_logger

logger = get_logger("rag_backup")


class RAGBackupManager:
    """Manage RAG data backups."""

    def __init__(self, db_path: str = "data/duckdb/extractions.db"):
        self.db_path = db_path
        try:
            self.conn = duckdb.connect(db_path, read_only=True)
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    def _serialize_datetime(self, obj):
        """JSON serializer for datetime objects."""
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not JSON serializable")

    def backup_incompatibilities(self, output_dir: Path) -> dict:
        """Backup incompatibilities to JSON and CSV."""
        try:
            query = """
                SELECT
                    cas_a,
                    cas_b,
                    rule,
                    source,
                    justification,
                    metadata
                FROM rag_incompatibilities
                ORDER BY source, cas_a, cas_b
            """

            results = self.conn.execute(query).fetchall()

            # Convert to JSON-serializable format
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
                        "cas_a": row[0],
                        "cas_b": row[1],
                        "rule": row[2],
                        "source": row[3],
                        "justification": row[4],
                        "metadata": metadata,
                    }
                )

            # Write JSON
            json_file = output_dir / "incompatibilities.json"
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2, ensure_ascii=False)

            # Write CSV
            csv_file = output_dir / "incompatibilities.csv"
            if records:
                with open(csv_file, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(
                        f,
                        fieldnames=[
                            "cas_a",
                            "cas_b",
                            "rule",
                            "source",
                            "justification",
                        ],
                    )
                    writer.writeheader()
                    for record in records:
                        writer.writerow(
                            {
                                "cas_a": record["cas_a"],
                                "cas_b": record["cas_b"],
                                "rule": record["rule"],
                                "source": record["source"],
                                "justification": record["justification"],
                            }
                        )

            logger.info(
                f"Backed up {len(records)} incompatibilities to "
                f"{json_file} and {csv_file}"
            )
            return {"count": len(records), "json": str(json_file), "csv": str(csv_file)}

        except Exception as e:
            logger.error(f"Error backing up incompatibilities: {e}")
            raise

    def backup_hazards(self, output_dir: Path) -> dict:
        """Backup hazards to JSON and CSV."""
        try:
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
                ORDER BY source, cas
            """

            results = self.conn.execute(query).fetchall()

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
                        "hazard_flags": hazard_flags,
                        "idlh": row[2],
                        "pel": row[3],
                        "rel": row[4],
                        "env_risk": row[5],
                        "source": row[6],
                        "metadata": metadata,
                    }
                )

            # Write JSON
            json_file = output_dir / "hazards.json"
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2, ensure_ascii=False)

            # Write CSV
            csv_file = output_dir / "hazards.csv"
            if records:
                with open(csv_file, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(
                        f,
                        fieldnames=[
                            "cas",
                            "idlh",
                            "pel",
                            "rel",
                            "env_risk",
                            "source",
                        ],
                    )
                    writer.writeheader()
                    for record in records:
                        writer.writerow(
                            {
                                "cas": record["cas"],
                                "idlh": record["idlh"],
                                "pel": record["pel"],
                                "rel": record["rel"],
                                "env_risk": record["env_risk"],
                                "source": record["source"],
                            }
                        )

            logger.info(
                f"Backed up {len(records)} hazards to {json_file} and " f"{csv_file}"
            )
            return {"count": len(records), "json": str(json_file), "csv": str(csv_file)}

        except Exception as e:
            logger.error(f"Error backing up hazards: {e}")
            raise

    def backup_documents(self, output_dir: Path) -> dict:
        """Backup documents index to JSON and CSV."""
        try:
            query = """
                SELECT
                    id,
                    title,
                    source_type,
                    chunk_count,
                    source_path,
                    source_url,
                    metadata
                FROM rag_documents
                ORDER BY source_type, id
            """

            results = self.conn.execute(query).fetchall()

            records = []
            for row in results:
                metadata = {}
                if row[6]:
                    try:
                        metadata = json.loads(row[6])
                    except json.JSONDecodeError:
                        pass

                records.append(
                    {
                        "id": row[0],
                        "title": row[1],
                        "source_type": row[2],
                        "chunk_count": row[3],
                        "source_path": row[4],
                        "source_url": row[5],
                        "metadata": metadata,
                    }
                )

            # Write JSON
            json_file = output_dir / "documents_index.json"
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2, ensure_ascii=False)

            # Write CSV
            csv_file = output_dir / "documents_index.csv"
            if records:
                with open(csv_file, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(
                        f,
                        fieldnames=[
                            "id",
                            "title",
                            "source_type",
                            "chunk_count",
                            "source_path",
                            "source_url",
                        ],
                    )
                    writer.writeheader()
                    for record in records:
                        writer.writerow(
                            {
                                "id": record["id"],
                                "title": record["title"],
                                "source_type": record["source_type"],
                                "chunk_count": record["chunk_count"],
                                "source_path": record["source_path"] or "",
                                "source_url": record["source_url"] or "",
                            }
                        )

            logger.info(
                f"Backed up {len(records)} documents to {json_file} and " f"{csv_file}"
            )
            return {"count": len(records), "json": str(json_file), "csv": str(csv_file)}

        except Exception as e:
            logger.error(f"Error backing up documents: {e}")
            raise

    def backup_all(self, backup_path: str | Path) -> dict:
        """Create full backup of all RAG data."""
        backup_dir = Path(backup_path)
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        versioned_dir = backup_dir / f"rag_backup_{timestamp}"
        versioned_dir.mkdir(exist_ok=True)

        try:
            logger.info(f"Starting RAG backup to {versioned_dir}")

            results = {
                "timestamp": timestamp,
                "backup_path": str(versioned_dir),
                "data": {},
            }

            # Backup each component
            results["data"]["incompatibilities"] = self.backup_incompatibilities(
                versioned_dir
            )
            results["data"]["hazards"] = self.backup_hazards(versioned_dir)
            results["data"]["documents"] = self.backup_documents(versioned_dir)

            # Write summary
            summary_file = versioned_dir / "backup_summary.json"
            with open(summary_file, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)

            total_records = (
                results["data"]["incompatibilities"]["count"]
                + results["data"]["hazards"]["count"]
                + results["data"]["documents"]["count"]
            )

            logger.info(
                f"✅ Backup complete! {total_records} records backed up to "
                f"{versioned_dir}"
            )

            return results

        except Exception as e:
            logger.error(f"Backup failed: {e}")
            raise

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Backup RAG ingested data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Backup to external folder
  python rag_backup.py --output /mnt/external/rag_backups

  # Backup with custom database
  python rag_backup.py --output ./backups --db data/duckdb/extractions.db

  # Show what would be backed up
  python rag_backup.py --output ./backups --dry-run
        """,
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Output directory for backup (creates versioned subdir)",
    )
    parser.add_argument(
        "--db",
        type=str,
        default="data/duckdb/extractions.db",
        help="Path to DuckDB database",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be backed up without creating files",
    )

    args = parser.parse_args()

    try:
        if args.dry_run:
            logger.info("DRY RUN MODE - No files will be created")
            logger.info(f"Would backup to: {args.output}")
            return 0

        # Validate DB path exists
        db_path = Path(args.db)
        if not db_path.exists():
            logger.error(f"Database file not found: {db_path}")
            print(f"Error: Database file not found: {db_path}")
            return 1

        # Always use temporary copy to avoid file lock contention
        import shutil
        import tempfile
        
        logger.info("Creating temporary DB copy to avoid file lock contention")
        tmp_dir = tempfile.mkdtemp(prefix="rag_backup_")
        tmp_db = Path(tmp_dir) / "extractions_temp.db"
        
        try:
            shutil.copy2(db_path, tmp_db)
            backup_manager = RAGBackupManager(str(tmp_db))
            logger.info(f"Using temporary DB copy: {tmp_db}")
        except Exception as exc:
            logger.error(f"Failed to create/use temporary DB copy: {exc}")
            print(f"Error: Failed to create temporary DB copy: {exc}")
            return 1

        # Preflight: required tables
        try:
            existing = set(
                r[0]
                for r in backup_manager.conn.execute(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
                ).fetchall()
            )
            required = {"rag_incompatibilities", "rag_hazards", "rag_documents"}
            missing = sorted(list(required - existing))
        except Exception as exc:
            logger.error(f"Failed to check tables: {exc}")
            missing = []
        if missing:
            logger.error("Missing required tables: %s", ", ".join(missing))
            print(
                "Error: Missing required tables: "
                + ", ".join(missing)
                + "\nRun ingestion or database initialization before backup."
            )
            return 1

        results = backup_manager.backup_all(args.output)

        # Print summary
        print("\n" + "=" * 70)
        print("📦 RAG BACKUP COMPLETE")
        print("=" * 70)
        print(f"\n📁 Backup location: {results['backup_path']}")
        print(f"⏰ Timestamp: {results['timestamp']}\n")

        for category, data in results["data"].items():
            print(f"  {category.upper()}:")
            print(f"    Records: {data['count']}")
            print(f"    JSON: {Path(data['json']).name}")
            print(f"    CSV:  {Path(data['csv']).name}\n")

        backup_manager.close()
        return 0

    except Exception as e:
        logger.exception(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
