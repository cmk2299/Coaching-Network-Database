#!/usr/bin/env python3
"""
Validate Classification
Comprehensive validation of node type classification and filters
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"


def load_network(filename):
    """Load network file"""
    with open(DATA_DIR / filename, 'r') as f:
        return json.load(f)


def validate_node_types(network):
    """Validate all nodes have valid type classifications"""
    print("\n📋 Validating Node Types...")

    valid_types = {
        'head_coach', 'assistant_coach', 'youth_coach',
        'scout', 'sporting_director', 'executive',
        'support_staff', 'unclassified'
    }

    errors = []
    type_counts = {}

    for node in network['nodes']:
        node_type = node.get('type')

        if not node_type:
            errors.append(f"  ❌ {node['name']}: Missing 'type' field")
        elif node_type not in valid_types:
            errors.append(f"  ❌ {node['name']}: Invalid type '{node_type}'")

        # Count
        if node_type:
            type_counts[node_type] = type_counts.get(node_type, 0) + 1

    if errors:
        print(f"  ⚠️  Found {len(errors)} errors:")
        for error in errors[:10]:
            print(error)
    else:
        print(f"  ✅ All {len(network['nodes'])} nodes have valid types")

    print("\n  Distribution:")
    for node_type in sorted(type_counts.keys()):
        print(f"    {node_type:20s}: {type_counts[node_type]:4d}")

    return len(errors) == 0


def validate_specific_classifications(network):
    """Test specific cases mentioned by user"""
    print("\n📋 Validating Specific Cases...")

    test_cases = {
        'Nils Schmadtke': {'expected_type': 'scout', 'reason': 'Head of Scouting'},
        'Niko Kovac': {'expected_type': 'head_coach', 'reason': 'Manager'},
        'Andreas Bornemann': {'expected_type': 'executive', 'reason': 'Managing Director Sport'}
    }

    all_pass = True
    node_map = {node['name']: node for node in network['nodes']}

    for name, test_case in test_cases.items():
        if name in node_map:
            node = node_map[name]
            actual_type = node.get('type')
            expected_type = test_case['expected_type']

            if actual_type == expected_type:
                print(f"  ✅ {name}: {actual_type} (correct)")
            else:
                print(f"  ❌ {name}: Expected {expected_type}, got {actual_type}")
                print(f"     Reason: {test_case['reason']}")
                all_pass = False
        else:
            print(f"  ⚠️  {name}: Not found in network")
            all_pass = False

    return all_pass


def validate_filters(filters):
    """Validate filtered networks maintain integrity"""
    print("\n📋 Validating Filtered Networks...")

    full_network = load_network('network_graph.json')
    full_node_names = {node['name'] for node in full_network['nodes']}

    all_pass = True

    for filter_name, expected_types in filters.items():
        print(f"\n  🔍 {filter_name}:")

        try:
            filtered = load_network(f'network_graph_{filter_name}.json')

            # Check all nodes have correct type
            wrong_types = []
            for node in filtered['nodes']:
                if node.get('type') not in expected_types:
                    wrong_types.append((node['name'], node.get('type')))

            if wrong_types:
                print(f"    ❌ {len(wrong_types)} nodes with wrong type:")
                for name, node_type in wrong_types[:5]:
                    print(f"       {name}: {node_type}")
                all_pass = False
            else:
                print(f"    ✅ All {len(filtered['nodes'])} nodes have correct type")

            # Check all edges reference existing nodes
            filtered_node_names = {node['name'] for node in filtered['nodes']}
            orphaned_edges = []

            for edge in filtered['edges']:
                if edge['source'] not in filtered_node_names:
                    orphaned_edges.append(f"source: {edge['source']}")
                if edge['target'] not in filtered_node_names:
                    orphaned_edges.append(f"target: {edge['target']}")

            if orphaned_edges:
                print(f"    ❌ {len(orphaned_edges)} orphaned edge references:")
                for orphan in orphaned_edges[:5]:
                    print(f"       {orphan}")
                all_pass = False
            else:
                print(f"    ✅ All {len(filtered['edges'])} edges reference existing nodes")

            # Check nodes exist in full network
            missing_nodes = filtered_node_names - full_node_names
            if missing_nodes:
                print(f"    ❌ {len(missing_nodes)} nodes not in full network:")
                for name in list(missing_nodes)[:5]:
                    print(f"       {name}")
                all_pass = False

        except FileNotFoundError:
            print(f"    ❌ File not found: network_graph_{filter_name}.json")
            all_pass = False

    return all_pass


def validate_exports():
    """Validate export files exist"""
    print("\n📋 Validating Export Files...")

    networks = ['full', 'coaches_only', 'decision_makers', 'technical_staff', 'academy']
    formats = ['gexf', 'd3.json', 'nodes.csv', 'edges.csv']

    all_exist = True

    for network_name in networks:
        base = 'network_graph' if network_name == 'full' else f'network_graph_{network_name}'

        for fmt in formats:
            if fmt == 'gexf':
                filename = f'{base}.gexf'
            elif fmt == 'd3.json':
                filename = f'{base}_d3.json'
            elif fmt == 'nodes.csv':
                filename = f'{base}_nodes.csv'
            elif fmt == 'edges.csv':
                filename = f'{base}_edges.csv'

            filepath = DATA_DIR / filename

            if filepath.exists():
                size_kb = filepath.stat().st_size / 1024
                print(f"  ✅ {filename} ({size_kb:.1f} KB)")
            else:
                print(f"  ❌ {filename} - MISSING")
                all_exist = False

    return all_exist


def validate_master_profiles():
    """Validate master profiles have node_type field"""
    print("\n📋 Validating Master Profiles...")

    with open(DATA_DIR / 'master_coach_profiles.json', 'r') as f:
        master_data = json.load(f)

    profiles = master_data.get('profiles', master_data)

    missing_type = []
    invalid_type = []

    valid_types = {
        'head_coach', 'assistant_coach', 'youth_coach',
        'scout', 'sporting_director', 'executive',
        'support_staff', 'unclassified'
    }

    for profile in profiles:
        name = profile.get('name', 'Unknown')
        node_type = profile.get('node_type')

        if not node_type:
            missing_type.append(name)
        elif node_type not in valid_types:
            invalid_type.append((name, node_type))

    if missing_type:
        print(f"  ❌ {len(missing_type)} profiles missing node_type:")
        for name in missing_type[:5]:
            print(f"     {name}")
    else:
        print(f"  ✅ All {len(profiles)} profiles have node_type field")

    if invalid_type:
        print(f"  ❌ {len(invalid_type)} profiles with invalid node_type:")
        for name, node_type in invalid_type[:5]:
            print(f"     {name}: {node_type}")

    return len(missing_type) == 0 and len(invalid_type) == 0


def main():
    print("=" * 70)
    print("CLASSIFICATION VALIDATION")
    print("=" * 70)

    # Load full network
    print("\n📂 Loading network...")
    network = load_network('network_graph.json')
    print(f"  ✓ Loaded {len(network['nodes'])} nodes, {len(network['edges'])} edges")

    # Run validations
    results = {}

    results['node_types'] = validate_node_types(network)
    results['specific_cases'] = validate_specific_classifications(network)

    # Validate filters
    filters = {
        'coaches_only': ['head_coach', 'assistant_coach'],
        'decision_makers': ['head_coach', 'sporting_director', 'executive'],
        'technical_staff': ['head_coach', 'assistant_coach', 'scout', 'support_staff'],
        'academy': ['youth_coach', 'executive']
    }
    results['filters'] = validate_filters(filters)

    results['exports'] = validate_exports()
    results['master_profiles'] = validate_master_profiles()

    # Summary
    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)

    all_pass = all(results.values())

    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {test_name:20s}: {status}")

    print("\n" + "=" * 70)
    if all_pass:
        print("🎉 ALL VALIDATIONS PASSED")
        print("=" * 70)
        print("✅ Node classification system is working correctly")
        print("✅ All filtered networks are valid")
        print("✅ All export files generated successfully")
        print("✅ Master profiles updated with node types")
    else:
        print("⚠️  SOME VALIDATIONS FAILED")
        print("=" * 70)
        print("Please review the errors above and fix them")

    print("=" * 70)

    return all_pass


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
