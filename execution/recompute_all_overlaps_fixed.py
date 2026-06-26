#!/usr/bin/env python3
"""
Recompute ALL overlaps with fixed merging logic
- SD ↔ Coach
- Executive ↔ Coach
- Coach ↔ Coach (already done, just verify)
"""

import json
from pathlib import Path
from datetime import datetime
from identify_coach_connections import (
    normalize_club_name,
    parse_period,
    calculate_overlap_years
)

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"

def load_all_profiles():
    """Load master coach profiles"""
    with open(DATA_DIR / "master_coach_profiles.json", 'r') as f:
        data = json.load(f)
    return data['profiles']

def load_sporting_directors():
    """Load SD data"""
    try:
        with open(DATA_DIR / "sporting_directors_bundesliga.json", 'r') as f:
            data = json.load(f)
        return data.get("sporting_directors", [])
    except FileNotFoundError:
        print("  ⚠️  SD file not found, skipping SD overlaps")
        return []

def load_executives():
    """Load executive data"""
    try:
        with open(DATA_DIR / "historical_executives_manual.json", 'r') as f:
            data = json.load(f)
        return data.get("executives", [])
    except FileNotFoundError:
        print("  ⚠️  Executives file not found, skipping executive overlaps")
        return []

def convert_sd_career_to_standard(sd_career):
    """Convert SD career format to standard format"""
    standard_career = []
    for station in sd_career:
        if not station.get('start_year'):
            continue

        start_year = station['start_year']
        end_year = station.get('end_year', datetime.now().year + 1)

        # Create period string compatible with parse_period
        period = f"{start_year:02d}/{start_year+1:02d} (01/07/{start_year}) - {end_year:02d}/{end_year+1:02d} (30/06/{end_year})"

        standard_career.append({
            'club': station.get('club', ''),
            'role': station.get('role', 'Sporting Director'),
            'period': period
        })

    return standard_career

def convert_executive_career_to_standard(exec_clubs):
    """Convert executive clubs format to standard"""
    standard_career = []
    for club_data in exec_clubs:
        start_year = club_data.get('start_year')
        end_year = club_data.get('end_year', datetime.now().year + 1)

        if not start_year:
            continue

        period = f"{start_year:02d}/{start_year+1:02d} (01/07/{start_year}) - {end_year:02d}/{end_year+1:02d} (30/06/{end_year})"

        standard_career.append({
            'club': club_data.get('club', ''),
            'role': f"{club_data.get('role', 'Executive')} ({club_data.get('category', 'General')})",
            'period': period
        })

    return standard_career

def find_overlaps_between_careers(career_a, career_b):
    """Find overlaps using the fixed merging logic"""
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

            if club_a.lower() == club_b.lower():
                overlap_years = calculate_overlap_years(dates_a, dates_b)

                if overlap_years > 0:
                    raw_overlaps.append({
                        'club': club_a,
                        'person_a_role': period_a.get('role', 'Unknown'),
                        'person_b_role': period_b.get('role', 'Unknown'),
                        'overlap_start': max(dates_a['start'], dates_b['start']),
                        'overlap_end': min(dates_a['end'], dates_b['end']),
                        'overlap_years': overlap_years
                    })

    # Merge overlapping periods
    return merge_overlapping_periods_generic(raw_overlaps)

def merge_overlapping_periods_generic(overlaps):
    """Generic version of merge that works with different role field names"""
    if not overlaps:
        return []

    by_club = {}
    for overlap in overlaps:
        club = overlap['club'].lower()
        if club not in by_club:
            by_club[club] = []
        by_club[club].append(overlap)

    merged = []

    for club, club_overlaps in by_club.items():
        club_overlaps.sort(key=lambda x: x['overlap_start'])
        current = club_overlaps[0].copy()

        for i in range(1, len(club_overlaps)):
            next_overlap = club_overlaps[i]

            if next_overlap['overlap_start'] <= current['overlap_end']:
                # Merge
                current['overlap_end'] = max(current['overlap_end'], next_overlap['overlap_end'])
                current['overlap_years'] = current['overlap_end'] - current['overlap_start']

                # Combine roles
                if 'person_a_role' in current:
                    if next_overlap['person_a_role'] not in current['person_a_role']:
                        current['person_a_role'] += f" / {next_overlap['person_a_role']}"
                    if next_overlap['person_b_role'] not in current['person_b_role']:
                        current['person_b_role'] += f" / {next_overlap['person_b_role']}"
            else:
                merged.append(current)
                current = next_overlap.copy()

        merged.append(current)

    return merged

def recompute_sd_coach_overlaps(profiles, sds):
    """Recompute SD ↔ Coach overlaps"""
    print("\n🔄 Recomputing SD ↔ Coach overlaps...")

    connections = []

    # Filter to only managers
    managers = [p for p in profiles if p.get('current_role', '').lower() == 'manager']

    for sd in sds:
        sd_name = sd.get('name', '')
        sd_career = convert_sd_career_to_standard(sd.get('career_history', []))

        for coach in managers:
            coach_name = coach.get('name', '')
            coach_career = coach.get('career_history', [])

            overlaps = find_overlaps_between_careers(sd_career, coach_career)

            if overlaps:
                total_years = sum(o['overlap_years'] for o in overlaps)
                total_clubs = len(set(o['club'] for o in overlaps))

                # Calculate strength
                strength = (total_clubs * 10) + (total_years * 2)
                recent = sum(5 for o in overlaps if o['overlap_end'] >= 2020)
                strength += recent

                connections.append({
                    'sd_name': sd_name,
                    'sd_current_club': sd.get('current_club', ''),
                    'sd_current_role': sd.get('current_role', ''),
                    'coach_name': coach_name,
                    'coach_current_club': coach.get('current_club', ''),
                    'overlaps': overlaps,
                    'total_years': total_years,
                    'total_clubs': total_clubs,
                    'relationship_strength': strength
                })

    print(f"  ✓ Found {len(connections)} SD ↔ Coach connections")
    return connections

def recompute_executive_coach_overlaps(profiles, executives):
    """Recompute Executive ↔ Coach overlaps"""
    print("\n🔄 Recomputing Executive ↔ Coach overlaps...")

    connections = []

    for exec in executives:
        exec_name = exec.get('name', '')
        exec_career = convert_executive_career_to_standard(exec.get('clubs', []))

        for coach in profiles:
            coach_name = coach.get('name', '')
            coach_career = coach.get('career_history', [])

            overlaps = find_overlaps_between_careers(exec_career, coach_career)

            if overlaps:
                total_years = sum(o['overlap_years'] for o in overlaps)
                total_clubs = len(set(o['club'] for o in overlaps))

                strength = (total_clubs * 10) + (total_years * 2)
                recent = sum(5 for o in overlaps if o['overlap_end'] >= 2020)
                strength += recent

                connections.append({
                    'exec_name': exec_name,
                    'exec_category': exec.get('category', 'Unknown'),
                    'coach_name': coach_name,
                    'coach_current_club': coach.get('current_club', ''),
                    'overlaps': overlaps,
                    'total_years': total_years,
                    'total_clubs': total_clubs,
                    'relationship_strength': strength
                })

    print(f"  ✓ Found {len(connections)} Executive ↔ Coach connections")
    return connections

def main():
    print("=" * 70)
    print("RECOMPUTE ALL OVERLAPS WITH FIXED MERGING")
    print("=" * 70)

    # Load data
    print("\n📂 Loading data...")
    profiles = load_all_profiles()
    sds = load_sporting_directors()
    executives = load_executives()

    print(f"  ✓ {len(profiles)} profiles")
    print(f"  ✓ {len(sds)} SDs")
    print(f"  ✓ {len(executives)} executives")

    # Recompute overlaps
    sd_connections = recompute_sd_coach_overlaps(profiles, sds)
    exec_connections = recompute_executive_coach_overlaps(profiles, executives)

    # Save results
    print("\n💾 Saving fixed overlaps...")

    # Save SD overlaps
    sd_output = {
        'generated_at': datetime.now().isoformat(),
        'total_connections': len(sd_connections),
        'connections': sd_connections,
        'note': 'Recomputed with fixed overlap merging logic'
    }

    with open(DATA_DIR / "sd_coach_overlaps_fixed.json", 'w') as f:
        json.dump(sd_output, f, indent=2, ensure_ascii=False)

    print(f"  ✓ SD overlaps: {DATA_DIR / 'sd_coach_overlaps_fixed.json'}")

    # Save Executive overlaps
    exec_output = {
        'generated_at': datetime.now().isoformat(),
        'total_connections': len(exec_connections),
        'connections': exec_connections,
        'note': 'Recomputed with fixed overlap merging logic'
    }

    with open(DATA_DIR / "executive_coach_overlaps_fixed.json", 'w') as f:
        json.dump(exec_output, f, indent=2, ensure_ascii=False)

    print(f"  ✓ Executive overlaps: {DATA_DIR / 'executive_coach_overlaps_fixed.json'}")

    # Summary
    print("\n" + "=" * 70)
    print("✅ OVERLAP RECOMPUTATION COMPLETE")
    print("=" * 70)
    print(f"SD ↔ Coach: {len(sd_connections)} connections")
    print(f"Executive ↔ Coach: {len(exec_connections)} connections")
    print("\nNext step: Update master_connections.json to use these fixed files")
    print("=" * 70)

if __name__ == "__main__":
    main()
