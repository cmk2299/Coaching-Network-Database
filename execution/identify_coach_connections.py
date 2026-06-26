#!/usr/bin/env python3
"""
Phase 3: Connection Identification
Find coach-to-coach connections based on temporal overlaps at same clubs
"""

import json
import re
from pathlib import Path
from datetime import datetime

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"

MASTER_PROFILES_FILE = DATA_DIR / "master_coach_profiles.json"
COACH_CONNECTIONS_FILE = DATA_DIR / "coach_to_coach_connections.json"

def normalize_club_name(club_name):
    """Normalize club names for matching"""
    if not club_name:
        return ""

    name = club_name.strip()

    # Remove common prefixes
    name = re.sub(r'^(FC|1\.|VfL|VfB|TSG|SC)\s+', '', name, flags=re.IGNORECASE)

    # Normalize common clubs
    normalizations = {
        "Bayern München": "Bayern Munich",
        "Bayern Munchen": "Bayern Munich",
        "Bor. Dortmund": "Dortmund",
        "Borussia Dortmund": "Dortmund",
        "BVB": "Dortmund",
        "Leverkusen": "Bayer 04 Leverkusen",
        "Eintracht Frankfurt": "Frankfurt",
        "St. Pauli": "St. Pauli",
        "Union SG": "Union Saint-Gilloise",
        "RB Leipzig": "RB Leipzig"
    }

    for key, value in normalizations.items():
        if key.lower() in name.lower():
            return value

    return name

def parse_period(period_str):
    """Parse period string to extract start/end years"""
    if not period_str:
        return None

    try:
        # Format: "24/25 (02/02/2025) - expected 30/06/2027"
        # or: "22/23 (01/07/2022) - 23/24 (17/03/2024)"

        parts = period_str.split(' - ')
        if len(parts) != 2:
            return None

        start_part = parts[0].strip()
        end_part = parts[1].strip()

        # Extract year from start (look for date in parentheses)
        start_match = re.search(r'\((\d{2})/(\d{2})/(\d{4})\)', start_part)
        if start_match:
            start_year = int(start_match.group(3))
        else:
            # Fallback: extract YY/YY format
            season_match = re.search(r'(\d{2})/\d{2}', start_part)
            if season_match:
                start_year = 2000 + int(season_match.group(1))
            else:
                return None

        # Extract year from end
        if 'expected' in end_part or '-' == end_part:
            # Current position, use current year + 1
            end_year = datetime.now().year + 1
        else:
            end_match = re.search(r'\((\d{2})/(\d{2})/(\d{4})\)', end_part)
            if end_match:
                end_year = int(end_match.group(3))
            else:
                # Fallback: extract YY/YY format
                season_match = re.search(r'(\d{2})/\d{2}', end_part)
                if season_match:
                    end_year = 2000 + int(season_match.group(1))
                else:
                    end_year = datetime.now().year

        return {
            'start': start_year,
            'end': end_year
        }

    except Exception as e:
        print(f"  ⚠️  Error parsing period '{period_str}': {e}")
        return None

def calculate_overlap_years(dates_a, dates_b):
    """Calculate years of overlap between two date ranges"""
    if not dates_a or not dates_b:
        return 0

    overlap_start = max(dates_a['start'], dates_b['start'])
    overlap_end = min(dates_a['end'], dates_b['end'])

    if overlap_start >= overlap_end:
        return 0

    return overlap_end - overlap_start

def merge_overlapping_periods(overlaps):
    """Merge overlapping time periods for the same club"""
    if not overlaps:
        return []

    # Group by club
    by_club = {}
    for overlap in overlaps:
        club = overlap['club'].lower()
        if club not in by_club:
            by_club[club] = []
        by_club[club].append(overlap)

    merged = []

    for club, club_overlaps in by_club.items():
        # Sort by start date
        club_overlaps.sort(key=lambda x: x['overlap_start'])

        # Merge overlapping periods
        current = club_overlaps[0].copy()

        for i in range(1, len(club_overlaps)):
            next_overlap = club_overlaps[i]

            # Check if overlaps or adjacent
            if next_overlap['overlap_start'] <= current['overlap_end']:
                # Merge: extend current period
                current['overlap_end'] = max(current['overlap_end'], next_overlap['overlap_end'])
                current['overlap_years'] = current['overlap_end'] - current['overlap_start']
                # Combine roles
                if next_overlap['coach_a_role'] not in current['coach_a_role']:
                    current['coach_a_role'] += f" / {next_overlap['coach_a_role']}"
                if next_overlap['coach_b_role'] not in current['coach_b_role']:
                    current['coach_b_role'] += f" / {next_overlap['coach_b_role']}"
            else:
                # No overlap, save current and start new period
                merged.append(current)
                current = next_overlap.copy()

        # Add the last period
        merged.append(current)

    return merged

def find_temporal_overlap(career_a, career_b):
    """Find temporal overlaps between two career histories"""
    raw_overlaps = []

    for period_a in career_a:
        club_a = normalize_club_name(period_a.get('club', ''))
        dates_a = parse_period(period_a.get('period', ''))

        if not club_a or not dates_a:
            continue

        for period_b in career_b:
            club_b = normalize_club_name(period_b.get('club', ''))
            dates_b = parse_period(period_b.get('period', ''))

            if not club_b or not dates_b:
                continue

            # Check if same club
            if club_a.lower() == club_b.lower():
                overlap_years = calculate_overlap_years(dates_a, dates_b)

                if overlap_years > 0:
                    overlap_start = max(dates_a['start'], dates_b['start'])
                    overlap_end = min(dates_a['end'], dates_b['end'])

                    raw_overlaps.append({
                        'club': club_a,
                        'coach_a_role': period_a.get('role', 'Unknown'),
                        'coach_b_role': period_b.get('role', 'Unknown'),
                        'overlap_start': overlap_start,
                        'overlap_end': overlap_end,
                        'overlap_years': overlap_years
                    })

    # Merge overlapping periods
    return merge_overlapping_periods(raw_overlaps)

def classify_relationship(overlaps):
    """Classify relationship type based on roles"""
    if not overlaps:
        return 'unknown'

    # Check roles in overlaps
    roles = [(o['coach_a_role'], o['coach_b_role']) for o in overlaps]

    # Check for manager + assistant patterns
    manager_assistant = any(
        ('Manager' in r[0] and 'Assistant' in r[1]) or
        ('Manager' in r[1] and 'Assistant' in r[0])
        for r in roles
    )

    if manager_assistant:
        return 'manager_assistant'

    # Check for both managers
    both_managers = any(
        'Manager' in r[0] and 'Manager' in r[1]
        for r in roles
    )

    if both_managers:
        return 'head_coach_together'

    # Check for youth/academy
    youth_roles = any(
        ('Youth' in r[0] or 'U1' in r[0] or 'U2' in r[0]) and
        ('Youth' in r[1] or 'U1' in r[1] or 'U2' in r[1])
        for r in roles
    )

    if youth_roles:
        return 'youth_colleagues'

    return 'colleagues'

def calculate_strength(overlaps):
    """Calculate relationship strength score"""
    if not overlaps:
        return 0

    score = 0
    num_clubs = len(set(o['club'] for o in overlaps))
    total_years = sum(o['overlap_years'] for o in overlaps)
    recent = sum(1 for o in overlaps if o['overlap_end'] >= 2020)

    score += num_clubs * 10       # 10 points per club
    score += total_years * 2       # 2 points per year
    score += recent * 5            # 5 points per recent overlap

    return score

def find_coach_connections(profiles):
    """Find all coach-to-coach connections"""
    print("🔍 Identifying coach-to-coach connections...")

    connections = []
    processed_pairs = set()

    # Only consider coaches with career history
    coaches_with_career = [p for p in profiles if len(p.get('career_history', [])) > 0]

    print(f"  Analyzing {len(coaches_with_career)} coaches...")

    for i, coach_a in enumerate(coaches_with_career):
        if i % 100 == 0:
            print(f"  Progress: {i}/{len(coaches_with_career)}")

        for coach_b in coaches_with_career[i+1:]:
            # Skip self
            if coach_a['name'] == coach_b['name']:
                continue

            # Create unique pair ID (sorted names to avoid duplicates)
            pair_id = tuple(sorted([coach_a['name'], coach_b['name']]))

            if pair_id in processed_pairs:
                continue

            processed_pairs.add(pair_id)

            # Find overlaps
            overlaps = find_temporal_overlap(
                coach_a.get('career_history', []),
                coach_b.get('career_history', [])
            )

            if overlaps:
                connection = {
                    'coach_a': coach_a['name'],
                    'coach_a_current_club': coach_a.get('current_club', 'Unknown'),
                    'coach_a_current_role': coach_a.get('current_role', 'Unknown'),
                    'coach_b': coach_b['name'],
                    'coach_b_current_club': coach_b.get('current_club', 'Unknown'),
                    'coach_b_current_role': coach_b.get('current_role', 'Unknown'),
                    'overlaps': overlaps,
                    'relationship_type': classify_relationship(overlaps),
                    'relationship_strength': calculate_strength(overlaps),
                    'total_clubs': len(set(o['club'] for o in overlaps)),
                    'total_years': sum(o['overlap_years'] for o in overlaps),
                    'most_recent_year': max(o['overlap_end'] for o in overlaps)
                }

                connections.append(connection)

    print(f"  ✓ Found {len(connections)} coach-to-coach connections")

    return connections

def main():
    print("=" * 70)
    print("PHASE 3: CONNECTION IDENTIFICATION")
    print("=" * 70)

    # Load master profiles
    print("\n📂 Loading master profiles...")
    with open(MASTER_PROFILES_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
        profiles = data['profiles']

    print(f"  ✓ Loaded {len(profiles)} profiles")

    # Find connections
    connections = find_coach_connections(profiles)

    # Save results
    print("\n💾 Saving coach-to-coach connections...")

    output = {
        'generated_at': datetime.now().isoformat(),
        'total_connections': len(connections),
        'connection_types': {
            'manager_assistant': sum(1 for c in connections if c['relationship_type'] == 'manager_assistant'),
            'head_coach_together': sum(1 for c in connections if c['relationship_type'] == 'head_coach_together'),
            'youth_colleagues': sum(1 for c in connections if c['relationship_type'] == 'youth_colleagues'),
            'colleagues': sum(1 for c in connections if c['relationship_type'] == 'colleagues')
        },
        'connections': connections
    }

    with open(COACH_CONNECTIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"  ✓ Saved to: {COACH_CONNECTIONS_FILE}")

    # Summary
    print("\n" + "=" * 70)
    print("✅ CONNECTION IDENTIFICATION COMPLETE")
    print("=" * 70)
    print(f"Total Connections: {len(connections)}")
    print("\nBy Type:")
    print(f"  - Manager ↔ Assistant: {output['connection_types']['manager_assistant']}")
    print(f"  - Head Coaches Together: {output['connection_types']['head_coach_together']}")
    print(f"  - Youth Colleagues: {output['connection_types']['youth_colleagues']}")
    print(f"  - Other Colleagues: {output['connection_types']['colleagues']}")

    # Top connections
    top_10 = sorted(connections, key=lambda x: x['relationship_strength'], reverse=True)[:10]
    print("\n🔥 Top 10 Strongest Connections:")
    for i, conn in enumerate(top_10, 1):
        print(f"  {i}. {conn['coach_a']} ↔ {conn['coach_b']}")
        print(f"     Strength: {conn['relationship_strength']} | Years: {conn['total_years']} | Clubs: {conn['total_clubs']}")

    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()
