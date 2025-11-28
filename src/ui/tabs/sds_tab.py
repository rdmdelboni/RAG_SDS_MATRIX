"""
SDS Processor Tab for the RAG SDS Matrix application.
"""

from __future__ import annotations

import customtkinter as ctk

from ..components import Table, TitledFrame, TitleLabel


class SdsTab(ctk.CTkFrame):
    """
    A class to create the SDS Processor Tab
    """

    def __init__(self, master, app):
        super().__init__(master)
        self.app = app

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup SDS Processor tab."""
        self.configure(fg_color="transparent")
        TitleLabel(
            self,
            text=self.app.get_text("sds.title"),
            text_color=self.app.colors["text"],
        )

        # Vector Store status banner (hidden if ready)
        self.vs_status_frame = ctk.CTkFrame(
            self, fg_color=self.app.colors["surface"], corner_radius=6
        )
        self.vs_status_label = ctk.CTkLabel(
            self.vs_status_frame,
            text="Knowledge Base unavailable (vector store)",
            text_color=self.app.colors.get("warning", self.app.colors["text"]),
            font=("JetBrains Mono", 11),
        )
        self.vs_status_label.pack(side="left", padx=12, pady=8)
        ctk.CTkButton(
            self.vs_status_frame,
            corner_radius=4,
            text="Retry Vector Store",
            fg_color=self.app.colors.get("accent", "#6272a4"),
            text_color=self.app.colors["header"],
            font=self.app.button_font_sm,
            command=self._on_retry_vector_store,
        ).pack(side="right", padx=12, pady=8)

        # Initial status check
        self._set_vs_status(self.app.vector_store.ensure_ready())

        # Actions
        actions_frame = TitledFrame(
            self, "Actions", fg_color=self.app.colors["surface"]
        )
        actions_frame.pack(fill="x", padx=20, pady=10)

        ctk.CTkButton(
            actions_frame,
            corner_radius=4,
            text=self.app.get_text("sds.select_folder"),
            fg_color=self.app.colors["primary"],
            text_color=self.app.colors["header"],
            font=self.app.button_font,
            command=self.app._on_select_folder,
        ).pack(side="left", padx=10, pady=10)

        ctk.CTkButton(
            actions_frame,
            corner_radius=4,
            text=self.app.get_text("sds.process_all"),
            fg_color=self.app.colors["success"],
            text_color=self.app.colors["header"],
            font=self.app.button_font,
            command=self.app._on_process,
        ).pack(side="left", padx=10, pady=10)

        ctk.CTkButton(
            actions_frame,
            corner_radius=4,
            text=self.app.get_text("sds.export_excel"),
            fg_color=self.app.colors["accent"],
            text_color=self.app.colors["header"],
            font=self.app.button_font,
            command=self.app._on_export,
        ).pack(side="left", padx=10, pady=10)

        ctk.CTkButton(
            actions_frame,
            corner_radius=4,
            text="Build Matrix",
            fg_color=self.app.colors["primary"],
            text_color=self.app.colors["header"],
            font=self.app.button_font,
            command=self.app._on_build_matrix,
        ).pack(side="left", padx=10, pady=10)

        # Processing Options
        options_frame = TitledFrame(
            self, "Processing Options", fg_color=self.app.colors["surface"]
        )
        options_frame.pack(fill="x", padx=20, pady=10)

        self.app.use_rag_var = ctk.BooleanVar(value=True)
        rag_check = ctk.CTkCheckBox(
            options_frame,
            text="Use RAG Enrichment",
            variable=self.app.use_rag_var,
            font=("JetBrains Mono", 11),
            text_color=self.app.colors["text"],
        )
        rag_check.pack(side="left", padx=10, pady=10)

        # Progress
        progress_frame = TitledFrame(
            self, "Progress", fg_color=self.app.colors["surface"]
        )
        progress_frame.pack(fill="x", padx=20, pady=10)

        stats = self.app.db.get_statistics()
        stats_text = (
            f"Documents: {stats.get('total_documents', 0)} | "
            f"Processed: {stats.get('successful_documents', 0)} | "
            f"Failed: {stats.get('failed_documents', 0)} | "
            f"Dangerous: {stats.get('dangerous_count', 0)}"
        )

        stats_label = ctk.CTkLabel(
            progress_frame,
            text=stats_text,
            font=("JetBrains Mono", 12),
            text_color=self.app.colors["subtext"],
        )
        stats_label.pack(pady=10, padx=10)

        self.app.sds_progress = ctk.CTkProgressBar(
            progress_frame, fg_color=self.app.colors["accent"]
        )
        self.app.sds_progress.set(0)
        self.app.sds_progress.pack(fill="x", padx=10, pady=5)

        self.app.sds_progress_text = ctk.CTkLabel(
            progress_frame,
            text="Ready",
            font=("JetBrains Mono", 10),
            text_color=self.app.colors["subtext"],
        )
        self.app.sds_progress_text.pack(pady=5, padx=10)

        files_frame = TitledFrame(
            self, "Arquivos Selecionados", fg_color=self.app.colors["surface"]
        )
        files_frame.pack(fill="both", padx=20, pady=10, expand=True)

        self.app.sds_files_table = Table(
            files_frame,
            headers=["Arquivo", "Status"],
            rows=[("Nenhum arquivo selecionado.", "")],
            fg_color=self.app.colors["input"],
            text_color=self.app.colors["text"],
            accent_color=self.app.colors["accent"],
            height=220,
        )
        self.app.sds_files_table.pack(fill="both", expand=True, padx=10, pady=10)

    # === Internal Handlers ===
    def _set_vs_status(self, ready: bool) -> None:
        """Show or hide the vector store banner based on readiness."""
        try:
            if ready:
                # Hide banner if currently visible
                try:
                    self.vs_status_frame.pack_forget()
                except Exception:
                    pass
            else:
                # Show banner at the top
                self.vs_status_frame.pack(fill="x", padx=20, pady=(10, 0))
        except Exception:
            pass

    def _on_retry_vector_store(self) -> None:
        ok = False
        try:
            ok = self.app.vector_store.ensure_ready()
        except Exception:
            ok = False
        self._set_vs_status(ok)
        if ok:
            self.app._update_status("Knowledge Base ready", level="success")
        else:
            self.app._update_status(
                "Knowledge Base unavailable (vector store)", level="warning"
            )

    # Public method used by the parent app when tab becomes active
    def refresh_vs_status(self) -> None:
        try:
            ready = self.app.vector_store.ensure_ready()
        except Exception:
            ready = False
        self._set_vs_status(ready)
