#!/usr/bin/env python3
"""
Fix Network Edge Names
Converts old edge names from lowercase_underscore to Proper Case format
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"

def normalize_name(ugly_name):
    """
    Convert 'maxeberl' or 'max_eberl' to 'Max Eberl'
    """
    # Remove underscores
    name = ugly_name.replace('_', ' ')

    # Title case
    name = name.title()

    return name

def find_matching_node(normalized_name, node_map):
    """
    Find exact match in node_map (case-insensitive)
    """
    normalized_lower = normalized_name.lower()
    for node_name in node_map:
        if node_name.lower() == normalized_lower:
            return node_name
    return None

def main():
    print("=" * 70)
    print("FIX NETWORK EDGE NAMES")
    print("=" * 70)

    # Load network
    print("\n📂 Loading network...")
    with open(DATA_DIR / "network_graph.json", 'r') as f:
        network = json.load(f)

    nodes = network['nodes']
    edges = network['edges']

    print(f"  ✓ {len(nodes)} nodes")
    print(f"  ✓ {len(edges)} edges")

    # Create node name mapping
    node_map = {node['name']: node for node in nodes}
    print("  ✓ Created node map")

    # Fix edge names
    print("\n🔧 Fixing edge names...")
    fixed_count = 0
    unfixable = []

    for edge in edges:
        source = edge['source']
        target = edge['target']

        # Check if names need fixing (have underscores or are all lowercase)
        source_needs_fix = '_' in source or (source.lower() == source and ' ' not in source)
        target_needs_fix = '_' in target or (target.lower() == target and ' ' not in target)

        if source_needs_fix or target_needs_fix:
            # Try to fix source
            if source_needs_fix:
                normalized_source = normalize_name(source)
                matched_source = find_matching_node(normalized_source, node_map)

                if matched_source:
                    edge['source'] = matched_source
                    fixed_count += 1
                else:
                    unfixable.append({'original': source, 'normalized': normalized_source, 'type': 'source'})

            # Try to fix target
            if target_needs_fix:
                normalized_target = normalize_name(target)
                matched_target = find_matching_node(normalized_target, node_map)

                if matched_target:
                    edge['target'] = matched_target
                    fixed_count += 1
                else:
                    unfixable.append({'original': target, 'normalized': normalized_target, 'type': 'target'})

    print(f"  ✓ Fixed {fixed_count} edge names")

    if unfixable:
        print(f"  ⚠️  {len(unfixable)} names could not be matched")
        print("\n  Sample unfixable names:")
        for item in unfixable[:10]:
            print(f"    {item['original']} → {item['normalized']} ({item['type']})")

    # Remove self-loops
    print("\n🔧 Removing self-loops...")
    original_edge_count = len(edges)
    edges = [e for e in edges if e['source'] != e['target']]
    removed_self_loops = original_edge_count - len(edges)
    print(f"  ✓ Removed {removed_self_loops} self-loops")

    # Remove orphaned edges
    print("\n🔧 Removing orphaned edges...")
    node_name_set = set(node_map.keys())
    original_edge_count = len(edges)
    edges = [e for e in edges if e['source'] in node_name_set and e['target'] in node_name_set]
    removed_orphaned = original_edge_count - len(edges)
    print(f"  ✓ Removed {removed_orphaned} orphaned edges")

    # Update network
    network['edges'] = edges
    network['total_edges'] = len(edges)

    # Save fixed network
    print("\n💾 Saving fixed network...")
    output_file = DATA_DIR / "network_graph_fixed.json"
    with open(output_file, 'w') as f:
        json.dump(network, f, indent=2, ensure_ascii=False)
    print(f"  ✓ Saved to: {output_file}")

    # Also overwrite main file
    main_file = DATA_DIR / "network_graph.json"
    with open(main_file, 'w') as f:
        json.dump(network, f, indent=2, ensure_ascii=False)
    print(f"  ✓ Updated: {main_file}")

    # Summary
    print("\n" + "=" * 70)
    print("✅ NETWORK FIXED")
    print("=" * 70)
    print(f"Nodes: {len(nodes)}")
    print(f"Edges: {len(edges)} (removed {removed_self_loops} self-loops, {removed_orphaned} orphaned)")
    print(f"Fixed: {fixed_count} edge names")
    print("=" * 70)

if __name__ == "__main__":
    main()
