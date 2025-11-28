#!/usr/bin/env python3
"""
Backup RAG ingested data to external location.

Exports all ingested documents, incompatibilities, hazards, and vector store
to external backup directory for safekeeping and recovery.
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

import duckdb

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.logger import get_logger

logger = get_logger("rag_backup")


class RAGBackupManager:
    """Manage RAG data backups."""

    def __init__(
        self,
        db_path: str = "data/duckdb/extractions.db",
        vector_store_path: str = "data/chroma_db",
    ):
        self.db_path = Path(db_path)
        self.vector_store_path = Path(vector_store_path)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        try:
            self.conn = duckdb.connect(str(self.db_path), read_only=True)
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    def export_documents(self, output_dir: Path) -> int:
        """Export all RAG documents to JSON."""
        try:
            query = """
                SELECT 
                    id,
                    title,
                    source_type,
                    source_url,
                    source_path,
                    chunk_count,
                    indexed_at,
                    metadata
                FROM rag_documents
                ORDER BY id
            """

            results = self.conn.execute(query).fetchall()
            documents = []

            for row in results:
                metadata = {}
                if row[7]:
                    try:
                        metadata = json.loads(row[7])
                    except json.JSONDecodeError:
                        pass

                documents.append(
                    {
                        "id": row[0],
                        "title": row[1],
                        "source_type": row[2],
                        "source_url": row[3],
                        "source_path": row[4],
                        "chunk_count": row[5],
                        "indexed_at": row[6],
                        "metadata": metadata,
                    }
                )

            output_file = output_dir / "rag_documents.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(
                    documents,
                    f,
                    indent=2,
                    ensure_ascii=False,
                    default=str,
                )

            logger.info(f"Exported {len(documents)} documents to {output_file}")
            return len(documents)

        except Exception as e:
            logger.error(f"Error exporting documents: {e}")
            raise

    def export_incompatibilities(self, output_dir: Path) -> int:
        """Export all incompatibilities to JSON."""
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
                ORDER BY cas_a, cas_b
            """

            results = self.conn.execute(query).fetchall()
            incompatibilities = []

            for row in results:
                metadata = {}
                if row[5]:
                    try:
                        metadata = json.loads(row[5])
                    except json.JSONDecodeError:
                        pass

                incompatibilities.append(
                    {
                        "cas_a": row[0],
                        "cas_b": row[1],
                        "rule": row[2],
                        "source": row[3],
                        "justification": row[4],
                        "metadata": metadata,
                    }
                )

            output_file = output_dir / "rag_incompatibilities.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(
                    incompatibilities,
                    f,
                    indent=2,
                    ensure_ascii=False,
                    default=str,
                )

            logger.info(
                f"Exported {len(incompatibilities)} incompatibilities "
                f"to {output_file}"
            )
            return len(incompatibilities)

        except Exception as e:
            logger.error(f"Error exporting incompatibilities: {e}")
            raise

    def export_hazards(self, output_dir: Path) -> int:
        """Export all hazards to JSON."""
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
                ORDER BY cas
            """

            results = self.conn.execute(query).fetchall()
            hazards = []

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

                hazards.append(
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

            output_file = output_dir / "rag_hazards.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(
                    hazards,
                    f,
                    indent=2,
                    ensure_ascii=False,
                    default=str,
                )

            logger.info(f"Exported {len(hazards)} hazards to {output_file}")
            return len(hazards)

        except Exception as e:
            logger.error(f"Error exporting hazards: {e}")
            raise

    def export_snapshots(self, output_dir: Path) -> int:
        """Export MRLP snapshots to JSON."""
        try:
            query = """
                SELECT 
                    id,
                    mrlp_id,
                    snapshot_type,
                    data,
                    created_at
                FROM mrlp_snapshots
                ORDER BY id
            """

            results = self.conn.execute(query).fetchall()
            snapshots = []

            for row in results:
                data = {}
                if row[3]:
                    try:
                        data = json.loads(row[3])
                    except json.JSONDecodeError:
                        pass

                snapshots.append(
                    {
                        "id": row[0],
                        "mrlp_id": row[1],
                        "snapshot_type": row[2],
                        "data": data,
                        "created_at": row[4],
                    }
                )

            if snapshots:
                output_file = output_dir / "mrlp_snapshots.json"
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(
                        snapshots,
                        f,
                        indent=2,
                        ensure_ascii=False,
                        default=str,
                    )

                logger.info(f"Exported {len(snapshots)} snapshots to {output_file}")
            else:
                logger.info("No snapshots to export")

            return len(snapshots)

        except Exception as e:
            logger.error(f"Error exporting snapshots: {e}")
            raise

    def backup_vector_store(self, backup_dir: Path) -> bool:
        """Backup ChromaDB vector store."""
        try:
            if not self.vector_store_path.exists():
                logger.warning(f"Vector store not found at {self.vector_store_path}")
                return False

            dest_path = backup_dir / "chroma_db"
            if dest_path.exists():
                shutil.rmtree(dest_path)

            shutil.copytree(
                self.vector_store_path,
                dest_path,
                ignore=shutil.ignore_patterns("*.pyc", "__pycache__"),
            )

            logger.info(f"Backed up vector store to {dest_path}")
            return True

        except Exception as e:
            logger.error(f"Error backing up vector store: {e}")
            raise

    def backup_database(self, backup_dir: Path) -> bool:
        """Backup DuckDB database file."""
        try:
            if not self.db_path.exists():
                logger.warning(f"Database not found at {self.db_path}")
                return False

            dest_path = backup_dir / self.db_path.name
            shutil.copy2(self.db_path, dest_path)

            logger.info(f"Backed up database to {dest_path}")
            return True

        except Exception as e:
            logger.error(f"Error backing up database: {e}")
            raise

    def create_backup_manifest(self, backup_dir: Path, stats: dict):
        """Create backup manifest with metadata."""
        try:
            manifest = {
                "backup_timestamp": self.timestamp,
                "backup_date": datetime.now().isoformat(),
                "source_db": str(self.db_path.absolute()),
                "source_vector_store": str(self.vector_store_path.absolute()),
                "backup_directory": str(backup_dir.absolute()),
                "statistics": {
                    "documents": stats.get("documents", 0),
                    "incompatibilities": stats.get("incompatibilities", 0),
                    "hazards": stats.get("hazards", 0),
                    "snapshots": stats.get("snapshots", 0),
                },
                "files_included": [
                    "rag_documents.json",
                    "rag_incompatibilities.json",
                    "rag_hazards.json",
                    "mrlp_snapshots.json",
                    "chroma_db/",
                    "extractions.db",
                ],
            }

            manifest_file = backup_dir / "BACKUP_MANIFEST.json"
            with open(manifest_file, "w", encoding="utf-8") as f:
                json.dump(
                    manifest,
                    f,
                    indent=2,
                    ensure_ascii=False,
                    default=str,
                )

            logger.info(f"Created backup manifest at {manifest_file}")

        except Exception as e:
            logger.error(f"Error creating manifest: {e}")
            raise

    def perform_backup(self, external_dir: str) -> bool:
        """Perform complete backup to external directory."""
        try:
            external_path = Path(external_dir).expanduser().absolute()

            # Create timestamped backup directory
            backup_dir = external_path / f"rag_backup_{self.timestamp}"
            backup_dir.mkdir(parents=True, exist_ok=True)

            logger.info(f"Starting backup to {backup_dir}")

            # Export structured data
            stats = {}
            stats["documents"] = self.export_documents(backup_dir)
            stats["incompatibilities"] = self.export_incompatibilities(backup_dir)
            stats["hazards"] = self.export_hazards(backup_dir)
            stats["snapshots"] = self.export_snapshots(backup_dir)

            # Backup binary data
            self.backup_database(backup_dir)
            self.backup_vector_store(backup_dir)

            # Create manifest
            self.create_backup_manifest(backup_dir, stats)

            logger.info(f"✅ Backup completed successfully at {backup_dir}")
            logger.info(f"   Documents: {stats['documents']}")
            logger.info(f"   Incompatibilities: {stats['incompatibilities']}")
            logger.info(f"   Hazards: {stats['hazards']}")
            logger.info(f"   Snapshots: {stats['snapshots']}")

            print("\n" + "=" * 70)
            print("✅ RAG BACKUP COMPLETED")
            print("=" * 70)
            print(f"Location: {backup_dir}")
            print("\nData exported:")
            print(f"  • Documents: {stats['documents']}")
            print(f"  • Incompatibilities: {stats['incompatibilities']}")
            print(f"  • Hazards: {stats['hazards']}")
            print(f"  • MRLP Snapshots: {stats['snapshots']}")
            print("\nFiles backed up:")
            print("  • Vector store (ChromaDB)")
            print("  • Database (DuckDB)")
            print("  • JSON exports")
            print("  • Backup manifest")
            print("=" * 70 + "\n")

            return True

        except Exception as e:
            logger.error(f"Backup failed: {e}")
            print(f"\n❌ Backup failed: {e}\n")
            return False

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Backup RAG ingested data to external location",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Backup to ~/backups
  python backup_rag.py --output ~/backups

  # Backup to external drive
  python backup_rag.py --output /mnt/external/backups

  # Backup with custom database path
  python backup_rag.py --output ~/backups --db data/duckdb/extractions.db

  # Backup only (no vector store)
  python backup_rag.py --output ~/backups --no-vector-store
        """,
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="External directory path for backup",
    )
    parser.add_argument(
        "--db",
        type=str,
        default="data/duckdb/extractions.db",
        help="Path to DuckDB database",
    )
    parser.add_argument(
        "--vector-store",
        type=str,
        default="data/chroma_db",
        help="Path to ChromaDB vector store",
    )

    args = parser.parse_args()

    try:
        backup_manager = RAGBackupManager(
            db_path=args.db,
            vector_store_path=args.vector_store,
        )

        success = backup_manager.perform_backup(args.output)
        backup_manager.close()

        return 0 if success else 1

    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
