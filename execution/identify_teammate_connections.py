#!/usr/bin/env python3
"""
Identify Teammate Connections
Finds coaches who played together as teammates
"""

import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"

def load_teammates_data():
    """Load bulk teammates data"""
    print("📂 Loading teammates data...")
    with open(DATA_DIR / "teammates_bulk.json", 'r') as f:
        data = json.load(f)

    print(f"  ✓ Loaded {data['total_scraped']} coaches")
    print(f"  ✓ {data['with_teammates']} have teammate data")
    print(f"  ✓ {data['total_teammates_found']} total teammates")

    return data['coaches']

def load_master_profiles():
    """Load master coach profiles for name matching"""
    print("\n📂 Loading master profiles...")
    with open(DATA_DIR / "master_coach_profiles.json", 'r') as f:
        data = json.load(f)

    profiles = data['profiles']
    print(f"  ✓ Loaded {len(profiles)} profiles")

    # Create name->profile mapping
    name_map = {}
    url_map = {}

    for profile in profiles:
        name = profile.get('name', '').strip()
        url = profile.get('url', '')

        if name:
            name_map[name.lower()] = profile
        if url:
            # Extract ID from URL
            if '/trainer/' in url:
                coach_id = url.split('/trainer/')[1].split('/')[0]
                url_map[coach_id] = profile

    return name_map, url_map

def identify_teammate_overlaps(coaches_data, name_map, url_map):
    """
    Identify which coaches were teammates (played together)

    Logic:
    - For each coach A, get their teammates list
    - For each teammate, check if that person is also a coach in our database
    - If yes, that's a connection: Coach A ↔ Coach B (played together)
    """
    print("\n🔍 Identifying teammate connections...")

    connections = []
    coach_connections_count = defaultdict(int)

    # Build reverse index: teammate_name -> list of coaches who played with them
    teammate_to_coaches = defaultdict(list)

    for coach_data in coaches_data:
        if not coach_data.get('has_teammates'):
            continue

        coach_name = coach_data.get('name')
        coach_id = coach_data.get('player_id')

        teammates = coach_data.get('teammates', [])

        for tm in teammates:
            tm_name = tm.get('name', '').strip()
            tm_url = tm.get('url', '')
            shared_matches = tm.get('shared_matches', 0)
            teams_together = tm.get('teams_together', 0)

            if not tm_name:
                continue

            # Check if this teammate is also a coach in our database
            # Try matching by name first
            tm_profile = name_map.get(tm_name.lower())

            # Try matching by URL if name didn't work
            if not tm_profile and tm_url and '/spieler/' in tm_url:
                tm_id = tm_url.split('/spieler/')[1].split('/')[0]
                tm_profile = url_map.get(tm_id)

            if tm_profile:
                # This teammate is also a coach!
                teammate_coach_name = tm_profile.get('name')

                # Avoid duplicates (A->B and B->A)
                pair = tuple(sorted([coach_name, teammate_coach_name]))

                # Check if we already recorded this connection
                existing = next((c for c in connections if
                               tuple(sorted([c['coach_a'], c['coach_b']])) == pair), None)

                if not existing:
                    connection = {
                        'coach_a': coach_name,
                        'coach_b': teammate_coach_name,
                        'shared_matches': shared_matches,
                        'teams_together': teams_together,
                        'connection_type': 'teammates',
                        'relationship': 'Played Together'
                    }
                    connections.append(connection)
                    coach_connections_count[coach_name] += 1
                    coach_connections_count[teammate_coach_name] += 1

    print(f"  ✓ Found {len(connections)} teammate connections")
    print(f"  ✓ {len(coach_connections_count)} coaches have teammate connections")

    return connections, coach_connections_count

def main():
    print("=" * 70)
    print("IDENTIFY TEAMMATE CONNECTIONS")
    print("=" * 70)

    # Load data
    coaches_data = load_teammates_data()
    name_map, url_map = load_master_profiles()

    # Identify connections
    connections, coach_connections_count = identify_teammate_overlaps(
        coaches_data, name_map, url_map
    )

    # Sort by shared matches
    connections.sort(key=lambda x: x['shared_matches'], reverse=True)

    # Save results
    print(f"\n💾 Saving results...")
    output = {
        'generated_at': datetime.now().isoformat(),
        'total_connections': len(connections),
        'coaches_with_connections': len(coach_connections_count),
        'connections': connections
    }

    output_file = DATA_DIR / "teammate_connections.json"
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"  ✓ Saved to: {output_file}")

    # Statistics
    print("\n" + "=" * 70)
    print("✅ TEAMMATE CONNECTIONS IDENTIFIED")
    print("=" * 70)
    print(f"Total connections: {len(connections)}")
    print(f"Coaches with teammate connections: {len(coach_connections_count)}")

    if connections:
        print(f"\nTop 10 strongest connections (by shared matches):")
        for i, conn in enumerate(connections[:10], 1):
            print(f"  {i}. {conn['coach_a']} ↔ {conn['coach_b']}")
            print(f"     {conn['shared_matches']} matches, {conn['teams_together']} teams")

    # Distribution
    if coach_connections_count:
        connections_list = list(coach_connections_count.values())
        avg_connections = sum(connections_list) / len(connections_list)
        max_connections = max(connections_list)

        print(f"\nConnection distribution:")
        print(f"  Average: {avg_connections:.1f} connections per coach")
        print(f"  Max: {max_connections} connections")

        # Find coach with most connections
        top_coach = max(coach_connections_count.items(), key=lambda x: x[1])
        print(f"  Most connected: {top_coach[0]} ({top_coach[1]} connections)")

    print("=" * 70)

if __name__ == "__main__":
    main()
