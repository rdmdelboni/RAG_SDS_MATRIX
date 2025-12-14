"""Unified RAG visualization module supporting multiple backends."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import networkx as nx
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ..utils.logger import get_logger

logger = get_logger(__name__)


class VisualizationType(Enum):
    """Supported visualization types."""

    RETRIEVAL_NETWORK = "retrieval_network"  # PyVis interactive graph
    RELEVANCE_DASHBOARD = "relevance_dashboard"  # Plotly scatter/bar charts
    RAG_PIPELINE = "rag_pipeline"  # Graphviz DAG diagram
    EMBEDDING_SPACE = "embedding_space"  # 2D/3D scatter plot
    DOCUMENT_SIMILARITY = "document_similarity"  # Heatmap


@dataclass
class RetrievalDocument:
    """Document from retrieval with metadata."""

    doc_id: str
    title: str
    relevance_score: float
    content_preview: str
    source: str
    embedding: list[float] | None = None


@dataclass
class RAGPipelineStep:
    """Step in RAG pipeline for visualization."""

    name: str
    step_type: str  # "input", "retrieval", "ranking", "generation", "output"
    description: str
    metrics: dict[str, Any] | None = None


class RAGVisualizer:
    """Unified RAG visualization interface supporting multiple backends."""

    def __init__(self):
        """Initialize RAG visualizer."""
        self.logger = logger

    # ============ RETRIEVAL NETWORK (PyVis) ============

    def visualize_retrieval_network(
        self,
        documents: list[RetrievalDocument],
        query: str,
        output_path: Path | str = "retrieval_network.html",
    ) -> None:
        """Visualize document retrieval network using PyVis.

        Args:
            documents: Retrieved documents with scores
            query: Original query
            output_path: Output HTML file path
        """
        from ..graph.interactive_visualizer import InteractiveGraphVisualizer

        try:
            # Create NetworkX graph
            graph = nx.Graph()

            # Add query node
            graph.add_node("query", node_type="query", label="Query", title=query)

            # Add document nodes with relevance-based sizing
            for doc in documents:
                graph.add_node(
                    doc.doc_id,
                    node_type="document",
                    label=doc.title[:20],  # Truncate label
                    title=f"{doc.title}\nRelevance: {doc.relevance_score:.2%}",
                    relevance=doc.relevance_score,
                )

                # Add edge from query to document (weight = relevance)
                graph.add_edge("query", doc.doc_id, weight=doc.relevance_score)

            # Visualize using PyVis
            InteractiveGraphVisualizer.visualize_interactive(
                graph,
                output_path=output_path,
                title=f"Document Retrieval Network: {query}",
                physics=True,
            )

            self.logger.info(f"Retrieval network visualization saved to {output_path}")

        except Exception as e:
            self.logger.error(f"Failed to create retrieval network visualization: {e}")
            raise

    def visualize_retrieval_network_with_clustering(
        self,
        documents: list[RetrievalDocument],
        query: str,
        similarity_matrix: list[list[float]] | None = None,
        output_path: Path | str = "retrieval_network_clustered.html",
    ) -> None:
        """Visualize document retrieval network with community detection clustering.

        Uses document similarity to build connections and detects communities.

        Args:
            documents: Retrieved documents with scores
            query: Original query
            similarity_matrix: Optional NxN similarity matrix for better clustering
            output_path: Output HTML file path
        """
        from ..graph.interactive_visualizer import InteractiveGraphVisualizer

        try:
            # Create NetworkX graph
            graph = nx.Graph()

            # Add query node
            graph.add_node("query", node_type="query", label="Query", title=query)

            # Add document nodes
            for doc in documents:
                graph.add_node(
                    doc.doc_id,
                    node_type="document",
                    label=doc.title[:20],
                    title=f"{doc.title}\nRelevance: {doc.relevance_score:.2%}",
                    relevance=doc.relevance_score,
                )

                # Add edge from query to document (weight = relevance)
                graph.add_edge("query", doc.doc_id, weight=doc.relevance_score)

            # Add document-to-document edges from similarity matrix
            if similarity_matrix and len(documents) == len(similarity_matrix):
                for i, doc_i in enumerate(documents):
                    for j, doc_j in enumerate(documents):
                        if i < j:  # Only add each edge once
                            similarity = similarity_matrix[i][j]
                            # Only add edges for significant similarities
                            if similarity > 0.3:
                                graph.add_edge(
                                    doc_i.doc_id,
                                    doc_j.doc_id,
                                    weight=similarity,
                                )

            # Detect communities using greedy modularity optimization
            communities = nx.community.greedy_modularity_communities(graph)
            self.logger.info(f"Detected {len(communities)} document clusters")

            # Map nodes to communities
            node_to_community = {}
            for community_id, community in enumerate(communities):
                for node in community:
                    node_to_community[node] = community_id

            # Assign colors based on community membership
            community_colors = [
                "#FF6B6B",  # Red
                "#4ECDC4",  # Teal
                "#45B7D1",  # Blue
                "#FFA07A",  # Light Salmon
                "#98D8C8",  # Mint
                "#F7DC6F",  # Yellow
                "#BB8FCE",  # Purple
                "#85C1E2",  # Sky Blue
            ]

            for node in graph.nodes():
                if node != "query":
                    community_id = node_to_community.get(node, 0)
                    color = community_colors[community_id % len(community_colors)]
                    graph.nodes[node]["community"] = community_id
                    graph.nodes[node]["color"] = color
                else:
                    graph.nodes[node]["color"] = "#FFD700"  # Gold for query
                    graph.nodes[node]["community"] = -1

            # Visualize using PyVis
            InteractiveGraphVisualizer.visualize_interactive(
                graph,
                output_path=output_path,
                title=f"Document Retrieval Network with Clustering: {query}",
                physics=True,
            )

            self.logger.info(
                f"Clustered retrieval network visualization saved to {output_path}"
            )

        except Exception as e:
            self.logger.error(
                f"Failed to create clustered retrieval network visualization: {e}"
            )
            raise

    # ============ RELEVANCE DASHBOARD (Plotly) ============

    def visualize_relevance_dashboard(
        self,
        documents: list[RetrievalDocument],
        output_path: Path | str = "relevance_dashboard.html",
    ) -> None:
        """Create interactive relevance scoring dashboard using Plotly.

        Args:
            documents: Documents with relevance scores
            output_path: Output HTML file path
        """
        try:
            # Sort by relevance
            sorted_docs = sorted(documents, key=lambda d: d.relevance_score, reverse=True)

            # Prepare data
            titles = [d.title[:30] for d in sorted_docs]
            scores = [d.relevance_score for d in sorted_docs]
            colors = [f"rgba({int(s*255)}, {int((1-s)*255)}, 100, 0.7)" for s in scores]

            # Create subplots
            fig = make_subplots(
                rows=1,
                cols=2,
                subplot_titles=("Relevance Scores", "Score Distribution"),
                specs=[[{"type": "bar"}, {"type": "box"}]],
            )

            # Bar chart of relevance scores
            fig.add_trace(
                go.Bar(
                    x=titles,
                    y=scores,
                    marker_color=colors,
                    marker_line_color="rgb(8,48,107)",
                    marker_line_width=1.5,
                    name="Relevance Score",
                    text=[f"{s:.1%}" for s in scores],
                    textposition="auto",
                ),
                row=1,
                col=1,
            )

            # Box plot of distribution
            fig.add_trace(
                go.Box(y=scores, name="Distribution", boxmean="sd"),
                row=1,
                col=2,
            )

            # Update layout
            fig.update_layout(
                title_text="RAG Document Relevance Dashboard",
                height=500,
                showlegend=True,
                hovermode="closest",
            )

            fig.update_xaxes(title_text="Documents", row=1, col=1)
            fig.update_yaxes(title_text="Relevance Score", row=1, col=1)
            fig.update_yaxes(title_text="Relevance Score", row=1, col=2)

            fig.write_html(str(output_path))
            self.logger.info(f"Relevance dashboard saved to {output_path}")

        except Exception as e:
            self.logger.error(f"Failed to create relevance dashboard: {e}")
            raise

    # ============ RAG PIPELINE (Graphviz) ============

    def visualize_rag_pipeline(
        self,
        steps: list[RAGPipelineStep],
        output_path: Path | str = "rag_pipeline",
    ) -> None:
        """Visualize RAG pipeline flow using Graphviz.

        Args:
            steps: Pipeline steps in order
            output_path: Output file path (without extension)
        """
        try:
            import graphviz

            # Create directed graph
            dot = graphviz.Digraph(format="svg")
            dot.attr(rankdir="LR")
            dot.attr("graph", bgcolor="white", splines="ortho")

            # Color mapping for step types
            colors = {
                "input": "#E8F4F8",
                "retrieval": "#B3E5FC",
                "ranking": "#81D4FA",
                "generation": "#4FC3F7",
                "output": "#29B6F6",
            }

            # Add nodes
            for i, step in enumerate(steps):
                color = colors.get(step.step_type, "#E0E0E0")
                label = f"{step.name}\n{step.description}"

                if step.metrics:
                    metric_str = "\n".join(
                        [f"{k}: {v}" for k, v in step.metrics.items()]
                    )
                    label += f"\n\n{metric_str}"

                dot.node(
                    f"step_{i}",
                    label=label,
                    shape="box",
                    style="filled",
                    fillcolor=color,
                    fontname="Helvetica",
                )

            # Add edges
            for i in range(len(steps) - 1):
                dot.edge(f"step_{i}", f"step_{i+1}", label="", arrowsize="1.5")

            # Render
            dot.render(str(output_path), cleanup=True)
            self.logger.info(f"RAG pipeline visualization saved to {output_path}.svg")

        except ImportError:
            self.logger.error("Graphviz not installed. Install with: pip install graphviz")
            raise
        except Exception as e:
            self.logger.error(f"Failed to create RAG pipeline visualization: {e}")
            raise

    # ============ EMBEDDING SPACE (Bokeh) ============

    def visualize_embedding_space(
        self,
        documents: list[RetrievalDocument],
        embeddings_2d: list[tuple[float, float]],
        output_path: Path | str = "embedding_space.html",
    ) -> None:
        """Visualize document embedding space using Bokeh.

        Args:
            documents: Documents with metadata
            embeddings_2d: 2D coordinates (e.g., from t-SNE or UMAP)
            output_path: Output HTML file path
        """
        try:
            from bokeh.plotting import figure
            from bokeh.models import HoverTool, ColumnDataSource
            from bokeh.embed import file_html
            from bokeh.resources import INLINE

            # Prepare data
            source_data = {
                "x": [e[0] for e in embeddings_2d],
                "y": [e[1] for e in embeddings_2d],
                "title": [d.title for d in documents],
                "relevance": [f"{d.relevance_score:.1%}" for d in documents],
                "source": [d.source for d in documents],
                "color": [
                    f"rgb({int(d.relevance_score*255)}, {int((1-d.relevance_score)*255)}, 100)"
                    for d in documents
                ],
            }

            source = ColumnDataSource(source_data)

            # Create figure
            p = figure(
                width=800,
                height=600,
                title="Document Embedding Space",
                toolbar_location="right",
                tools="pan,wheel_zoom,box_zoom,reset,save",
            )

            # Add circles
            p.circle(
                "x",
                "y",
                source=source,
                size=10,
                color="color",
                alpha=0.6,
                hover_color="white",
                hover_alpha=0.8,
            )

            # Add hover tool
            hover = HoverTool(
                tooltips=[
                    ("Title", "@title"),
                    ("Relevance", "@relevance"),
                    ("Source", "@source"),
                    ("(x, y)", "($x, $y)"),
                ]
            )
            p.add_tools(hover)

            # Styling
            p.xaxis.axis_label = "Dimension 1"
            p.yaxis.axis_label = "Dimension 2"
            p.title.text_font_size = "14pt"

            # Save as a self-contained HTML (no CDN) so it works inside QtWebEngine/offline.
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            html = file_html(p, INLINE, "Document Embedding Space")
            output_path.write_text(html, encoding="utf-8")
            self.logger.info(f"Embedding space visualization saved to {output_path}")

        except ImportError:
            self.logger.error("Bokeh not installed. Install with: pip install bokeh")
            raise
        except Exception as e:
            self.logger.error(f"Failed to create embedding space visualization: {e}")
            raise

    # ============ DOCUMENT SIMILARITY (Plotly Heatmap) ============

    def visualize_document_similarity(
        self,
        documents: list[RetrievalDocument],
        similarity_matrix: list[list[float]],
        output_path: Path | str = "similarity_heatmap.html",
    ) -> None:
        """Visualize document similarity matrix as heatmap.

        Args:
            documents: Documents
            similarity_matrix: NxN similarity scores
            output_path: Output HTML file path
        """
        try:
            # Create heatmap
            titles = [d.title[:20] for d in documents]

            fig = go.Figure(
                data=go.Heatmap(
                    z=similarity_matrix,
                    x=titles,
                    y=titles,
                    colorscale="Viridis",
                    hovertemplate="%{x} vs %{y}<br>Similarity: %{z:.3f}<extra></extra>",
                )
            )

            fig.update_layout(
                title="Document Similarity Matrix",
                xaxis_title="Document",
                yaxis_title="Document",
                height=600,
                width=800,
            )

            fig.write_html(str(output_path))
            self.logger.info(f"Similarity heatmap saved to {output_path}")

        except Exception as e:
            self.logger.error(f"Failed to create similarity heatmap: {e}")
            raise

    # ============ UTILITY METHODS ============

    def get_supported_types(self) -> list[str]:
        """Get list of supported visualization types."""
        return [v.value for v in VisualizationType]

    def create_all_visualizations(
        self,
        documents: list[RetrievalDocument],
        query: str,
        pipeline_steps: list[RAGPipelineStep],
        embeddings_2d: list[tuple[float, float]] | None = None,
        similarity_matrix: list[list[float]] | None = None,
        output_dir: Path | str = "visualizations",
    ) -> None:
        """Create all available visualizations.

        Args:
            documents: Retrieved documents
            query: Original query
            pipeline_steps: RAG pipeline steps
            embeddings_2d: Optional 2D embeddings
            similarity_matrix: Optional similarity matrix
            output_dir: Output directory for all visualizations
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)

        try:
            # Create each visualization
            self.visualize_retrieval_network(
                documents, query, output_dir / "retrieval_network.html"
            )
            self.visualize_relevance_dashboard(
                documents, output_dir / "relevance_dashboard.html"
            )
            self.visualize_rag_pipeline(
                pipeline_steps, str(output_dir / "rag_pipeline")
            )

            if embeddings_2d:
                self.visualize_embedding_space(
                    documents, embeddings_2d, output_dir / "embedding_space.html"
                )

            if similarity_matrix:
                self.visualize_document_similarity(
                    documents, similarity_matrix, output_dir / "similarity_heatmap.html"
                )
                # Also create clustered network visualization with similarity matrix
                self.visualize_retrieval_network_with_clustering(
                    documents,
                    query,
                    similarity_matrix,
                    output_dir / "retrieval_network_clustered.html",
                )

            self.logger.info(f"All visualizations created in {output_dir}")

        except Exception as e:
            self.logger.error(f"Failed to create all visualizations: {e}")
            raise
