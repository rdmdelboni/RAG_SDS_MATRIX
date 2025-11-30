"""
RAG Records Viewer Tab for the RAG SDS Matrix application.
"""

from __future__ import annotations

import shutil
import tempfile
import threading
from pathlib import Path

import customtkinter as ctk

from scripts.rag_records import RAGRecordViewer

from ..components import EditableTable, TitleLabel
from ..components.app_button import AppButton


class RecordsTab(ctk.CTkFrame):
    """
    A class to create the RAG Records Viewer Tab
    """

    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup Records Viewer tab."""
        # Title
        TitleLabel(self, text="RAG Records Viewer", text_color=self.app.colors["text"])

        # Main content frame
        content_frame = ctk.CTkFrame(
            self, fg_color=self.app.colors["surface"], corner_radius=10
        )
        content_frame.pack(fill="both", expand=True, padx=20, pady=10)

        # === Query Controls ===
        query_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        query_frame.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(
            query_frame,
            text="Query Type:",
            font=("JetBrains Mono", 12),
            text_color=self.app.colors["text"],
        ).pack(side="left", padx=5)

        self.query_var = ctk.StringVar(value="incompatibilities")
        query_options = [
            ("Incompatibilities", "incompatibilities"),
            ("Hazards", "hazards"),
            ("CAMEO Chemicals", "cameo"),
            ("File Documents", "files"),
        ]

        for label, value in query_options:
            ctk.CTkRadioButton(
                query_frame,
                text=label,
                variable=self.query_var,
                value=value,
                font=("JetBrains Mono", 11),
                text_color=self.app.colors["text"],
            ).pack(side="left", padx=10)

        # === Limit Controls ===
        limit_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        limit_frame.pack(fill="x", padx=20, pady=5)

        ctk.CTkLabel(
            limit_frame,
            text="Records to show:",
            font=("JetBrains Mono", 12),
            text_color=self.app.colors["text"],
        ).pack(side="left", padx=5)

        self.limit_var = ctk.StringVar(value="50")
        limit_entry = ctk.CTkEntry(
            limit_frame,
            textvariable=self.limit_var,
            width=80,
            font=("JetBrains Mono", 11),
            fg_color=self.app.colors["input"],
            text_color=self.app.colors["text"],
        )
        limit_entry.pack(side="left", padx=5)

        AppButton(
            limit_frame,
            text="Query Database",
            command=self._on_query,
            fg_color=self.app.colors["accent"],
            text_color=self.app.colors["header"],
            hover_color=self.app.colors["button_hover"],
            width=180,
        ).pack(side="left", padx=20)

        # Copy results helper
        AppButton(
            limit_frame,
            text="Copy Output",
            command=self._copy_results,
            fg_color=self.app.colors["surface"],
            text_color=self.app.colors["text"],
            hover_color=self.app.colors["button_hover"],
            width=160,
        ).pack(side="right", padx=5)

        # === Results Area ===
        results_label = ctk.CTkLabel(
            content_frame,
            text="Resultados:",
            font=("JetBrains Mono", 12, "bold"),
            text_color=self.app.colors["text"],
        )
        results_label.pack(anchor="w", padx=20, pady=(10, 5))

        self.results_table = EditableTable(
            content_frame,
            headers=["#", "Coluna 1", "Coluna 2", "Coluna 3"],
            rows=[["1", "Aguardando consulta...", "", ""]],
            fg_color=self.app.colors["input"],
            text_color=self.app.colors["text"],
            header_color=self.app.colors["surface"],
            accent_color=self.app.colors["accent"],
            selected_color=self.app.colors.get("surface", "#334155"),
            min_col_width=100,
            editable=False,
        )
        self.results_table.pack(fill="both", expand=True, padx=20, pady=(0, 20))

    def _on_query(self) -> None:
        """Handle RAG query."""
        query_type = self.query_var.get()
        limit = self.limit_var.get()

        # Run rag_records.py in thread
        thread = threading.Thread(
            target=self._run_query_async, args=(query_type, limit)
        )
        thread.daemon = True
        thread.start()

    def _run_query_async(self, query_type: str, limit: str) -> None:
        """Run the query asynchronously."""
        try:
            limit_int = max(1, int(limit))
        except ValueError:
            limit_int = 50

        tmp_dir: Path | None = None
        try:
            self.app.after(
                0,
                lambda: self.results_table.set_data(["Status"], [("Consultando...",)]),
            )

            # Usar cópia do DB para evitar lock
            db_path = Path(self.app.settings.paths.duckdb)
            tmp_dir = Path(tempfile.mkdtemp(prefix="records_query_"))
            tmp_db = tmp_dir / db_path.name
            shutil.copy2(db_path, tmp_db)

            viewer = RAGRecordViewer(str(tmp_db))
            headers: list[str] = []
            rows: list[tuple] = []

            if query_type == "incompatibilities":
                headers = ["CAS A", "Nome A", "CAS B", "Nome B", "Regra", "Fonte"]
                records = viewer.search_incompatibilities(limit=limit_int)
                rows = []
                for i, r in enumerate(records, start=1):
                    rows.append(
                        (
                            i,
                            r.get("cas_a"),
                            r.get("name_a") or "",
                            r.get("cas_b"),
                            r.get("name_b") or "",
                            r.get("rule"),
                            r.get("source"),
                        )
                    )
            elif query_type == "hazards":
                headers = ["CAS", "Nome", "Flags", "Fonte"]
                records = viewer.search_hazards(limit=limit_int)
                rows = []
                for i, r in enumerate(records, start=1):
                    rows.append(
                        (
                            i,
                            r.get("cas"),
                            r.get("name") or "",
                            ", ".join(
                                f"{k}:{v}" for k, v in r.get("hazard_flags", {}).items()
                            ),
                            r.get("source"),
                        )
                    )
            elif query_type == "cameo":
                headers = ["ID", "Título", "Nome Químico", "URL", "Chunks"]
                records = viewer.get_cameo_chemicals(limit=limit_int)
                rows = []
                for i, r in enumerate(records, start=1):
                    rows.append(
                        (
                            i,
                            r.get("id"),
                            r.get("title"),
                            r.get("chemical_name") or "",
                            r.get("url") or "",
                            r.get("chunk_count"),
                        )
                    )
            elif query_type == "files":
                headers = ["ID", "Título", "Nome Químico", "Caminho", "Chunks"]
                records = viewer.get_file_documents(limit=limit_int)
                rows = []
                for i, r in enumerate(records, start=1):
                    rows.append(
                        (
                            i,
                            r.get("id"),
                            r.get("title"),
                            r.get("chemical_name") or "",
                            r.get("path") or "",
                            r.get("chunk_count"),
                        )
                    )

            if not rows:
                headers = ["Resultado"]
                rows = [(1, "Sem resultados")]  # include row number

            # Prepend row number header
            headers = ["#"] + headers
            self.app.after(
                0,
                lambda h=headers, r=rows: self.results_table.set_data(
                    h or ["#", "Resultado"], r, accent_color=self.app.colors["accent"]
                ),
            )

        except Exception as e:
            error_msg = f"Error executing query: {str(e)}"
            self.app.after(
                0,
                lambda: self.results_table.set_data(
                    ["Erro", "Mensagem"], [("Falha", error_msg)]
                ),
            )
        finally:
            if tmp_dir:
                try:
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                except Exception:
                    pass

    def _copy_results(self) -> None:
        """Copy the current results to the clipboard for easy sharing."""
        try:
            data = self.results_table.get_all_data()
            if not data:
                return
            # Format as tab-separated values for pasting into spreadsheets
            text = "\n".join("\t".join(str(cell) for cell in row) for row in data)
            self.app.clipboard_clear()
            self.app.clipboard_append(text)
            self.app.update()  # ensure clipboard is updated
        except Exception:
            # Fail silently; copying is a convenience feature
            pass
