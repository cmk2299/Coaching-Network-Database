#!/usr/bin/env python3
"""
Filter network to decision makers only:
- Sporting Directors (SD)
- Geschäftsführer Sport
- Managers (Head Coaches)
- Executives in decision-making roles
"""

import json
from pathlib import Path
from datetime import datetime

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"

NETWORK_GRAPH_FILE = DATA_DIR / "network_graph.json"
DECISION_MAKERS_GRAPH_FILE = DATA_DIR / "decision_makers_network.json"
DECISION_MAKERS_GEXF_FILE = DATA_DIR / "decision_makers_network.gexf"
DECISION_MAKERS_CSV_NODES = DATA_DIR / "decision_makers_nodes.csv"
DECISION_MAKERS_CSV_EDGES = DATA_DIR / "decision_makers_edges.csv"

def is_decision_maker(node):
    """Check if node is a decision maker (strict filter)"""
    node_type = node.get('type', '').lower()
    role = node.get('current_role', '').lower()

    # ALWAYS include Sporting Directors
    if node_type == 'sporting_director':
        return True

    # Include executives with decision-making roles
    if node_type == 'executive':
        executive_roles = [
            'geschäftsführer sport',
            'sport director',
            'technical director',
            'director of football',
            'vorstand sport',
            'ceo',
            'president'
        ]
        if any(keyword in role for keyword in executive_roles):
            return True

    # Include ONLY Head Coaches/Managers (strict filter)
    if node_type == 'coach':
        # Must be "Manager" role exactly (not Assistant Manager, Kit Manager, etc.)
        if role == 'manager':
            return True
        # Also accept variations
        if role in ['head coach', 'trainer', 'cheftrainer', 'co-trainer']:
            return True
        # Check if role contains "manager" but NOT "assistant" or "kit" or "team" etc
        if 'manager' in role:
            excluded_keywords = ['assistant', 'kit', 'team', 'academy', 'performance', 'video']
            if not any(keyword in role for keyword in excluded_keywords):
                return True

    return False

def filter_network(graph):
    """Filter network to decision makers only"""
    print("\n🔍 Filtering network to decision makers...")

    # Filter nodes
    decision_maker_nodes = [
        node for node in graph['nodes']
        if is_decision_maker(node)
    ]

    # Get node IDs for filtering edges
    decision_maker_ids = set(node['id'] for node in decision_maker_nodes)

    # Filter edges - only connections between decision makers
    decision_maker_edges = [
        edge for edge in graph['edges']
        if edge['source'] in decision_maker_ids and edge['target'] in decision_maker_ids
    ]

    print(f"  ✓ Filtered from {len(graph['nodes'])} to {len(decision_maker_nodes)} nodes")
    print(f"  ✓ Filtered from {len(graph['edges'])} to {len(decision_maker_edges)} edges")

    # Calculate node type breakdown
    node_types = {}
    for node in decision_maker_nodes:
        role = node.get('current_role', 'Unknown')
        node_types[role] = node_types.get(role, 0) + 1

    print("\n  📊 Decision Makers by Role:")
    for role, count in sorted(node_types.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"    - {role}: {count}")

    return decision_maker_nodes, decision_maker_edges

def calculate_metrics(nodes, edges):
    """Calculate filtered network metrics"""
    total_nodes = len(nodes)
    total_edges = len(edges)

    # Graph density
    possible_edges = (total_nodes * (total_nodes - 1)) / 2
    density = total_edges / possible_edges if possible_edges > 0 else 0

    # Count connections per node
    connections_count = {}
    for edge in edges:
        connections_count[edge['source']] = connections_count.get(edge['source'], 0) + 1
        connections_count[edge['target']] = connections_count.get(edge['target'], 0) + 1

    avg_connections = sum(connections_count.values()) / len(connections_count) if connections_count else 0

    # Edge types
    edge_types = {}
    for edge in edges:
        rel_type = edge.get('relationship_type', 'unknown')
        edge_types[rel_type] = edge_types.get(rel_type, 0) + 1

    return {
        'total_nodes': total_nodes,
        'total_edges': total_edges,
        'graph_density': round(density, 4),
        'avg_connections_per_node': round(avg_connections, 2),
        'edge_types': edge_types,
        'generated_at': datetime.now().isoformat()
    }

def save_filtered_graph(nodes, edges, metadata):
    """Save filtered network graph"""
    print("\n💾 Saving decision makers network...")

    output = {
        'nodes': nodes,
        'edges': edges,
        'metadata': metadata
    }

    with open(DECISION_MAKERS_GRAPH_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"  ✓ JSON saved to: {DECISION_MAKERS_GRAPH_FILE}")

def export_to_gexf(nodes, edges):
    """Export to GEXF format"""
    print("\n📊 Exporting to GEXF...")

    import xml.etree.ElementTree as ET
    from xml.dom import minidom

    # Create root
    gexf = ET.Element('gexf', {
        'xmlns': 'http://www.gexf.net/1.2draft',
        'version': '1.2'
    })

    # Meta
    meta = ET.SubElement(gexf, 'meta', {
        'lastmodifieddate': datetime.now().strftime('%Y-%m-%d')
    })
    ET.SubElement(meta, 'creator').text = 'Football Coaches DB - Decision Makers'
    ET.SubElement(meta, 'description').text = 'Decision Makers Network (SDs, Managers, Executives)'

    # Graph
    graph_elem = ET.SubElement(gexf, 'graph', {
        'mode': 'static',
        'defaultedgetype': 'undirected'
    })

    # Node attributes
    attributes = ET.SubElement(graph_elem, 'attributes', {'class': 'node'})
    ET.SubElement(attributes, 'attribute', {'id': '0', 'title': 'type', 'type': 'string'})
    ET.SubElement(attributes, 'attribute', {'id': '1', 'title': 'current_club', 'type': 'string'})
    ET.SubElement(attributes, 'attribute', {'id': '2', 'title': 'current_role', 'type': 'string'})

    # Nodes
    nodes_elem = ET.SubElement(graph_elem, 'nodes')
    for node in nodes:
        node_elem = ET.SubElement(nodes_elem, 'node', {
            'id': node['id'],
            'label': node['name']
        })

        attvalues = ET.SubElement(node_elem, 'attvalues')
        ET.SubElement(attvalues, 'attvalue', {
            'for': '0',
            'value': node.get('type', '')
        })
        ET.SubElement(attvalues, 'attvalue', {
            'for': '1',
            'value': node.get('current_club', '')
        })
        ET.SubElement(attvalues, 'attvalue', {
            'for': '2',
            'value': node.get('current_role', '')
        })

    # Edges
    edges_elem = ET.SubElement(graph_elem, 'edges')
    for edge in edges:
        ET.SubElement(edges_elem, 'edge', {
            'id': str(edge['id']),
            'source': edge['source'],
            'target': edge['target'],
            'weight': str(edge.get('strength', 1))
        })

    # Pretty print and save
    xml_str = minidom.parseString(ET.tostring(gexf)).toprettyxml(indent="  ")
    with open(DECISION_MAKERS_GEXF_FILE, 'w', encoding='utf-8') as f:
        f.write(xml_str)

    print(f"  ✓ GEXF saved to: {DECISION_MAKERS_GEXF_FILE}")

def export_to_csv(nodes, edges):
    """Export to CSV"""
    print("\n📊 Exporting to CSV...")

    import csv

    # Nodes CSV
    with open(DECISION_MAKERS_CSV_NODES, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['ID', 'Name', 'Type', 'Current_Club', 'Current_Role'])

        for node in nodes:
            writer.writerow([
                node['id'],
                node['name'],
                node.get('type', ''),
                node.get('current_club', ''),
                node.get('current_role', '')
            ])

    print(f"  ✓ Nodes CSV: {DECISION_MAKERS_CSV_NODES}")

    # Edges CSV
    with open(DECISION_MAKERS_CSV_EDGES, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Source', 'Target', 'Relationship_Type', 'Strength', 'Total_Years'])

        for edge in edges:
            writer.writerow([
                edge['source'],
                edge['target'],
                edge.get('relationship_type', ''),
                edge.get('strength', 0),
                edge.get('total_years', 0)
            ])

    print(f"  ✓ Edges CSV: {DECISION_MAKERS_CSV_EDGES}")

def main():
    print("=" * 70)
    print("DECISION MAKERS NETWORK FILTER")
    print("=" * 70)

    # Load full network
    print("\n📂 Loading full network...")
    with open(NETWORK_GRAPH_FILE, 'r', encoding='utf-8') as f:
        graph = json.load(f)

    print(f"  ✓ Loaded {len(graph['nodes'])} nodes, {len(graph['edges'])} edges")

    # Filter to decision makers
    dm_nodes, dm_edges = filter_network(graph)

    # Calculate metrics
    metadata = calculate_metrics(dm_nodes, dm_edges)

    # Save filtered graph
    save_filtered_graph(dm_nodes, dm_edges, metadata)

    # Export to multiple formats
    export_to_gexf(dm_nodes, dm_edges)
    export_to_csv(dm_nodes, dm_edges)

    # Summary
    print("\n" + "=" * 70)
    print("✅ DECISION MAKERS NETWORK COMPLETE")
    print("=" * 70)
    print(f"\nNetwork Size: {metadata['total_nodes']} nodes, {metadata['total_edges']} edges")
    print(f"Graph Density: {metadata['graph_density']}")
    print(f"Avg Connections: {metadata['avg_connections_per_node']}")

    print("\n📁 Output Files:")
    print(f"  - {DECISION_MAKERS_GRAPH_FILE.name}")
    print(f"  - {DECISION_MAKERS_GEXF_FILE.name}")
    print(f"  - {DECISION_MAKERS_CSV_NODES.name}")
    print(f"  - {DECISION_MAKERS_CSV_EDGES.name}")

    # Top connections
    top_edges = sorted(dm_edges, key=lambda x: x.get('strength', 0), reverse=True)[:10]
    print("\n🔥 Top 10 Decision Maker Connections:")
    for i, edge in enumerate(top_edges, 1):
        # Find node names
        source_node = next(n for n in dm_nodes if n['id'] == edge['source'])
        target_node = next(n for n in dm_nodes if n['id'] == edge['target'])
        print(f"  {i}. {source_node['name']} ↔ {target_node['name']}")
        print(f"     Strength: {edge.get('strength', 0)} | Years: {edge.get('total_years', 0)}")

    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()
