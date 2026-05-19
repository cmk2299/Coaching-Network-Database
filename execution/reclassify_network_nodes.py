#!/usr/bin/env python3
"""
Reclassify Network Nodes
Applies node type classification to all nodes based on current_role
"""

import json
from pathlib import Path
from classify_node_types import classify_node_type, classify_subcategory, get_classification_summary

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"

def main():
    print("=" * 70)
    print("RECLASSIFY NETWORK NODES")
    print("=" * 70)

    # Load network
    print("\n📂 Loading network...")
    network_file = DATA_DIR / "network_graph.json"
    with open(network_file, 'r') as f:
        network = json.load(f)

    nodes = network['nodes']
    print(f"  ✓ Loaded {len(nodes)} nodes")

    # Initialize classification report
    classification_report = {
        'head_coach': 0,
        'assistant_coach': 0,
        'youth_coach': 0,
        'scout': 0,
        'sporting_director': 0,
        'executive': 0,
        'support_staff': 0,
        'unclassified': 0
    }

    subcategory_report = {}
    examples_per_type = {}

    # Reclassify all nodes
    print("\n🔧 Reclassifying nodes...")
    for node in nodes:
        current_role = node.get('current_role', '')

        # Classify
        node_type = classify_node_type(current_role)
        subcategory = classify_subcategory(current_role, node_type)

        # Update node
        node['type'] = node_type
        node['subcategory'] = subcategory

        # Count
        classification_report[node_type] += 1

        # Track subcategories
        if subcategory not in subcategory_report:
            subcategory_report[subcategory] = 0
        subcategory_report[subcategory] += 1

        # Save examples (first 3 per type)
        if node_type not in examples_per_type:
            examples_per_type[node_type] = []
        if len(examples_per_type[node_type]) < 3:
            examples_per_type[node_type].append({
                'name': node['name'],
                'role': current_role,
                'subcategory': subcategory
            })

    print(f"  ✓ Reclassified {len(nodes)} nodes")

    # Save updated network
    print("\n💾 Saving reclassified network...")

    # Create backup first
    backup_file = DATA_DIR / "network_graph_before_reclassification.json"
    with open(backup_file, 'w') as f:
        # Reload original to backup
        with open(network_file, 'r') as orig:
            original = json.load(orig)
        json.dump(original, f, indent=2, ensure_ascii=False)
    print(f"  ✓ Backup saved to: {backup_file}")

    # Save reclassified network
    with open(network_file, 'w') as f:
        json.dump(network, f, indent=2, ensure_ascii=False)
    print(f"  ✓ Updated: {network_file}")

    # Also save a separate copy
    reclassified_file = DATA_DIR / "network_graph_reclassified.json"
    with open(reclassified_file, 'w') as f:
        json.dump(network, f, indent=2, ensure_ascii=False)
    print(f"  ✓ Copy saved to: {reclassified_file}")

    # Print report
    print("\n" + "=" * 70)
    print("CLASSIFICATION REPORT")
    print("=" * 70)

    total = len(nodes)
    descriptions = get_classification_summary()

    print("\nNode Type Distribution:")
    print("-" * 70)
    for node_type in ['head_coach', 'assistant_coach', 'youth_coach', 'scout',
                      'sporting_director', 'executive', 'support_staff', 'unclassified']:
        count = classification_report[node_type]
        percentage = (count / total) * 100
        desc = descriptions[node_type]
        print(f"  {node_type:20s}: {count:4d} ({percentage:5.1f}%) - {desc}")

    print("\n" + "-" * 70)
    print(f"  {'TOTAL':20s}: {total:4d} (100.0%)")

    # Subcategory breakdown
    print("\n" + "=" * 70)
    print("SUBCATEGORY BREAKDOWN")
    print("=" * 70)

    for subcategory in sorted(subcategory_report.keys()):
        count = subcategory_report[subcategory]
        percentage = (count / total) * 100
        print(f"  {subcategory:30s}: {count:4d} ({percentage:5.1f}%)")

    # Examples per type
    print("\n" + "=" * 70)
    print("EXAMPLES PER TYPE")
    print("=" * 70)

    for node_type in ['head_coach', 'assistant_coach', 'youth_coach', 'scout',
                      'sporting_director', 'executive', 'support_staff', 'unclassified']:
        if node_type in examples_per_type and examples_per_type[node_type]:
            print(f"\n{node_type.upper()}:")
            for example in examples_per_type[node_type]:
                print(f"  • {example['name']}: \"{example['role']}\" → {example['subcategory']}")

    # Summary
    print("\n" + "=" * 70)
    print("✅ RECLASSIFICATION COMPLETE")
    print("=" * 70)
    print(f"Total nodes: {total}")
    print(f"Classified: {total - classification_report['unclassified']} ({((total - classification_report['unclassified']) / total * 100):.1f}%)")
    print(f"Unclassified: {classification_report['unclassified']} ({(classification_report['unclassified'] / total * 100):.1f}%)")
    print("=" * 70)

if __name__ == "__main__":
    main()
