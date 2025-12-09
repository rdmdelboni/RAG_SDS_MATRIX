"""RAG Visualization tab for multi-format visualization of retrieval and pipeline data."""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore, QtWidgets, QtWebEngineWidgets

from ...rag.rag_visualizer import RAGVisualizer, RetrievalDocument, RAGPipelineStep
from ...utils.logger import get_logger
from . import BaseTab, TabContext

logger = get_logger(__name__)


class RAGVisualizationTab(BaseTab):
    """Tab for visualizing RAG retrieval and pipeline data."""

    def __init__(self, context: TabContext) -> None:
        """Initialize RAG visualization tab."""
        super().__init__(context)
        self.visualizer = RAGVisualizer()
        self.output_dir = Path("visualizations")
        self.output_dir.mkdir(exist_ok=True)

        self._build_ui()

    def _build_ui(self) -> None:
        """Build the UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        # Title
        title = QtWidgets.QLabel("🎨 RAG Visualization Suite")
        self._style_label(title, bold=True)
        title.setStyleSheet(title.styleSheet() + "; font-size: 16px;")
        layout.addWidget(title)

        # Description
        desc = QtWidgets.QLabel(
            "Create multiple visualizations of your RAG system: "
            "retrieval networks, relevance dashboards, pipelines, and more."
        )
        self._style_label(desc, color=self.colors.get("subtext", "#a6adc8"))
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # ===== Controls Section =====
        controls_group = QtWidgets.QGroupBox("Visualization Controls")
        controls_layout = QtWidgets.QVBoxLayout(controls_group)

        # Visualization type selector
        type_layout = QtWidgets.QHBoxLayout()
        type_layout.addWidget(QtWidgets.QLabel("Visualization Type:"))

        self.viz_type_combo = QtWidgets.QComboBox()
        self.viz_type_combo.addItems([
            "Retrieval Network (PyVis)",
            "Retrieval Network with Clustering (PyVis)",
            "Relevance Dashboard (Plotly)",
            "RAG Pipeline (Graphviz)",
            "Embedding Space (Bokeh)",
            "Similarity Matrix (Heatmap)",
            "All Visualizations",
        ])
        type_layout.addWidget(self.viz_type_combo)
        type_layout.addStretch()
        controls_layout.addLayout(type_layout)

        # Sample data toggle
        self.use_sample_data_cb = QtWidgets.QCheckBox("Use Sample Data")
        self.use_sample_data_cb.setChecked(True)
        controls_layout.addWidget(self.use_sample_data_cb)

        # Output directory selection
        dir_layout = QtWidgets.QHBoxLayout()
        dir_layout.addWidget(QtWidgets.QLabel("Output Directory:"))
        self.dir_input = QtWidgets.QLineEdit(str(self.output_dir))
        dir_layout.addWidget(self.dir_input)
        browse_btn = QtWidgets.QPushButton("Browse...")
        browse_btn.clicked.connect(self._on_browse_dir)
        self._style_button(browse_btn)
        dir_layout.addWidget(browse_btn)
        controls_layout.addLayout(dir_layout)

        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()

        generate_btn = QtWidgets.QPushButton("🎨 Generate Visualizations")
        generate_btn.clicked.connect(self._on_generate)
        self._style_button(generate_btn)
        btn_layout.addWidget(generate_btn)

        open_btn = QtWidgets.QPushButton("📂 Open Output Folder")
        open_btn.clicked.connect(self._on_open_output)
        self._style_button(open_btn)
        btn_layout.addWidget(open_btn)

        controls_layout.addLayout(btn_layout)
        layout.addWidget(controls_group)

        # ===== Preview Section =====
        preview_group = QtWidgets.QGroupBox("Preview")
        preview_layout = QtWidgets.QVBoxLayout(preview_group)

        # Web view for HTML previews
        self.web_view = QtWebEngineWidgets.QWebEngineView()
        preview_layout.addWidget(self.web_view)

        layout.addWidget(preview_group)

        # ===== Status =====
        self.status_label = QtWidgets.QLabel("Ready to generate visualizations")
        self._style_label(self.status_label, color=self.colors.get("subtext", "#a6adc8"))
        layout.addWidget(self.status_label)

    def _on_browse_dir(self) -> None:
        """Browse for output directory."""
        dir_path = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select Output Directory", str(self.output_dir)
        )
        if dir_path:
            self.dir_input.setText(dir_path)

    def _on_generate(self) -> None:
        """Generate selected visualizations."""
        self._set_status("Generating visualizations...")

        try:
            output_dir = Path(self.dir_input.text())
            output_dir.mkdir(parents=True, exist_ok=True)

            viz_type = self.viz_type_combo.currentText()
            use_sample = self.use_sample_data_cb.isChecked()

            if use_sample:
                self._generate_sample_visualizations(output_dir, viz_type)
            else:
                self._set_status("Please implement data loading from RAG system")

            self._set_status(f"✅ Visualizations generated in {output_dir}")

        except Exception as e:
            self._set_status(f"❌ Error: {str(e)[:100]}", error=True)
            logger.error(f"Visualization generation failed: {e}")

    def _generate_sample_visualizations(
        self, output_dir: Path, viz_type: str
    ) -> None:
        """Generate sample visualizations for demonstration."""
        # Create sample data
        sample_docs = [
            RetrievalDocument(
                doc_id="doc1",
                title="Chemical Safety Guidelines for Sulfuric Acid",
                relevance_score=0.95,
                content_preview="Comprehensive safety information...",
                source="Safety Database",
            ),
            RetrievalDocument(
                doc_id="doc2",
                title="Handling Corrosive Materials",
                relevance_score=0.87,
                content_preview="Best practices for handling...",
                source="Training Manual",
            ),
            RetrievalDocument(
                doc_id="doc3",
                title="Emergency Response Procedures",
                relevance_score=0.76,
                content_preview="Step-by-step response guide...",
                source="Protocol Document",
            ),
            RetrievalDocument(
                doc_id="doc4",
                title="Incompatibility Matrix",
                relevance_score=0.68,
                content_preview="Chemical incompatibility table...",
                source="Reference Guide",
            ),
        ]

        sample_pipeline = [
            RAGPipelineStep(
                name="User Query",
                step_type="input",
                description="Chemical safety query from user",
                metrics={"tokens": 25, "language": "en"},
            ),
            RAGPipelineStep(
                name="Document Retrieval",
                step_type="retrieval",
                description="Search knowledge base for relevant documents",
                metrics={"documents_retrieved": 4, "query_time": "0.23s"},
            ),
            RAGPipelineStep(
                name="Ranking & Scoring",
                step_type="ranking",
                description="Rank documents by relevance",
                metrics={"top_k": 4, "avg_score": "0.82"},
            ),
            RAGPipelineStep(
                name="Context Assembly",
                step_type="ranking",
                description="Combine top documents as context",
                metrics={"context_length": 1250, "compression": "3.2x"},
            ),
            RAGPipelineStep(
                name="LLM Generation",
                step_type="generation",
                description="Generate response with LLM",
                metrics={"model": "qwen2.5", "latency": "1.45s", "tokens": 120},
            ),
            RAGPipelineStep(
                name="Response",
                step_type="output",
                description="Final answer to user",
                metrics={"confidence": "0.94", "sources": 3},
            ),
        ]

        # Sample embeddings (2D projection)
        sample_embeddings = [
            (0.5, 0.8),
            (0.4, 0.7),
            (0.6, 0.5),
            (0.3, 0.4),
        ]

        # Sample similarity matrix
        sample_similarity = [
            [1.0, 0.78, 0.65, 0.52],
            [0.78, 1.0, 0.71, 0.48],
            [0.65, 0.71, 1.0, 0.62],
            [0.52, 0.48, 0.62, 1.0],
        ]

        # Generate based on selection
        try:
            if "Clustering" in viz_type:
                self.visualizer.visualize_retrieval_network_with_clustering(
                    sample_docs,
                    "How to safely handle sulfuric acid?",
                    sample_similarity,
                    output_dir / "retrieval_network_clustered.html",
                )
            elif "Retrieval Network" in viz_type:
                self.visualizer.visualize_retrieval_network(
                    sample_docs,
                    "How to safely handle sulfuric acid?",
                    output_dir / "retrieval_network.html",
                )
            elif "Relevance Dashboard" in viz_type:
                self.visualizer.visualize_relevance_dashboard(
                    sample_docs, output_dir / "relevance_dashboard.html"
                )
            elif "RAG Pipeline" in viz_type:
                self.visualizer.visualize_rag_pipeline(
                    sample_pipeline, str(output_dir / "rag_pipeline")
                )
            elif "Embedding Space" in viz_type:
                self.visualizer.visualize_embedding_space(
                    sample_docs, sample_embeddings, output_dir / "embedding_space.html"
                )
            elif "Similarity Matrix" in viz_type:
                self.visualizer.visualize_document_similarity(
                    sample_docs, sample_similarity, output_dir / "similarity_heatmap.html"
                )
            elif "All" in viz_type:
                # For "All", generate each visualization separately with error handling
                self._generate_all_visualizations_resilient(
                    sample_docs,
                    sample_pipeline,
                    sample_embeddings,
                    sample_similarity,
                    output_dir,
                )
        except Exception as e:
            self._set_status(f"Error: {str(e)}", error=True)
            return

        # Load first generated visualization in preview
        self._load_preview(output_dir)

    def _generate_all_visualizations_resilient(
        self,
        documents,
        pipeline,
        embeddings,
        similarity,
        output_dir,
    ) -> None:
        """Generate all visualizations, skipping those that fail due to missing dependencies."""
        generated = []
        failed = []

        # 1. Retrieval Network
        try:
            self.visualizer.visualize_retrieval_network(
                documents, "How to safely handle sulfuric acid?", output_dir / "retrieval_network.html"
            )
            generated.append("Retrieval Network")
        except Exception as e:
            failed.append(("Retrieval Network", str(e)))

        # 2. Clustering Network
        try:
            self.visualizer.visualize_retrieval_network_with_clustering(
                documents,
                "How to safely handle sulfuric acid?",
                similarity,
                output_dir / "retrieval_network_clustered.html",
            )
            generated.append("Clustering Network")
        except Exception as e:
            failed.append(("Clustering Network", str(e)))

        # 3. Relevance Dashboard
        try:
            self.visualizer.visualize_relevance_dashboard(
                documents, output_dir / "relevance_dashboard.html"
            )
            generated.append("Relevance Dashboard")
        except Exception as e:
            failed.append(("Relevance Dashboard", str(e)))

        # 4. RAG Pipeline (may fail if Graphviz not installed)
        try:
            self.visualizer.visualize_rag_pipeline(
                pipeline, str(output_dir / "rag_pipeline")
            )
            generated.append("RAG Pipeline")
        except Exception as e:
            if "graphviz" in str(e).lower() or "dot" in str(e).lower():
                failed.append(("RAG Pipeline", "Graphviz not installed"))
            else:
                failed.append(("RAG Pipeline", str(e)))

        # 5. Embedding Space
        try:
            self.visualizer.visualize_embedding_space(
                documents, embeddings, output_dir / "embedding_space.html"
            )
            generated.append("Embedding Space")
        except Exception as e:
            failed.append(("Embedding Space", str(e)))

        # 6. Similarity Matrix
        try:
            self.visualizer.visualize_document_similarity(
                documents, similarity, output_dir / "similarity_heatmap.html"
            )
            generated.append("Similarity Matrix")
        except Exception as e:
            failed.append(("Similarity Matrix", str(e)))

        # Report results
        status_msg = f"Generated: {', '.join(generated)}"
        if failed:
            failed_names = [f[0] for f in failed]
            status_msg += f"\n⚠️  Skipped: {', '.join(failed_names)}"
            if any("Graphviz" in f[1] for f in failed):
                status_msg += "\n(Install Graphviz to enable RAG Pipeline visualization)"

        self._set_status(status_msg)

    def _load_preview(self, output_dir: Path) -> None:
        """Load first HTML visualization in preview."""
        html_files = list(output_dir.glob("*.html"))
        if html_files:
            # Load the first HTML file
            first_file = sorted(html_files)[0]
            file_url = first_file.as_uri()
            self.web_view.load(QtCore.QUrl(file_url))
            self._set_status(f"Preview: {first_file.name}")

    def _on_open_output(self) -> None:
        """Open output directory in file explorer."""
        import subprocess
        import sys

        output_dir = Path(self.dir_input.text())
        if not output_dir.exists():
            self._set_status("Output directory does not exist", error=True)
            return

        try:
            if sys.platform == "darwin":  # macOS
                subprocess.Popen(["open", str(output_dir)])
            elif sys.platform == "win32":  # Windows
                subprocess.Popen(f'explorer "{output_dir}"')
            else:  # Linux
                subprocess.Popen(["xdg-open", str(output_dir)])
        except Exception as e:
            self._set_status(f"Failed to open directory: {str(e)[:50]}", error=True)

    def _set_status(self, message: str, error: bool = False) -> None:
        """Update status message."""
        self.status_label.setText(message)
        color = self.colors.get("error" if error else "text", "#ffffff")
        self.status_label.setStyleSheet(f"color: {color};")
