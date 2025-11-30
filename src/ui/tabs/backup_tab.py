"""
Backup Tab for the RAG SDS Matrix application.
"""

from __future__ import annotations

import subprocess
import sys
import threading
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from ..components import SimpleTable, TitleLabel


class BackupTab(ctk.CTkFrame):
    """
    A class to create the Backup & Export Tab
    """

    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup Backup tab."""
        # Title
        TitleLabel(self, text="Backup & Export", text_color=self.app.colors["text"])

        # Main content frame
        content_frame = ctk.CTkFrame(
            self, fg_color=self.app.colors["surface"], corner_radius=10
        )
        content_frame.pack(fill="both", expand=True, padx=20, pady=10)

        # === Backup Section ===
        backup_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        backup_frame.pack(fill="x", padx=20, pady=20)

        ctk.CTkLabel(
            backup_frame,
            text="Backup RAG Data",
            font=("JetBrains Mono", 16, "bold"),
            text_color=self.app.colors["text"],
        ).pack(anchor="w", pady=(0, 5))

        ctk.CTkLabel(
            backup_frame,
            text="Export all RAG records (incompatibilities, hazards, documents) to JSON and CSV formats.",
            font=("JetBrains Mono", 12),
            text_color=self.app.colors["subtext"],
            wraplength=600,
            justify="left",
        ).pack(anchor="w", pady=(0, 15))

        ctk.CTkButton(
            backup_frame,
            corner_radius=4,
            text="Start Backup",
            command=self._on_backup_rag,
            fg_color=self.app.colors["accent"],
            text_color=self.app.colors["header"],
            font=self.app.button_font,
            height=40,
        ).pack(fill="x")

        # Open folder button (enabled after successful backup)
        self.open_folder_btn = ctk.CTkButton(
            backup_frame,
            corner_radius=4,
            text="Open Backup Folder",
            command=self._open_backup_folder,
            fg_color=self.app.colors.get("primary", "#6272a4"),
            text_color=self.app.colors["header"],
            font=self.app.button_font_sm,
        )
        self.open_folder_btn.pack(fill="x", pady=(10, 0))
        self.open_folder_btn.configure(state="disabled")
        self._last_backup_path: str | None = None

        # === Status Section ===
        status_label = ctk.CTkLabel(
            content_frame,
            text="Backup Log:",
            font=("JetBrains Mono", 12, "bold"),
            text_color=self.app.colors["text"],
        )
        status_label.pack(anchor="w", padx=20, pady=(20, 5))

        self.status_table = SimpleTable(
            content_frame,
            headers=["Log"],
            rows=[("Aguardando backup...",)],
            fg_color=self.app.colors["input"],
            text_color=self.app.colors["text"],
            header_color=self.app.colors["surface"],
            accent_color=self.app.colors["accent"],
            min_col_width=150,
        )
        self.status_table.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # Summary counts label (filled after successful backup)
        self.summary_label = ctk.CTkLabel(
            content_frame,
            text="",
            font=("JetBrains Mono", 12),
            text_color=self.app.colors["text"],
            justify="left",
        )
        self.summary_label.pack(anchor="w", padx=20, pady=(0, 12))

    def _on_backup_rag(self) -> None:
        """Handle RAG backup."""
        output_folder = filedialog.askdirectory(
            title="Select Backup Location", parent=self
        )
        if not output_folder:
            return

        # Preflight checks: DB exists and output folder is writable
        try:
            db_path = getattr(self.app.settings.paths, "duckdb", None)
            if not db_path or not Path(db_path).exists():
                messagebox.showerror(
                    "Database Missing",
                    f"DuckDB file not found:\n{db_path}\nConfigure the correct path in settings and try again.",
                )
                return
            # Ensure output folder can be created/written
            Path(output_folder).mkdir(parents=True, exist_ok=True)
            test_file = Path(output_folder) / ".write_test"
            try:
                with open(test_file, "w") as f:
                    f.write("ok")
            finally:
                if test_file.exists():
                    test_file.unlink(missing_ok=True)
        except Exception as exc:
            messagebox.showerror("Folder Error", f"Cannot use selected folder: {exc}")
            return

        # Run backup in thread
        thread = threading.Thread(target=self._run_backup_async, args=(output_folder,))
        thread.daemon = True
        thread.start()

    def _run_backup_async(self, output_folder: str) -> None:
        """Run the backup script asynchronously."""
        try:
            self.app.after(
                0,
                lambda: self.status_table.set_data(
                    ["Log"], [("Iniciando backup RAG...",)]
                ),
            )

            # Use configured DuckDB path from settings to avoid path mismatches
            db_path = str(getattr(self.app.settings.paths, "duckdb", "data/duckdb/extractions.db"))
            cmd = [
                sys.executable,
                "scripts/rag_backup.py",
                "--output",
                output_folder,
                "--db",
                db_path,
            ]

            # Run script
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=Path.cwd(),
            )

            lines = result.stdout.splitlines() if result.stdout else []
            if result.stderr:
                lines += ["Errors:"] + result.stderr.splitlines()

            display_rows = [(line,) for line in lines] if lines else [("Sem logs.",)]
            self.app.after(
                0, lambda rows=display_rows: self.status_table.set_data(["Log"], rows)
            )

            if result.returncode == 0:
                # Parse backup location from stdout if present
                backup_path = None
                for ln in lines:
                    if ln.strip().startswith("📁 Backup location:"):
                        backup_path = ln.split(":", 1)[1].strip()
                        break
                self._last_backup_path = backup_path or output_folder
                # Enable open folder button
                self.app.after(0, lambda: self.open_folder_btn.configure(state="normal"))
                # Show summary
                success_msg = (
                    f"Backup completed successfully!\nFolder: {self._last_backup_path}"
                )
                self.app.after(0, lambda: messagebox.showinfo("Success", success_msg))

                # Parse per-category record counts and render summary
                counts = {"INCOMPATIBILITIES": None, "HAZARDS": None, "DOCUMENTS": None}
                current = None
                for ln in lines:
                    s = ln.strip()
                    if s.endswith(":") and s[:-1].upper() in counts:
                        current = s[:-1].upper()
                        continue
                    if current and s.startswith("Records:"):
                        try:
                            num = int(s.split(":", 1)[1].strip())
                            counts[current] = num
                        except Exception:
                            pass
                        current = None
                summary_text = (
                    f"Incompatibilities: {counts['INCOMPATIBILITIES'] or 0}\n"
                    f"Hazards: {counts['HAZARDS'] or 0}\n"
                    f"Documents: {counts['DOCUMENTS'] or 0}"
                )
                self.app.after(0, lambda txt=summary_text: self.summary_label.configure(text=txt))
            else:
                error_msg = "\nBackup failed. Check log for details."
                self.app.after(0, lambda: messagebox.showerror("Error", error_msg))

        except Exception as e:
            error_msg = f"\nError executing backup: {str(e)}"
            self.app.after(0, lambda: self.status_text.insert("end", error_msg))
            self.app.after(0, lambda msg=str(e): messagebox.showerror("Error", msg))

    def _open_backup_folder(self) -> None:
        """Open the last backup folder in the system file manager."""
        path = self._last_backup_path
        if not path:
            messagebox.showinfo("No Backup", "Run a backup first.")
            return
        try:
            # Prefer xdg-open on Linux
            subprocess.Popen(["xdg-open", path])
        except Exception:
            try:
                # Fallback: open via Python
                import webbrowser
                webbrowser.open(f"file://{Path(path).resolve()}")
            except Exception as exc:
                messagebox.showerror("Open Folder Failed", str(exc))
