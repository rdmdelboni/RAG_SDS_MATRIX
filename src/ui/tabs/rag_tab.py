"""
RAG Knowledge Base Tab for the RAG SDS Matrix application.
"""

from __future__ import annotations

import threading
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog

import customtkinter as ctk

from ..components import SimpleTable, TitledFrame, TitleLabel


class RagTab(ctk.CTkFrame):
    """
    A class to create the RAG Knowledge Base Tab
    """

    def __init__(self, master, app):
        super().__init__(master)
        self.app = app

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup RAG Knowledge Base tab."""
        self.configure(fg_color="transparent")
        TitleLabel(
            self,
            text=self.app.get_text("rag.title"),
            text_color=self.app.colors["text"],
        )

        # Actions frame
        actions_frame = TitledFrame(
            self, "Actions", fg_color=self.app.colors["surface"]
        )
        actions_frame.pack(fill="x", padx=20, pady=10)

        ctk.CTkButton(
            actions_frame,
            corner_radius=4,
            text=self.app.get_text("rag.add_docs"),
            fg_color=self.app.colors["primary"],
            text_color=self.app.colors["header"],
            font=self.app.button_font,
            command=self._on_add_docs,
        ).pack(side="left", padx=10, pady=10)

        ctk.CTkButton(
            actions_frame,
            corner_radius=4,
            text=self.app.get_text("rag.add_url"),
            fg_color=self.app.colors["success"],
            text_color=self.app.colors["header"],
            font=self.app.button_font,
            command=self._on_add_url,
        ).pack(side="left", padx=10, pady=10)

        ctk.CTkButton(
            actions_frame,
            corner_radius=4,
            text="Clear Knowledge Base",
            fg_color=self.app.colors["error"],
            text_color=self.app.colors["header"],
            font=self.app.button_font,
            command=self._on_clear_rag,
        ).pack(side="left", padx=10, pady=10)

        # Search frame
        search_frame = TitledFrame(
            self, "Query Knowledge Base", fg_color=self.app.colors["surface"]
        )
        search_frame.pack(fill="x", padx=20, pady=10)

        self.rag_query_entry = ctk.CTkEntry(
            search_frame,
            placeholder_text="Enter search query...",
            font=("JetBrains Mono", 11),
            fg_color=self.app.colors["input"],
            text_color=self.app.colors["text"],
        )
        self.rag_query_entry.pack(side="left", fill="x", expand=True, padx=10, pady=10)

        ctk.CTkButton(
            search_frame,
            corner_radius=4,
            text="Search",
            fg_color=self.app.colors["accent"],
            text_color=self.app.colors["header"],
            font=self.app.button_font_sm,
            width=80,
            command=self._on_rag_search,
        ).pack(side="left", padx=10, pady=10)

        # Stats frame
        stats_frame = TitledFrame(
            self, "Statistics", fg_color=self.app.colors["surface"]
        )
        stats_frame.pack(fill="x", padx=20, pady=10)

        stats = self.app.db.get_statistics()
        rows = [
            ("Documentos", stats.get("rag_documents", 0)),
            ("Chunks", stats.get("rag_chunks", 0)),
            ("Atualizado", stats.get("rag_last_updated", "Nunca")),
        ]
        ollama_ok = self.app.ollama.test_connection()
        rows.append(("Ollama", "Conectado" if ollama_ok else "Não conectado"))

        self.rag_stats_table = SimpleTable(
            stats_frame,
            headers=["Métrica", "Valor"],
            rows=rows,
            fg_color=self.app.colors["input"],
            text_color=self.app.colors["text"],
            header_color=self.app.colors["surface"],
            accent_color=self.app.colors["accent"],
            min_col_width=120,
        )
        self.rag_stats_table.pack(fill="x", padx=10, pady=10, expand=False)

    def _on_add_docs(self) -> None:
        """Handle add documents button."""
        files = filedialog.askopenfilenames(
            title="Select documents for RAG",
            parent=self,
            filetypes=[
                ("PDF files", "*.pdf"),
                ("Text files", "*.txt"),
                ("Markdown", "*.md"),
                ("Word documents", "*.docx"),
                ("All files", "*.*"),
            ],
        )
        if files:
            self.app.logger.info("Selected %d files for RAG", len(files))
            self.app.status_text.configure(text=f"Loading {len(files)} documents...")
            # Start async document loading in background thread
            thread = threading.Thread(target=self._load_documents_async, args=(files,))
            thread.daemon = True
            thread.start()

    def _load_documents_async(self, file_paths: tuple[str, ...]) -> None:
        """Load documents asynchronously to prevent UI freezing.
        Args:
            file_paths: Tuple of file paths to load
        """
        try:
            self.app.after(
                0,
                lambda: self.app.status_text.configure(text="Processing documents..."),
            )
            summary = self.app.ingestion.ingest_local_files(
                [Path(p) for p in file_paths]
            )
            self.app.after(0, lambda: self.app._handle_ingestion_summary(summary))
        except Exception as e:
            error_msg = f"Error loading documents: {str(e)}"
            self.app.logger.error(error_msg)
            self.app.after(0, lambda: self.app.status_text.configure(text=error_msg))
            self.app.after(0, lambda: messagebox.showerror("Load Error", error_msg))

    def _on_add_url(self) -> None:
        """Handle add URL button."""
        # Create a simple dialog to ask for URL
        url = simpledialog.askstring(
            "Add URL to Knowledge Base", "Enter URL to fetch and add to knowledge base:"
        )
        if url and url.strip():
            self.app.logger.info("Adding URL to RAG: %s", url)
            self.app.status_text.configure(text="Fetching content from URL...")
            # Start async URL loading in background thread
            thread = threading.Thread(target=self._load_url_async, args=(url,))
            thread.daemon = True
            thread.start()

    def _load_url_async(self, url: str) -> None:
        """Load content from URL asynchronously.
        Args:
            url: URL to fetch
        """
        try:
            import requests
        except ImportError:
            error_msg = "requests library required for URL loading"
            self.app.logger.error(error_msg)
            self.app.after(0, lambda: self.app.status_text.configure(text=error_msg))
            self.app.after(
                0, lambda: messagebox.showerror("Missing Dependency", error_msg)
            )
            return

        try:
            self.app.after(
                0,
                lambda: self.app.status_text.configure(text="Fetching URL content..."),
            )
            summary = self.app.ingestion.ingest_url(url)
            self.app.after(0, lambda: self.app._handle_ingestion_summary(summary))
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to fetch URL: {str(e)}"
            self.app.logger.error(error_msg)
            self.app.after(0, lambda: self.app.status_text.configure(text=error_msg))
            self.app.after(0, lambda: messagebox.showerror("URL Error", error_msg))
        except Exception as e:
            error_msg = f"Error processing URL: {str(e)}"
            self.app.logger.error(error_msg)
            self.app.after(0, lambda: self.app.status_text.configure(text=error_msg))
            self.app.after(0, lambda: messagebox.showerror("Error", error_msg))

    def _on_clear_rag(self) -> None:
        """Handle clear knowledge base button."""
        if messagebox.askyesno(
            "Clear Knowledge Base", "Are you sure you want to clear the knowledge base?"
        ):
            try:
                self.app.logger.info("Clearing RAG knowledge base")
                self.app.status_text.configure(text="Clearing knowledge base...")
                self.app.vector_store.clear()
                self.app.status_text.configure(text="Knowledge base cleared")
                self.app._refresh_rag_stats()
                messagebox.showinfo("Success", "Knowledge base cleared successfully")
            except Exception as e:
                error_msg = f"Error clearing knowledge base: {str(e)}"
                self.app.logger.error(error_msg)
                self.app.status_text.configure(text=error_msg)
                messagebox.showerror("Clear Error", error_msg)

    def _on_rag_search(self) -> None:
        """Handle RAG search."""
        query = self.rag_query_entry.get()
        if not query.strip():
            self.app.status_text.configure(text="Please enter a search query")
            return

        # Check knowledge base size
        try:
            stats = self.app.vector_store.get_statistics()
            doc_count = stats.get("document_count", 0)
            chunk_count = stats.get("chunk_count", 0)

            if doc_count == 0 or chunk_count < 10:
                response = messagebox.askyesno(
                    "Limited Knowledge Base",
                    f"Warning: Knowledge base is small ({doc_count} documents, {chunk_count} chunks).\n\n"
                    "RAG search may not provide good results. Consider adding more documents first.\n\n"
                    "Continue anyway?",
                )
                if not response:
                    self.app.status_text.configure(text="Search cancelled")
                    return
        except Exception as e:
            self.app.logger.warning("Could not check knowledge base stats: %s", e)

        self.app.logger.info("Searching RAG for: %s", query)
        self.app.status_text.configure(text=f"Searching: {query}")
        # Start async search in background thread
        thread = threading.Thread(target=self._rag_search_async, args=(query,))
        thread.daemon = True
        thread.start()

    def _rag_search_async(self, query: str) -> None:
        """Perform RAG search asynchronously.
        Args:
            query: Search query
        """
        from src.rag.retriever import RAGRetriever

        try:
            self.app.after(
                0,
                lambda: self.app.status_text.configure(
                    text="Searching knowledge base..."
                ),
            )

            # Initialize RAG retriever
            retriever = RAGRetriever()

            # Get answer using RAG
            answer = retriever.answer(query, k=5)

            # Update status
            self.app.after(
                0, lambda: self.app.status_text.configure(text="Search complete")
            )

            # Show results in a message dialog
            self.app.after(0, lambda: self._show_rag_results(query, answer))

            self.app.logger.info("RAG search completed for: %s", query[:50])

        except Exception as e:
            error_msg = f"Search error: {str(e)}"
            self.app.logger.error(error_msg)
            self.app.after(0, lambda: self.app.status_text.configure(text=error_msg))
            self.app.after(0, lambda: messagebox.showerror("Search Error", error_msg))

    def _show_rag_results(self, query: str, answer: str) -> None:
        """Show RAG search results in a dialog window.
        Args:
            query: The search query
            answer: The RAG answer
        """
        # Create a top-level window for results
        result_window = ctk.CTkToplevel(self)
        result_window.title(f"RAG Search Results: {query[:30]}")
        result_window.geometry("600x400")

        # Title
        title_label = ctk.CTkLabel(
            result_window,
            text=f"Query: {query}",
            font=("JetBrains Mono", 12, "bold"),
            text_color=self.app.colors["text"],
        )
        title_label.pack(pady=10, padx=10)

        # Answer text in scrollable frame
        text_frame = ctk.CTkFrame(result_window, fg_color=self.app.colors["surface"])
        text_frame.pack(fill="both", expand=True, padx=10, pady=10)

        text_widget = ctk.CTkTextbox(
            text_frame,
            fg_color=self.app.colors["input"],
            text_color=self.app.colors["text"],
            border_color=self.app.colors["accent"],
            border_width=1,
        )
        text_widget.pack(fill="both", expand=True)
        text_widget.insert("1.0", answer)
        text_widget.configure(state="disabled")

        # Close button
        close_btn = ctk.CTkButton(
            result_window,
            corner_radius=4,
            text="Close",
            fg_color=self.app.colors["primary"],
            text_color=self.app.colors["header"],
            command=result_window.destroy,
        )
        close_btn.pack(pady=10)
