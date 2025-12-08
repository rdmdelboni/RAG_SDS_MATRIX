#!/usr/bin/env python3
"""Example: Graph RAG Usage"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.graph import ChemicalGraph, GraphQueryEngine, GraphVisualizer
from src.database import get_db_manager


def example_1_basic_graph():
    """Example 1: Build and inspect knowledge graph."""
    print("\n" + "=" * 60)
    print("Example 1: Building Knowledge Graph")
    print("=" * 60)

    graph = ChemicalGraph()
    graph.build_graph()

    stats = graph.get_graph_stats()
    print(f"\nGraph Statistics:")
    print(f"  Total nodes: {stats['nodes']}")
    print(f"  Total edges: {stats['edges']}")
    print(f"  Chemicals: {stats['chemicals']}")
    print(f"  Average degree: {stats['avg_degree']:.2f}")
    print(f"  Density: {stats['density']:.4f}")

    if stats["edge_types"]:
        print(f"\nEdge Types:")
        for edge_type, count in stats["edge_types"].items():
            print(f"  {edge_type}: {count}")


def example_2_incompatibilities():
    """Example 2: Find incompatibilities for a chemical."""
    print("\n" + "=" * 60)
    print("Example 2: Finding Incompatibilities")
    print("=" * 60)

    # Get a sample CAS from database
    db = get_db_manager()
    results = db.fetch_results()

    if not results:
        print("No chemicals in database. Please process some SDS files first.")
        return

    sample_cas = results[0].get("cas_number")
    sample_name = results[0].get("product_name", "Unknown")

    print(f"\nQuerying incompatibilities for:")
    print(f"  CAS: {sample_cas}")
    print(f"  Name: {sample_name}")

    graph = ChemicalGraph()
    graph.build_graph()

    # Direct incompatibilities (depth=1)
    incomp_1 = graph.find_incompatible_chemicals(sample_cas, max_depth=1)
    print(f"\nDirect incompatibilities (depth=1): {len(incomp_1)}")
    for cas, depth in incomp_1[:5]:  # Show first 5
        print(f"  Depth {depth}: {cas}")

    # Transitive incompatibilities (depth=2)
    incomp_2 = graph.find_incompatible_chemicals(sample_cas, max_depth=2)
    print(f"\nTransitive incompatibilities (depth=2): {len(incomp_2)}")
    for cas, depth in incomp_2[:5]:
        print(f"  Depth {depth}: {cas}")


def example_3_reaction_chains():
    """Example 3: Find reaction chains."""
    print("\n" + "=" * 60)
    print("Example 3: Finding Reaction Chains")
    print("=" * 60)

    db = get_db_manager()
    results = db.fetch_results()

    if not results:
        print("No chemicals in database.")
        return

    sample_cas = results[0].get("cas_number")

    graph = ChemicalGraph()
    graph.build_graph()

    chains = graph.find_reaction_chains(sample_cas, max_depth=3)

    print(f"\nReaction chains starting from {sample_cas}:")
    print(f"Total chains found: {len(chains)}")

    for i, chain in enumerate(chains[:5], 1):
        chain_str = " → ".join(chain)
        print(f"  Chain {i}: {chain_str}")


def example_4_sql_queries():
    """Example 4: Use SQL-based graph queries."""
    print("\n" + "=" * 60)
    print("Example 4: SQL Graph Queries (DuckDB CTEs)")
    print("=" * 60)

    db = get_db_manager()
    results = db.fetch_results()

    if not results:
        print("No chemicals in database.")
        return

    sample_cas = results[0].get("cas_number")

    engine = GraphQueryEngine()

    # Transitive incompatibilities using recursive CTE
    print(f"\nTransitive incompatibilities for {sample_cas}:")
    transitive = engine.find_transitive_incompatibilities(sample_cas, max_depth=3)
    print(f"Found {len(transitive)} results")

    for result in transitive[:5]:
        print(
            f"  {result['cas_a']} → {result['cas_b']} "
            f"(depth={result['depth']}, rule={result['rule']})"
        )

    # Chemical clusters
    print(f"\nChemical clusters (min 2 connections):")
    clusters = engine.find_chemical_clusters(min_connections=2)
    print(f"Found {len(clusters)} clusters")

    for cluster in clusters[:5]:
        print(
            f"  {cluster['cas']}: {cluster['connection_count']} connections"
        )


def example_5_visualization():
    """Example 5: Generate visualizations."""
    print("\n" + "=" * 60)
    print("Example 5: Graph Visualization")
    print("=" * 60)

    db = get_db_manager()
    results = db.fetch_results()

    if not results:
        print("No chemicals in database.")
        return

    sample_cas = results[0].get("cas_number")

    graph = ChemicalGraph()
    graph.build_graph()

    viz = GraphVisualizer()

    # Visualize incompatibility network
    output_dir = Path("data/output")
    output_dir.mkdir(exist_ok=True)

    output_path = output_dir / f"network_{sample_cas}.png"

    print(f"\nGenerating visualization for {sample_cas}...")
    print(f"Output: {output_path}")

    viz.visualize_incompatibility_network(
        graph.graph, sample_cas, depth=2, output_path=output_path
    )

    print("✓ Visualization saved")

    # Generate stats report
    stats_path = output_dir / "graph_stats.txt"
    print(f"\nGenerating statistics report...")
    print(f"Output: {stats_path}")

    viz.generate_stats_report(graph.graph, stats_path)
    print("✓ Stats report saved")


def main():
    """Run all examples."""
    print("=" * 60)
    print("Graph RAG Usage Examples")
    print("=" * 60)
    print("\nThese examples demonstrate:")
    print("  1. Building knowledge graph from database")
    print("  2. Finding incompatibilities (1-hop and multi-hop)")
    print("  3. Discovering reaction chains")
    print("  4. Using SQL recursive queries")
    print("  5. Generating visualizations")

    try:
        example_1_basic_graph()
        example_2_incompatibilities()
        example_3_reaction_chains()
        example_4_sql_queries()
        example_5_visualization()

        print("\n" + "=" * 60)
        print("✅ All examples completed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
