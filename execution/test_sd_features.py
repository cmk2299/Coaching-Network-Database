#!/usr/bin/env python3
"""
Test script for Sportdirektor-Coach relationship features.

Demonstrates the new Trainerberater use cases:
1. "Wer kennt meinen Trainer?" - Find SD connections
2. "Welcher SD hired welchen Trainer-Typ?" - SD hiring patterns
3. "Welche SDs passen zu meinem Trainer?" - Reverse search
"""

from coach_db import get_db

def test_sd_connections():
    """Test: Find all SDs connected to a coach."""
    print("\n" + "="*70)
    print("TEST 1: Wer kennt Alexander Blessin?")
    print("="*70)

    db = get_db()

    # Assuming Blessin has tm_id 26099
    connections = db.find_sd_connections_for_coach(26099)

    print(f"\n🟢 EXISTING RELATIONSHIPS ({len(connections['existing'])})")
    for conn in connections['existing']:
        status = "✅ CURRENT" if conn['status'] == 'active' else "🔄 PAST"
        print(f"\n{status}: {conn['sd_name']}")
        print(f"   Role: {conn['current_role']}")
        print(f"   Club: {conn['current_club']}")
        print(f"   Worked together: {conn['worked_at']} ({conn['period_start']}-{conn['period_end'] or 'present'})")
        if conn['outcome']:
            print(f"   Outcome: {conn['outcome']}")
        if conn['notes']:
            print(f"   Notes: {conn['notes']}")
        print(f"   📞 Contact type: {'WARM' if conn['status'] == 'active' else 'WARM (past collaboration)'}")

    print(f"\n🟡 INDIRECT CONNECTIONS ({len(connections['indirect'])})")
    for conn in connections['indirect']:
        print(f"  - {conn['sd_name']} via {conn['connection_path']}")

def test_sd_hiring_pattern():
    """Test: What type of coaches does an SD hire?"""
    print("\n" + "="*70)
    print("TEST 2: Welchen Trainer-Typ hired Andreas Bornemann?")
    print("="*70)

    db = get_db()

    coaches = db.find_coaches_for_sd("Andreas Bornemann")

    print(f"\n📊 HIRING HISTORY ({len(coaches)} coaches hired)\n")

    for i, coach in enumerate(coaches, 1):
        print(f"{i}. {coach['coach_name']}")
        print(f"   Nationality: {coach['nationality']}")
        print(f"   License: {coach['license_level']}")
        print(f"   Period: {coach['period_start']}-{coach['period_end'] or 'present'}")
        print(f"   Club: {coach['club_name']}")
        if coach['outcome']:
            print(f"   Outcome: {coach['outcome']}")
        if coach['notes']:
            print(f"   Context: {coach['notes']}")
        print()

    # Analyze pattern
    if coaches:
        nationalities = [c['nationality'] for c in coaches if c['nationality']]
        licenses = [c['license_level'] for c in coaches if c['license_level']]

        print("💡 PATTERN ANALYSIS:")
        if nationalities:
            from collections import Counter
            nat_counts = Counter(nationalities)
            print(f"   Preferred nationalities: {', '.join(f'{k} ({v}x)' for k, v in nat_counts.most_common())}")

        if licenses:
            license_counts = Counter(licenses)
            print(f"   License levels: {', '.join(f'{k} ({v}x)' for k, v in license_counts.most_common())}")

        outcomes = [c['outcome'] for c in coaches if c['outcome']]
        if outcomes:
            success_count = sum(1 for o in outcomes if 'Promot' in o or 'Success' in o)
            print(f"   Success rate: {success_count}/{len(outcomes)} ({success_count/len(outcomes)*100:.0f}%)")

def test_reverse_search():
    """Test: Which SDs hire coaches like mine?"""
    print("\n" + "="*70)
    print("TEST 3: Welche SDs hired deutsche Trainer mit UEFA Pro?")
    print("="*70)

    db = get_db()

    sds = db.find_matching_sds_for_coach_profile(
        nationality="Deutschland",
        license_level="UEFA-Pro-Lizenz"
    )

    print(f"\n🎯 MATCHING SPORTDIREKTOREN ({len(sds)} found)\n")

    for i, sd in enumerate(sds, 1):
        print(f"{i}. {sd['sd_name']} @ {sd['current_club']}")
        print(f"   Hired {sd['coaches_hired']} matching coaches")
        print(f"   Success rate: {sd['success_rate']*100:.0f}%")
        print(f"   Coaches: {sd['coaches_list']}")
        print(f"   📞 Recommendation: {'STRONG FIT' if sd['success_rate'] > 0.5 else 'POTENTIAL FIT'}")
        print()

def main():
    """Run all tests."""
    print("\n" + "🎯"*35)
    print("SPORTDIREKTOR-COACH RELATIONSHIP TESTS")
    print("For Trainerberater use cases")
    print("🎯"*35)

    # Check if database exists and has data
    db = get_db()

    try:
        test_sd_connections()
    except Exception as e:
        print(f"\n⚠️  Test 1 failed: {e}")
        print("   Make sure to run migrate_decision_makers_to_db.py first")

    try:
        test_sd_hiring_pattern()
    except Exception as e:
        print(f"\n⚠️  Test 2 failed: {e}")

    try:
        test_reverse_search()
    except Exception as e:
        print(f"\n⚠️  Test 3 failed: {e}")

    print("\n" + "="*70)
    print("✅ Tests complete!")
    print("="*70)

if __name__ == "__main__":
    main()
