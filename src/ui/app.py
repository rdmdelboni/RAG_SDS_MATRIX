"""Main application UI - RAG SDS Matrix."""

from __future__ import annotations

import json
import threading
from pathlib import Path
import time
from tkinter import END, filedialog, messagebox

import customtkinter as ctk

from ..config import get_settings, get_text
from ..config.constants import SUPPORTED_FORMATS
from ..config.i18n import set_language
from ..database import get_db_manager
from ..models import get_ollama_client
from ..rag.chunker import TextChunker
from ..rag.document_loader import DocumentLoader
from ..rag.ingestion_service import IngestionSummary, KnowledgeIngestionService
from ..rag.vector_store import get_vector_store
from ..utils.logger import get_logger
from .tabs import BackupTab, ChatTab, RagTab, RecordsTab, ReviewTab, SdsTab, SourcesTab, StatusTab
from .theme import get_colors
from .window_manager import create_window_manager

logger = get_logger(__name__)


class Application(ctk.CTk):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()

        self.settings = get_settings()
        self.colors = get_colors(self.settings.ui.theme)
        self.logger = logger
        self.button_font = ("Segoe UI", 12, "bold")
        self.button_font_sm = ("Segoe UI", 11, "bold")

        # Initialize services (with simple startup timings)
        t0 = time.time()
        self.db = get_db_manager()
        t_db = (time.time() - t0) * 1000

        t1 = time.time()
        self.ollama = get_ollama_client()
        t_ol = (time.time() - t1) * 1000

        t2 = time.time()
        self.doc_loader = DocumentLoader()
        self.chunker = TextChunker()
        self.vector_store = get_vector_store()
        self.ingestion = KnowledgeIngestionService()
        t_rest = (time.time() - t2) * 1000
        # sds_file_rows: filename -> (status, chemical_name)
        self.sds_file_rows: dict[str, tuple[str, str]] = {}

        # Fixar idioma da UI/relatórios em Português, independentemente do idioma do documento processado
        set_language(self.settings.ui.language or "pt")

        # Configure window (responsive)
        self.title(get_text("app.title"))
        self.minsize(self.settings.ui.min_width, self.settings.ui.min_height)
        self.configure(fg_color=self.colors["bg"])

        # Configure CustomTkinter
        ctk.set_appearance_mode("dark" if self.settings.ui.theme == "dark" else "light")
        self._apply_ui_scaling(initial=True)

        # Setup UI
        self._setup_ui()

        # Initialize window manager for sizing, positioning, and state management
        self.window_manager = create_window_manager(self, self.settings)

        # Prevent maximized state and handle window events (disabled auto-resize per user request)
        # self.bind("<Configure>", self._on_window_configure)

        # Close handler
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        logger.info(
            "Startup ready: DuckDB=%.0fms, Ollama=%.0fms, Core=%.0fms",
            t_db,
            t_ol,
            t_rest,
        )
        logger.info("Application initialized")

    def _on_window_configure(self, event=None) -> None:
        """Disabled: originally handled window configuration events.

        Left as no-op to satisfy existing references without resizing the window.
        """
        return

    def _center_window(self) -> None:
        """Center the window using configured dimensions without further resizing."""
        try:
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()
            target_w = int(self.settings.ui.window_width)
            target_h = int(self.settings.ui.window_height)
            x = max(0, (screen_w - target_w) // 2)
            y = max(0, (screen_h - target_h) // 2)
            self.geometry(f"{target_w}x{target_h}+{x}+{y}")
        except Exception:
            pass

    def _setup_ui(self) -> None:
        """Setup main UI components."""
        # Main container
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=8, pady=8)

        # Header bar with title and Exit button
        self._setup_header_bar()

        # Tab view
        self.tab_view = ctk.CTkTabview(
            self.main_frame,
            fg_color=self.colors["bg"],
            corner_radius=12,
            segmented_button_fg_color=self.colors.get(
                "tab_inactive", self.colors["surface"]
            ),
            segmented_button_selected_color=self.colors.get(
                "tab_active", self.colors["accent"]
            ),
            segmented_button_selected_hover_color=self.colors.get(
                "tab_hover", self.colors["button_hover"]
            ),
            text_color=self.colors["text"],
        )
        self.tab_view.pack(fill="both", expand=True)

        # Add tabs
        self.tab_view.add(get_text("tab.rag"))
        self.tab_view.add(get_text("tab.sources"))
        self.tab_view.add(get_text("tab.sds"))
        self.tab_view.add("Records")
        self.tab_view.add("Review")
        self.tab_view.add("Quality")
        self.tab_view.add("Backup")
        self.tab_view.add("Status")
        self.tab_view.add("Chat")


        # Center window once after UI is built
        self.after(50, self._center_window)
        # Setup tab contents (placeholders for now)
        self._setup_rag_tab()
        self._setup_sources_tab()
        self._setup_sds_tab()
        self._setup_records_tab()
        self._setup_review_tab()
        self._setup_quality_tab()
        self._setup_backup_tab()
        self._setup_status_tab()
        self._setup_chat_tab()

        # Status bar
        self._setup_status_bar()
        # Start tab change watchdog (polling) for SDS banner refresh
        self._last_tab_name = None
        self.after(300, self._check_tab_change)
        # Bind resize to adapt scaling for screen/window ratio
        self._last_size = (self.winfo_width(), self.winfo_height())
        self._last_scale_update = time.time()
        # Disable automatic window resizing behavior
        # self.bind("<Configure>", self._on_window_resize)

    def _check_tab_change(self) -> None:
        """Poll for tab selection changes and refresh SDS banner when needed."""
        try:
            current = self.tab_view.get()
            if current != getattr(self, "_last_tab_name", None):
                self._last_tab_name = current
                if current == get_text("tab.sds") and hasattr(self, "sds_tab"):
                    try:
                        self.sds_tab.refresh_vs_status()
                    except Exception:
                        pass
        finally:
            # keep polling
            self.after(300, self._check_tab_change)

    def _apply_ui_scaling(
        self,
        initial: bool = False,
        *,
        width: int | None = None,
        height: int | None = None,
    ) -> None:
        """Apply CustomTkinter scaling based on screen/window size ratio.

        This adjusts both widget sizes and text for better fit across resolutions.
        """
        try:
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()
            # Prefer provided width/height (e.g., current window), else screen-based
            target_w = width or int(screen_w * 0.85)
            target_h = height or int(screen_h * 0.85)

            # Base reference size (tuned for comfortable default)
            base_w, base_h = 1400, 800

            # Mode override mapping (fixed scales)
            mode = (self.settings.ui.scale_mode or "auto").lower()
            fixed_map = {
                "compact": 0.90,
                "comfortable": 1.00,
                "large": 1.25,
            }

            if mode != "auto" and mode in fixed_map:
                scale = fixed_map[mode]
            else:
                scale = min(target_w / base_w, target_h / base_h)
                # Clamp to range from settings (wider defaults)
                smin = float(getattr(self.settings.ui, "scale_min", 0.75) or 0.75)
                smax = float(getattr(self.settings.ui, "scale_max", 1.75) or 1.75)
                if smin > smax:
                    smin, smax = smax, smin
                scale = max(smin, min(scale, smax))

            # Apply global scaling
            ctk.set_widget_scaling(scale)
            ctk.set_window_scaling(scale)
            try:
                # Ensure native Tk dialogs (file pickers, message boxes) follow the same scaling
                self.tk.call("tk", "scaling", scale)
            except Exception:
                pass

            # Update commonly used font sizes for new widgets created afterwards
            def _sz(base: int) -> int:
                return max(10, int(round(base * scale)))

            self.button_font = ("Segoe UI", _sz(12), "bold")
            self.button_font_sm = ("Segoe UI", _sz(11), "bold")

            if initial:
                logger.info(
                    "UI scaling applied: %.2fx (mode=%s)", scale, mode or "auto"
                )
        except Exception as exc:
            logger.debug("Failed to apply UI scaling: %s", exc)

    def _on_window_resize(self, event) -> None:
        """Recompute scaling on significant window size changes."""
        try:
            # Only handle top-level window resize events
            if event.widget is not self:
                return
            w, h = event.width, event.height
            prev_w, prev_h = getattr(self, "_last_size", (w, h))
            # Avoid division by zero
            prev_w = max(prev_w, 1)
            prev_h = max(prev_h, 1)
            dw = abs(w - prev_w) / prev_w
            dh = abs(h - prev_h) / prev_h

            now = time.time()
            # Update scaling only on notable change and throttle updates
            if (dw > 0.15 or dh > 0.15) and (now - getattr(self, "_last_scale_update", 0) > 0.5):
                self._apply_ui_scaling(initial=False, width=w, height=h)
                self._last_scale_update = now
                self._last_size = (w, h)
        except Exception:
            pass

    def _setup_header_bar(self) -> None:
        """Top header with app title and close button."""
        self.header_bar = ctk.CTkFrame(
            self.main_frame,
            fg_color=self.colors["header"],
            height=40,
            corner_radius=6,
        )
        self.header_bar.pack(fill="x", side="top", pady=(0, 8))

        title_label = ctk.CTkLabel(
            self.header_bar,
            text=get_text("app.title"),
            font=("Segoe UI", 14, "bold"),
            text_color=self.colors["text"],
        )
        title_label.pack(side="left", padx=12, pady=6)

        # Close button (X) on the right
        close_btn = ctk.CTkButton(
            self.header_bar,
            text="✕",
            command=self._on_close,
            fg_color="transparent",
            hover_color=self.colors.get("error", "#d9534f"),
            text_color=self.colors["text"],
            corner_radius=4,
            font=("Segoe UI", 16, "bold"),
            width=32,
            height=32,
        )
        close_btn.pack(side="right", padx=8, pady=4)

    def _apply_responsive_geometry(self) -> None:
        """Center window on screen with fixed size."""
        try:
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()

            # Use configured size (no automatic sizing)
            target_w = int(self.settings.ui.window_width)
            target_h = int(self.settings.ui.window_height)

            # Center on screen
            x = max(0, (screen_w - target_w) // 2)
            y = max(0, (screen_h - target_h) // 2)

            self.geometry(f"{target_w}x{target_h}+{x}+{y}")
        except Exception:
            # Fallback to configured size
            self.geometry(
                f"{self.settings.ui.window_width}x{self.settings.ui.window_height}"
            )

    def _setup_rag_tab(self) -> None:
        """Setup RAG Knowledge Base tab."""
        rag_tab_frame = self.tab_view.tab(get_text("tab.rag"))
        self.rag_tab = RagTab(rag_tab_frame, app=self)
        self.rag_tab.pack(fill="both", expand=True)

    def _setup_sources_tab(self) -> None:
        """Setup the knowledge sources tab."""
        sources_tab_frame = self.tab_view.tab(get_text("tab.sources"))
        self.sources_tab = SourcesTab(sources_tab_frame, app=self)
        self.sources_tab.pack(fill="both", expand=True)

    def _setup_sds_tab(self) -> None:
        """Setup SDS Processor tab."""
        sds_tab_frame = self.tab_view.tab(get_text("tab.sds"))
        self.sds_tab = SdsTab(sds_tab_frame, app=self)
        self.sds_tab.pack(fill="both", expand=True)

    def _setup_records_tab(self) -> None:
        """Setup Records Viewer tab."""
        records_tab_frame = self.tab_view.tab("Records")
        self.records_tab = RecordsTab(records_tab_frame, app=self)
        self.records_tab.pack(fill="both", expand=True)

    def _setup_review_tab(self) -> None:
        """Setup Review tab."""
        review_tab_frame = self.tab_view.tab("Review")
        self.review_tab = ReviewTab(review_tab_frame, app=self)
        self.review_tab.pack(fill="both", expand=True)

    def _setup_quality_tab(self) -> None:
        """Setup Quality Dashboard tab."""
        from .tabs import QualityTab
        quality_tab_frame = self.tab_view.tab("Quality")
        self.quality_tab = QualityTab(quality_tab_frame, app=self)
        self.quality_tab.pack(fill="both", expand=True)

    def _setup_backup_tab(self) -> None:
        """Setup Backup tab."""
        backup_tab_frame = self.tab_view.tab("Backup")
        self.backup_tab = BackupTab(backup_tab_frame, app=self)
        self.backup_tab.pack(fill="both", expand=True)

    def _setup_status_tab(self) -> None:
        """Setup Status/Metrics tab."""
        status_tab_frame = self.tab_view.tab("Status")
        self.status_tab = StatusTab(status_tab_frame, app=self)
        self.status_tab.pack(fill="both", expand=True)

    def _setup_chat_tab(self) -> None:
        """Setup Chat tab."""
        chat_tab_frame = self.tab_view.tab("Chat")
        self.chat_tab = ChatTab(chat_tab_frame, app=self)
        self.chat_tab.pack(fill="both", expand=True)

    def _setup_status_bar(self) -> None:
        """Setup bottom status bar."""
        self.status_bar = ctk.CTkFrame(
            self.main_frame,
            fg_color=self.colors["header"],
            height=32,
            corner_radius=0,
        )
        self.status_bar.pack(fill="x", side="bottom", pady=(8, 0))

        # Status text
        self.status_text = ctk.CTkLabel(
            self.status_bar,
            text=get_text("app.ready"),
            font=("JetBrains Mono", 12),
            text_color=self.colors["text"],
        )
        self.status_text.pack(side="left", padx=12, pady=6)

        # Version
        version_label = ctk.CTkLabel(
            self.status_bar,
            text=f"{get_text('app.version')} 1.0.0",
            font=("JetBrains Mono", 11),
            text_color=self.colors["subtext"],
        )
        version_label.pack(side="right", padx=12, pady=6)

    def _update_status(self, message: str, level: str = "info") -> None:
        """Update the status bar text and log the message."""
        color_map = {
            "error": self.colors.get("error", "#ff5555"),
            "warning": self.colors.get("warning", "#f1fa8c"),
            "success": self.colors.get("success", "#50fa7b"),
            "info": self.colors.get("text", "#ffffff"),
        }

        try:
            if hasattr(self, "status_text"):
                color = color_map.get(level, self.colors.get("text", "#ffffff"))
                self.status_text.configure(text=message, text_color=color)
        except Exception as exc:
            logger.debug("Failed to update status label: %s", exc)

        log_fn = {
            "error": logger.error,
            "warning": logger.warning,
            "success": logger.info,
            "info": logger.info,
        }.get(level, logger.info)
        log_fn(message)

    # === Event Handlers ===

    # === Knowledge Source Events ===

    def _on_ingest_local_files(self) -> None:
        """Prompt user for files and ingest them into the knowledge base."""
        files = filedialog.askopenfilenames(
            title="Select knowledge files",
            parent=self,
            filetypes=[
                (
                    "Supported files",
                    " ".join(f"*{ext}" for ext in SUPPORTED_FORMATS.keys()),
                )
            ],
        )
        if files:
            self.sources_status_var.set(f"Ingesting {len(files)} files...")
            thread = threading.Thread(target=self._ingest_files_async, args=(files,))
            thread.daemon = True
            thread.start()

    def _on_ingest_local_folder(self) -> None:
        """Ingest all supported files from a folder."""
        folder = filedialog.askdirectory(
            title="Select folder with knowledge files", parent=self
        )
        if not folder:
            return

        folder_path = Path(folder)
        files: list[Path] = []
        for suffix in SUPPORTED_FORMATS.keys():
            files.extend(folder_path.rglob(f"*{suffix}"))

        if not files:
            messagebox.showinfo(
                "No Files", "No supported files found in the selected folder."
            )
            return

        self.sources_status_var.set(f"Ingesting {len(files)} files from folder...")
        thread = threading.Thread(
            target=self._ingest_files_async, args=(tuple(str(f) for f in files),)
        )
        thread.daemon = True
        thread.start()

    def _on_ingest_snapshot_file(self) -> None:
        """Ingest a Bright Data snapshot file."""
        file_path = filedialog.askopenfilename(
            title="Select Bright Data snapshot",
            parent=self,
            filetypes=[("Snapshot files", "*.json *.txt"), ("All files", "*.*")],
        )
        if file_path:
            self.sources_status_var.set("Loading snapshot...")
            thread = threading.Thread(
                target=self._ingest_snapshot_async, args=(file_path,)
            )
            thread.daemon = True
            thread.start()

    def _on_sources_add_url(self) -> None:
        """Handle ingestion of a URL from the sources tab."""
        url = self.sources_url_entry.get().strip()
        if not url:
            messagebox.showwarning("Missing URL", "Enter a URL to fetch.")
            return

        self.sources_status_var.set(f"Fetching {url}...")
        thread = threading.Thread(target=self._sources_add_url_async, args=(url,))
        thread.daemon = True
        thread.start()

    def _on_sources_search(self) -> None:
        """Handle Google search ingestion."""
        query = self.sources_search_entry.get().strip()
        if not query:
            messagebox.showwarning("Missing Query", "Enter a search query.")
            return

        if not self.ingestion.search_client:
            messagebox.showwarning(
                "Search Not Configured",
                "Set GOOGLE_API_KEY and GOOGLE_CSE_ID in your .env file to enable Google search ingestion.",
            )
            return

        try:
            max_results = int(self.sources_search_results_entry.get().strip() or "5")
        except ValueError:
            max_results = 5

        self.sources_status_var.set(f"Searching for '{query}'...")
        thread = threading.Thread(
            target=self._sources_search_async, args=(query, max_results)
        )
        thread.daemon = True
        thread.start()

    def _on_simple_urls(self) -> None:
        """Handle batch simple URL ingestion."""
        urls = [
            line.strip()
            for line in self.simple_urls_text.get("1.0", END).splitlines()
            if line.strip()
        ]
        if not urls:
            messagebox.showwarning("No URLs", "Enter one or more URLs.")
            return
        self.sources_status_var.set(f"Fetching {len(urls)} URLs...")
        thread = threading.Thread(target=self._simple_urls_async, args=(urls,))
        thread.daemon = True
        thread.start()

    def _on_bright_trigger(self) -> None:
        """Handle Bright Data crawl trigger."""
        if not (
            self.settings.ingestion.brightdata_api_key
            and self.settings.ingestion.brightdata_dataset_id
        ):
            messagebox.showwarning(
                "Bright Data Not Configured",
                "Set BRIGHTDATA_API_KEY and BRIGHTDATA_DATASET_ID in .env to trigger a crawl.",
            )
            return
        try:
            keywords = self._parse_bright_keywords()
        except ValueError as exc:
            messagebox.showwarning("Invalid Keywords", str(exc))
            return

        if not keywords:
            messagebox.showwarning("No Keywords", "Enter at least one keyword.")
            return

        self.sources_status_var.set("Triggering Bright Data crawl...")
        thread = threading.Thread(target=self._bright_trigger_async, args=(keywords,))
        thread.daemon = True
        thread.start()

    def _on_bright_check(self) -> None:
        """Check Bright Data snapshot status."""
        if not (
            self.settings.ingestion.brightdata_api_key
            and self.settings.ingestion.brightdata_dataset_id
        ):
            messagebox.showwarning(
                "Bright Data Not Configured",
                "Set BRIGHTDATA_API_KEY and BRIGHTDATA_DATASET_ID in .env to check snapshot status.",
            )
            return
        self.sources_status_var.set("Checking snapshot status...")
        thread = threading.Thread(target=self._bright_check_async)
        thread.daemon = True
        thread.start()

    def _on_bright_download(self) -> None:
        """Download latest snapshot and ingest."""
        if not (
            self.settings.ingestion.brightdata_api_key
            and self.settings.ingestion.brightdata_dataset_id
        ):
            messagebox.showwarning(
                "Bright Data Not Configured",
                "Set BRIGHTDATA_API_KEY and BRIGHTDATA_DATASET_ID in .env to download snapshots.",
            )
            return
        self.sources_status_var.set("Downloading snapshot...")
        thread = threading.Thread(target=self._bright_download_async)
        thread.daemon = True
        thread.start()

    def _on_craw4ai_run(self) -> None:
        """Run Craw4AI job and ingest results."""
        seeds = [
            line.strip()
            for line in self.craw_seeds_text.get("1.0", END).splitlines()
            if line.strip()
        ]
        if not seeds:
            messagebox.showwarning("No Seeds", "Enter one or more seed URLs.")
            return
        if not self.settings.ingestion.craw4ai_command:
            messagebox.showwarning(
                "Craw4AI Not Configured",
                "Set CRAW4AI_COMMAND in your .env (e.g., 'crawl4ai run --mode {mode} --input {input_file} --output {output_file}').",
            )
            return
        self.sources_status_var.set("Running Craw4AI...")
        thread = threading.Thread(target=self._craw4ai_run_async, args=(seeds,))
        thread.daemon = True
        thread.start()

    # === Knowledge ingestion workers ===

    def _ingest_files_async(self, files: tuple[str, ...]) -> None:
        summary = self.ingestion.ingest_local_files([Path(f) for f in files])
        self.after(0, lambda: self._handle_ingestion_summary(summary))

    def _ingest_snapshot_async(self, file_path: str) -> None:
        summary = self.ingestion.ingest_snapshot_file(Path(file_path))
        self.after(0, lambda: self._handle_ingestion_summary(summary))

    def _sources_add_url_async(self, url: str) -> None:
        summary = self.ingestion.ingest_url(url)
        self.after(0, lambda: self._handle_ingestion_summary(summary))

    def _sources_search_async(self, query: str, max_results: int) -> None:
        summary = self.ingestion.ingest_web_search(query, max_results=max_results)
        self.after(0, lambda: self._handle_ingestion_summary(summary))

    def _simple_urls_async(self, urls: list[str]) -> None:
        summary = self.ingestion.ingest_simple_urls(urls)
        self.after(0, lambda: self._handle_ingestion_summary(summary))

    def _bright_trigger_async(self, keywords: list[tuple[str, int]]) -> None:
        try:
            snapshot_id = self.ingestion.trigger_brightdata_keywords(keywords)
            msg = f"Bright Data snapshot triggered: {snapshot_id}"
            self.after(0, lambda: self.sources_status_var.set(msg))
            self.after(0, lambda: messagebox.showinfo("Snapshot Triggered", msg))
            self.after(0, self._update_snapshot_label)
        except Exception as exc:
            logger.error("Bright Data trigger failed: %s", exc)
            err = str(exc)
            self.after(0, lambda: self.sources_status_var.set(err))
            self.after(0, lambda e=err: messagebox.showerror("Bright Data Error", e))

    def _bright_check_async(self) -> None:
        try:
            status = self.ingestion.check_brightdata_status()
            msg = f"Snapshot status: {status.get('status')}"
            self.after(0, lambda: self.sources_status_var.set(msg))
            detail = json.dumps(status, indent=2, ensure_ascii=False)
            self.after(0, lambda: messagebox.showinfo("Snapshot Status", detail))
        except Exception as exc:
            logger.error("Bright Data status check failed: %s", exc)
            err = str(exc)
            self.after(0, lambda: self.sources_status_var.set(err))
            self.after(0, lambda e=err: messagebox.showerror("Bright Data Error", e))

    def _bright_download_async(self) -> None:
        try:
            summary = self.ingestion.download_and_ingest_snapshot()
            self.after(0, lambda: self._handle_ingestion_summary(summary))
            self.after(0, self._update_snapshot_label)
        except Exception as exc:
            logger.error("Bright Data download failed: %s", exc)
            err = str(exc)
            self.after(0, lambda: self.sources_status_var.set(err))
            self.after(0, lambda e=err: messagebox.showerror("Bright Data Error", e))

    def _craw4ai_run_async(self, seeds: list[str]) -> None:
        try:
            summary = self.ingestion.run_and_ingest_craw4ai_job(seeds)
            self.after(0, lambda: self._handle_ingestion_summary(summary))
        except Exception as exc:
            logger.error("Craw4AI run failed: %s", exc)
            err = str(exc)
            self.after(0, lambda: self.sources_status_var.set(err))
            self.after(0, lambda e=err: messagebox.showerror("Craw4AI Error", e))

    def _parse_bright_keywords(self) -> list[tuple[str, int]]:
        """Parse the keywords textbox into (keyword, pages) tuples."""
        text = self.bright_keywords_text.get("1.0", END).strip()
        default_pages = self._get_default_pages()
        keywords: list[tuple[str, int]] = []
        for line in text.splitlines():
            cleaned = line.strip()
            if not cleaned:
                continue
            if ":" in cleaned:
                keyword, pages_str = cleaned.split(":", 1)
                try:
                    pages = max(1, int(pages_str.strip()))
                except ValueError:
                    raise ValueError(f"Invalid page count in '{cleaned}'")
                keywords.append((keyword.strip(), pages))
            else:
                keywords.append((cleaned, default_pages))
        return keywords

    def _get_default_pages(self) -> int:
        try:
            return max(1, int(self.bright_pages_entry.get().strip() or "1"))
        except (ValueError, AttributeError):
            return 1

    def _handle_ingestion_summary(self, summary: IngestionSummary) -> None:
        """Update UI after an ingestion completes."""
        msg = summary.to_message()
        self.status_text.configure(text=msg)
        self.sources_status_var.set(msg)

        details = msg
        if summary.errors:
            details += "\nErrors:\n- " + "\n- ".join(summary.errors)
        if summary.skipped:
            details += "\nSkipped:\n- " + "\n- ".join(summary.skipped[:5])

        messagebox.showinfo("Ingestion Complete", details)
        self._refresh_rag_stats()
        self._refresh_sources_list()

    def _on_select_folder(self) -> None:
        """Handle select folder button."""
        folder = filedialog.askdirectory(title="Select SDS folder", parent=self)
        if folder:
            logger.info("Selected folder: %s", folder)
            self.selected_sds_folder = folder

            # Scan and list SDS files
            sds_files = list(Path(folder).rglob("*.pdf")) + list(
                Path(folder).rglob("*.txt")
            )
            if not sds_files:
                self.status_text.configure(text=f"No SDS files found in {folder}")
                self.sds_progress_text.configure(text="No files to process")
                return

            file_count = len(sds_files)
            self.status_text.configure(
                text=f"Found {file_count} SDS files - Ready to process"
            )
            self.sds_progress_text.configure(text=f"Ready: {file_count} files")
            self._reset_sds_file_table(sds_files)

    def _on_process(self) -> None:
        """Handle process button."""
        if not hasattr(self, "selected_sds_folder"):
            messagebox.showwarning("No Folder Selected", "Please select a folder first")
            return

        stats = self.db.get_statistics()
        if stats.get("rag_chunks", 0) == 0:
            messagebox.showwarning(
                "Knowledge Base Empty",
                "Please ingest knowledge sources (files, URLs, or snapshots) before processing SDS files.",
            )
            return

        logger.info("Starting SDS processing")
        self.status_text.configure(text="Processing SDS documents...")
        self.sds_progress.set(0)
        self.sds_progress_text.configure(text="Processing (0%)")

        # Start async processing in background thread
        mode = getattr(self, "process_mode_var", None)
        mode_val = mode.get() if mode else "standard"

        if mode_val == "rag_script":
            thread = threading.Thread(
                target=self._process_sds_script_async, args=(self.selected_sds_folder,)
            )
        else:
            use_rag = self.use_rag_var.get()
            thread = threading.Thread(
                target=self._process_sds_async, args=(self.selected_sds_folder, use_rag)
            )

        thread.daemon = True
        thread.start()

    def _reset_sds_file_table(self, sds_files: list[Path]) -> None:
        """Prepare the SDS file status table with pending state."""
        self.sds_file_rows = {f.name: ("Pending", "") for f in sds_files}
        self._render_sds_file_table()

    def _set_sds_file_status(self, filename: str, status: str, chemical_name: str = "") -> None:
        """Update a single file status in the SDS table.

        Args:
            filename: Name of the file
            status: Status string (Processing, Success, Failed, etc.)
            chemical_name: Identified chemical name from the document
        """
        if not hasattr(self, "sds_file_rows"):
            self.sds_file_rows = {}
        # Keep existing chemical name if not provided
        existing_name = self.sds_file_rows.get(filename, ("", ""))[1] if filename in self.sds_file_rows else ""
        chemical_name = chemical_name or existing_name
        self.sds_file_rows[filename] = (status, chemical_name)
        self._render_sds_file_table()

    def _render_sds_file_table(self) -> None:
        """Render the SDS file status table in the UI."""
        if not hasattr(self, "sds_files_table"):
            return

        try:
            if not self.sds_file_rows:
                self.sds_files_table.set_data(
                    ["Arquivo", "Composto Químico", "Status"],
                    [("Nenhum arquivo", "", "")]
                )
                return
            rows = [(name, chemical_name, status) for name, (status, chemical_name) in self.sds_file_rows.items()]
            self.sds_files_table.set_data(
                ["Arquivo", "Composto Químico", "Status"], rows, accent_color=self.colors["accent"]
            )
        except Exception as exc:  # pragma: no cover - UI best effort
            logger.debug("Failed to render SDS file table: %s", exc)

    def _process_sds_async(self, folder: str, use_rag: bool) -> None:
        """Process SDS documents asynchronously.

        Args:
            folder: Path to SDS folder
            use_rag: Whether to use RAG enrichment
        """
        from ..sds.processor import SDSProcessor

        try:
            self.after(
                0, lambda: self.status_text.configure(text="Initializing processor...")
            )

            # Get SDS files
            folder_path = Path(folder)
            sds_files = sorted(
                list(folder_path.rglob("*.pdf")) + list(folder_path.rglob("*.txt"))
            )

            if not sds_files:
                error_msg = "No SDS files found in selected folder"
                self.after(0, lambda: self.status_text.configure(text=error_msg))
                self.after(0, lambda: messagebox.showwarning("No Files", error_msg))
                return

            total_files = len(sds_files)
            logger.info("Processing %d SDS files", total_files)

            # Initialize processor
            processor = SDSProcessor()

            successful = 0
            failed = 0
            dangerous_count = 0

            # Process each file
            for i, file_path in enumerate(sds_files, 1):
                try:
                    # Update progress
                    progress = (i - 1) / total_files
                    status_text = f"Processing: {file_path.name} ({i}/{total_files})"
                    progress_text = f"Processing ({int(progress * 100)}%)"

                    self.after(0, lambda p=progress: self.sds_progress.set(p))
                    self.after(
                        0, lambda s=status_text: self.status_text.configure(text=s)
                    )
                    self.after(
                        0,
                        lambda p=progress_text: self.sds_progress_text.configure(
                            text=p
                        ),
                    )
                    self.after(
                        0,
                        lambda n=file_path.name: self._set_sds_file_status(
                            n, "Processing"
                        ),
                    )

                    # Process document
                    result = processor.process(file_path, use_rag=use_rag)

                    # Extract chemical name from extractions
                    chemical_name = ""
                    if result.extractions and "product_name" in result.extractions:
                        product_info = result.extractions.get("product_name", {})
                        chemical_name = product_info.get("value", "") or product_info.get("normalized_value", "")

                    if result.status == "success":
                        successful += 1
                        if result.is_dangerous:
                            dangerous_count += 1
                        self.after(
                            0,
                            lambda n=file_path.name, c=chemical_name: self._set_sds_file_status(
                                n, "Success", c
                            ),
                        )
                    else:
                        failed += 1
                        self.after(
                            0,
                            lambda n=file_path.name, c=chemical_name: self._set_sds_file_status(
                                n, "Failed", c
                            ),
                        )

                    logger.info(
                        "Processed %s: %s (confidence: %.0f%%)",
                        file_path.name,
                        result.status,
                        result.avg_confidence * 100,
                    )

                except Exception as e:
                    failed += 1
                    self.after(
                        0,
                        lambda n=file_path.name: self._set_sds_file_status(n, "Failed"),
                    )
                    logger.error("Failed to process %s: %s", file_path.name, e)
                    continue

            # Final status
            progress = 1.0
            status_msg = f"Complete: {successful} successful, {failed} failed, {dangerous_count} dangerous"
            progress_msg = "Complete (100%)"

            self.after(0, lambda p=progress: self.sds_progress.set(p))
            self.after(0, lambda s=status_msg: self.status_text.configure(text=s))
            self.after(
                0, lambda p=progress_msg: self.sds_progress_text.configure(text=p)
            )

            # Show results dialog
            result_text = (
                f"Processing Complete\n\n"
                f"Total Files: {total_files}\n"
                f"Successful: {successful}\n"
                f"Failed: {failed}\n"
                f"Dangerous: {dangerous_count}"
            )
            self.after(
                0, lambda: messagebox.showinfo("Processing Complete", result_text)
            )

            logger.info(
                "SDS batch processing complete: %d successful, %d failed, %d dangerous",
                successful,
                failed,
                dangerous_count,
            )

        except Exception as e:
            error_msg = f"Processing error: {str(e)}"
            logger.error(error_msg)
            self.after(0, lambda: self.status_text.configure(text=error_msg))
            self.after(0, lambda: messagebox.showerror("Processing Error", error_msg))

    def _process_sds_script_async(self, folder: str) -> None:
        """Process SDS documents using the RAG script asynchronously.

        Args:
            folder: Path to SDS folder
        """
        import subprocess
        import sys

        try:
            self.after(
                0, lambda: self.status_text.configure(text="Initializing RAG script...")
            )
            self.after(0, lambda: self.sds_progress.set(0))
            self.after(
                0, lambda: self.sds_progress_text.configure(text="Starting script...")
            )

            cmd = [
                sys.executable,
                "scripts/rag_sds_processor.py",
                "--input",
                folder,
            ]

            # Run script
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=Path.cwd(),
            )

            # Read output
            stdout, stderr = process.communicate()

            if process.returncode == 0:
                self.after(
                    0, lambda: self.status_text.configure(text="Processing complete")
                )
                self.after(0, lambda: self.sds_progress.set(1.0))
                self.after(
                    0, lambda: self.sds_progress_text.configure(text="Complete (100%)")
                )

                msg = f"Script Output:\n{stdout}"
                self.after(0, lambda: messagebox.showinfo("Processing Complete", msg))
            else:
                error_msg = f"Script failed:\n{stderr}"
                self.after(
                    0, lambda: self.status_text.configure(text="Processing failed")
                )
                self.after(0, lambda: messagebox.showerror("Error", error_msg))

            logger.info("RAG script finished with code %d", process.returncode)

        except Exception as e:
            error_msg = f"Script execution error: {str(e)}"
            logger.error(error_msg)
            self.after(0, lambda: self.status_text.configure(text=error_msg))
            self.after(0, lambda: messagebox.showerror("Error", error_msg))

    def _on_export(self) -> None:
        """Handle export button."""
        folder = filedialog.askdirectory(title="Select export location", parent=self)
        if folder:
            logger.info("Exporting to: %s", folder)
            self.status_text.configure(text=f"Exporting to: {folder}")
            # Start async export in background thread
            thread = threading.Thread(target=self._export_async, args=(folder,))
            thread.daemon = True
            thread.start()

    def _export_async(self, output_dir: str) -> None:
        """Export matrices asynchronously.

        Args:
            output_dir: Directory to export to
        """
        from ..matrix.builder import MatrixBuilder
        from ..matrix.exporter import MatrixExporter

        try:
            self.after(
                0, lambda: self.status_text.configure(text="Building matrices...")
            )

            # Build matrices
            builder = MatrixBuilder()
            incomp_matrix = builder.build_incompatibility_matrix()
            hazard_matrix = builder.build_hazard_matrix()
            stats = builder.get_matrix_statistics()
            dangerous_chems = builder.get_dangerous_chemicals()
            processing_summary = builder.get_processing_summary()

            if incomp_matrix.empty and hazard_matrix.empty:
                error_msg = (
                    "No data available for export. Please process some SDS files first."
                )
                self.after(0, lambda: self.status_text.configure(text=error_msg))
                self.after(0, lambda: messagebox.showwarning("No Data", error_msg))
                return

            self.after(
                0, lambda: self.status_text.configure(text="Exporting matrices...")
            )

            # Export using MatrixExporter
            exporter = MatrixExporter()

            # Prepare matrices dict
            matrices = {}
            if not incomp_matrix.empty:
                matrices["Matriz_Incompatibilidades"] = incomp_matrix
            if not hazard_matrix.empty:
                matrices["Matriz_Classes_de_Perigo"] = hazard_matrix

            # Prepare statistics
            stats_dict = {
                "Total de Produtos": stats.total_chemicals,
                "Pares de Incompatibilidade": stats.incompatibility_pairs,
                "Distribuicao de Perigos": stats.hazard_distribution,
                "Status de Processamento": stats.processing_status,
                "Media de Completude (%)": f"{stats.avg_completeness * 100:.1f}%",
                "Media de Confianca (%)": f"{stats.avg_confidence * 100:.1f}%",
                "Resumo de Processamento": processing_summary,
            }

            # Export report
            export_results = exporter.export_report(
                matrices=matrices,
                statistics=stats_dict,
                output_dir=output_dir,
                format_type="all",
            )

            # Export dangerous chemicals if available
            if dangerous_chems:
                dangerous_path = Path(output_dir) / "dangerous_chemicals.xlsx"
                exporter.export_dangerous_chemicals_report(
                    dangerous_chems, dangerous_path
                )
                export_results["dangerous_chemicals"] = True

            # Summary
            status_msg = f"Export complete: {len(export_results)} files exported"
            self.after(0, lambda: self.status_text.configure(text=status_msg))

            logger.info("Export complete with results: %s", export_results)
            self.after(
                0,
                lambda: messagebox.showinfo(
                    "Export Complete",
                    f"Successfully exported {len(export_results)} files to:\n{output_dir}",
                ),
            )

        except Exception as e:
            error_msg = f"Export error: {str(e)}"
            logger.error(error_msg)
            self.after(0, lambda: self.status_text.configure(text=error_msg))
            self.after(0, lambda: messagebox.showerror("Export Error", error_msg))

    def _on_build_matrix(self) -> None:
        """Handle build matrix button."""
        logger.info("Building chemical compatibility matrix")
        self.status_text.configure(text="Building compatibility matrix...")
        # Start async matrix building in background thread
        thread = threading.Thread(target=self._build_matrix_async)
        thread.daemon = True
        thread.start()

    def _build_matrix_async(self) -> None:
        """Build and display chemical compatibility matrix asynchronously."""
        from ..matrix.builder import MatrixBuilder

        try:
            self.after(
                0, lambda: self.status_text.configure(text="Building matrices...")
            )

            # Build matrices and statistics
            builder = MatrixBuilder()
            incomp_matrix = builder.build_incompatibility_matrix()
            hazard_matrix = builder.build_hazard_matrix()
            stats = builder.get_matrix_statistics()
            dangerous_chems = builder.get_dangerous_chemicals()

            if incomp_matrix.empty and hazard_matrix.empty:
                error_msg = "No data available. Please process some SDS files first."
                self.after(0, lambda: self.status_text.configure(text=error_msg))
                self.after(0, lambda: messagebox.showwarning("No Data", error_msg))
                return

            self.after(0, lambda: self.status_text.configure(text="Building complete"))

            # Show results in a new window
            self.after(
                0,
                lambda: self._show_matrix_results(
                    incomp_matrix, hazard_matrix, stats, dangerous_chems
                ),
            )

        except Exception as e:
            error_msg = f"Matrix building error: {str(e)}"
            logger.error(error_msg)
            self.after(0, lambda: self.status_text.configure(text=error_msg))
            self.after(0, lambda: messagebox.showerror("Build Error", error_msg))

    def _show_matrix_results(
        self,
        incomp_matrix,
        hazard_matrix,
        stats,
        dangerous_chems,
    ) -> None:
        """Show matrix results in a dedicated window.

        Args:
            incomp_matrix: Incompatibility matrix DataFrame
            hazard_matrix: Hazard matrix DataFrame
            stats: Matrix statistics
            dangerous_chems: List of dangerous chemicals
        """
        # Create results window
        results_window = ctk.CTkToplevel(self)
        results_window.title("Resultados da Matriz de Compatibilidade")
        results_window.geometry("900x600")

        # Create main frame with tabs
        tab_view = ctk.CTkTabview(
            results_window,
            fg_color=self.colors["bg"],
            segmented_button_fg_color=self.colors["surface"],
            segmented_button_selected_color=self.colors["accent"],
        )
        tab_view.pack(fill="both", expand=True, padx=10, pady=10)

        # === Statistics Tab ===
        tab_view.add("Statistics")
        stats_tab = tab_view.tab("Statistics")

        stats_frame = ctk.CTkFrame(
            stats_tab, fg_color=self.colors["surface"], corner_radius=10
        )
        stats_frame.pack(fill="both", expand=True, padx=10, pady=10)

        stats_text = (
            f"Total de Produtos: {stats.total_chemicals}\n"
            f"Pares de Incompatibilidade: {stats.incompatibility_pairs}\n"
            f"Média de Completude: {stats.avg_completeness * 100:.1f}%\n"
            f"Média de Confiança: {stats.avg_confidence * 100:.1f}%\n\n"
            f"Distribuição de Perigos:\n"
        )

        for hazard, count in stats.hazard_distribution.items():
            stats_text += f"  {hazard}: {count}\n"

        stats_text += "\nStatus de Processamento:\n"
        for status, count in stats.processing_status.items():
            stats_text += f"  {status}: {count}\n"

        stats_label = ctk.CTkLabel(
            stats_frame,
            text=stats_text,
            font=("JetBrains Mono", 11),
            text_color=self.colors["text"],
            justify="left",
        )
        stats_label.pack(fill="both", expand=True, padx=10, pady=10)

        # === Incompatibility Matrix Tab ===
        if not incomp_matrix.empty:
            tab_view.add("Incompatibilidades")
            incomp_tab = tab_view.tab("Incompatibilidades")

            incomp_frame = ctk.CTkFrame(
                incomp_tab, fg_color=self.colors["surface"], corner_radius=10
            )
            incomp_frame.pack(fill="both", expand=True, padx=10, pady=10)

            # Create text widget to display matrix
            incomp_text = ctk.CTkTextbox(
                incomp_frame,
                fg_color=self.colors["input"],
                text_color=self.colors["text"],
                font=("JetBrains Mono", 11),
                border_color=self.colors["accent"],
                border_width=1,
                wrap="none",
            )
            incomp_text.pack(fill="both", expand=True)

            # Format matrix as table
            matrix_str = self._format_dataframe_for_display(incomp_matrix)
            incomp_text.insert("1.0", matrix_str)
            incomp_text.configure(state="disabled")

        # === Hazard Matrix Tab ===
        if not hazard_matrix.empty:
            tab_view.add("Classes de Perigo")
            hazard_tab = tab_view.tab("Classes de Perigo")

            hazard_frame = ctk.CTkFrame(
                hazard_tab, fg_color=self.colors["surface"], corner_radius=10
            )
            hazard_frame.pack(fill="both", expand=True, padx=10, pady=10)

            # Create text widget to display matrix
            hazard_text = ctk.CTkTextbox(
                hazard_frame,
                fg_color=self.colors["input"],
                text_color=self.colors["text"],
                font=("JetBrains Mono", 11),
                border_color=self.colors["accent"],
                border_width=1,
                wrap="none",
            )
            hazard_text.pack(fill="both", expand=True)

            # Format matrix as table
            matrix_str = self._format_dataframe_for_display(hazard_matrix)
            hazard_text.insert("1.0", matrix_str)
            hazard_text.configure(state="disabled")

        # === Dangerous Chemicals Tab ===
        if dangerous_chems:
            tab_view.add("Perigosos")
            dangerous_tab = tab_view.tab("Perigosos")

            dangerous_frame = ctk.CTkFrame(
                dangerous_tab, fg_color=self.colors["surface"], corner_radius=10
            )
            dangerous_frame.pack(fill="both", expand=True, padx=10, pady=10)

            # Create text widget to display dangerous chemicals
            dangerous_text = ctk.CTkTextbox(
                dangerous_frame,
                fg_color=self.colors["input"],
                text_color=self.colors["text"],
                border_color=self.colors["accent"],
                border_width=1,
            )
            dangerous_text.pack(fill="both", expand=True)

            # Format dangerous chemicals
            dangerous_str = "QUÍMICOS PERIGOSOS:\n" + "=" * 80 + "\n\n"
            for i, chem in enumerate(dangerous_chems, 1):
                dangerous_str += (
                    f"{i}. {chem.get('product_name', 'Desconhecido')}\n"
                    f"   Classe de Perigo: {chem.get('hazard_class', 'Desconhecida')}\n"
                    f"   Número ONU: {chem.get('un_number', 'Desconhecido')}\n"
                    f"   Incompatibilidades: {chem.get('incompatibilities', 'Nenhuma listada')}\n\n"
                )

            dangerous_text.insert("1.0", dangerous_str)
            dangerous_text.configure(state="disabled")

        # === Bottom button frame ===
        btn_frame = ctk.CTkFrame(results_window, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=10)

        from .components.app_button import AppButton
        AppButton(
            btn_frame,
            text="Close",
            command=results_window.destroy,
            fg_color=self.colors["primary"],
            text_color=self.colors["header"],
            hover_color=self.colors["button_hover"],
            width=160,
        ).pack(side="left", padx=5)

        AppButton(
            btn_frame,
            text="Export Results",
            command=lambda: self._on_export(),
            fg_color=self.colors["accent"],
            text_color=self.colors["header"],
            hover_color=self.colors["button_hover"],
            width=180,
        ).pack(side="left", padx=5)

    def _format_dataframe_for_display(self, df) -> str:
        """Format a DataFrame for text display.

        Args:
            df: DataFrame to format

        Returns:
            Formatted string representation
        """
        try:
            # Limit extreme widths to keep columns aligned in the textbox
            return df.to_string(index=True, max_colwidth=24, justify="center")
        except Exception:
            return str(df)

    def _refresh_rag_stats(self) -> None:
        """Refresh the RAG knowledge base statistics display."""
        try:
            stats = self.db.get_statistics()
            last_updated = stats.get("rag_last_updated") or "Never"
            stats_text = (
                f"Documents: {stats.get('rag_documents', 0)} | "
                f"Chunks: {stats.get('rag_chunks', 0)} | "
                f"Last Updated: {last_updated}"
            )
            if hasattr(self, "rag_stats_label"):
                self.rag_stats_label.configure(text=stats_text)
            if hasattr(self, "sources_status_var") and stats.get("rag_chunks", 0) == 0:
                self.sources_status_var.set("Knowledge base empty - ingest sources")
        except Exception as e:
            logger.error("Error refreshing RAG stats: %s", e)

    def _refresh_sources_list(self) -> None:
        """Refresh the recent sources display."""
        if not hasattr(self, "sources_textbox"):
            return

        try:
            sources = self.db.get_rag_documents()
            rows = []
            for doc in sources[:100]:
                timestamp = doc.get("indexed_at")
                if timestamp and hasattr(timestamp, "strftime"):
                    ts_str = timestamp.strftime("%Y-%m-%d %H:%M")
                else:
                    ts_str = str(timestamp) if timestamp else ""
                title = (
                    doc.get("title")
                    or doc.get("source_path")
                    or doc.get("source_url")
                    or "Sem título"
                )
                rows.append(
                    (
                        ts_str,
                        title,
                        doc.get("chemical_name") or "",
                        doc.get("source_type"),
                        doc.get("chunk_count", 0),
                    )
                )

            if hasattr(self, "sources_table"):
                if not rows:
                    rows = [("Nenhum dado", "", "", "", "")]
                self.sources_table.set_data(
                    ["Data/Hora", "Título", "Nome Químico", "Tipo", "Chunks"],
                    rows,
                    accent_color=self.colors["accent"],
                )
        except Exception as e:
            logger.error("Failed to refresh knowledge sources: %s", e)

    def _update_snapshot_label(self) -> None:
        """Display the last Bright Data snapshot id."""
        if not hasattr(self, "bright_snapshot_var"):
            return
        snapshot_id = self.ingestion.get_last_snapshot_id()
        if snapshot_id:
            self.bright_snapshot_var.set(f"Snapshot: {snapshot_id}")
        else:
            self.bright_snapshot_var.set("Snapshot: None")

    def get_text(self, key: str, **kwargs: str) -> str:
        """Expose translation helper for child widgets."""
        return get_text(key, **kwargs)

    def _toggle_language(self) -> None:
        """Toggle between PT and EN."""
        from ..config.i18n import get_i18n

        i18n = get_i18n()
        new_lang = "en" if i18n.language == "pt" else "pt"
        set_language(new_lang)
        logger.info("Language changed to: %s", new_lang)
        self.status_text.configure(text=f"Language: {new_lang.upper()}")

    def _on_close(self) -> None:
        """Handle window close - save window state before exiting."""
        logger.info("Application closing")
        if hasattr(self, "window_manager"):
            self.window_manager.handle_window_close()
        else:
            self.destroy()


def run_app() -> None:
    """Application entry point."""
    app = Application()
    app.mainloop()
