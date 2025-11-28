"""Query performance and feedback tracking for RAG system optimization."""

from __future__ import annotations

import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from ..database.db_manager import DatabaseManager
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class QueryRecord:
    """Represents a single RAG query and its results."""

    query_text: str
    query_embedding_time: float  # Time to embed the query
    search_time: float  # Time to search vector store
    result_count: int  # Number of results returned
    top_result_relevance: float | None  # Relevance score of top result
    answer_generation_time: float | None  # Time to generate LLM answer
    total_time: float  # Total end-to-end time
    returned_document_ids: list[int]  # Which documents were retrieved
    returned_chunks: list[int]  # Which chunks from those documents
    query_timestamp: datetime = None
    feedback_rating: str | None = None  # "relevant" | "partially_relevant" | "irrelevant"
    feedback_notes: str | None = None
    user_id: str | None = None

    def __post_init__(self):
        if self.query_timestamp is None:
            self.query_timestamp = datetime.now()


class QueryTracker:
    """Track RAG queries, performance metrics, and user feedback."""

    def __init__(self, db_manager: DatabaseManager) -> None:
        """Initialize query tracker with database backend.

        Args:
            db_manager: DatabaseManager instance for persistence
        """
        self.db = db_manager
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        """Create query tracking tables if they don't exist."""
        with self.db._lock:
            # Query performance log
            self.db.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS query_logs (
                    id BIGINT PRIMARY KEY DEFAULT nextval('rag_documents_seq'),
                    query_text TEXT NOT NULL,
                    query_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    query_embedding_time DOUBLE,
                    search_time DOUBLE,
                    result_count INTEGER,
                    top_result_relevance DOUBLE,
                    answer_generation_time DOUBLE,
                    total_time DOUBLE,
                    user_id VARCHAR,
                    metadata TEXT
                );
                """
            )

            # Query results mapping (which documents/chunks were returned)
            self.db.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS query_results (
                    id BIGINT PRIMARY KEY DEFAULT nextval('rag_documents_seq'),
                    query_id BIGINT NOT NULL,
                    document_id BIGINT NOT NULL,
                    chunk_index INTEGER,
                    relevance_score DOUBLE,
                    rank INTEGER,
                    FOREIGN KEY (query_id) REFERENCES query_logs(id)
                );
                """
            )

            # User feedback on query results
            self.db.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS query_feedback (
                    id BIGINT PRIMARY KEY DEFAULT nextval('rag_documents_seq'),
                    query_id BIGINT NOT NULL,
                    feedback_rating VARCHAR NOT NULL,
                    feedback_notes TEXT,
                    document_rating STRUCT(document_id BIGINT, rating VARCHAR)[] DEFAULT [],
                    feedback_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    user_id VARCHAR,
                    FOREIGN KEY (query_id) REFERENCES query_logs(id)
                );
                """
            )

            # Query performance trends (for analysis)
            self.db.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS query_metrics (
                    metric_date DATE,
                    metric_hour INTEGER,
                    avg_query_time DOUBLE,
                    avg_embedding_time DOUBLE,
                    avg_search_time DOUBLE,
                    avg_generation_time DOUBLE,
                    total_queries INTEGER,
                    relevant_queries INTEGER,
                    partially_relevant_queries INTEGER,
                    irrelevant_queries INTEGER,
                    PRIMARY KEY (metric_date, metric_hour)
                );
                """
            )

            logger.info("Initialized query tracking schema")

    def log_query(self, record: QueryRecord) -> int:
        """Log a query and its performance metrics.

        Args:
            record: QueryRecord containing query details

        Returns:
            Query ID for reference in feedback
        """
        try:
            with self.db._lock:
                result = self.db.conn.execute(
                    """
                    INSERT INTO query_logs (
                        query_text,
                        query_timestamp,
                        query_embedding_time,
                        search_time,
                        result_count,
                        top_result_relevance,
                        answer_generation_time,
                        total_time,
                        user_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    RETURNING id
                    """,
                    [
                        record.query_text,
                        record.query_timestamp,
                        record.query_embedding_time,
                        record.search_time,
                        record.result_count,
                        record.top_result_relevance,
                        record.answer_generation_time,
                        record.total_time,
                        record.user_id,
                    ],
                )
                query_id = result.fetchall()[0][0]

                # Log individual results
                for rank, (doc_id, chunk_idx, score) in enumerate(
                    zip(
                        record.returned_document_ids,
                        record.returned_chunks,
                        [record.top_result_relevance] + [None] * (len(record.returned_document_ids) - 1),
                    ),
                    1,
                ):
                    self.db.conn.execute(
                        """
                        INSERT INTO query_results (
                            query_id,
                            document_id,
                            chunk_index,
                            relevance_score,
                            rank
                        ) VALUES (?, ?, ?, ?, ?)
                        """,
                        [query_id, doc_id, chunk_idx, score, rank],
                    )

                logger.debug(f"Logged query {query_id}: {record.query_text[:50]}...")
                return query_id

        except Exception as e:
            logger.error(f"Failed to log query: {e}")
            return -1

    def submit_feedback(self, query_id: int, rating: str, notes: str | None = None, user_id: str | None = None) -> bool:
        """Submit feedback on a query's results.

        Args:
            query_id: ID of the query to rate
            rating: "relevant" | "partially_relevant" | "irrelevant"
            notes: Optional user notes
            user_id: Optional user identifier

        Returns:
            True if feedback was recorded successfully
        """
        if rating not in ("relevant", "partially_relevant", "irrelevant"):
            logger.warning(f"Invalid feedback rating: {rating}")
            return False

        try:
            with self.db._lock:
                self.db.conn.execute(
                    """
                    INSERT INTO query_feedback (
                        query_id,
                        feedback_rating,
                        feedback_notes,
                        user_id,
                        feedback_timestamp
                    ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    [query_id, rating, notes, user_id],
                )

                logger.info(f"Recorded feedback for query {query_id}: {rating}")
                return True

        except Exception as e:
            logger.error(f"Failed to record feedback: {e}")
            return False

    def get_performance_summary(self, days: int = 7) -> dict[str, Any]:
        """Get performance summary for the last N days.

        Args:
            days: Number of days to analyze

        Returns:
            Dictionary with performance metrics
        """
        try:
            with self.db._lock:
                result = self.db.conn.execute(
                    f"""
                    SELECT
                        COUNT(*) as total_queries,
                        AVG(total_time) as avg_query_time,
                        MIN(total_time) as min_query_time,
                        MAX(total_time) as max_query_time,
                        AVG(query_embedding_time) as avg_embedding_time,
                        AVG(search_time) as avg_search_time,
                        AVG(result_count) as avg_result_count,
                        COUNT(CASE WHEN result_count > 0 THEN 1 END) as queries_with_results
                    FROM query_logs
                    WHERE query_timestamp > CURRENT_TIMESTAMP - INTERVAL '{days} days'
                    """
                ).fetchall()

                if result:
                    row = result[0]
                    return {
                        "total_queries": int(row[0]) if row[0] else 0,
                        "avg_query_time_ms": round(row[1] * 1000, 2) if row[1] else 0,
                        "min_query_time_ms": round(row[2] * 1000, 2) if row[2] else 0,
                        "max_query_time_ms": round(row[3] * 1000, 2) if row[3] else 0,
                        "avg_embedding_time_ms": round(row[4] * 1000, 2) if row[4] else 0,
                        "avg_search_time_ms": round(row[5] * 1000, 2) if row[5] else 0,
                        "avg_result_count": round(row[6], 2) if row[6] else 0,
                        "queries_with_results": int(row[7]) if row[7] else 0,
                        "period_days": days,
                    }
                return {}

        except Exception as e:
            logger.error(f"Failed to get performance summary: {e}")
            return {}

    def get_feedback_summary(self, days: int = 7) -> dict[str, Any]:
        """Get feedback summary for the last N days.

        Args:
            days: Number of days to analyze

        Returns:
            Dictionary with feedback statistics
        """
        try:
            with self.db._lock:
                result = self.db.conn.execute(
                    f"""
                    SELECT
                        COUNT(*) as total_feedback,
                        COUNT(CASE WHEN feedback_rating = 'relevant' THEN 1 END) as relevant,
                        COUNT(CASE WHEN feedback_rating = 'partially_relevant' THEN 1 END) as partially_relevant,
                        COUNT(CASE WHEN feedback_rating = 'irrelevant' THEN 1 END) as irrelevant
                    FROM query_feedback
                    WHERE feedback_timestamp > CURRENT_TIMESTAMP - INTERVAL '{days} days'
                    """
                ).fetchall()

                if result:
                    row = result[0]
                    total = int(row[0]) if row[0] else 1
                    return {
                        "total_feedback": total,
                        "relevant": int(row[1]) if row[1] else 0,
                        "partially_relevant": int(row[2]) if row[2] else 0,
                        "irrelevant": int(row[3]) if row[3] else 0,
                        "relevant_percentage": round((int(row[1]) / total * 100) if total > 0 else 0, 2),
                        "period_days": days,
                    }
                return {}

        except Exception as e:
            logger.error(f"Failed to get feedback summary: {e}")
            return {}

    def identify_low_performing_queries(self, threshold_percentile: int = 90) -> list[dict[str, Any]]:
        """Identify queries that are slow or have no results.

        Args:
            threshold_percentile: Queries slower than this percentile are flagged

        Returns:
            List of problematic queries
        """
        try:
            with self.db._lock:
                # Get percentile threshold
                threshold_result = self.db.conn.execute(
                    f"""
                    SELECT percentile_cont({threshold_percentile / 100.0})
                    WITHIN GROUP (ORDER BY total_time)
                    FROM query_logs
                    """
                ).fetchall()

                threshold = threshold_result[0][0] if threshold_result else None

                if threshold is None:
                    return []

                # Get slow queries
                result = self.db.conn.execute(
                    f"""
                    SELECT
                        id,
                        query_text,
                        total_time,
                        result_count,
                        query_timestamp
                    FROM query_logs
                    WHERE total_time > ? OR result_count = 0
                    ORDER BY total_time DESC
                    LIMIT 20
                    """,
                    [threshold],
                ).fetchall()

                return [
                    {
                        "query_id": row[0],
                        "query_text": row[1],
                        "total_time_ms": round(row[2] * 1000, 2),
                        "result_count": row[3],
                        "query_timestamp": row[4],
                    }
                    for row in result
                ]

        except Exception as e:
            logger.error(f"Failed to identify low-performing queries: {e}")
            return []
