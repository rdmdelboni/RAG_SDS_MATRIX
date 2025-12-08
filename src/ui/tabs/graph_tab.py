"""Graph query tab for chemical relationship analysis."""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore, QtWidgets

from ...graph.chemical_graph import ChemicalGraph
from ...graph.graph_queries import GraphQueryEngine
from ...graph.graph_visualizer import GraphVisualizer
from ...graph.interactive_visualizer import InteractiveGraphVisualizer
from ...utils.logger import get_logger
from ..components.workers import TaskRunner
from . import BaseTab, TabContext

logger = get_logger(__name__)


class GraphTab(BaseTab):
    """Tab for graph-based chemical queries and visualization."""

    def __init__(self, context: TabContext) -> None:
        """Initialize graph tab."""
        super().__init__(context)

        self.graph = ChemicalGraph()
        self.query_engine = GraphQueryEngine()
        self.visualizer = GraphVisualizer()

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup UI components."""
        layout = QtWidgets.QVBoxLayout(self)

        # Title
        title = QtWidgets.QLabel("Chemical Graph Queries")
        self._style_label(title, bold=True)
        title.setStyleSheet(
            f"color: {self.colors.get('text', '#ffffff')};"
            " font-size: 18px; font-weight: 700;"
        )
        layout.addWidget(title)

        # Build graph button
        build_btn = QtWidgets.QPushButton("Build Knowledge Graph")
        build_btn.clicked.connect(self._on_build_graph)
        self._style_button(build_btn)
        layout.addWidget(build_btn)

        # Stats display
        self.stats_label = QtWidgets.QLabel("Graph not built yet")
        self._style_label(self.stats_label)
        layout.addWidget(self.stats_label)

        # Query section
        query_group = QtWidgets.QGroupBox("Graph Queries")
        query_layout = QtWidgets.QVBoxLayout(query_group)

        # CAS input
        cas_layout = QtWidgets.QHBoxLayout()
        cas_layout.addWidget(QtWidgets.QLabel("CAS Number:"))
        self.cas_input = QtWidgets.QLineEdit()
        self.cas_input.setPlaceholderText("e.g., 67-64-1")
        cas_layout.addWidget(self.cas_input)
        query_layout.addLayout(cas_layout)

        # Depth control
        depth_layout = QtWidgets.QHBoxLayout()
        depth_layout.addWidget(QtWidgets.QLabel("Traversal Depth:"))
        self.depth_spin = QtWidgets.QSpinBox()
        self.depth_spin.setMinimum(1)
        self.depth_spin.setMaximum(5)
        self.depth_spin.setValue(2)
        depth_layout.addWidget(self.depth_spin)
        depth_layout.addStretch()
        query_layout.addLayout(depth_layout)

        # Query buttons
        btn_layout = QtWidgets.QHBoxLayout()

        incomp_btn = QtWidgets.QPushButton("Find Incompatibilities")
        incomp_btn.clicked.connect(self._on_find_incompatibilities)
        self._style_button(incomp_btn)
        btn_layout.addWidget(incomp_btn)

        chains_btn = QtWidgets.QPushButton("Find Reaction Chains")
        chains_btn.clicked.connect(self._on_find_chains)
        self._style_button(chains_btn)
        btn_layout.addWidget(chains_btn)

        visualize_btn = QtWidgets.QPushButton("Visualize Network")
        visualize_btn.clicked.connect(self._on_visualize)
        self._style_button(visualize_btn)
        btn_layout.addWidget(visualize_btn)

        full_viz_btn = QtWidgets.QPushButton("Visualize Full Graph")
        full_viz_btn.clicked.connect(self._on_visualize_full)
        self._style_button(full_viz_btn)
        btn_layout.addWidget(full_viz_btn)

        interactive_btn = QtWidgets.QPushButton("Interactive View")
        interactive_btn.clicked.connect(self._on_interactive_view)
        self._style_button(interactive_btn)
        btn_layout.addWidget(interactive_btn)

        query_layout.addLayout(btn_layout)

        layout.addWidget(query_group)

        # Advanced queries
        advanced_group = QtWidgets.QGroupBox("Advanced Queries")
        advanced_layout = QtWidgets.QVBoxLayout(advanced_group)

        clusters_btn = QtWidgets.QPushButton("Find Chemical Clusters")
        clusters_btn.clicked.connect(self._on_find_clusters)
        self._style_button(clusters_btn)
        advanced_layout.addWidget(clusters_btn)

        hazard_btn = QtWidgets.QPushButton("Find Hazardous Clusters")
        hazard_btn.clicked.connect(self._on_find_hazardous)
        self._style_button(hazard_btn)
        advanced_layout.addWidget(hazard_btn)

        layout.addWidget(advanced_group)

        # Results display
        self.results_text = QtWidgets.QTextEdit()
        self.results_text.setReadOnly(True)
        self._style_textedit(self.results_text)
        layout.addWidget(self.results_text)

    def _on_build_graph(self) -> None:
        """Build knowledge graph."""
        self.context.set_status("Building knowledge graph...")

        def task() -> dict:
            self.graph.build_graph()
            return self.graph.get_graph_stats()

        def on_complete(stats: dict) -> None:
            self.stats_label.setText(
                f"Graph: {stats['nodes']} nodes, {stats['edges']} edges, "
                f"density: {stats['density']:.4f}"
            )
            self.context.set_status("Graph built successfully")
            self._append_results("✓ Knowledge graph built successfully")
            self._append_results(f"  Nodes: {stats['nodes']}")
            self._append_results(f"  Edges: {stats['edges']}")
            self._append_results(f"  Chemicals: {stats['chemicals']}")
            self._append_results(f"  Avg Degree: {stats['avg_degree']:.2f}")

        runner = TaskRunner(task)
        runner.signals.finished.connect(on_complete)
        runner.signals.error.connect(
            lambda e: self.context.on_error(f"Error building graph: {e}")
        )

        self.context.thread_pool.start(runner)

    def _on_visualize_full(self) -> None:
        """Visualize the entire knowledge graph."""
        # Ask for output path
        output_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save Full Graph",
            str(Path.home() / "graph_full.png"),
            "PNG Files (*.png);;SVG Files (*.svg)",
        )

        if not output_path:
            return

        self.context.set_status("Generating full graph visualization...")

        def task() -> None:
            if not self.graph._initialized:
                self.graph.build_graph()
            self.visualizer.visualize_subgraph(
                self.graph.graph,
                output_path,
                title="Full Chemical Knowledge Graph",
                layout="kamada_kawai",
                figsize=(14, 10),
            )

        def on_complete(_: None) -> None:
            self._append_results(f"\n✓ Full graph visualization saved to {output_path}")
            self.context.set_status("Visualization complete")

        runner = TaskRunner(task)
        runner.signals.finished.connect(on_complete)
        runner.signals.error.connect(
            lambda e: self.context.on_error(f"Visualization error: {e}")
        )

        self.context.thread_pool.start(runner)

    def _on_find_incompatibilities(self) -> None:
        """Find incompatibilities for CAS."""
        cas = self.cas_input.text().strip()
        if not cas:
            self.context.on_error("Please enter a CAS number")
            return

        depth = self.depth_spin.value()
        self.context.set_status(f"Finding incompatibilities for {cas}...")

        def task() -> list:
            return self.graph.find_incompatible_chemicals(cas, depth)

        def on_complete(incompatible: list) -> None:
            self._append_results(f"\n=== Incompatibilities for {cas} ===")
            if incompatible:
                for chemical, d in incompatible:
                    self._append_results(f"  Depth {d}: {chemical}")
                self._append_results(
                    f"\nTotal: {len(incompatible)} incompatibilities found"
                )
            else:
                self._append_results("  No incompatibilities found")

            self.context.set_status("Query complete")

        runner = TaskRunner(task)
        runner.signals.finished.connect(on_complete)
        runner.signals.error.connect(
            lambda e: self.context.on_error(f"Query error: {e}")
        )

        self.context.thread_pool.start(runner)

    def _on_find_chains(self) -> None:
        """Find reaction chains."""
        cas = self.cas_input.text().strip()
        if not cas:
            self.context.on_error("Please enter a CAS number")
            return

        depth = self.depth_spin.value()
        self.context.set_status(f"Finding reaction chains for {cas}...")

        def task() -> list:
            return self.graph.find_reaction_chains(cas, depth)

        def on_complete(chains: list) -> None:
            self._append_results(f"\n=== Reaction Chains for {cas} ===")
            if chains:
                for i, chain in enumerate(chains[:10], 1):
                    chain_str = " → ".join(chain)
                    self._append_results(f"  Chain {i}: {chain_str}")
                self._append_results(f"\nTotal: {len(chains)} chains found")
            else:
                self._append_results("  No reaction chains found")

            self.context.set_status("Query complete")

        runner = TaskRunner(task)
        runner.signals.finished.connect(on_complete)
        runner.signals.error.connect(
            lambda e: self.context.on_error(f"Query error: {e}")
        )

        self.context.thread_pool.start(runner)

    def _on_visualize(self) -> None:
        """Visualize incompatibility network."""
        cas = self.cas_input.text().strip()
        if not cas:
            self.context.on_error("Please enter a CAS number")
            return

        depth = self.depth_spin.value()

        # Ask for output path
        output_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save Visualization",
            str(Path.home() / f"graph_{cas}.png"),
            "PNG Files (*.png);;SVG Files (*.svg)",
        )

        if not output_path:
            return

        self.context.set_status("Generating visualization...")

        def task() -> None:
            self.visualizer.visualize_incompatibility_network(
                self.graph.graph, cas, depth, output_path
            )

        def on_complete(_: None) -> None:
            self._append_results(f"\n✓ Visualization saved to {output_path}")
            self.context.set_status("Visualization complete")

        runner = TaskRunner(task)
        runner.signals.finished.connect(on_complete)
        runner.signals.error.connect(
            lambda e: self.context.on_error(f"Visualization error: {e}")
        )

        self.context.thread_pool.start(runner)

    def _on_find_clusters(self) -> None:
        """Find chemical clusters."""
        self.context.set_status("Finding chemical clusters...")

        def task() -> list:
            return self.query_engine.find_chemical_clusters(min_connections=2)

        def on_complete(clusters: list) -> None:
            self._append_results("\n=== Chemical Clusters ===")
            if clusters:
                for cluster in clusters[:10]:
                    self._append_results(
                        f"  {cluster['cas']}: {cluster['connection_count']} "
                        f"connections"
                    )
                self._append_results(f"\nTotal: {len(clusters)} clusters found")
            else:
                self._append_results("  No clusters found")

            self.context.set_status("Query complete")

        runner = TaskRunner(task)
        runner.signals.finished.connect(on_complete)
        runner.signals.error.connect(
            lambda e: self.context.on_error(f"Query error: {e}")
        )

        self.context.thread_pool.start(runner)

    def _on_find_hazardous(self) -> None:
        """Find hazardous clusters."""
        self.context.set_status("Finding hazardous clusters...")

        def task() -> list:
            return self.query_engine.find_hazardous_clusters(hazard_threshold=100.0)

        def on_complete(clusters: list) -> None:
            self._append_results("\n=== Hazardous Clusters (IDLH >= 100) ===")
            if clusters:
                for cluster in clusters[:10]:
                    self._append_results(
                        f"  {cluster['cas_a']} ↔ {cluster['cas_b']}: "
                        f"IDLH {cluster['idlh_a']:.0f} / {cluster['idlh_b']:.0f}"
                    )
                self._append_results(f"\nTotal: {len(clusters)} pairs found")
            else:
                self._append_results("  No hazardous clusters found")

            self.context.set_status("Query complete")

        runner = TaskRunner(task)
        runner.signals.finished.connect(on_complete)
        runner.signals.error.connect(
            lambda e: self.context.on_error(f"Query error: {e}")
        )

        self.context.thread_pool.start(runner)

    def _on_interactive_view(self) -> None:
        """Open interactive 2D/3D graph view in browser."""
        import webbrowser
        import tempfile

        if not self.graph._initialized:
            self.context.on_error("Build graph first")
            return

        self.context.set_status("Generating interactive visualization...")

        def task() -> str:
            # Get the graph or a subgraph based on CAS input
            cas = self.cas_input.text().strip()
            if cas and cas in self.graph.graph:
                # Visualize neighborhood around CAS
                depth = self.depth_spin.value()
                neighbors = set([cas])
                for _ in range(depth):
                    new_neighbors = set()
                    for node in neighbors:
                        for neighbor in self.graph.graph.neighbors(node):
                            edges = self.graph.graph.get_edge_data(node, neighbor)
                            if edges:
                                new_neighbors.add(neighbor)
                    neighbors.update(new_neighbors)
                subgraph = self.graph.graph.subgraph(neighbors).copy()
                title = f"Network around {cas}"
            else:
                # Use full graph
                subgraph = self.graph.graph
                title = "Full Chemical Network"

            # Generate HTML
            html_content = InteractiveGraphVisualizer.get_html_string(
                subgraph,
                title=title,
                physics=True,
            )

            # Save to temp file
            with tempfile.NamedTemporaryFile(
                mode='w', suffix='.html', delete=False
            ) as f:
                f.write(html_content)
                return f.name

        def on_complete(html_file: str) -> None:
            try:
                webbrowser.open(f"file://{html_file}")
                self._append_results(f"\n✓ Interactive view opened in browser: {html_file}")
                self.context.set_status("Interactive view ready")
            except Exception as e:
                self.context.on_error(f"Failed to open browser: {e}")

        runner = TaskRunner(task)
        runner.signals.finished.connect(on_complete)
        runner.signals.error.connect(
            lambda e: self.context.on_error(f"Visualization error: {e}")
        )

        self.context.thread_pool.start(runner)

    def _append_results(self, text: str) -> None:
        """Append text to results display."""
        self.results_text.append(text)
