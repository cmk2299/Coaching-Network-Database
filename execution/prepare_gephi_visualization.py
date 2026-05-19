#!/usr/bin/env python3
"""
Prepare Gephi Visualization
Creates optimized GEXF files with visual attributes for fancy Gephi visualization
"""

import json
from pathlib import Path
import xml.etree.ElementTree as ET
from xml.dom import minidom

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"


def create_fancy_gexf(network, output_file, filter_name="full"):
    """
    Create GEXF with visual attributes for Gephi
    """
    print(f"\n🎨 Creating fancy GEXF for: {filter_name}")

    # Type colors (RGB)
    type_colors = {
        'head_coach': {'r': 231, 'g': 76, 'b': 60},        # Red
        'assistant_coach': {'r': 52, 'g': 152, 'b': 219},  # Blue
        'scout': {'r': 46, 'g': 204, 'b': 113},            # Green
        'sporting_director': {'r': 241, 'g': 196, 'b': 15},  # Yellow
        'executive': {'r': 155, 'g': 89, 'b': 182},        # Purple
        'youth_coach': {'r': 230, 'g': 126, 'b': 34},      # Orange
        'support_staff': {'r': 149, 'g': 165, 'b': 166},   # Gray
        'unclassified': {'r': 127, 'g': 140, 'b': 141}     # Dark Gray
    }

    # Calculate node degrees (for size)
    node_degrees = {}
    for edge in network['edges']:
        source = edge['source']
        target = edge['target']
        node_degrees[source] = node_degrees.get(source, 0) + 1
        node_degrees[target] = node_degrees.get(target, 0) + 1

    # Create root
    gexf = ET.Element('gexf', {
        'xmlns': 'http://www.gexf.net/1.2draft',
        'xmlns:viz': 'http://www.gexf.net/1.2draft/viz',
        'version': '1.2'
    })

    # Meta
    meta = ET.SubElement(gexf, 'meta')
    ET.SubElement(meta, 'creator').text = 'Football Coaches DB'
    description = f'Football Coaches Network - {filter_name}'
    if 'metadata' in network and 'description' in network['metadata']:
        description = network['metadata']['description']
    ET.SubElement(meta, 'description').text = description

    # Graph
    graph_elem = ET.SubElement(gexf, 'graph', {
        'mode': 'static',
        'defaultedgetype': 'undirected'
    })

    # Node attributes
    node_attrs = ET.SubElement(graph_elem, 'attributes', {'class': 'node'})
    ET.SubElement(node_attrs, 'attribute', {'id': '0', 'title': 'current_role', 'type': 'string'})
    ET.SubElement(node_attrs, 'attribute', {'id': '1', 'title': 'current_club', 'type': 'string'})
    ET.SubElement(node_attrs, 'attribute', {'id': '2', 'title': 'type', 'type': 'string'})
    ET.SubElement(node_attrs, 'attribute', {'id': '3', 'title': 'subcategory', 'type': 'string'})
    ET.SubElement(node_attrs, 'attribute', {'id': '4', 'title': 'connections', 'type': 'integer'})

    # Nodes with visual attributes
    nodes_elem = ET.SubElement(graph_elem, 'nodes')

    for node in network['nodes']:
        node_type = node.get('type', 'unclassified')
        degree = node_degrees.get(node['name'], 0)

        # Node size based on connections (min 5, max 50)
        size = min(max(degree * 0.5 + 5, 5), 50)

        # Color based on type
        color = type_colors.get(node_type, type_colors['unclassified'])

        node_elem = ET.SubElement(nodes_elem, 'node', {
            'id': node['name'],
            'label': node['name']
        })

        # Visual attributes
        viz_color = ET.SubElement(node_elem, 'viz:color', {
            'r': str(color['r']),
            'g': str(color['g']),
            'b': str(color['b'])
        })

        viz_size = ET.SubElement(node_elem, 'viz:size', {
            'value': str(size)
        })

        # Node attributes
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
            'value': node_type
        })
        ET.SubElement(attvalues, 'attvalue', {
            'for': '3',
            'value': node.get('subcategory', 'unclassified')
        })
        ET.SubElement(attvalues, 'attvalue', {
            'for': '4',
            'value': str(degree)
        })

    # Edges with visual attributes
    edges_elem = ET.SubElement(graph_elem, 'edges')

    for idx, edge in enumerate(network['edges']):
        edge_id = edge.get('id', f"e{idx}")
        strength = edge.get('strength', 1.0)

        # Edge thickness based on strength (min 0.5, max 5)
        thickness = min(max(strength * 0.1, 0.5), 5)

        edge_elem = ET.SubElement(edges_elem, 'edge', {
            'id': str(edge_id),
            'source': edge['source'],
            'target': edge['target'],
            'weight': str(strength)
        })

        # Edge thickness
        ET.SubElement(edge_elem, 'viz:thickness', {
            'value': str(thickness)
        })

        # Edge color (light gray, semi-transparent)
        ET.SubElement(edge_elem, 'viz:color', {
            'r': '150',
            'g': '150',
            'b': '150',
            'a': '0.3'
        })

    # Pretty print and save
    xml_str = minidom.parseString(ET.tostring(gexf)).toprettyxml(indent="  ")

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(xml_str)

    print(f"  ✓ Nodes: {len(network['nodes'])}")
    print(f"  ✓ Edges: {len(network['edges'])}")
    print(f"  ✓ Saved: {output_file.name}")


def main():
    print("=" * 70)
    print("PREPARE FANCY GEPHI VISUALIZATIONS")
    print("=" * 70)

    # Networks to create fancy versions for
    networks = [
        ('network_graph.json', 'full', 'Full Network'),
        ('network_graph_coaches_only.json', 'coaches_only', 'Coaches Only'),
        ('network_graph_decision_makers.json', 'decision_makers', 'Decision Makers'),
        ('network_graph_technical_staff.json', 'technical_staff', 'Technical Staff'),
        ('network_graph_academy.json', 'academy', 'Academy Network')
    ]

    for filename, filter_name, display_name in networks:
        graph_file = DATA_DIR / filename

        if not graph_file.exists():
            print(f"\n⚠️  Skipping {display_name}: File not found")
            continue

        # Load network
        with open(graph_file, 'r', encoding='utf-8') as f:
            network = json.load(f)

        # Output file
        output_file = DATA_DIR / f"gephi_{filter_name}.gexf"

        # Create fancy GEXF
        create_fancy_gexf(network, output_file, display_name)

    # Instructions
    print("\n" + "=" * 70)
    print("✅ FANCY GEXF FILES CREATED")
    print("=" * 70)
    print("\n📖 HOW TO USE IN GEPHI:\n")
    print("1. Download Gephi: https://gephi.org/")
    print("2. Open Gephi → File → Open → Select a .gexf file from data/")
    print("\n3. RECOMMENDED SETTINGS FOR FANCY LOOK:")
    print("   ")
    print("   LAYOUT:")
    print("   • Use 'ForceAtlas 2' or 'Yifan Hu'")
    print("   • Settings: Gravity 1.0, Prevent Overlap: ON")
    print("   • Run for 30-60 seconds until stable")
    print("   ")
    print("   APPEARANCE:")
    print("   • Nodes already colored by type!")
    print("   • Nodes already sized by connections!")
    print("   • You can adjust in Appearance tab if needed")
    print("   ")
    print("   FILTERS:")
    print("   • Topology → Degree Range (show only highly connected)")
    print("   • Attributes → Type (filter by node type)")
    print("   ")
    print("   PREVIEW:")
    print("   • Switch to Preview tab")
    print("   • Preset: 'Default Straight'")
    print("   • Node Labels: Show (font size 8-12)")
    print("   • Edge Thickness: Proportional")
    print("   • Background: Dark (#1a1a1a) or White")
    print("   ")
    print("4. RECOMMENDED NETWORKS TO START:")
    print("   • 'gephi_coaches_only.gexf' - Most focused (196 nodes)")
    print("   • 'gephi_decision_makers.gexf' - Executive level (95 nodes)")
    print("   ")
    print("5. EXPORT:")
    print("   • File → Export → PDF/PNG/SVG")
    print("   • For presentations: SVG (vector, scalable)")
    print("   • For quick share: PNG (4096x4096px)")
    print("\n" + "=" * 70)
    print("\n🎨 COLOR LEGEND:")
    print("   🔴 Red    = Head Coach")
    print("   🔵 Blue   = Assistant Coach")
    print("   🟢 Green  = Scout")
    print("   🟡 Yellow = Sporting Director")
    print("   🟣 Purple = Executive")
    print("   🟠 Orange = Youth Coach")
    print("   ⚪ Gray   = Support Staff")
    print("=" * 70)


if __name__ == "__main__":
    main()
