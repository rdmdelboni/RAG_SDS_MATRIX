"""
Example: Integrating UI Tabs into Main Application

This file shows how to replace the placeholder tab implementations
with the new modular RAGViewerTab, SDSProcessorTab, and BackupTab.
"""

# BEFORE: In src/ui/app.py (lines 92-197):
# def _setup_rag_tab(self) -> None:
#     """Setup RAG Knowledge Base tab."""
#     tab = self.tab_view.tab(get_text("tab.rag"))
#     # ... lots of placeholder code ...


# AFTER: Replace with this implementation:

def _setup_rag_tab(self) -> None:
    """Setup RAG Knowledge Base tab with integrated tabs."""
    from .tabs import RAGViewerTab
    
    tab = self.tab_view.tab("RAG")
    
    # Create a container for the title
    title_frame = ctk.CTkFrame(tab, fg_color="transparent")
    title_frame.pack(fill="x", padx=10, pady=10)
    
    title = ctk.CTkLabel(
        title_frame,
        text="📚 RAG Knowledge Base",
        font=("JetBrains Mono", 20, "bold"),
        text_color=self.colors["text"],
    )
    title.pack()
    
    # Add RAG viewer tab
    viewer = RAGViewerTab(tab)
    viewer.pack(fill="both", expand=True, padx=10, pady=10)


def _setup_sds_tab(self) -> None:
    """Setup SDS Processing tab with integrated tabs."""
    from .tabs import SDSProcessorTab
    
    tab = self.tab_view.tab("SDS")
    
    # Add SDS processor tab
    processor = SDSProcessorTab(tab)
    processor.pack(fill="both", expand=True, padx=10, pady=10)


def _setup_sources_tab(self) -> None:
    """Setup document sources tab."""
    tab = self.tab_view.tab("Sources")
    
    # Keep existing document ingestion UI
    # This can remain as-is since it handles document upload
    # The new tabs are for READING/QUERYING the RAG
    
    # For now, you could add document upload UI here
    title = ctk.CTkLabel(
        tab,
        text="📄 Document Ingestion",
        font=("JetBrains Mono", 20, "bold"),
        text_color=self.colors["text"],
    )
    title.pack(pady=10)
    
    # Existing ingestion code can go here...
    # (keep the original implementation)


def _setup_status_tab(self) -> None:
    """Setup status and backup tab."""
    from .tabs import BackupTab
    
    tab = self.tab_view.tab("Status")
    
    # Create container
    container = ctk.CTkFrame(tab, fg_color="transparent")
    container.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Add backup tab
    backup = BackupTab(container)
    backup.pack(fill="both", expand=True)


# ============================================================
# INTEGRATION CHECKLIST:
# ============================================================

# 1. Update src/ui/app.py imports:
#    Add: from .tabs import RAGViewerTab, SDSProcessorTab, BackupTab

# 2. Replace _setup_rag_tab() with the RAGViewerTab implementation

# 3. Replace _setup_sds_tab() with the SDSProcessorTab implementation

# 4. Replace _setup_status_tab() with the BackupTab implementation

# 5. Ensure tabs/__init__.py exports the new classes:
#    __all__ = ["RAGViewerTab", "SDSProcessorTab", "BackupTab"]

# 6. Test by running: python main.py

# ============================================================
# TESTING: Individual Tabs
# ============================================================

# Test RAGViewerTab alone:
# 
# python -c "
# import customtkinter as ctk
# from src.ui.tabs import RAGViewerTab
# from src.ui.theme import get_colors
#
# app = ctk.CTk()
# frame = ctk.CTkFrame(app)
# frame.pack(fill='both', expand=True)
# tab = RAGViewerTab(frame)
# tab.pack(fill='both', expand=True)
# app.mainloop()
# "

# Test SDSProcessorTab alone:
#
# python -c "
# import customtkinter as ctk
# from src.ui.tabs import SDSProcessorTab
# from src.ui.theme import get_colors
#
# app = ctk.CTk()
# frame = ctk.CTkFrame(app)
# frame.pack(fill='both', expand=True)
# tab = SDSProcessorTab(frame)
# tab.pack(fill='both', expand=True)
# app.mainloop()
# "

# ============================================================
# FEATURE MATRIX
# ============================================================

# ┌─────────────────────┬──────────────────┬──────────────────┐
# │ Feature             │ Tab              │ CLI Tool         │
# ├─────────────────────┼──────────────────┼──────────────────┤
# │ Query Incomp.       │ RAGViewerTab     │ rag_records.py   │
# │ Query Hazards       │ RAGViewerTab     │ rag_records.py   │
# │ Query CAMEO         │ RAGViewerTab     │ rag_records.py   │
# │ Query Files         │ RAGViewerTab     │ rag_records.py   │
# ├─────────────────────┼──────────────────┼──────────────────┤
# │ List SDS files      │ SDSProcessorTab  │ sds_pipeline.py  │
# │ Extract chemicals   │ SDSProcessorTab  │ sds_pipeline.py  │
# │ Process SDS         │ SDSProcessorTab  │ sds_pipeline.py  │
# │ RAG-enhanced SDS    │ SDSProcessorTab  │ rag_sds_processor│
# ├─────────────────────┼──────────────────┼──────────────────┤
# │ Backup RAG          │ BackupTab        │ rag_backup.py    │
# └─────────────────────┴──────────────────┴──────────────────┘

# ============================================================
# DATA FLOW
# ============================================================

# USER INTERACTION → TAB UI → SUBPROCESS CALL → CLI TOOL → DATABASE/OUTPUT

# Example: Query RAG
# 1. User opens RAG tab
# 2. User selects query type: "Incompatibilities"
# 3. User clicks "Query RAG" button
# 4. RAGViewerTab._on_query() executes
# 5. Subprocess runs: python scripts/rag_records.py --incompatibilities
# 6. Results piped to text widget
# 7. User sees formatted results

# Example: Process SDS
# 1. User opens SDS tab
# 2. User selects input folder
# 3. User selects mode: "RAG-enhanced"
# 4. User clicks "Process SDS"
# 5. SDSProcessorTab._on_process() executes
# 6. Subprocess runs: python scripts/rag_sds_processor.py --input <folder>
# 7. Progress displayed in real-time
# 8. Results saved to output folder
# 9. Completion message shown

# ============================================================
# MULTI-THREADING EXPLAINED
# ============================================================

# All tabs use threading to prevent UI freezing:
#
# import threading
#
# def _on_query(self):
#     def run_query():
#         # This runs in background thread
#         result = subprocess.run(...)
#         self.results_text.insert("end", result.stdout)
#     
#     # Start background thread
#     thread = threading.Thread(target=run_query, daemon=True)
#     thread.start()
#     # UI remains responsive while thread runs

# ============================================================
# COMMON ISSUES & FIXES
# ============================================================

# Issue: "ImportError: cannot import name 'RAGViewerTab'"
# Fix: Make sure tabs/__init__.py has:
#      from .ui_tabs import RAGViewerTab, SDSProcessorTab, BackupTab
#      __all__ = ["RAGViewerTab", "SDSProcessorTab", "BackupTab"]

# Issue: "FileNotFoundError: scripts/rag_records.py"
# Fix: Make sure working directory is project root
#      subprocess.run(cmd, cwd=Path.cwd())

# Issue: UI freezes during processing
# Fix: Ensure operations run in background thread
#      thread = threading.Thread(target=run_process, daemon=True)
#      thread.start()

# Issue: Results not showing
# Fix: Check that text widget is configured:
#      self.results_text.pack(fill="both", expand=True)

# ============================================================
# NEXT STEPS
# ============================================================

# 1. Update src/ui/app.py with new tab implementations
# 2. Test tabs individually
# 3. Run full application: python main.py
# 4. Verify all tabs are clickable and responsive
# 5. Test each feature (query, process, backup)
# 6. Add progress bars if needed
# 7. Add more UI polish (colors, fonts, spacing)

