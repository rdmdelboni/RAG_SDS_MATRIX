## 2025-12-14 - Graph Traversal Optimization
**Learning:** `nx.all_simple_paths` on a NetworkX `MultiDiGraph` is extremely expensive when filtering post-hoc because it explores *all* valid paths between nodes, regardless of edge attributes. Even in small graphs (20 nodes) with high connectivity (e.g., product family links), this can lead to O(N!) complexity.
**Action:** When filtering paths by edge type in a multi-graph, always implement a custom traversal (DFS/BFS) that checks edge attributes *during* exploration to prune the search space early.
