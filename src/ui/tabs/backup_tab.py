"""Backup tab for RAG data export.

Provides UI and handlers for backing up RAG ingested documents, incompatibilities,
hazards, and vector store to external locations.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6 import QtWidgets

from . import BaseTab, TabContext
from ...config import get_settings
from ..components import TaskRunner, WorkerSignals
from ...utils.logger import get_logger

logger = get_logger(__name__)


class BackupTab(BaseTab):
    """Tab for managing RAG data backups."""

    def __init__(self, context: TabContext) -> None:
        super().__init__(context)
        self.settings = get_settings()
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the backup tab UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        # Description
        desc = QtWidgets.QLabel(
            "Run the backup script to export RAG data (incompatibilities, hazards, documents)."
        )
        self._style_label(desc, color=self.colors.get("subtext", "#888888"))
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Start button
        run_btn = QtWidgets.QPushButton("💾 Start Backup")
        self._style_button(run_btn)
        run_btn.clicked.connect(self._on_backup)
        layout.addWidget(run_btn)

        # Logs
        self.backup_log = QtWidgets.QTextEdit()
        self.backup_log.setReadOnly(True)
        self.backup_log.setPlaceholderText("Backup logs will appear here…")
        self._style_textedit(self.backup_log)
        layout.addWidget(self.backup_log)

    def _on_backup(self) -> None:
        """Handle backup button click."""
        output_dir = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select backup directory", str(self.settings.paths.output_dir)
        )
        if not output_dir:
            return
        self._set_status(f"Starting backup to {output_dir}…")
        self._start_task(self._backup_task, Path(output_dir), on_result=self._on_backup_done)

    def _backup_task(
        self, output_dir: Path, *, signals: WorkerSignals | None = None
    ) -> str:
        """Execute backup script in background."""
        db_path = str(
            getattr(self.settings.paths, "duckdb", "data/duckdb/extractions.db")
        )
        cmd = [
            sys.executable,
            "scripts/rag_backup.py",
            "--output",
            str(output_dir),
            "--db",
            db_path,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())
        log = proc.stdout or ""
        if proc.stderr:
            log += "\n[stderr]\n" + proc.stderr
        if signals:
            signals.message.emit(f"Backup finished (code {proc.returncode})")
        return log

    def _on_backup_done(self, result: object) -> None:
        """Handle backup completion."""
        if isinstance(result, str):
            self.backup_log.setPlainText(result.strip() or "No log output.")
        self._set_status("Backup complete")
