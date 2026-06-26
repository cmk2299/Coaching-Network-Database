#!/usr/bin/env python3
"""
Phase 4: Network Graph Construction
Build graph structure from all connections (coach-to-coach + executive connections)
"""

import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"

MASTER_PROFILES_FILE = DATA_DIR / "master_coach_profiles.json"
MASTER_CONNECTIONS_FILE = DATA_DIR / "master_connections.json"
COACH_CONNECTIONS_FILE = DATA_DIR / "coach_to_coach_connections.json"
NETWORK_GRAPH_FILE = DATA_DIR / "network_graph.json"

def load_data():
    """Load all required data files"""
    print("📂 Loading data files...")

    # Load profiles
    with open(MASTER_PROFILES_FILE, 'r', encoding='utf-8') as f:
        profiles_data = json.load(f)
        profiles = profiles_data['profiles']

    # Load existing connections (SD + Executive)
    with open(MASTER_CONNECTIONS_FILE, 'r', encoding='utf-8') as f:
        existing_conn_data = json.load(f)
        existing_connections = existing_conn_data['connections']

    # Load coach-to-coach connections
    try:
        with open(COACH_CONNECTIONS_FILE, 'r', encoding='utf-8') as f:
            coach_conn_data = json.load(f)
            coach_connections = coach_conn_data['connections']
    except FileNotFoundError:
        print("  ⚠️  Coach connections file not found yet")
        coach_connections = []

    print(f"  ✓ Loaded {len(profiles)} profiles")
    print(f"  ✓ Loaded {len(existing_connections)} existing connections")
    print(f"  ✓ Loaded {len(coach_connections)} coach-to-coach connections")

    return profiles, existing_connections, coach_connections

def create_node(person_name, person_type, profile_data=None):
    """Create a node for the graph"""
    node = {
        'id': person_name.lower().replace(' ', '_'),
        'name': person_name,
        'type': person_type
    }

    if profile_data:
        node['current_club'] = profile_data.get('current_club', 'Unknown')
        node['current_role'] = profile_data.get('current_role', 'Unknown')
        node['career_length'] = len(profile_data.get('career_history', []))

    return node

def build_graph(profiles, existing_connections, coach_connections):
    """Build network graph from all connections"""
    print("\n🕸️  Building network graph...")

    nodes = {}
    edges = []
    edge_id = 0

    # Create coach nodes from profiles
    for profile in profiles:
        name = profile['name']
        if name not in nodes:
            nodes[name] = create_node(name, 'coach', profile)

    print(f"  ✓ Created {len(nodes)} coach nodes")

    # Add edges from existing connections (SD + Executive)
    for conn in existing_connections:
        person_a = conn['person_a']
        person_b = conn['person_b']

        # Create executive/SD node if not exists
        if person_a not in nodes:
            nodes[person_a] = create_node(
                person_a,
                conn['person_a_type']
            )

        # Coach should already exist
        if person_b not in nodes:
            nodes[person_b] = create_node(
                person_b,
                conn['person_b_type']
            )

        # Create edge
        edges.append({
            'id': edge_id,
            'source': nodes[person_a]['id'],
            'target': nodes[person_b]['id'],
            'relationship_type': conn['type'],
            'strength': conn.get('strength', 0),
            'total_clubs': conn.get('total_clubs', 0),
            'total_years': conn.get('total_years', 0),
            'overlaps': conn.get('overlaps', [])
        })

        edge_id += 1

    print(f"  ✓ Added {len(existing_connections)} existing connection edges")

    # Add edges from coach-to-coach connections
    for conn in coach_connections:
        coach_a = conn['coach_a']
        coach_b = conn['coach_b']

        # Both should already exist as nodes
        if coach_a not in nodes or coach_b not in nodes:
            continue

        # Create edge
        edges.append({
            'id': edge_id,
            'source': nodes[coach_a]['id'],
            'target': nodes[coach_b]['id'],
            'relationship_type': f"coach_{conn['relationship_type']}",
            'strength': conn.get('relationship_strength', 0),
            'total_clubs': conn.get('total_clubs', 0),
            'total_years': conn.get('total_years', 0),
            'overlaps': conn.get('overlaps', [])
        })

        edge_id += 1

    print(f"  ✓ Added {len(coach_connections)} coach-to-coach edges")

    return list(nodes.values()), edges

def calculate_graph_metrics(nodes, edges):
    """Calculate graph statistics"""
    print("\n📊 Calculating graph metrics...")

    # Count connections per node
    connections_per_node = defaultdict(int)
    for edge in edges:
        connections_per_node[edge['source']] += 1
        connections_per_node[edge['target']] += 1

    # Calculate metrics
    total_nodes = len(nodes)
    total_edges = len(edges)

    # Graph density (actual edges / possible edges)
    possible_edges = (total_nodes * (total_nodes - 1)) / 2
    density = total_edges / possible_edges if possible_edges > 0 else 0

    # Average connections per node
    avg_connections = sum(connections_per_node.values()) / len(connections_per_node) if connections_per_node else 0

    # Node types
    node_types = defaultdict(int)
    for node in nodes:
        node_types[node['type']] += 1

    # Edge types
    edge_types = defaultdict(int)
    for edge in edges:
        edge_types[edge['relationship_type']] += 1

    metrics = {
        'total_nodes': total_nodes,
        'total_edges': total_edges,
        'graph_density': round(density, 4),
        'avg_connections_per_node': round(avg_connections, 2),
        'node_types': dict(node_types),
        'edge_types': dict(edge_types),
        'generated_at': datetime.now().isoformat()
    }

    print(f"  ✓ Total Nodes: {total_nodes}")
    print(f"  ✓ Total Edges: {total_edges}")
    print(f"  ✓ Graph Density: {metrics['graph_density']}")
    print(f"  ✓ Avg Connections/Node: {metrics['avg_connections_per_node']}")

    return metrics

def save_graph(nodes, edges, metadata):
    """Save network graph to JSON"""
    print("\n💾 Saving network graph...")

    output = {
        'nodes': nodes,
        'edges': edges,
        'metadata': metadata
    }

    with open(NETWORK_GRAPH_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"  ✓ Saved to: {NETWORK_GRAPH_FILE}")

def main():
    print("=" * 70)
    print("PHASE 4: NETWORK GRAPH CONSTRUCTION")
    print("=" * 70)

    # Load data
    profiles, existing_connections, coach_connections = load_data()

    # Build graph
    nodes, edges = build_graph(profiles, existing_connections, coach_connections)

    # Calculate metrics
    metadata = calculate_graph_metrics(nodes, edges)

    # Save graph
    save_graph(nodes, edges, metadata)

    # Summary
    print("\n" + "=" * 70)
    print("✅ NETWORK GRAPH CONSTRUCTION COMPLETE")
    print("=" * 70)
    print(f"Network Size: {metadata['total_nodes']} nodes, {metadata['total_edges']} edges")
    print("\nNode Types:")
    for node_type, count in metadata['node_types'].items():
        print(f"  - {node_type}: {count}")
    print("\nEdge Types:")
    for edge_type, count in metadata['edge_types'].items():
        print(f"  - {edge_type}: {count}")
    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()
