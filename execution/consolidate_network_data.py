#!/usr/bin/env python3
"""
Phase 2: Data Consolidation
Consolidate all coach profiles and existing connections into master files
"""

import json
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
PRELOADED_DIR = PROJECT_ROOT / "tmp" / "preloaded"
DATA_DIR = PROJECT_ROOT / "data"

# Output files
MASTER_PROFILES_FILE = DATA_DIR / "master_coach_profiles.json"
MASTER_CONNECTIONS_FILE = DATA_DIR / "master_connections.json"

def normalize_club_name(club_name):
    """Normalize club names for matching"""
    if not club_name:
        return ""

    # Common normalizations
    normalizations = {
        "FC Bayern München": "Bayern Munich",
        "FC Bayern Munchen": "Bayern Munich",
        "Bor. Dortmund": "Borussia Dortmund",
        "Borussia Dortmund": "Dortmund",
        "BVB": "Dortmund",
        "RB Leipzig": "RB Leipzig",
        "Bayer Leverkusen": "Bayer 04 Leverkusen",
        "Leverkusen": "Bayer 04 Leverkusen",
        "VfB Stuttgart": "Stuttgart",
        "Eintracht Frankfurt": "Frankfurt",
        "SC Freiburg": "Freiburg",
        "FC St. Pauli": "St. Pauli",
        "1. FC Heidenheim": "Heidenheim",
        "TSG Hoffenheim": "Hoffenheim",
        "VfL Wolfsburg": "Wolfsburg",
        "Werder Bremen": "Bremen",
        "Borussia Mönchengladbach": "Mönchengladbach",
        "1. FC Union Berlin": "Union Berlin",
        "Holstein Kiel": "Kiel",
        "1. FC Köln": "Köln",
        "VfL Bochum": "Bochum"
    }

    # Check if exact match exists
    if club_name in normalizations:
        return normalizations[club_name]

    # Otherwise return simplified version
    name = club_name.strip()
    # Remove common prefixes
    name = re.sub(r'^(FC|1\.|VfL|VfB|TSG|SC)\s+', '', name)
    return name

def load_all_coach_profiles():
    """Load all coach profiles from tmp/preloaded/*.json"""
    print("📂 Loading coach profiles...")

    profiles = []
    json_files = sorted(PRELOADED_DIR.glob("*.json"))

    with_career = 0
    without_career = 0

    for file_path in json_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

                # Skip if no name or URL
                if not data.get('name') or not data.get('url'):
                    continue

                # Track career history status
                career_count = len(data.get('career_history', []))
                if career_count > 0:
                    with_career += 1
                else:
                    without_career += 1

                profiles.append(data)

        except Exception as e:
            print(f"  ⚠️  Error loading {file_path.name}: {e}")
            continue

    print(f"  ✓ Loaded {len(profiles)} profiles")
    print(f"    - With career data: {with_career}")
    print(f"    - Without career data: {without_career}")

    return profiles

def load_existing_connections():
    """Load existing SD/Executive overlap data (using FIXED versions)"""
    print("\n📂 Loading existing connections...")

    connections = []

    # Load FIXED SD ↔ Coach overlaps
    sd_coach_file = DATA_DIR / "sd_coach_overlaps_fixed.json"
    if sd_coach_file.exists():
        with open(sd_coach_file, 'r', encoding='utf-8') as f:
            sd_data = json.load(f)

        for rel in sd_data.get('connections', []):
            connections.append({
                'type': 'sd_coach',
                'person_a': rel['sd_name'],
                'person_a_type': 'sporting_director',
                'person_b': rel['coach_name'],
                'person_b_type': 'coach',
                'overlaps': rel.get('overlaps', []),
                'strength': rel.get('relationship_strength', 0),
                'total_clubs': rel.get('total_clubs', 0),
                'total_years': rel.get('total_years', 0)
            })

        print(f"  ✓ Loaded {len(sd_data.get('connections', []))} SD ↔ Coach connections (FIXED)")
    else:
        print(f"  ⚠️  No fixed SD overlaps found, skipping")

    # Load FIXED Executive ↔ Coach overlaps (filter to top connections only)
    exec_coach_file = DATA_DIR / "executive_coach_overlaps_fixed.json"
    if exec_coach_file.exists():
        with open(exec_coach_file, 'r', encoding='utf-8') as f:
            exec_data = json.load(f)

        # Filter: Only include connections with strength > 20 (to avoid noise)
        filtered_exec = [
            rel for rel in exec_data.get('connections', [])
            if rel.get('relationship_strength', 0) > 20
        ]

        for rel in filtered_exec:
            connections.append({
                'type': 'executive_coach',
                'person_a': rel['exec_name'],
                'person_a_type': 'executive',
                'person_a_category': rel.get('exec_category', 'Unknown'),
                'person_b': rel['coach_name'],
                'person_b_type': 'coach',
                'overlaps': rel.get('overlaps', []),
                'strength': rel.get('relationship_strength', 0),
                'total_clubs': rel.get('total_clubs', 0),
                'total_years': rel.get('total_years', 0)
            })

        print(f"  ✓ Loaded {len(filtered_exec)} Executive ↔ Coach connections (FIXED, filtered)")
    else:
        print(f"  ⚠️  No fixed executive overlaps found, skipping")

    print(f"  Total existing connections: {len(connections)}")

    return connections

def deduplicate_profiles(profiles):
    """Remove duplicate coaches (same name or URL)"""
    print("\n🔍 Deduplicating profiles...")

    seen_urls = set()
    seen_names = set()
    unique_profiles = []

    for profile in profiles:
        url = profile.get('url', '')
        name = profile.get('name', '').lower().strip()

        # Skip if we've seen this URL or name
        if url in seen_urls or name in seen_names:
            continue

        seen_urls.add(url)
        seen_names.add(name)
        unique_profiles.append(profile)

    duplicates = len(profiles) - len(unique_profiles)
    print(f"  ✓ Removed {duplicates} duplicates")
    print(f"  ✓ {len(unique_profiles)} unique profiles")

    return unique_profiles

def save_master_profiles(profiles):
    """Save consolidated master profile file"""
    print(f"\n💾 Saving master profiles...")

    output = {
        'generated_at': datetime.now().isoformat(),
        'total_profiles': len(profiles),
        'profiles_with_career': sum(1 for p in profiles if len(p.get('career_history', [])) > 0),
        'profiles': profiles
    }

    with open(MASTER_PROFILES_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"  ✓ Saved to: {MASTER_PROFILES_FILE}")

def save_master_connections(connections):
    """Save consolidated master connections file"""
    print(f"\n💾 Saving master connections...")

    output = {
        'generated_at': datetime.now().isoformat(),
        'total_connections': len(connections),
        'connection_types': {
            'sd_coach': sum(1 for c in connections if c['type'] == 'sd_coach'),
            'executive_coach': sum(1 for c in connections if c['type'] == 'executive_coach')
        },
        'connections': connections
    }

    with open(MASTER_CONNECTIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"  ✓ Saved to: {MASTER_CONNECTIONS_FILE}")

def main():
    print("=" * 70)
    print("PHASE 2: DATA CONSOLIDATION")
    print("=" * 70)

    # Step 1: Load all coach profiles
    profiles = load_all_coach_profiles()

    # Step 2: Load existing connections
    connections = load_existing_connections()

    # Step 3: Deduplicate
    unique_profiles = deduplicate_profiles(profiles)

    # Step 4: Save master files
    save_master_profiles(unique_profiles)
    save_master_connections(connections)

    # Summary
    print("\n" + "=" * 70)
    print("✅ DATA CONSOLIDATION COMPLETE")
    print("=" * 70)
    print(f"Master Profiles: {len(unique_profiles)}")
    print(f"  - With career data: {sum(1 for p in unique_profiles if len(p.get('career_history', [])) > 0)}")
    print(f"  - Without career data: {sum(1 for p in unique_profiles if len(p.get('career_history', [])) == 0)}")
    print(f"\nExisting Connections: {len(connections)}")
    print(f"  - SD ↔ Coach: {sum(1 for c in connections if c['type'] == 'sd_coach')}")
    print(f"  - Executive ↔ Coach: {sum(1 for c in connections if c['type'] == 'executive_coach')}")
    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()
