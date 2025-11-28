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

from ..components import Table, TitleLabel


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

        # === Status Section ===
        status_label = ctk.CTkLabel(
            content_frame,
            text="Backup Log:",
            font=("JetBrains Mono", 12, "bold"),
            text_color=self.app.colors["text"],
        )
        status_label.pack(anchor="w", padx=20, pady=(20, 5))

        self.status_table = Table(
            content_frame,
            headers=["Log"],
            rows=[("Aguardando backup...",)],
            fg_color=self.app.colors["input"],
            text_color=self.app.colors["text"],
            accent_color=self.app.colors["accent"],
            height=260,
        )
        self.status_table.pack(fill="both", expand=True, padx=20, pady=(0, 20))

    def _on_backup_rag(self) -> None:
        """Handle RAG backup."""
        output_folder = filedialog.askdirectory(title="Select Backup Location")
        if not output_folder:
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

            cmd = [
                sys.executable,
                "scripts/rag_backup.py",
                "--output",
                output_folder,
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
                success_msg = (
                    f"\nBackup completed successfully!\nFiles saved to: {output_folder}"
                )
                self.app.after(0, lambda: messagebox.showinfo("Success", success_msg))
            else:
                error_msg = "\nBackup failed. Check log for details."
                self.app.after(0, lambda: messagebox.showerror("Error", error_msg))

        except Exception as e:
            error_msg = f"\nError executing backup: {str(e)}"
            self.app.after(0, lambda: self.status_text.insert("end", error_msg))
            self.app.after(0, lambda msg=str(e): messagebox.showerror("Error", msg))
