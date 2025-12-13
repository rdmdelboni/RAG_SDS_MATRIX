"""Graph visualization utilities for chemical relationships."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import json

import matplotlib.pyplot as plt
import networkx as nx

from ..utils.logger import get_logger

logger = get_logger(__name__)


class GraphVisualizer:
    """Visualize chemical knowledge graphs."""

    def __init__(self) -> None:
        """Initialize visualizer."""
        self.color_map = {
            "chemical": "#4ECDC4",
            "hazard": "#FF6B6B",
            "ghs_class": "#FFE66D",
            "supplier": "#95E1D3",
        }

        self.edge_color_map = {
            "incompatible_with": "#FF6B6B",
            "has_hazard": "#FFA07A",
            "belongs_to": "#87CEEB",
            "manufactured_by": "#90EE90",
        }

    def visualize_subgraph(
        self,
        graph: nx.MultiDiGraph,
        output_path: Path | str,
        title: str = "Chemical Graph",
        layout: str = "spring",
        figsize: tuple[int, int] = (12, 8),
    ) -> None:
        """Visualize a subgraph and save to file.

        Args:
            graph: NetworkX graph to visualize
            output_path: Output file path (PNG, SVG, PDF)
            title: Graph title
            layout: Layout algorithm (spring, circular, kamada_kawai)
            figsize: Figure size in inches
        """
        if graph.number_of_nodes() == 0:
            logger.warning("Empty graph, skipping visualization")
            return

        try:
            fig, ax = plt.subplots(figsize=figsize)

            # Choose layout
            if layout == "spring":
                pos = nx.spring_layout(graph, k=1, iterations=50)
            elif layout == "circular":
                pos = nx.circular_layout(graph)
            elif layout == "kamada_kawai":
                pos = nx.kamada_kawai_layout(graph)
            else:
                pos = nx.spring_layout(graph)

            # Node colors based on type
            node_colors = []
            for node in graph.nodes():
                node_type = graph.nodes[node].get("type", "chemical")
                node_colors.append(self.color_map.get(node_type, "#CCCCCC"))

            # Draw nodes
            nx.draw_networkx_nodes(
                graph,
                pos,
                node_color=node_colors,
                node_size=500,
                alpha=0.9,
                ax=ax,
            )

            # Draw edges with colors
            edge_colors = []
            for u, v, key in graph.edges(keys=True):
                edge_data = graph.get_edge_data(u, v, key)
                edge_type = edge_data.get("type", "unknown") if edge_data else "unknown"
                edge_colors.append(
                    self.edge_color_map.get(edge_type, "#888888")
                )

            nx.draw_networkx_edges(
                graph,
                pos,
                edge_color=edge_colors,
                alpha=0.6,
                arrows=True,
                arrowsize=10,
                ax=ax,
            )

            # Draw labels
            labels = {}
            for node in graph.nodes():
                # Use CAS or product name
                product_name = graph.nodes[node].get("product_name")
                if product_name:
                    labels[node] = product_name[:15]  # Truncate
                else:
                    labels[node] = str(node)[:15]

            nx.draw_networkx_labels(
                graph, pos, labels, font_size=8, font_weight="bold", ax=ax
            )

            ax.set_title(title, fontsize=16, fontweight="bold")
            ax.axis("off")

            plt.tight_layout()
            plt.savefig(output_path, dpi=300, bbox_inches="tight")
            plt.close()

            logger.info(f"Graph visualization saved to {output_path}")

        except Exception as e:
            logger.error(f"Error visualizing graph: {e}")

    def visualize_incompatibility_network(
        self,
        graph: nx.MultiDiGraph,
        cas: str,
        depth: int,
        output_path: Path | str,
    ) -> None:
        """Visualize incompatibility network around a chemical.

        Args:
            graph: Full chemical graph
            cas: Central CAS number
            depth: Neighborhood depth
            output_path: Output file path
        """
        if cas not in graph:
            logger.warning(f"CAS {cas} not in graph")
            return

        # Extract subgraph
        neighbors = set([cas])
        for _ in range(depth):
            new_neighbors = set()
            for node in neighbors:
                # Get incompatibility edges
                for neighbor in graph.neighbors(node):
                    edges = graph.get_edge_data(node, neighbor)
                    if edges:
                        for edge_data in edges.values():
                            if edge_data.get("type") == "incompatible_with":
                                new_neighbors.add(neighbor)

            neighbors.update(new_neighbors)

        subgraph = graph.subgraph(neighbors).copy()

        # Visualize
        title = f"Incompatibility Network: {cas} (depth={depth})"
        self.visualize_subgraph(
            subgraph,
            output_path,
            title=title,
            layout="spring",
        )

    def visualize_hazardous_clusters(
        self,
        graph: nx.MultiDiGraph,
        clusters: list[dict[str, Any]],
        output_path: Path | str,
    ) -> None:
        """Visualize hazardous chemical clusters.

        Args:
            graph: Full chemical graph
            clusters: List of cluster dicts with cas_a, cas_b
            output_path: Output file path
        """
        # Extract all chemicals in clusters
        cluster_chemicals = set()
        for cluster in clusters:
            cluster_chemicals.add(cluster["cas_a"])
            cluster_chemicals.add(cluster["cas_b"])

        # Create subgraph
        subgraph = graph.subgraph(cluster_chemicals).copy()

        # Visualize
        self.visualize_subgraph(
            subgraph,
            output_path,
            title=f"Hazardous Chemical Clusters ({len(clusters)} pairs)",
            layout="kamada_kawai",
            figsize=(14, 10),
        )

    def generate_html_visualization(
        self,
        graph: nx.MultiDiGraph,
        output_path: Path | str,
        title: str = "Chemical Graph",
    ) -> None:
        """Generate interactive HTML visualization using D3.js format.

        Args:
            graph: NetworkX graph
            output_path: Output HTML file path
            title: Graph title
        """
        # Convert to D3.js JSON format
        nodes = []
        for node in graph.nodes():
            node_data = graph.nodes[node]
            nodes.append(
                {
                    "id": str(node),
                    "type": node_data.get("type", "chemical"),
                    "label": node_data.get("product_name", str(node)),
                    "properties": {
                        k: str(v) for k, v in node_data.items()
                    },
                }
            )

        links = []
        for u, v, key in graph.edges(keys=True):
            edge_data = graph.get_edge_data(u, v, key)
            links.append(
                {
                    "source": str(u),
                    "target": str(v),
                    "type": edge_data.get("type", "unknown") if edge_data else "unknown",
                    "properties": {
                        k: str(v) for k, v in edge_data.items()
                    } if edge_data else {},
                }
            )

        # Generate HTML with embedded JSON
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title}</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }}
        #graph {{
            width: 100%;
            height: 800px;
            border: 1px solid #ccc;
            background: white;
            position: relative;
        }}
        .node {{
            cursor: pointer;
        }}
        .node circle {{
            stroke: #fff;
            stroke-width: 2px;
        }}
        .link {{
            stroke: #999;
            stroke-opacity: 0.6;
        }}
        .node-label {{
            font-family: Arial, sans-serif;
            font-size: 12px;
            pointer-events: none;
            text-shadow: 0 1px 0 #fff, 1px 0 0 #fff, 0 -1px 0 #fff, -1px 0 0 #fff;
        }}
        #info {{
            margin-top: 20px;
            padding: 15px;
            background: white;
            border: 1px solid #ccc;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        button {{
            padding: 8px 16px;
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            margin-top: 10px;
        }}
        button:hover {{
            background-color: #45a049;
        }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <div id="graph"></div>
    <div id="info">
        <h3>Graph Statistics</h3>
        <p>Nodes: {len(nodes)}</p>
        <p>Edges: {len(links)}</p>
        <p><em>Click on a node to view details</em></p>
    </div>

    <script>
        // Graph data
        const graphData = {{
            nodes: {json.dumps(nodes)},
            links: {json.dumps(links)}
        }};

        // Color maps from Python
        const colorMap = {json.dumps(self.color_map)};
        const edgeColorMap = {json.dumps(self.edge_color_map)};
        const defaultNodeColor = "#CCCCCC";
        const defaultEdgeColor = "#999999";

        console.log("Graph data loaded:", graphData);

        // Dimensions
        const container = document.getElementById("graph");
        const width = container.clientWidth;
        const height = container.clientHeight;

        // Create SVG
        const svg = d3.select("#graph").append("svg")
            .attr("width", width)
            .attr("height", height)
            .call(d3.zoom().on("zoom", (event) => {{
                g.attr("transform", event.transform);
            }}))
            .on("dblclick.zoom", null); // Disable double click zoom

        const g = svg.append("g");

        // Simulation
        const simulation = d3.forceSimulation(graphData.nodes)
            .force("link", d3.forceLink(graphData.links).id(d => d.id).distance(150))
            .force("charge", d3.forceManyBody().strength(-500))
            .force("center", d3.forceCenter(width / 2, height / 2))
            .force("collide", d3.forceCollide(50));

        // Arrow marker for directed edges
        svg.append("defs").selectAll("marker")
            .data(["end"])
            .enter().append("marker")
            .attr("id", "arrow")
            .attr("viewBox", "0 -5 10 10")
            .attr("refX", 25) // Shift arrow back so it doesn't overlap node
            .attr("refY", 0)
            .attr("markerWidth", 6)
            .attr("markerHeight", 6)
            .attr("orient", "auto")
            .append("path")
            .attr("d", "M0,-5L10,0L0,5")
            .attr("fill", "#999");

        // Links
        const link = g.append("g")
            .attr("class", "links")
            .selectAll("line")
            .data(graphData.links)
            .enter().append("line")
            .attr("class", "link")
            .attr("stroke", d => edgeColorMap[d.type] || defaultEdgeColor)
            .attr("stroke-width", 2)
            .attr("marker-end", "url(#arrow)");

        // Nodes
        const node = g.append("g")
            .attr("class", "nodes")
            .selectAll("g")
            .data(graphData.nodes)
            .enter().append("g")
            .call(d3.drag()
                .on("start", dragstarted)
                .on("drag", dragged)
                .on("end", dragended));

        node.append("circle")
            .attr("r", 15)
            .attr("fill", d => colorMap[d.type] || defaultNodeColor);

        // Node Labels
        node.append("text")
            .attr("dy", -20)
            .attr("text-anchor", "middle")
            .text(d => d.label)
            .attr("class", "node-label");

        // Node interaction
        node.on("click", (event, d) => {{
            // Highlight selected node
            node.selectAll("circle").attr("stroke", null).attr("stroke-width", null);
            d3.select(event.currentTarget).select("circle")
                .attr("stroke", "#333")
                .attr("stroke-width", 3);

            const infoDiv = document.getElementById("info");
            let propertiesHtml = "";
            for (const [key, value] of Object.entries(d.properties)) {{
                propertiesHtml += `<li><strong>${{key}}:</strong> ${{value}}</li>`;
            }}

            infoDiv.innerHTML = `
                <h3>${{d.label}}</h3>
                <p><strong>Type:</strong> ${{d.type}}</p>
                <p><strong>ID:</strong> ${{d.id}}</p>
                <h4>Properties:</h4>
                <ul>${{propertiesHtml}}</ul>
                <button onclick="resetInfo()">Show Graph Stats</button>
            `;
        }});

        // Link interaction (tooltip)
        link.append("title")
            .text(d => `${{d.type}}`);

        // Tick function
        simulation.on("tick", () => {{
            link
                .attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x)
                .attr("y2", d => d.target.y);

            node
                .attr("transform", d => `translate(${{d.x}},${{d.y}})`);
        }});

        // Drag functions
        function dragstarted(event, d) {{
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
        }}

        function dragged(event, d) {{
            d.fx = event.x;
            d.fy = event.y;
        }}

        function dragended(event, d) {{
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
        }}

        // Reset info function
        window.resetInfo = function() {{
             // Remove highlight
             node.selectAll("circle").attr("stroke", "#fff").attr("stroke-width", 2);

             const infoDiv = document.getElementById("info");
             infoDiv.innerHTML = `
                <h3>Graph Statistics</h3>
                <p>Nodes: {len(nodes)}</p>
                <p>Edges: {len(links)}</p>
                <p><em>Click on a node to view details</em></p>
            `;
        }};
    </script>
</body>
</html>
        """

        try:
            with open(output_path, "w") as f:
                f.write(html_content)

            logger.info(f"HTML visualization saved to {output_path}")

        except Exception as e:
            logger.error(f"Error generating HTML visualization: {e}")

    def generate_stats_report(
        self,
        graph: nx.MultiDiGraph,
        output_path: Path | str,
    ) -> None:
        """Generate statistical report about the graph.

        Args:
            graph: NetworkX graph
            output_path: Output text file path
        """
        try:
            with open(output_path, "w") as f:
                f.write("Chemical Knowledge Graph - Statistical Report\n")
                f.write("=" * 60 + "\n\n")

                # Basic stats
                f.write(f"Total Nodes: {graph.number_of_nodes()}\n")
                f.write(f"Total Edges: {graph.number_of_edges()}\n")
                f.write(f"Graph Density: {nx.density(graph):.4f}\n\n")

                # Node types
                f.write("Node Type Distribution:\n")
                node_types: dict[str, int] = {}
                for _, data in graph.nodes(data=True):
                    node_type = data.get("type", "unknown")
                    node_types[node_type] = node_types.get(node_type, 0) + 1

                for node_type, count in sorted(node_types.items()):
                    f.write(f"  {node_type}: {count}\n")

                f.write("\n")

                # Edge types
                f.write("Edge Type Distribution:\n")
                edge_types: dict[str, int] = {}
                for _, _, data in graph.edges(data=True):
                    edge_type = data.get("type", "unknown")
                    edge_types[edge_type] = edge_types.get(edge_type, 0) + 1

                for edge_type, count in sorted(edge_types.items()):
                    f.write(f"  {edge_type}: {count}\n")

                f.write("\n")

                # Degree statistics
                degrees = [d for _, d in graph.degree()]
                if degrees:
                    f.write("Degree Statistics:\n")
                    f.write(f"  Average: {sum(degrees) / len(degrees):.2f}\n")
                    f.write(f"  Maximum: {max(degrees)}\n")
                    f.write(f"  Minimum: {min(degrees)}\n\n")

                # Most connected nodes
                f.write("Most Connected Nodes (Top 10):\n")
                top_nodes = sorted(
                    graph.degree(), key=lambda x: x[1], reverse=True
                )[:10]

                for node, degree in top_nodes:
                    node_data = graph.nodes[node]
                    label = node_data.get("product_name", str(node))
                    f.write(f"  {label} ({node}): {degree} connections\n")

            logger.info(f"Stats report saved to {output_path}")

        except Exception as e:
            logger.error(f"Error generating stats report: {e}")
