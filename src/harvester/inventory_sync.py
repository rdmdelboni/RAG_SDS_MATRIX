"""Inventory sync hooks (copy or MySQL update for Open Enventory-style DB)."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Optional

from ..database import get_db_manager
from ..utils.logger import get_logger

logger = get_logger(__name__)


class InventorySync:
    """
    Sync downloaded SDS files to:
      - A staging directory (copy mode)
      - An Open Enventory-like MySQL DB (mysql mode)

    Controlled via env vars:
      OE_SYNC_ENABLED=true|false
      OE_SYNC_MODE=copy|mysql (default: copy)
      OE_SYNC_EXPORT_DIR=/path/to/stage   (for copy mode)
      OE_SYNC_DB_HOST, OE_SYNC_DB_PORT, OE_SYNC_DB_USER,
      OE_SYNC_DB_PASSWORD, OE_SYNC_DB_NAME (for mysql mode)
    """

    def __init__(self) -> None:
        self.enabled = os.getenv("OE_SYNC_ENABLED", "false").lower() in ("true", "1", "yes")
        self.mode = os.getenv("OE_SYNC_MODE", "copy").lower()
        
        # Use existing database pipeline
        self.db_manager = get_db_manager()

        # Copy mode
        raw_dir = os.getenv("OE_SYNC_EXPORT_DIR")
        self.export_dir: Optional[Path] = Path(raw_dir) if raw_dir else None

        # MySQL mode
        self.db_host = os.getenv("OE_SYNC_DB_HOST")
        self.db_port = int(os.getenv("OE_SYNC_DB_PORT", "3306"))
        self.db_user = os.getenv("OE_SYNC_DB_USER")
        self.db_password = os.getenv("OE_SYNC_DB_PASSWORD")
        self.db_name = os.getenv("OE_SYNC_DB_NAME")
        self.db_table = os.getenv("OE_SYNC_DB_TABLE", "molecule")
        self.db_cas_field = os.getenv("OE_SYNC_DB_CAS_FIELD", "cas_nr")
        self.db_blob_field = os.getenv(
            "OE_SYNC_DB_BLOB_FIELD", "default_safety_sheet_blob"
        )
        self.db_source_field = os.getenv(
            "OE_SYNC_DB_SOURCE_FIELD", "default_safety_sheet_by"
        )
        self.db_url_field = os.getenv("OE_SYNC_DB_URL_FIELD", "default_safety_sheet_url")
        self.db_mime_field = os.getenv(
            "OE_SYNC_DB_MIME_FIELD", "default_safety_sheet_mime"
        )
        self.db_source_label = os.getenv("OE_SYNC_SOURCE_LABEL", "harvester")
        self.db_missing_table = os.getenv("OE_SYNC_MISSING_TABLE")
        self.db_missing_cas_field = os.getenv("OE_SYNC_MISSING_CAS_FIELD", "cas_nr")

        if not self.enabled:
            return

        if self.mode == "copy":
            if not self.export_dir:
                logger.warning(
                    "OE_SYNC_ENABLED is true but OE_SYNC_EXPORT_DIR is not set; sync disabled."
                )
                self.enabled = False
                return
            self.export_dir.mkdir(parents=True, exist_ok=True)
            logger.info("Inventory sync (copy mode) staging to %s", self.export_dir)

        elif self.mode == "mysql":
            self._init_mysql()
        else:
            logger.warning("Unknown OE_SYNC_MODE=%s; sync disabled.", self.mode)
            self.enabled = False

    # === Public API ===

    def sync_download(self, cas_number: str, file_path: Path, source: str = "harvester", url: str = "") -> None:
        """Sync a downloaded SDS according to configured mode.
        
        Also records the download in the existing database pipeline.
        """
        # Always record in existing database pipeline
        try:
            self.db_manager.record_harvest_download(
                cas_number=cas_number,
                source=source,
                url=url,
                saved_path=file_path,
                status="downloaded"
            )
        except Exception as exc:
            logger.warning("Failed to record download in database: %s", exc)
        
        # Then sync to external systems if enabled
        if not self.enabled:
            return
        if self.mode == "copy":
            self._copy_file(file_path)
        elif self.mode == "mysql":
            self._push_mysql(cas_number, file_path)

    def mark_missing(self, cas_number: str, source: str = "harvester", url: str = "", error_message: str = "Not found") -> None:
        """Mark a CAS as missing in configured sinks.
        
        Also records the failure in the existing database pipeline.
        """
        # Always record in existing database pipeline
        try:
            self.db_manager.record_harvest_download(
                cas_number=cas_number,
                source=source,
                url=url,
                saved_path=None,
                status="failed",
                error_message=error_message
            )
        except Exception as exc:
            logger.warning("Failed to record missing CAS in database: %s", exc)
        
        # Then mark in external systems if enabled
        if not self.enabled:
            return
        if self.mode == "copy" and self.export_dir:
            try:
                missing_file = self.export_dir / "missing_sds.txt"
                with missing_file.open("a", encoding="utf-8") as f:
                    f.write(f"{cas_number}\n")
            except Exception as exc:  # pragma: no cover - best effort
                logger.debug("Failed to append missing CAS to file: %s", exc)
        elif self.mode == "mysql":
            self._push_missing_mysql(cas_number)

    # === Copy mode ===

    def _copy_file(self, file_path: Path) -> None:
        try:
            dest = self.export_dir / file_path.name  # type: ignore[arg-type]
            shutil.copy2(file_path, dest)
            logger.info("Staged SDS to %s", dest)
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("Inventory sync copy failed for %s: %s", file_path, exc)

    # === MySQL mode ===

    def _init_mysql(self) -> None:
        try:
            import mysql.connector  # type: ignore
        except Exception:
            logger.warning(
                "OE_SYNC_MODE=mysql but mysql-connector-python is not installed; sync disabled."
            )
            self.enabled = False
            return

        required = [
            self.db_host,
            self.db_user,
            self.db_password,
            self.db_name,
        ]
        if not all(required):
            logger.warning(
                "OE_SYNC_MODE=mysql but DB credentials are missing; sync disabled."
            )
            self.enabled = False
            return

        self._mysql_connector = mysql.connector  # type: ignore[attr-defined]
        logger.info("Inventory sync (mysql mode) targeting %s/%s", self.db_host, self.db_name)

    def _get_mysql_conn(self):
        mysql = getattr(self, "_mysql_connector", None)
        if not mysql:
            return None
        try:
            return mysql.connect(
                host=self.db_host,
                port=self.db_port,
                user=self.db_user,
                password=self.db_password,
                database=self.db_name,
            )
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("Failed to connect to MySQL for inventory sync: %s", exc)
            return None

    def _push_mysql(self, cas_number: str, file_path: Path) -> None:
        conn = self._get_mysql_conn()
        if not conn:
            return
        try:
            blob = file_path.read_bytes()
            cursor = conn.cursor()
            query = f"""
                UPDATE {self.db_table}
                SET {self.db_blob_field} = %s,
                    {self.db_source_field} = %s,
                    {self.db_url_field} = NULL,
                    {self.db_mime_field} = 'application/pdf'
                WHERE {self.db_cas_field} = %s
            """
            cursor.execute(query, (blob, self.db_source_label, cas_number))
            conn.commit()
            logger.info("Synced SDS for CAS %s into table %s", cas_number, self.db_table)
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("MySQL sync failed for %s: %s", cas_number, exc)
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _push_missing_mysql(self, cas_number: str) -> None:
        if not self.db_missing_table:
            return
        conn = self._get_mysql_conn()
        if not conn:
            return
        try:
            cursor = conn.cursor()
            query = f"""
                INSERT INTO {self.db_missing_table} ({self.db_missing_cas_field})
                VALUES (%s)
                ON DUPLICATE KEY UPDATE {self.db_missing_cas_field} = VALUES({self.db_missing_cas_field})
            """
            cursor.execute(query, (cas_number,))
            conn.commit()
            logger.info("Marked CAS %s as missing in %s", cas_number, self.db_missing_table)
        except Exception as exc:  # pragma: no cover - best effort
            logger.debug("MySQL missing sync failed for %s: %s", cas_number, exc)
        finally:
            try:
                conn.close()
            except Exception:
                pass
