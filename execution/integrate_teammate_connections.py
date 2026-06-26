#!/usr/bin/env python3
"""
Integrate Teammate Connections into Network
Adds teammate connections as a new edge type to the existing network
"""

import json
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"

def load_existing_network():
    """Load the network graph data"""
    print("📂 Loading existing network...")
    with open(DATA_DIR / "network_graph.json", 'r') as f:
        network = json.load(f)

    print(f"  ✓ {len(network['nodes'])} nodes")
    print(f"  ✓ {len(network['edges'])} edges")

    return network

def load_teammate_connections():
    """Load teammate connections"""
    print("\n📂 Loading teammate connections...")
    with open(DATA_DIR / "teammate_connections.json", 'r') as f:
        data = json.load(f)

    connections = data['connections']
    print(f"  ✓ {len(connections)} teammate connections")

    return connections

def integrate_connections(network, teammate_connections):
    """Add teammate connections as edges to the network"""
    print("\n🔗 Integrating teammate connections...")

    # Create name->node mapping
    node_map = {node['name']: node for node in network['nodes']}

    # Find max edge ID to continue numbering
    max_id = 0
    for edge in network['edges']:
        edge_id = edge.get('id', 0)
        if isinstance(edge_id, int):
            max_id = max(max_id, edge_id)

    added = 0
    skipped = 0
    next_id = max_id + 1

    for conn in teammate_connections:
        coach_a = conn['coach_a']
        coach_b = conn['coach_b']

        # Check if both nodes exist
        if coach_a not in node_map or coach_b not in node_map:
            skipped += 1
            continue

        # Create edge with ID
        edge = {
            'id': next_id,
            'source': coach_a,
            'target': coach_b,
            'type': 'teammate',
            'relationship': 'Played Together',
            'shared_matches': conn.get('shared_matches', 0),
            'teams_together': conn.get('teams_together', 0),
            'strength': calculate_teammate_strength(conn)
        }

        network['edges'].append(edge)
        added += 1
        next_id += 1

    print(f"  ✓ Added {added} teammate edges")
    print(f"  ⚠️  Skipped {skipped} (nodes not in network)")

    return network

def calculate_teammate_strength(connection):
    """
    Calculate connection strength for teammates
    Based on shared matches and teams
    """
    shared_matches = connection.get('shared_matches', 0)
    teams_together = connection.get('teams_together', 0)

    # Formula: (matches / 10) + (teams × 5)
    # 100 matches = 10 points, 1 team = 5 points
    strength = (shared_matches / 10) + (teams_together * 5)

    return round(strength, 1)

def main():
    print("=" * 70)
    print("INTEGRATE TEAMMATE CONNECTIONS INTO NETWORK")
    print("=" * 70)

    # Load data
    network = load_existing_network()
    teammate_connections = load_teammate_connections()

    # Integrate
    network = integrate_connections(network, teammate_connections)

    # Update metadata
    network['updated_at'] = datetime.now().isoformat()
    network['total_edges'] = len(network['edges'])

    # Count edge types
    edge_types = {}
    for edge in network['edges']:
        edge_type = edge.get('type', 'unknown')
        edge_types[edge_type] = edge_types.get(edge_type, 0) + 1

    # Save updated network
    print("\n💾 Saving updated network...")
    output_file = DATA_DIR / "network_graph_with_teammates.json"
    with open(output_file, 'w') as f:
        json.dump(network, f, indent=2, ensure_ascii=False)

    print(f"  ✓ Saved to: {output_file}")

    # Also update the main network_graph.json
    main_output = DATA_DIR / "network_graph.json"
    with open(main_output, 'w') as f:
        json.dump(network, f, indent=2, ensure_ascii=False)
    print(f"  ✓ Updated: {main_output}")

    # Summary
    print("\n" + "=" * 70)
    print("✅ TEAMMATE CONNECTIONS INTEGRATED")
    print("=" * 70)
    print(f"Total nodes: {len(network['nodes'])}")
    print(f"Total edges: {len(network['edges'])}")
    print("\nEdge types:")
    for edge_type, count in sorted(edge_types.items(), key=lambda x: x[1], reverse=True):
        print(f"  {edge_type}: {count}")
    print("=" * 70)

if __name__ == "__main__":
    main()
