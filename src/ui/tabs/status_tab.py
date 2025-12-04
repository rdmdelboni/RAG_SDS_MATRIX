"""Status tab for monitoring system health.

Provides real-time status information for database, Ollama, and RAG systems.
"""

from __future__ import annotations

from PySide6 import QtWidgets

from . import BaseTab, TabContext


class StatusTab(BaseTab):
    """Tab for monitoring system status and statistics."""

    def __init__(self, context: TabContext) -> None:
        super().__init__(context)
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the status tab UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        # Title
        title = QtWidgets.QLabel("📊 System Status")
        self._style_label(title, bold=True)
        title.setStyleSheet(title.styleSheet() + f"; font-size: 16px;")
        layout.addWidget(title)

        # Database Statistics Section
        db_title = QtWidgets.QLabel("📁 Database Statistics")
        self._style_label(db_title, bold=True)
        db_title.setStyleSheet(db_title.styleSheet() + f"; font-size: 12px;")
        layout.addWidget(db_title)

        db_frame = QtWidgets.QFrame()
        db_frame.setStyleSheet(
            f"QFrame {{"
            f"background-color: {self.colors['surface']};"
            f"border-radius: 6px;"
            f"padding: 12px;"
            f"}}"
        )
        db_layout = QtWidgets.QVBoxLayout(db_frame)
        db_layout.setSpacing(6)

        self.status_stats_label = QtWidgets.QLabel("Stats unavailable")
        self._style_label(self.status_stats_label)
        self.status_stats_label.setWordWrap(True)
        db_layout.addWidget(self.status_stats_label)

        db_frame.setLayout(db_layout)
        layout.addWidget(db_frame)

        # Ollama Status Section
        ollama_title = QtWidgets.QLabel("🤖 Ollama Connection")
        self._style_label(ollama_title, bold=True)
        ollama_title.setStyleSheet(ollama_title.styleSheet() + f"; font-size: 12px;")
        layout.addWidget(ollama_title)

        ollama_frame = QtWidgets.QFrame()
        ollama_frame.setStyleSheet(
            f"QFrame {{"
            f"background-color: {self.colors['surface']};"
            f"border-radius: 6px;"
            f"padding: 12px;"
            f"}}"
        )
        ollama_layout = QtWidgets.QVBoxLayout(ollama_frame)
        ollama_layout.setSpacing(6)

        self.ollama_status_label = QtWidgets.QLabel("Checking connection...")
        self._style_label(self.ollama_status_label)
        ollama_layout.addWidget(self.ollama_status_label)

        self.ollama_models_label = QtWidgets.QLabel("Available models: --")
        self._style_label(self.ollama_models_label, color=self.colors.get("subtext", "#a6adc8"))
        ollama_layout.addWidget(self.ollama_models_label)

        ollama_frame.setLayout(ollama_layout)
        layout.addWidget(ollama_frame)

        # RAG Status Section
        rag_title = QtWidgets.QLabel("🧠 RAG System")
        self._style_label(rag_title, bold=True)
        rag_title.setStyleSheet(rag_title.styleSheet() + f"; font-size: 12px;")
        layout.addWidget(rag_title)

        rag_frame = QtWidgets.QFrame()
        rag_frame.setStyleSheet(
            f"QFrame {{"
            f"background-color: {self.colors['surface']};"
            f"border-radius: 6px;"
            f"padding: 12px;"
            f"}}"
        )
        rag_layout = QtWidgets.QVBoxLayout(rag_frame)
        rag_layout.setSpacing(6)

        self.rag_status_label = QtWidgets.QLabel("RAG Status: Initializing...")
        self._style_label(self.rag_status_label)
        rag_layout.addWidget(self.rag_status_label)

        self.rag_documents_label = QtWidgets.QLabel("Indexed documents: --")
        self._style_label(self.rag_documents_label, color=self.colors.get("subtext", "#a6adc8"))
        rag_layout.addWidget(self.rag_documents_label)

        rag_frame.setLayout(rag_layout)
        layout.addWidget(rag_frame)

        # Refresh Button
        refresh_btn = QtWidgets.QPushButton("🔄 Refresh All Statistics")
        self._style_button(refresh_btn)
        refresh_btn.clicked.connect(self._on_refresh)
        layout.addWidget(refresh_btn)

        layout.addStretch()

    def _on_refresh(self) -> None:
        """Handle refresh button click."""
        self._set_status("Refreshing system statistics…")
        self._refresh_db_stats()

    def _refresh_db_stats(self) -> None:
        """Refresh all status statistics."""
        stats = self.context.db.get_statistics()

        # Database Statistics
        total_docs = stats.get('total_documents', 0)
        processed_docs = stats.get('processed', stats.get('successful_documents', 0))
        failed_docs = stats.get('failed_documents', 0)
        rag_docs = stats.get('rag_documents', 0)

        # Calculate success rate
        success_rate = 0
        if total_docs > 0:
            success_rate = int((processed_docs / total_docs) * 100)

        stats_text = (
            f"📄 Total: {total_docs} | "
            f"✅ Processed: {processed_docs} ({success_rate}%) | "
            f"❌ Failed: {failed_docs} | "
            f"🧠 RAG Indexed: {rag_docs}"
        )
        self.status_stats_label.setText(stats_text)

        # Update Ollama status
        try:
            models = self.context.ollama.list_models()
            if models:
                status_text = "✓ Connected"
                self._style_label(self.ollama_status_label, color=self.colors.get("success", "#a6e3a1"))
                models_text = f"Available models: {len(models)} - {', '.join(models[:3])}"
                if len(models) > 3:
                    models_text += f" +{len(models)-3} more"
                self.ollama_models_label.setText(models_text)
                self._style_label(self.ollama_models_label, color=self.colors.get("subtext", "#a6adc8"))
            else:
                status_text = "⚠ Connected but no models available"
                self._style_label(self.ollama_status_label, color=self.colors.get("warning", "#f9e2af"))
                self.ollama_models_label.setText("No models installed")
        except Exception as e:
            status_text = "✗ Not connected"
            self._style_label(self.ollama_status_label, color=self.colors.get("error", "#f38ba8"))
            self.ollama_models_label.setText(f"Connection error: {str(e)[:50]}")
            self._style_label(self.ollama_models_label, color=self.colors.get("error", "#f38ba8"))

        self.ollama_status_label.setText(status_text)

        # Update RAG status
        try:
            vector_store = self.context.ingestion.vector_store
            vector_count = len(vector_store.db.get())  # Approximate count
            if vector_count > 0:
                self.rag_status_label.setText("✓ RAG System Active")
                self._style_label(self.rag_status_label, color=self.colors.get("success", "#a6e3a1"))
            else:
                self.rag_status_label.setText("⚠ RAG System Idle")
                self._style_label(self.rag_status_label, color=self.colors.get("warning", "#f9e2af"))

            self.rag_documents_label.setText(f"Indexed documents: {vector_count}")
            self._style_label(self.rag_documents_label, color=self.colors.get("subtext", "#a6adc8"))
        except Exception as e:
            self.rag_status_label.setText("✗ RAG System Error")
            self._style_label(self.rag_status_label, color=self.colors.get("error", "#f38ba8"))
            self.rag_documents_label.setText(f"Error: {str(e)[:50]}")
            self._style_label(self.rag_documents_label, color=self.colors.get("error", "#f38ba8"))

        self._set_status("System statistics refreshed")
