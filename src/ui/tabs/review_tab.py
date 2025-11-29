"""
PDF Review Tab for the RAG SDS Matrix application.

Allows users to review and edit extracted data from processed PDFs.
"""

from __future__ import annotations

import threading
from tkinter import END, messagebox, Toplevel
from typing import Any, Callable

import customtkinter as ctk

from ..components import EditableTable, TitleLabel


class ReviewTab(ctk.CTkFrame):
    """
    A class to create the PDF Review Tab for reviewing and editing extracted data.
    """

    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.current_data: list[dict[str, Any]] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup Review tab UI."""
        # Title
        TitleLabel(
            self,
            text="PDF Review & Correction",
            text_color=self.app.colors["text"],
        )

        # Info banner
        info_frame = ctk.CTkFrame(
            self, fg_color=self.app.colors["surface"], corner_radius=8
        )
        info_frame.pack(fill="x", padx=20, pady=(0, 10))

        info_text = (
            "📋 Review processed PDFs and correct extracted data\n"
            "✏️  Click 'Edit' to modify extraction results\n"
            "💾 Corrections will improve the RAG system's accuracy"
        )
        ctk.CTkLabel(
            info_frame,
            text=info_text,
            font=("JetBrains Mono", 11),
            text_color=self.app.colors["text"],
            justify="left",
        ).pack(padx=15, pady=10)

        # Main content frame
        content_frame = ctk.CTkFrame(
            self, fg_color=self.app.colors["surface"], corner_radius=10
        )
        content_frame.pack(fill="both", expand=True, padx=20, pady=10)

        # === Control Bar ===
        control_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        control_frame.pack(fill="x", padx=20, pady=15)

        # Filter controls
        ctk.CTkLabel(
            control_frame,
            text="Status Filter:",
            font=("JetBrains Mono", 12),
            text_color=self.app.colors["text"],
        ).pack(side="left", padx=5)

        self.status_filter = ctk.StringVar(value="all")
        status_options = [
            ("All", "all"),
            ("Success", "success"),
            ("Partial", "partial"),
            ("Failed", "failed"),
        ]

        for label, value in status_options:
            ctk.CTkRadioButton(
                control_frame,
                text=label,
                variable=self.status_filter,
                value=value,
                font=("JetBrains Mono", 11),
                text_color=self.app.colors["text"],
                fg_color=self.app.colors["accent"],
            ).pack(side="left", padx=10)

        # Refresh button
        ctk.CTkButton(
            control_frame,
            corner_radius=4,
            text="🔄 Refresh",
            command=self._on_refresh,
            fg_color=self.app.colors["primary"],
            text_color=self.app.colors["header"],
            font=self.app.button_font,
            width=120,
        ).pack(side="right", padx=5)

        # Limit control
        ctk.CTkLabel(
            control_frame,
            text="Limit:",
            font=("JetBrains Mono", 11),
            text_color=self.app.colors["text"],
        ).pack(side="right", padx=(20, 5))

        self.limit_var = ctk.StringVar(value="50")
        ctk.CTkEntry(
            control_frame,
            textvariable=self.limit_var,
            width=60,
            font=("JetBrains Mono", 11),
            fg_color=self.app.colors["input"],
            text_color=self.app.colors["text"],
        ).pack(side="right", padx=5)

        # === Table Frame ===
        table_frame = ctk.CTkFrame(
            content_frame, fg_color=self.app.colors["bg"], corner_radius=8
        )
        table_frame.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        # Create editable table with cell editing capabilities
        self.results_table = EditableTable(
            table_frame,
            fg_color=self.app.colors["bg"],
            text_color=self.app.colors["text"],
            header_color=self.app.colors["header"],
            accent_color=self.app.colors["accent"],
            selected_color=self.app.colors.get("surface", "#334155"),
            font=("JetBrains Mono", 11),
            header_font=("JetBrains Mono", 11, "bold"),
            editable=True,
            on_cell_edit=self._on_cell_edit_inline,
            on_row_double_click=lambda idx: self._on_edit_row(idx),
        )
        self.results_table.pack(fill="both", expand=True)

        # === Status Label ===
        self.status_label = ctk.CTkLabel(
            content_frame,
            text="Click Refresh to load data",
            font=("JetBrains Mono", 11),
            text_color=self.app.colors["subtext"],
        )
        self.status_label.pack(pady=(5, 10))

        # Load initial data
        self.after(500, self._on_refresh)

    def _on_cell_edit_inline(self, row_idx: int, col_idx: int, new_value: Any) -> None:
        """Handle inline cell edit from EditableTable."""
        if row_idx >= len(self.current_data):
            return

        # Map column index to field name
        headers = ["Filename", "Status", "Product", "CAS", "UN", "Hazard Class", "Confidence", "Actions"]
        if col_idx >= len(headers) or col_idx < 2:  # Skip Filename and Status columns
            return

        field_map = {
            2: "product_name",
            3: "cas_number",
            4: "un_number",
            5: "hazard_class",
        }

        field_name = field_map.get(col_idx)
        if not field_name:
            return

        # Get document ID
        document_id = self.current_data[row_idx].get("id")
        if not document_id:
            return

        # Save to database
        try:
            self.app.db.store_extraction(
                document_id=document_id,
                field=field_name,
                value=new_value,
                source="user_correction",
                confidence=1.0,
            )
            self.current_data[row_idx][field_name] = new_value
            self.status_label.configure(
                text=f"✅ Saved {field_name} for document {document_id}"
            )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")

    def _on_edit_row(self, row_idx: int) -> None:
        """Handle row double-click - open full edit dialog."""
        if 0 <= row_idx < len(self.current_data):
            self._open_edit_dialog(self.current_data[row_idx])

    def _on_refresh(self) -> None:
        """Refresh the table data."""
        self.status_label.configure(text="Loading data...")
        thread = threading.Thread(target=self._load_data_async)
        thread.daemon = True
        thread.start()

    def _load_data_async(self) -> None:
        """Load data from database asynchronously."""
        try:
            # Get limit
            try:
                limit = int(self.limit_var.get() or "50")
            except ValueError:
                limit = 50

            # Fetch data from database
            all_results = self.app.db.fetch_results(limit=limit)

            # Apply status filter
            status_filter = self.status_filter.get()
            if status_filter != "all":
                all_results = [
                    r for r in all_results if r.get("status") == status_filter
                ]

            self.current_data = all_results

            # Update UI in main thread
            self.after(0, lambda: self._display_results(all_results))

        except Exception as e:
            error_msg = f"Error loading data: {str(e)}"
            self.app.logger.error(error_msg)
            self.after(0, lambda: self.status_label.configure(text=error_msg))
            self.after(0, lambda: messagebox.showerror("Load Error", error_msg))

    def _display_results(self, results: list[dict[str, Any]]) -> None:
        """Display results in the table."""
        if not results:
            self.status_label.configure(text="No data found")
            self.results_table.set_data(
                ["File", "Status", "Product", "Actions"],
                [["No data", "", "", ""]],
            )
            return

        # Prepare table data
        # Add row number as first column and remove obsolete Actions/Edit column
        headers = [
            "#",
            "File",
            "Status",
            "Product Name",
            "CAS",
            "UN",
            "Hazard Class",
            "Confidence",
        ]

        rows = []
        for idx, result in enumerate(results, start=1):
            filename = result.get("filename", "Unknown")
            status = result.get("status", "unknown")
            product = result.get("product_name", "N/A") or "N/A"
            cas = result.get("cas_number", "N/A") or "N/A"
            un = result.get("un_number", "N/A") or "N/A"
            hazard = result.get("hazard_class", "N/A") or "N/A"
            confidence = result.get("avg_confidence", 0)
            conf_str = f"{confidence * 100:.0f}%" if confidence else "N/A"

            # Truncate long text
            if len(filename) > 30:
                filename = filename[:27] + "..."
            if len(product) > 25:
                product = product[:22] + "..."

            # Status emoji
            status_display = {
                "success": "✅ Success",
                "partial": "⚠️  Partial",
                "failed": "❌ Failed",
            }.get(status, status)

            rows.append([
                str(idx),
                filename,
                status_display,
                product,
                cas,
                un,
                hazard,
                conf_str,
            ])

        # Display in table
        self.results_table.set_data(headers, rows, accent_color=self.app.colors["accent"])

        # EditableTable handles double-click through on_row_double_click callback

        # Update status
        status_msg = f"Showing {len(results)} documents"
        self.status_label.configure(text=status_msg)

    def _open_edit_dialog(self, record: dict[str, Any]) -> None:
        """Open an edit dialog for the selected record."""
        # Load full extraction details from database
        document_id = record.get("id")
        if document_id:
            # Get detailed extractions with context and source
            extractions = self.app.db.get_extractions(document_id)
            record["_extractions_detail"] = extractions
        
        # Keep reference to prevent garbage collection
        EditDialog(self, self.app, record, on_save=self._on_save_edits)

    def _on_save_edits(self, document_id: int, updated_fields: dict[str, Any]) -> None:
        """Save edited fields back to the database."""
        self.status_label.configure(text="Saving changes...")
        thread = threading.Thread(
            target=self._save_edits_async, args=(document_id, updated_fields)
        )
        thread.daemon = True
        thread.start()

    def _save_edits_async(self, document_id: int, updated_fields: dict[str, Any]) -> None:
        """Save edited fields asynchronously."""
        try:
            # Update each field in the database
            for field_name, field_data in updated_fields.items():
                value = field_data.get("value", "")
                confidence = field_data.get("confidence", 1.0)
                source = "user_correction"
                validation_status = "validated"

                self.app.db.store_extraction(
                    document_id=document_id,
                    field_name=field_name,
                    value=value,
                    confidence=confidence,
                    context="User corrected via review tab",
                    validation_status=validation_status,
                    source=source,
                )

            success_msg = "Changes saved successfully"
            self.app.logger.info(f"Updated document {document_id} with corrected fields")

            # Refresh the display
            self.after(0, lambda: self.status_label.configure(text=success_msg))
            self.after(0, self._on_refresh)
            self.after(0, lambda: messagebox.showinfo("Success", success_msg))

        except Exception as e:
            error_msg = f"Error saving changes: {str(e)}"
            self.app.logger.error(error_msg)
            self.after(0, lambda: self.status_label.configure(text=error_msg))
            self.after(0, lambda: messagebox.showerror("Save Error", error_msg))


class EditDialog:
    """Dialog for editing extraction results."""

    def __init__(
        self,
        parent,
        app,
        record: dict[str, Any],
        on_save: Callable[[int, dict[str, Any]], None] | None = None,
    ):
        self.app = app
        self.record = record
        self.on_save_callback = on_save
        self.field_entries: dict[str, Any] = {}  # Can be CTkEntry or CTkTextbox
        self.confidence_entries: dict[str, ctk.CTkEntry] = {}

        # Create dialog window
        self.dialog = Toplevel(parent)
        self.dialog.title(f"Edit: {record.get('filename', 'Unknown')}")
        self.dialog.geometry("800x700")
        self.dialog.configure(bg=app.colors["bg"])

        # Make modal
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._setup_dialog()

    def _setup_dialog(self) -> None:
        """Setup the edit dialog UI."""
        # Main frame with scrolling
        main_frame = ctk.CTkFrame(
            self.dialog,
            fg_color=self.app.colors["bg"],
        )
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Title
        title_frame = ctk.CTkFrame(main_frame, fg_color=self.app.colors["header"])
        title_frame.pack(fill="x", padx=0, pady=(0, 10))

        ctk.CTkLabel(
            title_frame,
            text=f"📝 Editing: {self.record.get('filename', 'Unknown')}",
            font=("JetBrains Mono", 14, "bold"),
            text_color=self.app.colors["text"],
        ).pack(pady=10, padx=15)

        # Scrollable content frame
        canvas = ctk.CTkCanvas(
            main_frame,
            bg=self.app.colors["bg"],
            highlightthickness=0,
        )
        scrollbar = ctk.CTkScrollbar(main_frame, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        content_frame = ctk.CTkFrame(canvas, fg_color=self.app.colors["surface"])
        canvas_window = canvas.create_window((0, 0), window=content_frame, anchor="nw")

        # Bind scrolling
        content_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )

        # Make canvas expand with content
        def _configure_canvas(event):
            canvas.itemconfig(canvas_window, width=event.width)

        canvas.bind("<Configure>", _configure_canvas)

        # === Extraction Fields ===
        fields_to_edit = [
            ("product_name", "Product Name"),
            ("manufacturer", "Manufacturer"),
            ("cas_number", "CAS Number"),
            ("un_number", "UN Number"),
            ("hazard_class", "Hazard Class"),
            ("packing_group", "Packing Group"),
            ("h_statements", "H Statements"),
            ("p_statements", "P Statements"),
            ("incompatibilities", "Incompatibilities"),
        ]

        for field_name, field_label in fields_to_edit:
            self._create_field_editor(
                content_frame,
                field_name,
                field_label,
                self.record.get(field_name, ""),
            )

        # === Buttons ===
        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(fill="x", pady=10)

        ctk.CTkButton(
            button_frame,
            corner_radius=4,
            text="💾 Save Changes",
            command=self._on_save,
            fg_color=self.app.colors["accent"],
            text_color=self.app.colors["header"],
            font=("JetBrains Mono", 12, "bold"),
            width=150,
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            button_frame,
            corner_radius=4,
            text="❌ Cancel",
            command=self.dialog.destroy,
            fg_color=self.app.colors["error"],
            text_color=self.app.colors["header"],
            font=("JetBrains Mono", 12, "bold"),
            width=150,
        ).pack(side="left", padx=10)

        # View original document button
        ctk.CTkButton(
            button_frame,
            corner_radius=4,
            text="📄 View Original",
            command=self._view_original,
            fg_color=self.app.colors["primary"],
            text_color=self.app.colors["header"],
            font=("JetBrains Mono", 11),
            width=150,
        ).pack(side="right", padx=10)

    def _create_field_editor(
        self, parent, field_name: str, field_label: str, current_value: Any
    ) -> None:
        """Create an editable field in the dialog."""
        field_frame = ctk.CTkFrame(parent, fg_color="transparent")
        field_frame.pack(fill="x", padx=15, pady=8)

        # Label with extraction info
        label_text = field_label
        
        # Get extraction details if available
        extractions_detail = self.record.get("_extractions_detail", {})
        field_detail = extractions_detail.get(field_name, {})
        source = field_detail.get("source", "")
        original_confidence = field_detail.get("confidence", 0)
        
        if source:
            label_text += f" [{source}]"
        
        ctk.CTkLabel(
            field_frame,
            text=label_text,
            font=("JetBrains Mono", 11, "bold"),
            text_color=self.app.colors["text"],
            anchor="w",
            width=150,
        ).pack(side="top", anchor="w", pady=(0, 5))
        
        # Show context if available (as hint)
        context = field_detail.get("context", "")
        if context and len(context) > 10:
            context_display = context[:100] + "..." if len(context) > 100 else context
            ctk.CTkLabel(
                field_frame,
                text=f"Context: {context_display}",
                font=("JetBrains Mono", 9),
                text_color=self.app.colors["subtext"],
                anchor="w",
                wraplength=700,
            ).pack(side="top", anchor="w", pady=(0, 5))

        # Input row
        input_frame = ctk.CTkFrame(field_frame, fg_color="transparent")
        input_frame.pack(fill="x")

        # Value entry (multiline for long fields)
        if field_name in ["h_statements", "p_statements", "incompatibilities"]:
            # Text area for long content
            entry = ctk.CTkTextbox(
                input_frame,
                height=80,
                font=("JetBrains Mono", 10),
                fg_color=self.app.colors["input"],
                text_color=self.app.colors["text"],
                border_color=self.app.colors["accent"],
                border_width=1,
            )
            entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
            entry.insert("1.0", str(current_value or ""))
        else:
            # Single line entry
            entry = ctk.CTkEntry(
                input_frame,
                font=("JetBrains Mono", 10),
                fg_color=self.app.colors["input"],
                text_color=self.app.colors["text"],
                border_color=self.app.colors["accent"],
                border_width=1,
            )
            entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
            entry.insert(0, str(current_value or ""))

        self.field_entries[field_name] = entry

        # Confidence entry
        conf_label = ctk.CTkLabel(
            input_frame,
            text="Confidence:",
            font=("JetBrains Mono", 10),
            text_color=self.app.colors["subtext"],
        )
        conf_label.pack(side="left", padx=(0, 5))

        conf_entry = ctk.CTkEntry(
            input_frame,
            width=60,
            font=("JetBrains Mono", 10),
            fg_color=self.app.colors["input"],
            text_color=self.app.colors["text"],
        )
        conf_entry.pack(side="left")
        # Show original confidence or default to 1.0 for user corrections
        conf_display = f"{original_confidence:.2f}" if original_confidence else "1.0"
        conf_entry.insert(0, conf_display)

        self.confidence_entries[field_name] = conf_entry

    def _on_save(self) -> None:
        """Save the edited fields."""
        updated_fields = {}

        for field_name, entry_widget in self.field_entries.items():
            try:
                # Get value based on widget type
                if isinstance(entry_widget, ctk.CTkTextbox):
                    value = entry_widget.get("1.0", END).strip()
                else:
                    value = entry_widget.get().strip()

                # Get confidence
                conf_str = self.confidence_entries[field_name].get().strip()
                try:
                    confidence = float(conf_str)
                    confidence = max(0.0, min(1.0, confidence))  # Clamp to 0-1
                except ValueError:
                    confidence = 1.0  # Default to 100% for user corrections

                updated_fields[field_name] = {
                    "value": value,
                    "confidence": confidence,
                }

            except Exception as e:
                self.app.logger.error(f"Error reading field {field_name}: {e}")
                continue

        # Call the save callback
        if self.on_save_callback:
            document_id = self.record.get("id")
            if document_id:
                self.on_save_callback(document_id, updated_fields)

        # Close dialog
        self.dialog.destroy()

    def _view_original(self) -> None:
        """Open the original document file (if accessible)."""
        file_path = self.record.get("file_path")
        if file_path:
            import subprocess
            import sys
            from pathlib import Path

            path_obj = Path(file_path)
            if path_obj.exists():
                try:
                    if sys.platform == "darwin":  # macOS
                        subprocess.run(["open", str(path_obj)])
                    elif sys.platform == "win32":  # Windows
                        subprocess.run(["start", str(path_obj)], shell=True)
                    else:  # Linux
                        subprocess.run(["xdg-open", str(path_obj)])
                except Exception as e:
                    messagebox.showerror(
                        "Error", f"Could not open file: {str(e)}"
                    )
            else:
                messagebox.showwarning(
                    "File Not Found",
                    f"Original file not found at: {file_path}",
                )
        else:
            messagebox.showwarning("No File Path", "No file path available")
