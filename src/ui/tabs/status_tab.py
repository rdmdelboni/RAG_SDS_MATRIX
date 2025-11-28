"""
Status Tab for the RAG SDS Matrix application.
"""

from __future__ import annotations

import customtkinter as ctk

from ..components import Table, TitleLabel


class StatusTab(ctk.CTkFrame):
    """
    A class to create the Status Tab
    """

    def __init__(self, master, app):
        super().__init__(master)
        self.app = app

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup Status/Metrics tab."""
        # Title
        TitleLabel(
            self, text="System Status & Metrics", text_color=self.app.colors["text"]
        )

        # Refresh button
        refresh_btn = ctk.CTkButton(
            self,
            corner_radius=4,
            text="Refresh Stats",
            command=self._refresh_status_metrics,
            fg_color=self.app.colors["accent"],
            hover_color=self.app.colors["button_hover"],
            font=self.app.button_font,
            width=200,
            height=40,
        )
        refresh_btn.pack(pady=10)

        # Metrics display (scrollable)
        metrics_frame = ctk.CTkFrame(self, fg_color="transparent")
        metrics_frame.pack(fill="both", expand=True, padx=20, pady=10)

        self.app.status_metrics_table = Table(
            metrics_frame,
            headers=["Métrica", "Valor"],
            rows=[],
            fg_color=self.app.colors["input"],
            text_color=self.app.colors["text"],
            accent_color=self.app.colors["accent"],
            height=400,
        )
        self.app.status_metrics_table.pack(fill="both", expand=True, padx=4, pady=4)

        # Load initial metrics
        self._refresh_status_metrics()

    def _refresh_status_metrics(self) -> None:
        """Refresh and display system metrics."""
        try:
            # Gather all metrics
            db_stats = self.app.db.get_statistics()

            # Vector store stats
            try:
                vs_stats = self.app.vector_store.get_statistics()
            except Exception:
                vs_stats = {"error": "Unable to connect"}

            # MRLP stats
            with self.app.db._lock:
                incompat_count = self.app.db.conn.execute(
                    "SELECT COUNT(*) FROM rag_incompatibilities"
                ).fetchone()[0]
                hazard_count = self.app.db.conn.execute(
                    "SELECT COUNT(*) FROM rag_hazards"
                ).fetchone()[0]
                snapshots = self.app.db.conn.execute(
                    "SELECT COUNT(*) FROM mrlp_snapshots"
                ).fetchone()[0]
                decisions = self.app.db.conn.execute(
                    "SELECT COUNT(*) FROM matrix_decisions"
                ).fetchone()[0]

            # Format output
            rows = []
            for key, value in db_stats.items():
                rows.append(("Banco de Dados", f"{key}: {value}"))

            rows.append(("MRLP", f"Regras de incompatibilidade: {incompat_count}"))
            rows.append(("MRLP", f"Registros de perigo: {hazard_count}"))
            rows.append(("MRLP", f"Snapshots MRLP: {snapshots}"))
            rows.append(("MRLP", f"Decisões registradas: {decisions}"))

            if "error" in vs_stats:
                rows.append(("ChromaDB", vs_stats["error"]))
            else:
                for key, value in vs_stats.items():
                    rows.append(("ChromaDB", f"{key}: {value}"))

            ollama_connected = self.app.ollama.test_connection()
            rows.append(
                ("Ollama", "Conectado" if ollama_connected else "Não conectado")
            )
            if ollama_connected:
                models = self.app.ollama.list_models()[:5]
                rows.append(("Ollama", f"Modelos disponíveis: {len(models)}"))
                for model in models:
                    rows.append(("Modelo", model))

            self.app.status_metrics_table.set_data(
                ["Seção", "Valor"], rows, accent_color=self.app.colors["accent"]
            )

            if hasattr(self.app, "status_text"):
                self.app._update_status("Status atualizado", "success")
        except Exception as e:
            if hasattr(self.app, "status_metrics_table"):
                self.app.status_metrics_table.set_data(
                    ["Erro", "Mensagem"], [("Falha", str(e))]
                )
