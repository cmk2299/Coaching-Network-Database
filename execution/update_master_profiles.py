#!/usr/bin/env python3
"""
Update Master Profiles
Adds node_type and node_subcategory to master coach profiles
"""

import json
from pathlib import Path
from classify_node_types import classify_node_type, classify_subcategory

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"


def main():
    print("=" * 70)
    print("UPDATE MASTER PROFILES WITH NODE TYPES")
    print("=" * 70)

    # Load master profiles
    print("\n📂 Loading master coach profiles...")
    master_file = DATA_DIR / "master_coach_profiles.json"

    with open(master_file, 'r') as f:
        master_data = json.load(f)

    # Extract profiles list
    if isinstance(master_data, dict) and 'profiles' in master_data:
        profiles = master_data['profiles']
    else:
        profiles = master_data

    print(f"  ✓ Loaded {len(profiles)} profiles")

    # Load network to get node types
    print("\n📂 Loading network for node types...")
    with open(DATA_DIR / "network_graph.json", 'r') as f:
        network = json.load(f)

    # Create name -> node mapping
    node_map = {}
    for node in network['nodes']:
        node_map[node['name']] = {
            'type': node.get('type', 'unclassified'),
            'subcategory': node.get('subcategory', 'unclassified')
        }

    print(f"  ✓ Loaded {len(node_map)} network nodes")

    # Update profiles
    print("\n🔧 Updating profiles with node types...")
    updated_count = 0
    missing_count = 0
    classification_summary = {}

    for profile in profiles:
        name = profile['name']

        if name in node_map:
            # Get from network
            profile['node_type'] = node_map[name]['type']
            profile['node_subcategory'] = node_map[name]['subcategory']
            updated_count += 1
        else:
            # Classify from current_role
            current_role = profile.get('current_role', '')
            node_type = classify_node_type(current_role)
            subcategory = classify_subcategory(current_role, node_type)

            profile['node_type'] = node_type
            profile['node_subcategory'] = subcategory
            missing_count += 1

        # Track distribution
        node_type = profile['node_type']
        if node_type not in classification_summary:
            classification_summary[node_type] = 0
        classification_summary[node_type] += 1

    print(f"  ✓ Updated {updated_count} profiles from network")
    print(f"  ✓ Classified {missing_count} profiles from current_role")

    # Create backup
    print("\n💾 Saving updated profiles...")
    backup_file = DATA_DIR / "master_coach_profiles_before_node_types.json"
    with open(backup_file, 'w') as f:
        # Reload original to backup
        with open(master_file, 'r') as orig:
            original = json.load(orig)
        json.dump(original, f, indent=2, ensure_ascii=False)
    print(f"  ✓ Backup saved to: {backup_file}")

    # Save updated profiles (preserve original structure)
    if isinstance(master_data, dict) and 'profiles' in master_data:
        master_data['profiles'] = profiles
        output_data = master_data
    else:
        output_data = profiles

    with open(master_file, 'w') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    print(f"  ✓ Updated: {master_file}")

    # Report
    print("\n" + "=" * 70)
    print("CLASSIFICATION SUMMARY")
    print("=" * 70)

    total = len(profiles)
    for node_type in sorted(classification_summary.keys()):
        count = classification_summary[node_type]
        percentage = (count / total) * 100
        print(f"  {node_type:20s}: {count:4d} ({percentage:5.1f}%)")

    print("\n" + "-" * 70)
    print(f"  {'TOTAL':20s}: {total:4d} (100.0%)")

    # Examples
    print("\n" + "=" * 70)
    print("SAMPLE UPDATED PROFILES")
    print("=" * 70)

    for profile in profiles[:5]:
        print(f"\n  {profile['name']}")
        print(f"    Role: {profile.get('current_role', 'N/A')}")
        print(f"    Type: {profile.get('node_type', 'N/A')}")
        print(f"    Subcategory: {profile.get('node_subcategory', 'N/A')}")

    # Summary
    print("\n" + "=" * 70)
    print("✅ MASTER PROFILES UPDATED")
    print("=" * 70)
    print(f"Total profiles: {len(profiles)}")
    print(f"All profiles now have node_type and node_subcategory fields")
    print("=" * 70)


if __name__ == "__main__":
    main()
