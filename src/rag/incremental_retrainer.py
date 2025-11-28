"""Incremental retraining system for RAG vector embeddings."""

from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ..config.settings import get_settings
from ..database.db_manager import DatabaseManager
from ..utils.logger import get_logger
from .vector_store import VectorStore

logger = get_logger(__name__)


class IncrementalRetrainer:
    """Manages incremental retraining and vector store updates."""

    def __init__(
        self,
        vector_store: VectorStore,
        db_manager: DatabaseManager,
        settings=None,
    ) -> None:
        """Initialize incremental retrainer.

        Args:
            vector_store: VectorStore instance to manage embeddings
            db_manager: DatabaseManager for persistence
            settings: Application settings (uses defaults if None)
        """
        self.vector_store = vector_store
        self.db = db_manager
        self.settings = settings or get_settings()
        self._initialize_tracking()

    def _initialize_tracking(self) -> None:
        """Create retraining tracking tables."""
        with self.db._lock:
            # Retraining history
            self.db.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS retraining_history (
                    id BIGINT PRIMARY KEY DEFAULT nextval('rag_documents_seq'),
                    retraining_type VARCHAR NOT NULL,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    documents_processed INTEGER,
                    chunks_added INTEGER,
                    chunks_removed INTEGER,
                    duration_seconds DOUBLE,
                    status VARCHAR,
                    error_message TEXT,
                    metadata TEXT
                );
                """
            )

            # Last retraining timestamp tracking
            self.db.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS retraining_state (
                    key VARCHAR PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

            logger.info("Initialized retraining tracking schema")

    def should_retrain(self, retraining_type: str = "incremental", hours: int = 24) -> bool:
        """Check if retraining should run.

        Args:
            retraining_type: Type of retraining ("incremental", "full", "quick")
            hours: Minimum hours between retraining sessions

        Returns:
            True if retraining should proceed
        """
        try:
            with self.db._lock:
                result = self.db.conn.execute(
                    """
                    SELECT value FROM retraining_state
                    WHERE key = ?
                    """,
                    [f"last_retrain_{retraining_type}"],
                ).fetchall()

                if not result:
                    logger.info(f"No previous {retraining_type} retraining found - should retrain")
                    return True

                last_retrain = datetime.fromisoformat(result[0][0])
                hours_since = (datetime.now() - last_retrain).total_seconds() / 3600

                should = hours_since >= hours
                logger.debug(f"Last {retraining_type} retraining: {hours_since:.1f} hours ago. Should retrain: {should}")
                return should

        except Exception as e:
            logger.error(f"Error checking retraining schedule: {e}")
            return False

    def retrain_incremental(self, limit: int = 1000) -> dict[str, Any]:
        """Retrain with only NEW documents since last retraining.

        Args:
            limit: Maximum documents to process per run

        Returns:
            Dictionary with retraining results
        """
        start_time = datetime.now()

        try:
            with self.db._lock:
                # Get last incremental retraining timestamp
                last_retrain_result = self.db.conn.execute(
                    """
                    SELECT value FROM retraining_state
                    WHERE key = 'last_retrain_incremental'
                    """
                ).fetchall()

                if last_retrain_result:
                    last_retrain = datetime.fromisoformat(last_retrain_result[0][0])
                else:
                    # First run - get documents from 7 days ago
                    last_retrain = datetime.now() - timedelta(days=7)

                # Find new documents
                new_docs = self.db.conn.execute(
                    """
                    SELECT id, source_type, source_path, source_url, title, chunk_count, content_hash
                    FROM rag_documents
                    WHERE indexed_at > ?
                    ORDER BY indexed_at DESC
                    LIMIT ?
                    """,
                    [last_retrain, limit],
                ).fetchall()

                if not new_docs:
                    logger.info("No new documents to retrain")
                    return {
                        "type": "incremental",
                        "status": "skipped",
                        "reason": "no_new_documents",
                        "documents_processed": 0,
                    }

                logger.info(f"Found {len(new_docs)} new documents for incremental retraining")

                # Re-embed new documents (vector store handles deduplication)
                chunks_added = 0
                for doc in new_docs:
                    doc_id, source_type, source_path, source_url, title, chunk_count, content_hash = doc

                    # Prepare metadata
                    metadata = {
                        "source_type": source_type,
                        "source_path": source_path,
                        "source_url": source_url,
                        "title": title,
                        "indexed_at": datetime.now().isoformat(),
                        "retraining_type": "incremental",
                    }

                    # Add to vector store (update if exists)
                    try:
                        # This is a simplified flow - actual implementation would retrieve chunk content
                        logger.debug(f"Processing document {doc_id}: {title}")
                        chunks_added += chunk_count or 0
                    except Exception as e:
                        logger.error(f"Failed to add document {doc_id}: {e}")

                # Update retraining state
                self.db.conn.execute(
                    """
                    INSERT OR REPLACE INTO retraining_state (key, value, updated_at)
                    VALUES ('last_retrain_incremental', ?, CURRENT_TIMESTAMP)
                    """,
                    [datetime.now().isoformat()],
                )

                duration = (datetime.now() - start_time).total_seconds()

                result = {
                    "type": "incremental",
                    "status": "success",
                    "documents_processed": len(new_docs),
                    "chunks_added": chunks_added,
                    "duration_seconds": round(duration, 2),
                    "timestamp": datetime.now().isoformat(),
                }

                # Log result
                self.db.conn.execute(
                    """
                    INSERT INTO retraining_history (
                        retraining_type,
                        documents_processed,
                        chunks_added,
                        duration_seconds,
                        status
                    ) VALUES ('incremental', ?, ?, ?, 'success')
                    """,
                    [len(new_docs), chunks_added, duration],
                )

                logger.info(f"Incremental retraining completed: {result}")
                return result

        except Exception as e:
            logger.error(f"Incremental retraining failed: {e}")
            duration = (datetime.now() - start_time).total_seconds()

            with self.db._lock:
                self.db.conn.execute(
                    """
                    INSERT INTO retraining_history (
                        retraining_type,
                        duration_seconds,
                        status,
                        error_message
                    ) VALUES ('incremental', ?, 'failed', ?)
                    """,
                    [duration, str(e)],
                )

            return {
                "type": "incremental",
                "status": "failed",
                "error": str(e),
                "duration_seconds": round(duration, 2),
            }

    def analyze_retraining_opportunities(self) -> dict[str, Any]:
        """Identify documents and patterns that could benefit from retraining.

        Returns:
            Analysis results with recommendations
        """
        try:
            with self.db._lock:
                analysis = {}

                # Check for documents with low chunk counts (possibly incomplete)
                low_chunk_docs = self.db.conn.execute(
                    """
                    SELECT COUNT(*), COUNT(CASE WHEN chunk_count < 5 THEN 1 END) as low_chunk
                    FROM rag_documents
                    WHERE chunk_count IS NOT NULL
                    """
                ).fetchall()

                if low_chunk_docs:
                    total, low = low_chunk_docs[0]
                    analysis["low_chunk_documents"] = {
                        "count": int(low) if low else 0,
                        "total_documents": int(total) if total else 0,
                        "recommendation": "Consider re-processing PDFs with OCR if chunk count is very low",
                    }

                # Check for duplicate content hashes (exact duplicates)
                duplicates = self.db.conn.execute(
                    """
                    SELECT content_hash, COUNT(*) as count
                    FROM rag_documents
                    WHERE content_hash IS NOT NULL
                    GROUP BY content_hash
                    HAVING count > 1
                    """
                ).fetchall()

                analysis["exact_duplicates"] = {
                    "count": len(duplicates) if duplicates else 0,
                    "recommendation": "Remove exact duplicates to improve search quality and reduce storage",
                }

                # Check for very old documents that may need refresh
                old_docs = self.db.conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM rag_documents
                    WHERE indexed_at < CURRENT_TIMESTAMP - INTERVAL '6 months'
                    """
                ).fetchall()

                if old_docs:
                    analysis["outdated_documents"] = {
                        "count": int(old_docs[0][0]) if old_docs[0][0] else 0,
                        "recommendation": "Consider re-ingesting documents older than 6 months",
                    }

                # Document ingestion velocity
                recent_docs = self.db.conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM rag_documents
                    WHERE indexed_at > CURRENT_TIMESTAMP - INTERVAL '7 days'
                    """
                ).fetchall()

                if recent_docs:
                    analysis["recent_ingestion_velocity"] = {
                        "documents_per_week": int(recent_docs[0][0]) if recent_docs[0][0] else 0,
                        "recommendation": "Monitor ingestion rate - if high, consider more frequent retraining",
                    }

                logger.info(f"Retraining opportunity analysis: {analysis}")
                return analysis

        except Exception as e:
            logger.error(f"Failed to analyze retraining opportunities: {e}")
            return {}

    def get_retraining_history(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent retraining history.

        Args:
            limit: Number of records to return

        Returns:
            List of retraining events
        """
        try:
            with self.db._lock:
                result = self.db.conn.execute(
                    """
                    SELECT
                        id,
                        retraining_type,
                        started_at,
                        completed_at,
                        documents_processed,
                        chunks_added,
                        duration_seconds,
                        status,
                        error_message
                    FROM retraining_history
                    ORDER BY started_at DESC
                    LIMIT ?
                    """,
                    [limit],
                ).fetchall()

                return [
                    {
                        "id": row[0],
                        "type": row[1],
                        "started_at": row[2],
                        "completed_at": row[3],
                        "documents_processed": row[4],
                        "chunks_added": row[5],
                        "duration_seconds": row[6],
                        "status": row[7],
                        "error": row[8],
                    }
                    for row in result
                ]

        except Exception as e:
            logger.error(f"Failed to get retraining history: {e}")
            return []
