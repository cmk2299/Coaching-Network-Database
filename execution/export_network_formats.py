#!/usr/bin/env python3
"""
Phase 5: Multi-Format Export
Export network graph to GEXF (Gephi), D3.js, and CSV formats
"""

import json
import csv
from pathlib import Path
from datetime import datetime
import xml.etree.ElementTree as ET
from xml.dom import minidom

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"

NETWORK_GRAPH_FILE = DATA_DIR / "network_graph.json"
GEXF_FILE = DATA_DIR / "network_graph.gexf"
D3_FILE = DATA_DIR / "network_graph_d3.json"
NODES_CSV_FILE = DATA_DIR / "network_nodes.csv"
EDGES_CSV_FILE = DATA_DIR / "network_edges.csv"

def load_graph():
    """Load network graph"""
    print("📂 Loading network graph...")

    with open(NETWORK_GRAPH_FILE, 'r', encoding='utf-8') as f:
        graph = json.load(f)

    print(f"  ✓ Loaded {len(graph['nodes'])} nodes, {len(graph['edges'])} edges")

    return graph

def export_to_gexf(graph):
    """Export to GEXF format for Gephi"""
    print("\n📊 Exporting to GEXF (Gephi)...")

    # Create root
    gexf = ET.Element('gexf', {
        'xmlns': 'http://www.gexf.net/1.2draft',
        'version': '1.2'
    })

    # Meta
    meta = ET.SubElement(gexf, 'meta', {
        'lastmodifieddate': datetime.now().strftime('%Y-%m-%d')
    })
    ET.SubElement(meta, 'creator').text = 'Football Coaches DB'
    ET.SubElement(meta, 'description').text = 'Coach and Executive Network'

    # Graph
    graph_elem = ET.SubElement(gexf, 'graph', {
        'mode': 'static',
        'defaultedgetype': 'undirected'
    })

    # Node attributes
    attributes = ET.SubElement(graph_elem, 'attributes', {'class': 'node'})
    ET.SubElement(attributes, 'attribute', {
        'id': '0',
        'title': 'type',
        'type': 'string'
    })
    ET.SubElement(attributes, 'attribute', {
        'id': '1',
        'title': 'current_club',
        'type': 'string'
    })
    ET.SubElement(attributes, 'attribute', {
        'id': '2',
        'title': 'current_role',
        'type': 'string'
    })

    # Nodes
    nodes_elem = ET.SubElement(graph_elem, 'nodes')
    for node in graph['nodes']:
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
    for i, edge in enumerate(graph['edges']):
        edge_id = edge.get('id', i)  # Use index as fallback ID
        ET.SubElement(edges_elem, 'edge', {
            'id': str(edge_id),
            'source': edge['source'],
            'target': edge['target'],
            'weight': str(edge.get('strength', 1))
        })

    # Pretty print and save
    xml_str = minidom.parseString(ET.tostring(gexf)).toprettyxml(indent="  ")
    with open(GEXF_FILE, 'w', encoding='utf-8') as f:
        f.write(xml_str)

    print(f"  ✓ Saved to: {GEXF_FILE}")

def export_to_d3(graph):
    """Export to D3.js format"""
    print("\n📊 Exporting to D3.js format...")

    # D3 uses simpler structure
    d3_graph = {
        'nodes': [
            {
                'id': node['id'],
                'name': node['name'],
                'group': 1 if node['type'] == 'coach' else 2,
                'type': node['type'],
                'current_club': node.get('current_club', ''),
                'current_role': node.get('current_role', '')
            }
            for node in graph['nodes']
        ],
        'links': [
            {
                'source': edge['source'],
                'target': edge['target'],
                'value': edge.get('strength', 1),
                'type': edge.get('relationship_type', '')
            }
            for edge in graph['edges']
        ]
    }

    with open(D3_FILE, 'w', encoding='utf-8') as f:
        json.dump(d3_graph, f, indent=2, ensure_ascii=False)

    print(f"  ✓ Saved to: {D3_FILE}")

def export_to_csv(graph):
    """Export to CSV format"""
    print("\n📊 Exporting to CSV (Excel/Tableau)...")

    # Nodes CSV
    with open(NODES_CSV_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)

        # Header
        writer.writerow([
            'ID',
            'Name',
            'Type',
            'Current_Club',
            'Current_Role',
            'Career_Length'
        ])

        # Data
        for node in graph['nodes']:
            writer.writerow([
                node['id'],
                node['name'],
                node.get('type', ''),
                node.get('current_club', ''),
                node.get('current_role', ''),
                node.get('career_length', 0)
            ])

    print(f"  ✓ Nodes saved to: {NODES_CSV_FILE}")

    # Edges CSV
    with open(EDGES_CSV_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)

        # Header
        writer.writerow([
            'Source',
            'Target',
            'Relationship_Type',
            'Strength',
            'Total_Clubs',
            'Total_Years'
        ])

        # Data
        for edge in graph['edges']:
            writer.writerow([
                edge['source'],
                edge['target'],
                edge.get('relationship_type', ''),
                edge.get('strength', 0),
                edge.get('total_clubs', 0),
                edge.get('total_years', 0)
            ])

    print(f"  ✓ Edges saved to: {EDGES_CSV_FILE}")

def main():
    print("=" * 70)
    print("PHASE 5: MULTI-FORMAT EXPORT")
    print("=" * 70)

    # Load graph
    graph = load_graph()

    # Export to different formats
    export_to_gexf(graph)
    export_to_d3(graph)
    export_to_csv(graph)

    # Summary
    print("\n" + "=" * 70)
    print("✅ MULTI-FORMAT EXPORT COMPLETE")
    print("=" * 70)
    print(f"\nExported Files:")
    print(f"  📊 GEXF (Gephi): {GEXF_FILE.name}")
    print(f"  📊 D3.js: {D3_FILE.name}")
    print(f"  📊 Nodes CSV: {NODES_CSV_FILE.name}")
    print(f"  📊 Edges CSV: {EDGES_CSV_FILE.name}")
    print(f"\nNetwork Stats:")
    print(f"  - Nodes: {len(graph['nodes'])}")
    print(f"  - Edges: {len(graph['edges'])}")
    print(f"  - Density: {graph['metadata']['graph_density']}")
    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()
