#!/usr/bin/env python3
"""
Remove Duplicate Edges
Keeps only one edge between each pair of nodes
"""

import json
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"

def main():
    print("=" * 70)
    print("REMOVE DUPLICATE EDGES")
    print("=" * 70)

    # Load network
    print("\n📂 Loading network...")
    with open(DATA_DIR / "network_graph.json", 'r') as f:
        network = json.load(f)

    edges = network['edges']
    print(f"  ✓ Original edges: {len(edges)}")

    # Group edges by pair
    edge_groups = defaultdict(list)
    for edge in edges:
        source, target = edge['source'], edge['target']
        sig = tuple(sorted([source, target]))
        edge_groups[sig].append(edge)

    # Deduplicate - keep the edge with highest strength or most data
    print("\n🔧 Deduplicating edges...")
    deduplicated_edges = []
    removed_count = 0

    for sig, group in edge_groups.items():
        if len(group) == 1:
            # No duplicates
            deduplicated_edges.append(group[0])
        else:
            # Multiple edges for same pair - keep best one
            # Priority: teammate > unknown
            # Then by strength

            # Sort by: 1) type priority, 2) strength
            def sort_key(edge):
                edge_type = edge.get('type', 'unknown')
                strength = edge.get('strength', 0)

                type_priority = 0 if edge_type == 'teammate' else 1

                return (type_priority, -strength)

            sorted_group = sorted(group, key=sort_key)
            best_edge = sorted_group[0]

            deduplicated_edges.append(best_edge)
            removed_count += len(group) - 1

    print(f"  ✓ Kept {len(deduplicated_edges)} edges")
    print(f"  ✓ Removed {removed_count} duplicates")

    # Update network
    network['edges'] = deduplicated_edges
    network['total_edges'] = len(deduplicated_edges)

    # Save
    print("\n💾 Saving deduplicated network...")
    output_file = DATA_DIR / "network_graph.json"
    with open(output_file, 'w') as f:
        json.dump(network, f, indent=2, ensure_ascii=False)
    print(f"  ✓ Saved to: {output_file}")

    # Summary
    print("\n" + "=" * 70)
    print("✅ DUPLICATES REMOVED")
    print("=" * 70)
    print(f"Original edges: {len(edges)}")
    print(f"Final edges: {len(deduplicated_edges)}")
    print(f"Removed: {removed_count}")
    print("=" * 70)

if __name__ == "__main__":
    main()
