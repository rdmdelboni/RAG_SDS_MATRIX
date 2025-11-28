"""
Sources Tab for the RAG SDS Matrix application.
"""

from __future__ import annotations


import customtkinter as ctk

from ..components import SimpleTable, TitledFrame, TitleLabel


class SourcesTab(ctk.CTkFrame):
    """
    A class to create the Sources Tab
    """

    def __init__(self, master, app):
        super().__init__(master)
        self.app = app

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the knowledge sources tab."""
        self.configure(fg_color="transparent")
        TitleLabel(
            self,
            text=self.app.get_text("sources.title"),
            text_color=self.app.colors["text"],
        )

        # Local sources
        local_frame = TitledFrame(
            self,
            self.app.get_text("sources.local"),
            fg_color=self.app.colors["surface"],
        )
        local_frame.pack(fill="x", padx=20, pady=10)

        local_btn_frame = ctk.CTkFrame(local_frame, fg_color="transparent")
        local_btn_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkButton(
            local_btn_frame,
            corner_radius=4,
            text="Add Local Files",
            fg_color=self.app.colors["primary"],
            font=self.app.button_font,
            command=self.app._on_ingest_local_files,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            local_btn_frame,
            corner_radius=4,
            text="Add Folder",
            fg_color=self.app.colors["accent"],
            font=self.app.button_font,
            command=self.app._on_ingest_local_folder,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            local_btn_frame,
            corner_radius=4,
            text="Load Snapshot",
            fg_color=self.app.colors["success"],
            font=self.app.button_font,
            command=self.app._on_ingest_snapshot_file,
        ).pack(side="left", padx=5)

        # Web ingestion
        web_frame = TitledFrame(
            self, self.app.get_text("sources.web"), fg_color=self.app.colors["surface"]
        )
        web_frame.pack(fill="x", padx=20, pady=10)

        url_frame = ctk.CTkFrame(web_frame, fg_color="transparent")
        url_frame.pack(fill="x", padx=10, pady=10)

        self.app.sources_url_entry = ctk.CTkEntry(
            url_frame,
            placeholder_text="https://example.com/article",
            fg_color=self.app.colors["input"],
            text_color=self.app.colors["text"],
        )
        self.app.sources_url_entry.pack(side="left", fill="x", expand=True, padx=5)

        ctk.CTkButton(
            url_frame,
            corner_radius=4,
            text="Fetch URL",
            fg_color=self.app.colors["accent"],
            font=self.app.button_font_sm,
            command=self.app._on_sources_add_url,
        ).pack(side="left", padx=5)

        search_frame = ctk.CTkFrame(web_frame, fg_color="transparent")
        search_frame.pack(fill="x", padx=10, pady=10)

        self.app.sources_search_entry = ctk.CTkEntry(
            search_frame,
            placeholder_text="Search query (e.g., solvent storage best practices)",
            fg_color=self.app.colors["input"],
            text_color=self.app.colors["text"],
        )
        self.app.sources_search_entry.pack(side="left", fill="x", expand=True, padx=5)

        self.app.sources_search_results_entry = ctk.CTkEntry(
            search_frame,
            width=60,
            fg_color=self.app.colors["input"],
            text_color=self.app.colors["text"],
        )
        self.app.sources_search_results_entry.insert(0, "5")
        self.app.sources_search_results_entry.pack(side="left", padx=5)

        ctk.CTkButton(
            search_frame,
            corner_radius=4,
            text="Google Search",
            fg_color=self.app.colors["primary"],
            font=self.app.button_font_sm,
            command=self.app._on_sources_search,
        ).pack(side="left", padx=5)

        # Simple URL batch ingestion
        batch_frame = TitledFrame(
            self,
            "Fetch multiple URLs (free scraper)",
            fg_color=self.app.colors["surface"],
        )
        batch_frame.pack(fill="x", padx=20, pady=10)

        self.app.simple_urls_text = ctk.CTkTextbox(
            batch_frame,
            fg_color=self.app.colors["input"],
            text_color=self.app.colors["text"],
            height=80,
            border_color=self.app.colors["accent"],
            border_width=1,
        )
        self.app.simple_urls_text.insert(
            "1.0",
            "\n".join(
                [
                    "https://www.osha.gov/",
                    "https://www.cdc.gov/niosh/",
                    "https://sistemasinter.cetesb.sp.gov.br/produtos/produto_consulta_completa.asp",
                    "https://cameochemicals.noaa.gov/help/reactivity/reactive_groups.htm",
                    "https://safescience.cas.org/",
                    "https://www.cdc.gov/niosh/npg/npgdcas.html",
                ]
            ),
        )
        self.app.simple_urls_text.pack(fill="x", padx=10, pady=10)

        ctk.CTkButton(
            batch_frame,
            corner_radius=4,
            text="Fetch URLs (simple)",
            fg_color=self.app.colors["primary"],
            font=self.app.button_font_sm,
            command=self.app._on_simple_urls,
        ).pack(anchor="w", padx=10, pady=10)

        # Sources list
        list_frame = TitledFrame(
            self,
            self.app.get_text("sources.recent"),
            fg_color=self.app.colors["surface"],
        )
        list_frame.pack(fill="both", expand=True, padx=20, pady=10)

        self.app.sources_table = SimpleTable(
            list_frame,
            headers=["Data/Hora", "Título", "Tipo", "Chunks"],
            rows=[("Nenhum dado", "", "", "")],
            fg_color=self.app.colors["input"],
            text_color=self.app.colors["text"],
            header_color=self.app.colors["surface"],
            accent_color=self.app.colors["accent"],
            min_col_width=100,
        )
        self.app.sources_table.pack(fill="both", expand=True, padx=10, pady=10)

        # Bright Data Section
        bright_frame = TitledFrame(
            self,
            self.app.get_text("sources.brightdata"),
            fg_color=self.app.colors["surface"],
        )
        bright_frame.pack(fill="x", padx=20, pady=10)

        keyword_label = ctk.CTkLabel(
            bright_frame,
            text="Keywords (one per line, optional :pages):",
            font=("JetBrains Mono", 11),
            text_color=self.app.colors["subtext"],
        )
        keyword_label.pack(anchor="w", pady=(5, 0), padx=10)

        self.app.bright_keywords_text = ctk.CTkTextbox(
            bright_frame,
            fg_color=self.app.colors["input"],
            text_color=self.app.colors["text"],
            height=100,
            border_color=self.app.colors["accent"],
            border_width=1,
        )
        self.app.bright_keywords_text.pack(fill="x", pady=5, padx=10)

        default_keywords = "solvent storage\nflammable liquids handling"
        self.app.bright_keywords_text.insert("1.0", default_keywords)

        pages_frame = ctk.CTkFrame(bright_frame, fg_color="transparent")
        pages_frame.pack(fill="x", pady=5, padx=10)

        ctk.CTkLabel(
            pages_frame,
            text="Default pages per keyword:",
            font=("JetBrains Mono", 11),
            text_color=self.app.colors["text"],
        ).pack(side="left")

        self.app.bright_pages_entry = ctk.CTkEntry(
            pages_frame,
            width=60,
            fg_color=self.app.colors["input"],
            text_color=self.app.colors["text"],
        )
        self.app.bright_pages_entry.insert(0, "2")
        self.app.bright_pages_entry.pack(side="left", padx=5)

        bright_btn_frame = ctk.CTkFrame(bright_frame, fg_color="transparent")
        bright_btn_frame.pack(fill="x", pady=5, padx=10)

        ctk.CTkButton(
            bright_btn_frame,
            corner_radius=4,
            text="Trigger Crawl",
            fg_color=self.app.colors["primary"],
            font=self.app.button_font_sm,
            command=self.app._on_bright_trigger,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            bright_btn_frame,
            corner_radius=4,
            text="Check Status",
            fg_color=self.app.colors["accent"],
            font=self.app.button_font_sm,
            command=self.app._on_bright_check,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            bright_btn_frame,
            corner_radius=4,
            text="Download & Ingest",
            fg_color=self.app.colors["success"],
            font=self.app.button_font_sm,
            command=self.app._on_bright_download,
        ).pack(side="left", padx=5)

        self.app.bright_snapshot_var = ctk.StringVar(value="Snapshot: None")
        ctk.CTkLabel(
            bright_frame,
            textvariable=self.app.bright_snapshot_var,
            font=("JetBrains Mono", 11),
            text_color=self.app.colors["subtext"],
        ).pack(anchor="w", pady=(5, 0), padx=10)

        # Craw4AI section
        craw_frame = TitledFrame(
            self, "Craw4AI (local crawler)", fg_color=self.app.colors["surface"]
        )
        craw_frame.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(
            craw_frame,
            text="Seeds (one URL per line):",
            font=("JetBrains Mono", 11),
            text_color=self.app.colors["subtext"],
        ).pack(anchor="w", pady=(5, 0), padx=10)

        self.app.craw_seeds_text = ctk.CTkTextbox(
            craw_frame,
            fg_color=self.app.colors["input"],
            text_color=self.app.colors["text"],
            height=80,
            border_color=self.app.colors["accent"],
            border_width=1,
        )
        self.app.craw_seeds_text.insert(
            "1.0",
            "\n".join(
                [
                    "https://www.osha.gov/",
                    "https://www.cdc.gov/niosh/",
                    "https://sistemasinter.cetesb.sp.gov.br/produtos/produto_consulta_completa.asp",
                    "https://cameochemicals.noaa.gov/help/reactivity/reactive_groups.htm",
                    "https://safescience.cas.org/",
                    "https://www.cdc.gov/niosh/npg/npgdcas.html",
                ]
            ),
        )
        self.app.craw_seeds_text.pack(fill="x", pady=5, padx=10)

        ctk.CTkButton(
            craw_frame,
            corner_radius=4,
            text="Run Craw4AI Job",
            fg_color=self.app.colors["accent"],
            command=self.app._on_craw4ai_run,
        ).pack(anchor="w", padx=10, pady=10)

        # Status label
        self.app.sources_status_var = ctk.StringVar(
            value=self.app.get_text("app.ready")
        )
        self.app.sources_status_label = ctk.CTkLabel(
            self,
            textvariable=self.app.sources_status_var,
            font=("JetBrains Mono", 12),
            text_color=self.app.colors["subtext"],
        )
        self.app.sources_status_label.pack(pady=10)

        self.app._refresh_sources_list()
        self.app._update_snapshot_label()
