#!/usr/bin/env python3
"""
Export Filtered Networks
Exports all filtered networks to GEXF, D3.js, and CSV formats
"""

import json
import csv
from pathlib import Path
from datetime import datetime
import xml.etree.ElementTree as ET
from xml.dom import minidom

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"


def export_to_gexf(graph, output_file, filter_name="full"):
    """Export to GEXF format for Gephi"""
    print(f"  📊 Exporting to GEXF...")

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

    description = f"Football Coaches Network - {filter_name} filter"
    if 'metadata' in graph and 'description' in graph['metadata']:
        description = graph['metadata']['description']
    ET.SubElement(meta, 'description').text = description

    # Graph
    graph_elem = ET.SubElement(gexf, 'graph', {
        'mode': 'static',
        'defaultedgetype': 'undirected'
    })

    # Attributes for nodes
    attrs = ET.SubElement(graph_elem, 'attributes', {'class': 'node'})
    ET.SubElement(attrs, 'attribute', {'id': '0', 'title': 'current_role', 'type': 'string'})
    ET.SubElement(attrs, 'attribute', {'id': '1', 'title': 'current_club', 'type': 'string'})
    ET.SubElement(attrs, 'attribute', {'id': '2', 'title': 'type', 'type': 'string'})
    ET.SubElement(attrs, 'attribute', {'id': '3', 'title': 'subcategory', 'type': 'string'})

    # Nodes
    nodes_elem = ET.SubElement(graph_elem, 'nodes')
    for node in graph['nodes']:
        node_elem = ET.SubElement(nodes_elem, 'node', {
            'id': node['name'],
            'label': node['name']
        })

        # Attributes
        attvalues = ET.SubElement(node_elem, 'attvalues')
        ET.SubElement(attvalues, 'attvalue', {
            'for': '0',
            'value': node.get('current_role', '')
        })
        ET.SubElement(attvalues, 'attvalue', {
            'for': '1',
            'value': node.get('current_club', '')
        })
        ET.SubElement(attvalues, 'attvalue', {
            'for': '2',
            'value': node.get('type', 'unclassified')
        })
        ET.SubElement(attvalues, 'attvalue', {
            'for': '3',
            'value': node.get('subcategory', 'unclassified')
        })

    # Edges
    edges_elem = ET.SubElement(graph_elem, 'edges')
    for idx, edge in enumerate(graph['edges']):
        edge_id = edge.get('id', f"e{idx}")
        edge_elem = ET.SubElement(edges_elem, 'edge', {
            'id': str(edge_id),
            'source': edge['source'],
            'target': edge['target'],
            'weight': str(edge.get('strength', 1.0))
        })

    # Pretty print
    xml_str = minidom.parseString(ET.tostring(gexf)).toprettyxml(indent="  ")

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(xml_str)

    print(f"     ✓ Saved to: {output_file}")


def export_to_d3(graph, output_file, filter_name="full"):
    """Export to D3.js format"""
    print(f"  📊 Exporting to D3.js...")

    d3_graph = {
        'nodes': [],
        'links': []
    }

    # Convert nodes
    for node in graph['nodes']:
        d3_graph['nodes'].append({
            'id': node['name'],
            'name': node['name'],
            'current_role': node.get('current_role', ''),
            'current_club': node.get('current_club', ''),
            'type': node.get('type', 'unclassified'),
            'subcategory': node.get('subcategory', 'unclassified')
        })

    # Convert edges
    for edge in graph['edges']:
        d3_graph['links'].append({
            'source': edge['source'],
            'target': edge['target'],
            'strength': edge.get('strength', 1.0),
            'type': edge.get('type', 'unknown')
        })

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(d3_graph, f, indent=2, ensure_ascii=False)

    print(f"     ✓ Saved to: {output_file}")


def export_to_csv(graph, nodes_file, edges_file, filter_name="full"):
    """Export to CSV format"""
    print(f"  📊 Exporting to CSV...")

    # Export nodes
    with open(nodes_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'name', 'current_role', 'current_club', 'type', 'subcategory'
        ])
        writer.writeheader()

        for node in graph['nodes']:
            writer.writerow({
                'name': node['name'],
                'current_role': node.get('current_role', ''),
                'current_club': node.get('current_club', ''),
                'type': node.get('type', 'unclassified'),
                'subcategory': node.get('subcategory', 'unclassified')
            })

    print(f"     ✓ Nodes CSV: {nodes_file}")

    # Export edges
    with open(edges_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'source', 'target', 'strength', 'type'
        ])
        writer.writeheader()

        for edge in graph['edges']:
            writer.writerow({
                'source': edge['source'],
                'target': edge['target'],
                'strength': edge.get('strength', 1.0),
                'type': edge.get('type', 'unknown')
            })

    print(f"     ✓ Edges CSV: {edges_file}")


def export_all_formats(graph_file, filter_name):
    """Export a single network to all formats"""
    print(f"\n🔧 Processing: {filter_name}")

    # Load graph
    with open(graph_file, 'r', encoding='utf-8') as f:
        graph = json.load(f)

    nodes = len(graph['nodes'])
    edges = len(graph['edges'])
    print(f"     Network: {nodes} nodes, {edges} edges")

    # Define output files
    base_name = f"network_graph_{filter_name}" if filter_name != "full" else "network_graph"
    gexf_file = DATA_DIR / f"{base_name}.gexf"
    d3_file = DATA_DIR / f"{base_name}_d3.json"
    nodes_csv = DATA_DIR / f"{base_name}_nodes.csv"
    edges_csv = DATA_DIR / f"{base_name}_edges.csv"

    # Export to all formats
    export_to_gexf(graph, gexf_file, filter_name)
    export_to_d3(graph, d3_file, filter_name)
    export_to_csv(graph, nodes_csv, edges_csv, filter_name)


def main():
    print("=" * 70)
    print("EXPORT FILTERED NETWORKS")
    print("=" * 70)

    # Define all networks to export
    networks_to_export = [
        ('network_graph.json', 'full'),
        ('network_graph_coaches_only.json', 'coaches_only'),
        ('network_graph_decision_makers.json', 'decision_makers'),
        ('network_graph_technical_staff.json', 'technical_staff'),
        ('network_graph_academy.json', 'academy')
    ]

    # Export each network
    for filename, filter_name in networks_to_export:
        graph_file = DATA_DIR / filename
        if graph_file.exists():
            export_all_formats(graph_file, filter_name)
        else:
            print(f"\n⚠️  Skipping {filter_name}: File not found")

    # Summary
    print("\n" + "=" * 70)
    print("✅ EXPORT COMPLETE")
    print("=" * 70)
    print(f"Exported {len([f for f, _ in networks_to_export if (DATA_DIR / f).exists()])} networks to:")
    print("  • GEXF (Gephi visualization)")
    print("  • D3.js (web visualization)")
    print("  • CSV (Excel/Tableau analysis)")
    print("=" * 70)


if __name__ == "__main__":
    main()
