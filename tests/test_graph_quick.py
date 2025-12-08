#!/usr/bin/env python3
"""Quick test of Graph RAG implementation."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.graph import ChemicalGraph, GraphQueryEngine, GraphVisualizer

def main():
    print("=" * 60)
    print("Graph RAG Quick Test")
    print("=" * 60)
    
    # Test 1: Graph initialization
    print("\n[1/3] Testing ChemicalGraph initialization...")
    graph = ChemicalGraph()
    print("✓ ChemicalGraph created")
    
    # Test 2: Query engine
    print("\n[2/3] Testing GraphQueryEngine...")
    engine = GraphQueryEngine()
    print("✓ GraphQueryEngine created")
    
    # Test 3: Visualizer
    print("\n[3/3] Testing GraphVisualizer...")
    viz = GraphVisualizer()
    print("✓ GraphVisualizer created")
    
    print("\n" + "=" * 60)
    print("✅ All components initialized successfully!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Populate MRLP data (incompatibilities + hazards)")
    print("2. Run graph.build_graph() to create knowledge graph")
    print("3. Use UI Graph tab or API for queries")
    print("4. Visualize networks with graph_visualizer")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
