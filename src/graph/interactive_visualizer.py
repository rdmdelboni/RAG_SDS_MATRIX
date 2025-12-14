"""Interactive graph visualization widget using pyvis."""

from __future__ import annotations

from pathlib import Path

import networkx as nx
from pyvis.network import Network

from ..utils.logger import get_logger

logger = get_logger(__name__)


class InteractiveGraphVisualizer:
    """Generate interactive 2D/3D visualizations using pyvis."""

    @staticmethod
    def visualize_interactive(
        graph: nx.MultiDiGraph,
        output_path: Path | str,
        title: str = "Chemical Network",
        physics: bool = True,
        height: str = "750px",
        width: str = "100%",
    ) -> None:
        """Generate interactive HTML visualization.

        Args:
            graph: NetworkX graph
            output_path: Output HTML file path
            title: Visualization title
            physics: Enable physics simulation
            height: Canvas height
            width: Canvas width
        """
        try:
            # Create pyvis network
            net = Network(
                height=height,
                width=width,
                directed=True,
                # Make the HTML self-contained (no external CDNs) so it works in QtWebEngine/offline.
                cdn_resources="in_line",
            )

            # Add nodes with colors based on type
            for node in graph.nodes():
                node_attrs = graph.nodes[node]

                # Support both RAG visualizer attributes and chemical network attributes
                node_type = node_attrs.get("node_type") or node_attrs.get("type", "unknown")
                color_map = {
                    "chemical": "#4ECDC4",
                    "hazard": "#FF6B6B",
                    "ghs_class": "#FFE66D",
                    "supplier": "#95E1D3",
                    "query": "#FFD700",
                    "document": "#4ECDC4",
                    "unknown": "#CCCCCC",
                }

                # Use explicit color if provided, otherwise map from type
                color = node_attrs.get("color") or color_map.get(node_type, "#CCCCCC")

                # Get label - support RAG visualizer label attribute
                label = node_attrs.get("label")
                if not label:
                    product_name = node_attrs.get("product_name")
                    label = (product_name[:20] if product_name else str(node)[:20])

                # Get title
                title = node_attrs.get("title")
                if not title:
                    product_name = node_attrs.get("product_name")
                    title = f"{node}\n{product_name or 'Unknown'}"

                net.add_node(
                    node,
                    label=label,
                    title=title,
                    color=color,
                    size=node_attrs.get("size", 30),
                )

            # Add edges with colors
            edge_color_map = {
                "incompatible_with": "#FF6B6B",
                "has_hazard": "#FFA07A",
                "belongs_to": "#87CEEB",
                "manufactured_by": "#90EE90",
            }

            # Handle both MultiDiGraph and regular Graph types
            if isinstance(graph, nx.MultiDiGraph):
                edge_iterator = graph.edges(keys=True, data=True)
                for u, v, key, data in edge_iterator:
                    edge_type = data.get("type", "unknown")
                    color = edge_color_map.get(edge_type, "#888888")
                    title = f"{edge_type}\n{data.get('justification', '')[:50]}"
                    net.add_edge(u, v, color=color, title=title, arrows="to")
            else:
                # Regular Graph or DiGraph
                edge_iterator = graph.edges(data=True)
                for u, v, data in edge_iterator:
                    edge_type = data.get("type", "unknown")
                    edge_label = data.get("label", "")
                    weight = data.get("weight", 1)
                    color = edge_color_map.get(edge_type, "#888888")
                    title = f"{edge_label or edge_type}\nWeight: {weight:.2f}"
                    net.add_edge(u, v, color=color, title=title, arrows="to")

            # Configure physics
            if physics:
                net.show_buttons(filter_=["physics"])

            # Save visualization
            try:
                # `show()` tries to open a browser and relies on template rendering; for the UI
                # we only need a file to load, so write HTML directly.
                net.write_html(str(output_path))
            except Exception as write_error:
                logger.error(f"PyVis write_html() failed: {write_error}")
                raise

            logger.info(f"Interactive visualization saved to {output_path}")

        except Exception as e:
            logger.error(f"Error creating interactive visualization: {e}")
            raise

    @staticmethod
    def get_html_string(
        graph: nx.MultiDiGraph,
        title: str = "Chemical Network",
        physics: bool = True,
    ) -> str:
        """Get interactive visualization as HTML string using vis.js.

        Args:
            graph: NetworkX graph
            title: Visualization title
            physics: Enable physics simulation

        Returns:
            HTML string
        """
        try:
            # Build nodes and edges for vis.js
            nodes = []
            node_id = 0
            node_map = {}

            for node in graph.nodes():
                node_attrs = graph.nodes[node]

                # Support both RAG visualizer attributes and chemical network attributes
                node_type = node_attrs.get("node_type") or node_attrs.get("type", "unknown")
                color_map = {
                    "chemical": "#4ECDC4",
                    "hazard": "#FF6B6B",
                    "ghs_class": "#FFE66D",
                    "supplier": "#95E1D3",
                    "query": "#FFD700",
                    "document": "#4ECDC4",
                    "unknown": "#CCCCCC",
                }

                # Use explicit color if provided, otherwise map from type
                color = node_attrs.get("color") or color_map.get(node_type, "#CCCCCC")

                # Get label
                label = node_attrs.get("label")
                if not label:
                    product_name = node_attrs.get("product_name", "")
                    label = product_name[:20] if product_name else str(node)[:20]

                # Get title
                title = node_attrs.get("title")
                if not title:
                    product_name = node_attrs.get("product_name", "")
                    title = f"{node}\n{product_name}"

                node_map[node] = node_id
                nodes.append({
                    "id": node_id,
                    "label": label,
                    "title": title,
                    "color": color,
                    "size": node_attrs.get("size", 30),
                })
                node_id += 1

            # Build edges
            edges = []
            edge_color_map = {
                "incompatible_with": "#FF6B6B",
                "has_hazard": "#FFA07A",
                "belongs_to": "#87CEEB",
                "manufactured_by": "#90EE90",
            }

            # Handle both MultiDiGraph and regular Graph types
            if isinstance(graph, nx.MultiDiGraph):
                edge_iterator = graph.edges(keys=True, data=True)
                for u, v, key, data in edge_iterator:
                    edge_type = data.get("type", "unknown")
                    color = edge_color_map.get(edge_type, "#888888")
                    justification = data.get("justification", "")[:50]

                    edges.append({
                        "from": node_map[u],
                        "to": node_map[v],
                        "color": {"color": color},
                        "title": f"{edge_type}\n{justification}",
                        "arrows": "to",
                    })
            else:
                # Regular Graph or DiGraph
                edge_iterator = graph.edges(data=True)
                for u, v, data in edge_iterator:
                    edge_type = data.get("type", "unknown")
                    edge_label = data.get("label", "")
                    weight = data.get("weight", 1)
                    color = edge_color_map.get(edge_type, "#888888")
                    title = f"{edge_label or edge_type}\nWeight: {weight:.2f}"

                    edges.append({
                        "from": node_map[u],
                        "to": node_map[v],
                        "color": {"color": color},
                        "title": title,
                        "arrows": "to",
                    })

            # Generate HTML with vis.js
            html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style type="text/css">
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #1e1e1e;
            color: #e0e0e0;
        }}
        #network {{
            width: 100%;
            height: 100vh;
            border: 1px solid #404040;
        }}
        .info {{
            position: absolute;
            top: 10px;
            left: 10px;
            background: #2d2d2d;
            padding: 15px;
            border-radius: 8px;
            border: 1px solid #404040;
            max-width: 300px;
            z-index: 10;
        }}
        .info h2 {{
            color: #4ECDC4;
            margin-bottom: 10px;
            font-size: 16px;
        }}
        .info p {{
            color: #b0b0b0;
            font-size: 12px;
            line-height: 1.6;
        }}
    </style>
</head>
<body>
    <div id="network"></div>
    <div class="info">
        <h2>{title}</h2>
        <p>Nodes: {len(nodes)}</p>
        <p>Edges: {len(edges)}</p>
        <p style="color: #FFE66D; margin-top: 10px;">
            Drag nodes • Scroll to zoom • Click to interact
        </p>
    </div>
    <script type="text/javascript">
        var nodes = new vis.DataSet({str(nodes)});
        var edges = new vis.DataSet({str(edges)});

        var container = document.getElementById('network');
        var data = {{
            nodes: nodes,
            edges: edges
        }};

        var options = {{
            physics: {str(physics).lower()},
            nodes: {{
                font: {{
                    color: '#e0e0e0'
                }}
            }},
            edges: {{
                smooth: {{
                    type: 'continuous'
                }}
            }},
            interaction: {{
                navigationButtons: true,
                keyboard: true
            }}
        }};

        var network = new vis.Network(container, data, options);
    </script>
</body>
</html>
"""
            return html

        except Exception as e:
            logger.error(f"Error generating HTML visualization: {e}")
            return "<h1>Error generating visualization</h1>"
