#!/usr/bin/env python3
"""
Filter Network
Creates filtered versions of the network for different analysis needs
"""

import json
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"

def filter_network(network, node_types_to_include, filter_name):
    """
    Filter network to only include specified node types

    Args:
        network: Full network dict with nodes and edges
        node_types_to_include: List of node types to keep
        filter_name: Name of the filter for metadata

    Returns:
        Filtered network dict
    """
    # Get node names that match filter
    included_nodes = set()
    for node in network['nodes']:
        if node.get('type') in node_types_to_include:
            included_nodes.add(node['name'])

    # Filter nodes
    filtered_nodes = [n for n in network['nodes'] if n['name'] in included_nodes]

    # Filter edges (only keep edges where BOTH nodes are included)
    filtered_edges = []
    for edge in network['edges']:
        if edge['source'] in included_nodes and edge['target'] in included_nodes:
            filtered_edges.append(edge)

    # Calculate statistics
    original_nodes = len(network['nodes'])
    original_edges = len(network['edges'])
    filtered_node_count = len(filtered_nodes)
    filtered_edge_count = len(filtered_edges)

    # Build filtered network
    filtered_network = {
        'nodes': filtered_nodes,
        'edges': filtered_edges,
        'metadata': {
            'filter_name': filter_name,
            'node_types_included': node_types_to_include,
            'original_nodes': original_nodes,
            'filtered_nodes': filtered_node_count,
            'nodes_kept_percentage': round((filtered_node_count / original_nodes) * 100, 2),
            'original_edges': original_edges,
            'filtered_edges': filtered_edge_count,
            'edges_kept_percentage': round((filtered_edge_count / original_edges) * 100, 2),
            'generated_at': datetime.now().isoformat(),
            'source_file': 'network_graph.json'
        },
        'total_nodes': filtered_node_count,
        'total_edges': filtered_edge_count
    }

    return filtered_network


def main():
    print("=" * 70)
    print("FILTER NETWORK")
    print("=" * 70)

    # Load reclassified network
    print("\n📂 Loading reclassified network...")
    with open(DATA_DIR / "network_graph.json", 'r') as f:
        network = json.load(f)

    print(f"  ✓ Loaded {len(network['nodes'])} nodes, {len(network['edges'])} edges")

    # Define filters
    filters = {
        'coaches_only': {
            'types': ['head_coach', 'assistant_coach'],
            'description': 'Pure coaching network (head coaches + assistants)'
        },
        'decision_makers': {
            'types': ['head_coach', 'sporting_director', 'executive'],
            'description': 'High-level decision makers'
        },
        'technical_staff': {
            'types': ['head_coach', 'assistant_coach', 'scout', 'support_staff'],
            'description': 'Complete technical team network'
        },
        'academy': {
            'types': ['youth_coach', 'executive'],  # executives include academy directors
            'description': 'Youth development network'
        }
    }

    # Create filtered versions
    print("\n🔧 Creating filtered networks...")
    results = []

    for filter_name, filter_config in filters.items():
        print(f"\n  📊 Filter: {filter_name}")
        print(f"     Types: {', '.join(filter_config['types'])}")

        # Apply filter
        filtered = filter_network(network, filter_config['types'], filter_name)

        # Add description to metadata
        filtered['metadata']['description'] = filter_config['description']

        # Save filtered network
        output_file = DATA_DIR / f"network_graph_{filter_name}.json"
        with open(output_file, 'w') as f:
            json.dump(filtered, f, indent=2, ensure_ascii=False)

        print(f"     ✓ Nodes: {filtered['metadata']['filtered_nodes']} ({filtered['metadata']['nodes_kept_percentage']}%)")
        print(f"     ✓ Edges: {filtered['metadata']['filtered_edges']} ({filtered['metadata']['edges_kept_percentage']}%)")
        print(f"     ✓ Saved: {output_file}")

        # Track results
        results.append({
            'name': filter_name,
            'description': filter_config['description'],
            'nodes': filtered['metadata']['filtered_nodes'],
            'edges': filtered['metadata']['filtered_edges'],
            'nodes_pct': filtered['metadata']['nodes_kept_percentage'],
            'edges_pct': filtered['metadata']['edges_kept_percentage']
        })

    # Summary
    print("\n" + "=" * 70)
    print("FILTER SUMMARY")
    print("=" * 70)

    print("\nOriginal Network:")
    print(f"  • Nodes: {len(network['nodes'])}")
    print(f"  • Edges: {len(network['edges'])}")

    print("\nFiltered Networks Created:")
    for result in results:
        print(f"\n  {result['name']}:")
        print(f"    Description: {result['description']}")
        print(f"    Nodes: {result['nodes']:4d} ({result['nodes_pct']:5.1f}%)")
        print(f"    Edges: {result['edges']:5d} ({result['edges_pct']:5.1f}%)")
        print(f"    File: network_graph_{result['name']}.json")

    print("\n" + "=" * 70)
    print("✅ FILTERING COMPLETE")
    print("=" * 70)
    print(f"Created {len(filters)} filtered network versions")
    print("=" * 70)


if __name__ == "__main__":
    main()
