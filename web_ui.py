#!/usr/bin/env python3
"""Simple web UI for RAG SDS Matrix - no Qt required."""

from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from flask import Flask, render_template_string, request, jsonify
from src.database import get_db_manager
from src.graph.chemical_graph import ChemicalGraph
from src.graph.graph_queries import GraphQueryEngine

app = Flask(__name__)
db = get_db_manager()
graph = ChemicalGraph()
query_engine = GraphQueryEngine()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>RAG SDS Matrix</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #1e1e1e; color: #e0e0e0; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        header { text-align: center; margin-bottom: 30px; }
        h1 { color: #4ECDC4; margin-bottom: 10px; }
        .section { background: #2d2d2d; border-radius: 8px; padding: 20px; margin-bottom: 20px; border: 1px solid #404040; }
        .button-group { display: flex; gap: 10px; margin-bottom: 15px; flex-wrap: wrap; }
        button { 
            background: #4ECDC4; color: #1e1e1e; border: none; padding: 10px 20px; 
            border-radius: 6px; cursor: pointer; font-weight: 600; transition: all 0.3s;
        }
        button:hover { background: #45b8b0; transform: translateY(-2px); }
        input { background: #3d3d3d; color: #e0e0e0; border: 1px solid #404040; padding: 8px 12px; border-radius: 6px; width: 100%; }
        .input-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; color: #b0b0b0; font-size: 0.9em; }
        #results { 
            background: #1e1e1e; border: 1px solid #404040; border-radius: 6px; 
            padding: 15px; max-height: 400px; overflow-y: auto; font-family: monospace; font-size: 0.9em; line-height: 1.5;
        }
        .loading { color: #FFE66D; }
        .error { color: #FF6B6B; }
        .success { color: #90EE90; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🕸️ RAG SDS Matrix - Web UI</h1>
            <p>Chemical Graph & RAG Analysis</p>
        </header>

        <div class="section">
            <h2>Graph Operations</h2>
            <div class="button-group">
                <button onclick="buildGraph()">🔨 Build Knowledge Graph</button>
                <button onclick="getStats()">📊 Get Graph Stats</button>
            </div>
            <div id="graph-status" style="color: #b0b0b0;"></div>
        </div>

        <div class="section">
            <h2>Chemical Queries</h2>
            <div class="input-group">
                <label>CAS Number:</label>
                <input type="text" id="cas-input" placeholder="e.g., 67-64-1">
            </div>
            <div class="input-group">
                <label>Max Depth (1-5):</label>
                <input type="number" id="depth-input" value="2" min="1" max="5">
            </div>
            <div class="button-group">
                <button onclick="findIncompatibilities()">🔴 Find Incompatibilities</button>
                <button onclick="findChains()">⛓️ Find Reaction Chains</button>
                <button onclick="findClusters()">🎯 Find Clusters</button>
            </div>
        </div>

        <div class="section">
            <h2>Results</h2>
            <div id="results">Ready. Select an operation above.</div>
        </div>
    </div>

    <script>
        const resultsDiv = document.getElementById('results');
        
        function escapeHtml(text) {
            if (!text) return text;
            return text
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
        }

        function log(msg, type = 'info') {
            const timestamp = new Date().toLocaleTimeString();
            const className = type === 'error' ? 'error' : type === 'success' ? 'success' : 'loading';
            // Sanitize message to prevent XSS
            const safeMsg = escapeHtml(msg);
            resultsDiv.innerHTML += `<div class="${className}">[${timestamp}] ${safeMsg}</div>`;
            resultsDiv.scrollTop = resultsDiv.scrollHeight;
        }

        function buildGraph() {
            log('Building knowledge graph...');
            fetch('/api/build-graph', { method: 'POST' })
                .then(r => r.json())
                .then(data => {
                    if (data.error) log(data.error, 'error');
                    else {
                        log(`✓ Graph built: ${data.nodes} nodes, ${data.edges} edges`, 'success');
                        document.getElementById('graph-status').innerHTML = `<strong>Nodes:</strong> ${data.nodes} | <strong>Edges:</strong> ${data.edges}`;
                    }
                })
                .catch(e => log(e.message, 'error'));
        }

        function getStats() {
            log('Fetching graph statistics...');
            fetch('/api/graph-stats')
                .then(r => r.json())
                .then(data => {
                    if (data.error) log(data.error, 'error');
                    else {
                        log(`Nodes: ${data.nodes} | Edges: ${data.edges} | Density: ${data.density.toFixed(4)}`, 'success');
                    }
                })
                .catch(e => log(e.message, 'error'));
        }

        function findIncompatibilities() {
            const cas = document.getElementById('cas-input').value.trim();
            if (!cas) return log('Enter a CAS number', 'error');
            const depth = document.getElementById('depth-input').value;
            log(`Finding incompatibilities for ${cas}...`);
            fetch(`/api/incompatibilities?cas=${cas}&depth=${depth}`)
                .then(r => r.json())
                .then(data => {
                    if (data.error) log(data.error, 'error');
                    else {
                        log(`Found ${data.count} incompatibilities:`, 'success');
                        data.results.forEach(r => log(`  ${r.cas_b} (depth ${r.depth}): ${r.justification || 'N/A'}`));
                    }
                })
                .catch(e => log(e.message, 'error'));
        }

        function findChains() {
            const cas = document.getElementById('cas-input').value.trim();
            if (!cas) return log('Enter a CAS number', 'error');
            const depth = document.getElementById('depth-input').value;
            log(`Finding reaction chains for ${cas}...`);
            fetch(`/api/chains?cas=${cas}&depth=${depth}`)
                .then(r => r.json())
                .then(data => {
                    if (data.error) log(data.error, 'error');
                    else {
                        log(`Found ${data.count} chains:`, 'success');
                        data.results.slice(0, 5).forEach(chain => log(`  ${chain.join(' → ')}`));
                        if (data.count > 5) log(`  ... and ${data.count - 5} more`);
                    }
                })
                .catch(e => log(e.message, 'error'));
        }

        function findClusters() {
            log('Finding chemical clusters...');
            fetch('/api/clusters')
                .then(r => r.json())
                .then(data => {
                    if (data.error) log(data.error, 'error');
                    else {
                        log(`Found ${data.count} clusters:`, 'success');
                        data.results.slice(0, 10).forEach(c => log(`  ${c.cas}: ${c.connection_count} connections`));
                        if (data.count > 10) log(`  ... and ${data.count - 10} more`);
                    }
                })
                .catch(e => log(e.message, 'error'));
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/build-graph', methods=['POST'])
def build_graph():
    try:
        graph.build_graph()
        stats = graph.get_graph_stats()
        return jsonify({'nodes': stats['nodes'], 'edges': stats['edges']})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/graph-stats')
def graph_stats():
    try:
        if not graph._initialized:
            graph.build_graph()
        stats = graph.get_graph_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/incompatibilities')
def incompatibilities():
    try:
        cas = request.args.get('cas', '')
        depth = int(request.args.get('depth', 2))
        if not cas:
            return jsonify({'error': 'CAS number required'}), 400
        
        if not graph._initialized:
            graph.build_graph()
        
        results = graph.find_incompatible_chemicals(cas, depth)
        
        # Get justifications from DB
        details = []
        for chem, d in results:
            details.append({'cas_b': chem, 'depth': d, 'justification': 'Incompatible'})
        
        return jsonify({'count': len(details), 'results': details})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/chains')
def chains():
    try:
        cas = request.args.get('cas', '')
        depth = int(request.args.get('depth', 2))
        if not cas:
            return jsonify({'error': 'CAS number required'}), 400
        
        if not graph._initialized:
            graph.build_graph()
        
        results = graph.find_reaction_chains(cas, depth)
        return jsonify({'count': len(results), 'results': results})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/clusters')
def clusters():
    try:
        results = query_engine.find_chemical_clusters(min_connections=2)
        return jsonify({'count': len(results), 'results': results})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    print("=" * 60)
    print("  RAG SDS Matrix - Web UI")
    print("=" * 60)
    print("\nStarting server on http://localhost:5000")
    print("Open in your browser to access the interface.\n")
    app.run(host='127.0.0.1', port=5000, debug=False)
