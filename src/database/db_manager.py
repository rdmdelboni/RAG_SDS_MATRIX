"""DuckDB database manager for SDS extraction persistence."""

from __future__ import annotations

import hashlib
import os
import json
import threading
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import duckdb

from ..config.settings import get_settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DocumentRecord:
    """Representation of a stored document."""

    id: int
    filename: str
    file_path: str
    file_hash: str
    status: str
    processed_at: datetime | None
    error_message: str | None


@dataclass
class ExtractionRecord:
    """Representation of an extracted field."""

    id: int
    document_id: int
    field_name: str
    value: str
    confidence: float
    context: str
    validation_status: str
    source: str
    created_at: datetime


class DatabaseManager:
    """Thread-safe DuckDB manager for SDS extraction data."""

    def __init__(self, db_path: Path | None = None) -> None:
        """Initialize database connection.

        Args:
            db_path: Path to database file (uses settings default if None)
        """
        self.db_path = db_path or get_settings().paths.duckdb
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Allow forcing in-memory DB via environment variable
        db_mode = os.getenv("RAG_SDS_MATRIX_DB_MODE", "file").lower()

        try:
            if db_mode == "memory":
                self.conn = duckdb.connect(":memory:")
                logger.warning("Using in-memory DuckDB (RAG_SDS_MATRIX_DB_MODE=memory)")
            else:
                self.conn = duckdb.connect(str(self.db_path))
        except duckdb.IOException as e:
            # Fallback to in-memory DB on lock conflicts to keep tests runnable
            if "lock" in str(e).lower():
                logger.warning(
                    "DuckDB lock detected on %s; falling back to in-memory DB for this session",
                    self.db_path,
                )
                self.conn = duckdb.connect(":memory:")
            else:
                raise
        self._lock = threading.Lock()

        logger.info("Connected to DuckDB: %s", self.db_path)
        self._initialize_schema()
        try:
            self._create_indexes()
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.warning("Skipping index creation: %s", exc)

    def _initialize_schema(self) -> None:
        """Create database schema if not exists."""
        logger.debug("Initializing database schema")

        with self._lock:
            # Sequences for auto-increment
            self.conn.execute("CREATE SEQUENCE IF NOT EXISTS documents_seq START 1;")
            self.conn.execute("CREATE SEQUENCE IF NOT EXISTS extractions_seq START 1;")
            self.conn.execute(
                "CREATE SEQUENCE IF NOT EXISTS rag_documents_seq START 1;"
            )

            # Documents table
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id BIGINT PRIMARY KEY DEFAULT nextval('documents_seq'),
                    filename VARCHAR NOT NULL,
                    file_path VARCHAR NOT NULL,
                    file_hash VARCHAR UNIQUE NOT NULL,
                    file_size_bytes BIGINT,
                    file_type VARCHAR,
                    num_pages INTEGER,
                    status VARCHAR DEFAULT 'pending',
                    is_dangerous BOOLEAN DEFAULT FALSE,
                    processed_at TIMESTAMP,
                    processing_time_seconds DOUBLE,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """
            )

            # Extractions table
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS extractions (
                    id BIGINT PRIMARY KEY DEFAULT nextval('extractions_seq'),
                    document_id BIGINT NOT NULL,
                    field_name VARCHAR NOT NULL,
                    value TEXT,
                    confidence DOUBLE,
                    context TEXT,
                    validation_status VARCHAR,
                    validation_message TEXT,
                    source VARCHAR DEFAULT 'heuristic',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(document_id, field_name)
                );
            """
            )

            # RAG documents table (for knowledge base tracking)
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS rag_documents (
                    id BIGINT PRIMARY KEY DEFAULT nextval('rag_documents_seq'),
                    source_type VARCHAR NOT NULL,
                    source_path VARCHAR,
                    source_url VARCHAR,
                    title VARCHAR,
                    chunk_count INTEGER,
                    content_hash VARCHAR,
                    metadata TEXT,
                    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """
            )

            # Ensure new columns exist for older databases
            self.conn.execute(
                """
                ALTER TABLE extractions ADD COLUMN IF NOT EXISTS metadata TEXT;
            """
            )
            self.conn.execute(
                """
                ALTER TABLE rag_documents ADD COLUMN IF NOT EXISTS content_hash VARCHAR;
            """
            )
            self.conn.execute(
                """
                ALTER TABLE rag_documents ADD COLUMN IF NOT EXISTS metadata TEXT;
            """
            )

            # Incompatibility rules table (structured MRLP ingestion)
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS rag_incompatibilities (
                    cas_a VARCHAR NOT NULL,
                    cas_b VARCHAR NOT NULL,
                    rule VARCHAR NOT NULL, -- I/R/C
                    source VARCHAR NOT NULL,
                    justification TEXT,
                    group_a VARCHAR,
                    group_b VARCHAR,
                    metadata TEXT,
                    content_hash VARCHAR,
                    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (cas_a, cas_b)
                );
            """
            )

            # Hazard flags table (tox/ambiental)
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS rag_hazards (
                    cas VARCHAR PRIMARY KEY,
                    hazard_flags TEXT,
                    idlh DOUBLE,
                    pel DOUBLE,
                    rel DOUBLE,
                    env_risk BOOLEAN,
                    source VARCHAR,
                    metadata TEXT,
                    content_hash VARCHAR,
                    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """
            )

            # MRLP snapshots (track files ingested)
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS mrlp_snapshots (
                    id BIGINT PRIMARY KEY DEFAULT nextval('rag_documents_seq'),
                    source_type VARCHAR NOT NULL,
                    file_path VARCHAR,
                    content_hash VARCHAR UNIQUE,
                    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """
            )

            # Matrix decision audit log
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS matrix_decisions (
                    id BIGINT PRIMARY KEY DEFAULT nextval('rag_documents_seq'),
                    product_a VARCHAR,
                    product_b VARCHAR,
                    cas_a VARCHAR,
                    cas_b VARCHAR,
                    decision VARCHAR,
                    source_layer VARCHAR,
                    rule_source VARCHAR,
                    justification TEXT,
                    decision_hash VARCHAR,
                    decided_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """
            )

    def _create_indexes(self) -> None:
        """Create database indexes for frequently queried fields."""
        logger.debug("Creating database indexes")
        
        with self._lock:
            # Documents table indexes
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);"
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_documents_filename ON documents(filename);"
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_documents_processed_at ON documents(processed_at);"
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_documents_is_dangerous ON documents(is_dangerous);"
            )
            
            # Extractions table indexes
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_extractions_document_id ON extractions(document_id);"
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_extractions_field_name ON extractions(field_name);"
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_extractions_validation_status ON extractions(validation_status);"
            )
            
            # Composite index for common query pattern (document + field lookup)
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_extractions_doc_field ON extractions(document_id, field_name);"
            )
            
            # Index on JSON-extracted fields for quality queries
            # Note: DuckDB supports function-based indexes
            self.conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_extractions_quality_tier
                ON extractions(
                    CAST(json_extract(metadata, '$.quality_tier') AS VARCHAR)
                ) WHERE metadata IS NOT NULL;
                """
            )
            
            # RAG incompatibilities indexes
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_rag_incomp_cas_a ON rag_incompatibilities(cas_a);"
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_rag_incomp_cas_b ON rag_incompatibilities(cas_b);"
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_rag_incomp_rule ON rag_incompatibilities(rule);"
            )
            
            # RAG hazards indexes
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_rag_hazards_cas ON rag_hazards(cas);"
            )
            
            # Matrix decisions indexes
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_matrix_cas_a ON matrix_decisions(cas_a);"
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_matrix_cas_b ON matrix_decisions(cas_b);"
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_matrix_decision ON matrix_decisions(decision);"
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_matrix_decided_at ON matrix_decisions(decided_at);"
            )
            
            logger.info("Database indexes created successfully")

    # === Hash Utilities ===

    @staticmethod
    def calculate_hash(file_path: Path) -> str:
        """Calculate SHA256 hash for file deduplication."""
        digest = hashlib.sha256()
        with file_path.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                digest.update(chunk)
        return digest.hexdigest()

    # === Document Operations ===

    def register_document(
        self,
        filename: str,
        file_path: Path,
        file_size: int,
        file_type: str,
        num_pages: int | None = None,
    ) -> int:
        """Register a document, returning existing ID if duplicate."""
        file_hash = self.calculate_hash(file_path)

        with self._lock:
            # Check for existing document
            existing = self.conn.execute(
                "SELECT id FROM documents WHERE file_hash = ?",
                [file_hash],
            ).fetchone()

            if existing:
                logger.info(
                    "Document already exists: %s (id=%d)", filename, existing[0]
                )
                return existing[0]

            # Insert new document
            result = self.conn.execute(
                """
                INSERT INTO documents (filename, file_path, file_hash, file_size_bytes, file_type, num_pages, status)
                VALUES (?, ?, ?, ?, ?, ?, 'pending')
                RETURNING id;
                """,
                [filename, str(file_path), file_hash, file_size, file_type, num_pages],
            ).fetchone()

            if not result:
                raise RuntimeError("Failed to register document")

            logger.info("Registered document: %s (id=%d)", filename, result[0])
            return result[0]

    def update_document_status(
        self,
        document_id: int,
        status: str,
        processing_time: float | None = None,
        error_message: str | None = None,
        is_dangerous: bool | None = None,
    ) -> None:
        """Update document processing status."""
        with self._lock:
            self.conn.execute(
                """
                UPDATE documents
                SET status = ?,
                    processed_at = CURRENT_TIMESTAMP,
                    processing_time_seconds = COALESCE(?, processing_time_seconds),
                    error_message = ?,
                    is_dangerous = COALESCE(?, is_dangerous)
                WHERE id = ?;
                """,
                [status, processing_time, error_message, is_dangerous, document_id],
            )

    def get_document(self, document_id: int) -> DocumentRecord | None:
        """Get document by ID."""
        with self._lock:
            row = self.conn.execute(
                """SELECT id, filename, file_path, file_hash, status, processed_at, error_message
                   FROM documents WHERE id = ?""",
                [document_id],
            ).fetchone()

            if row:
                return DocumentRecord(*row)
            return None

    def get_document_by_path(self, file_path: Path) -> DocumentRecord | None:
        """Get document by file path."""
        with self._lock:
            row = self.conn.execute(
                """SELECT id, filename, file_path, file_hash, status, processed_at, error_message
                   FROM documents WHERE file_path = ?""",
                [str(file_path)],
            ).fetchone()

            if row:
                return DocumentRecord(*row)
            return None

    # === Extraction Operations ===

    def store_extraction(
        self,
        document_id: int,
        field_name: str,
        value: str,
        confidence: float,
        context: str = "",
        validation_status: str = "pending",
        validation_message: str | None = None,
        source: str = "heuristic",
    ) -> None:
        """Store or update a field extraction result."""
        with self._lock:
            # Upsert extraction
            self.conn.execute(
                """
                INSERT INTO extractions (document_id, field_name, value, confidence, context,
                                         validation_status, validation_message, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, now())
                ON CONFLICT (document_id, field_name)
                DO UPDATE SET value = EXCLUDED.value,
                              confidence = EXCLUDED.confidence,
                              context = EXCLUDED.context,
                              validation_status = EXCLUDED.validation_status,
                              validation_message = EXCLUDED.validation_message,
                              source = EXCLUDED.source,
                              created_at = now();
                """,
                [
                    document_id,
                    field_name,
                    value,
                    confidence,
                    context,
                    validation_status,
                    validation_message,
                    source,
                ],
            )

    def get_extractions(self, document_id: int) -> dict[str, dict[str, Any]]:
        """Get all extractions for a document."""
        with self._lock:
            rows = self.conn.execute(
                """SELECT field_name, value, confidence, context, validation_status,
                          validation_message, source
                   FROM extractions WHERE document_id = ?""",
                [document_id],
            ).fetchall()

            return {
                row[0]: {
                    "value": row[1],
                    "confidence": row[2],
                    "context": row[3],
                    "validation_status": row[4],
                    "validation_message": row[5],
                    "source": row[6],
                }
                for row in rows
            }

    # === Results / Matrix Queries ===

    def fetch_results(self, limit: int = 500) -> list[dict[str, Any]]:
        """Fetch processed documents with their extractions for matrix display."""
        query = """
            WITH latest_extractions AS (
                SELECT document_id, field_name, value, confidence, validation_status, source, metadata
                FROM extractions
            )
            SELECT
                d.id,
                d.filename,
                d.status,
                d.is_dangerous,
                d.processed_at,
                d.processing_time_seconds,
                MAX(CASE WHEN e.field_name = 'product_name' THEN e.value END) AS product_name,
                MAX(CASE WHEN e.field_name = 'manufacturer' THEN e.value END) AS manufacturer,
                MAX(CASE WHEN e.field_name = 'cas_number' THEN e.value END) AS cas_number,
                MAX(CASE WHEN e.field_name = 'un_number' THEN e.value END) AS un_number,
                MAX(CASE WHEN e.field_name = 'hazard_class' THEN e.value END) AS hazard_class,
                MAX(CASE WHEN e.field_name = 'packing_group' THEN e.value END) AS packing_group,
                MAX(CASE WHEN e.field_name = 'h_statements' THEN e.value END) AS h_statements,
                MAX(CASE WHEN e.field_name = 'p_statements' THEN e.value END) AS p_statements,
                MAX(CASE WHEN e.field_name = 'incompatibilities' THEN e.value END) AS incompatibilities,
                AVG(e.confidence) AS avg_confidence,
                COALESCE(MAX(CASE WHEN e.field_name = 'product_name' THEN TRY_CAST(json_extract(e.metadata, '$.quality_tier') AS VARCHAR) END), 'unknown') AS quality_tier,
                COALESCE(MAX(CASE WHEN e.field_name = 'product_name' THEN json_extract(e.metadata, '$.external_validation.is_valid') END), FALSE) AS validated
            FROM documents d
            LEFT JOIN latest_extractions e ON e.document_id = d.id
            WHERE d.status IN ('success', 'failed', 'partial')
            GROUP BY d.id, d.filename, d.status, d.is_dangerous, d.processed_at, d.processing_time_seconds
            ORDER BY d.processed_at DESC NULLS LAST
            LIMIT ?;
        """

        with self._lock:
            rows = self.conn.execute(query, [limit]).fetchall()
            columns = [
                "id",
                "filename",
                "status",
                "is_dangerous",
                "processed_at",
                "processing_time",
                "product_name",
                "manufacturer",
                "cas_number",
                "un_number",
                "hazard_class",
                "packing_group",
                "h_statements",
                "p_statements",
                "incompatibilities",
                "avg_confidence",
                "quality_tier",
                "validated",
            ]
            return [dict(zip(columns, row)) for row in rows]

    def get_dangerous_chemicals(self) -> list[dict[str, Any]]:
        """Get all documents marked as dangerous for RAG enrichment."""
        with self._lock:
            rows = self.conn.execute(
                """SELECT id, filename FROM documents WHERE is_dangerous = TRUE"""
            ).fetchall()
            return [{"id": row[0], "filename": row[1]} for row in rows]

    # === RAG Document Tracking ===

    def register_rag_document(
        self,
        source_type: str,
        chunk_count: int,
        source_path: str | None = None,
        source_url: str | None = None,
        title: str | None = None,
        content_hash: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """Register a document added to the RAG knowledge base."""
        with self._lock:
            if content_hash:
                existing = self.conn.execute(
                    "SELECT id FROM rag_documents WHERE content_hash = ?",
                    [content_hash],
                ).fetchone()
                if existing:
                    return existing[0]

            metadata_str = None
            if metadata:
                metadata_str = json.dumps(metadata)

            result = self.conn.execute(
                """
                INSERT INTO rag_documents (
                    source_type, source_path, source_url, title, chunk_count, content_hash, metadata
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                RETURNING id;
                """,
                [
                    source_type,
                    source_path,
                    source_url,
                    title,
                    chunk_count,
                    content_hash,
                    metadata_str,
                ],
            ).fetchone()

            return result[0] if result else 0

    def get_rag_documents(self) -> list[dict[str, Any]]:
        """Get all RAG indexed documents."""
        with self._lock:
            rows = self.conn.execute(
                """SELECT id, source_type, source_path, source_url, title, chunk_count, content_hash, metadata, indexed_at
                   FROM rag_documents ORDER BY indexed_at DESC"""
            ).fetchall()

            return [
                {
                    "id": row[0],
                    "source_type": row[1],
                    "source_path": row[2],
                    "source_url": row[3],
                    "title": row[4],
                    "chunk_count": row[5],
                    "content_hash": row[6],
                    "metadata": row[7],
                    "indexed_at": row[8],
                }
                for row in rows
            ]

    def rag_document_exists(self, content_hash: str) -> bool:
        """Check if a RAG document with the given hash already exists."""
        if not content_hash:
            return False

        with self._lock:
            row = self.conn.execute(
                "SELECT 1 FROM rag_documents WHERE content_hash = ?",
                [content_hash],
            ).fetchone()
            return bool(row)

    # === Incompatibility Rules (Structured MRLP) ===

    def register_incompatibility_rule(
        self,
        cas_a: str,
        cas_b: str,
        rule: str,
        source: str,
        justification: str | None = None,
        group_a: str | None = None,
        group_b: str | None = None,
        metadata: dict[str, Any] | None = None,
        content_hash: str | None = None,
    ) -> None:
        """Upsert a binary incompatibility rule."""
        cas_a, cas_b = sorted([cas_a.strip(), cas_b.strip()])
        rule = rule.upper().strip()
        metadata_str = json.dumps(metadata) if metadata else None

        with self._lock:
            self.conn.execute(
                """
                INSERT INTO rag_incompatibilities (cas_a, cas_b, rule, source, justification,
                                                    group_a, group_b, metadata, content_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (cas_a, cas_b)
                DO UPDATE SET rule = EXCLUDED.rule,
                              source = EXCLUDED.source,
                              justification = EXCLUDED.justification,
                              group_a = EXCLUDED.group_a,
                              group_b = EXCLUDED.group_b,
                              metadata = EXCLUDED.metadata,
                              content_hash = EXCLUDED.content_hash;
                """,
                [
                    cas_a,
                    cas_b,
                    rule,
                    source,
                    justification,
                    group_a,
                    group_b,
                    metadata_str,
                    content_hash,
                ],
            )

    def get_incompatibility_rule(
        self, cas_a: str | None, cas_b: str | None
    ) -> dict[str, Any] | None:
        """Return a stored incompatibility rule for a CAS pair, if any."""
        if not cas_a or not cas_b:
            return None

        cas_a, cas_b = sorted([cas_a.strip(), cas_b.strip()])

        with self._lock:
            row = self.conn.execute(
                """
                SELECT cas_a, cas_b, rule, source, justification, group_a, group_b, metadata
                FROM rag_incompatibilities
                WHERE cas_a = ? AND cas_b = ?;
                """,
                [cas_a, cas_b],
            ).fetchone()

            if not row:
                return None

            return {
                "cas_a": row[0],
                "cas_b": row[1],
                "rule": row[2],
                "source": row[3],
                "justification": row[4],
                "group_a": row[5],
                "group_b": row[6],
                "metadata": json.loads(row[7]) if row[7] else None,
            }

    # === Hazard Flags (Structured MRLP) ===

    def register_hazard_record(
        self,
        cas: str,
        hazard_flags: dict[str, Any] | None = None,
        idlh: float | None = None,
        pel: float | None = None,
        rel: float | None = None,
        env_risk: bool | None = None,
        source: str | None = None,
        metadata: dict[str, Any] | None = None,
        content_hash: str | None = None,
    ) -> None:
        """Upsert hazard flags for a CAS."""
        hazard_json = json.dumps(hazard_flags) if hazard_flags else None
        metadata_str = json.dumps(metadata) if metadata else None

        with self._lock:
            self.conn.execute(
                """
                INSERT INTO rag_hazards (cas, hazard_flags, idlh, pel, rel, env_risk, source, metadata, content_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (cas)
                DO UPDATE SET hazard_flags = EXCLUDED.hazard_flags,
                              idlh = EXCLUDED.idlh,
                              pel = EXCLUDED.pel,
                              rel = EXCLUDED.rel,
                              env_risk = EXCLUDED.env_risk,
                              source = EXCLUDED.source,
                              metadata = EXCLUDED.metadata,
                              content_hash = EXCLUDED.content_hash;
                """,
                [
                    cas.strip(),
                    hazard_json,
                    idlh,
                    pel,
                    rel,
                    env_risk,
                    source,
                    metadata_str,
                    content_hash,
                ],
            )

    def get_hazard_record(self, cas: str | None) -> dict[str, Any] | None:
        """Return hazard flags for a CAS."""
        if not cas:
            return None

        with self._lock:
            row = self.conn.execute(
                """
                SELECT cas, hazard_flags, idlh, pel, rel, env_risk, source, metadata
                FROM rag_hazards WHERE cas = ?;
                """,
                [cas.strip()],
            ).fetchone()

            if not row:
                return None

            return {
                "cas": row[0],
                "hazard_flags": json.loads(row[1]) if row[1] else None,
                "idlh": row[2],
                "pel": row[3],
                "rel": row[4],
                "env_risk": row[5],
                "source": row[6],
                "metadata": json.loads(row[7]) if row[7] else None,
            }

    # === MRLP Snapshots ===

    def register_snapshot(
        self,
        source_type: str,
        file_path: Path | str,
        content_hash: str,
    ) -> None:
        """Register a snapshot ingestion (dedupe by hash)."""
        with self._lock:
            self.conn.execute(
                """
                INSERT INTO mrlp_snapshots (source_type, file_path, content_hash)
                VALUES (?, ?, ?)
                ON CONFLICT (content_hash) DO NOTHING;
                """,
                [source_type, str(file_path), content_hash],
            )

    def snapshot_exists(self, content_hash: str) -> bool:
        with self._lock:
            row = self.conn.execute(
                "SELECT 1 FROM mrlp_snapshots WHERE content_hash = ?",
                [content_hash],
            ).fetchone()
        return bool(row)

    # === Matrix Decisions Audit ===

    def store_matrix_decision(
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
        """Audit log for matrix decisions."""
        payload = f"{product_a}|{product_b}|{cas_a}|{cas_b}|{decision}|{source_layer}|{rule_source or ''}"
        decision_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

        with self._lock:
            self.conn.execute(
                """
                INSERT INTO matrix_decisions (product_a, product_b, cas_a, cas_b, decision,
                                              source_layer, rule_source, justification, decision_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                [
                    product_a,
                    product_b,
                    cas_a,
                    cas_b,
                    decision,
                    source_layer,
                    rule_source,
                    justification,
                    decision_hash,
                ],
            )

    # === Statistics ===

    def get_statistics(self) -> dict[str, Any]:
        """Get database statistics."""
        with self._lock:
            doc_count = self.conn.execute("SELECT COUNT(*) FROM documents").fetchone()[
                0
            ]
            processed = self.conn.execute(
                "SELECT COUNT(*) FROM documents WHERE status = 'success'"
            ).fetchone()[0]
            failed = self.conn.execute(
                "SELECT COUNT(*) FROM documents WHERE status = 'failed'"
            ).fetchone()[0]
            dangerous = self.conn.execute(
                "SELECT COUNT(*) FROM documents WHERE is_dangerous = TRUE"
            ).fetchone()[0]
            rag_docs = self.conn.execute(
                "SELECT COUNT(*) FROM rag_documents"
            ).fetchone()[0]
            rag_chunks = self.conn.execute(
                "SELECT COALESCE(SUM(chunk_count), 0) FROM rag_documents"
            ).fetchone()[0]
            rag_last_updated = self.conn.execute(
                "SELECT MAX(indexed_at) FROM rag_documents"
            ).fetchone()[0]

            return {
                "total_documents": doc_count,
                "processed": processed,
                "successful_documents": processed,
                "failed": failed,
                "failed_documents": failed,
                "dangerous_chemicals": dangerous,
                "dangerous_count": dangerous,
                "rag_documents": rag_docs,
                "rag_chunks": rag_chunks,
                "rag_last_updated": (
                    rag_last_updated.isoformat() if rag_last_updated else None
                ),
            }


@lru_cache(maxsize=1)
def get_db_manager() -> DatabaseManager:
    """Get cached database manager instance."""
    return DatabaseManager()
