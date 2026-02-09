#!/usr/bin/env python3
"""
Merge all research JSON files into historical_executives_manual.json
"""
import json
from pathlib import Path
from datetime import datetime

# Paths
DATA_DIR = Path(__file__).parent.parent / "data"
MANUAL_FILE = DATA_DIR / "historical_executives_manual.json"

# Research files to merge
RESEARCH_FILES = [
    "eintracht_frankfurt_historical_executives.json",
    "historical_executives_bayer_leverkusen.json",
    "union_berlin_historical_executives_2010-2024.json",
    "fc_st_pauli_historical_executives.json",
    "1_fc_koeln_historical_executives_research.json",
    "historical_executives_fc_augsburg.json",
    "historical_executives_1fc_heidenheim.json"
]

def load_json(filepath):
    """Load JSON file"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(filepath, data):
    """Save JSON file with formatting"""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def main():
    print("=" * 70)
    print("MERGING HISTORICAL EXECUTIVES RESEARCH")
    print("=" * 70)

    # Load current manual data
    print(f"\n[1/3] Loading current data from {MANUAL_FILE.name}...")
    manual_data = load_json(MANUAL_FILE)
    current_executives = manual_data["executives"]
    print(f"  ✓ Current executives: {len(current_executives)}")

    # Merge all research files
    print(f"\n[2/3] Merging {len(RESEARCH_FILES)} research files...")
    new_executives = []
    clubs_added = []

    for filename in RESEARCH_FILES:
        filepath = DATA_DIR / filename
        if not filepath.exists():
            print(f"  ⚠ File not found: {filename}")
            continue

        research_data = load_json(filepath)
        executives = research_data.get("executives", [])
        club_name = research_data.get("club", "Unknown")

        print(f"  ✓ {club_name}: {len(executives)} executives")
        new_executives.extend(executives)
        clubs_added.append(club_name)

    # Combine and update metadata
    all_executives = current_executives + new_executives

    manual_data["executives"] = all_executives
    manual_data["total_executives"] = len(all_executives)
    manual_data["updated_date"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    # Update coverage
    clubs_coverage = {}
    for exec_data in all_executives:
        for club_info in exec_data["clubs"]:
            club = club_info["club"]
            if club not in clubs_coverage:
                clubs_coverage[club] = {
                    "executives": 0,
                    "years_covered": "",
                    "categories": set()
                }
            clubs_coverage[club]["executives"] += 1
            clubs_coverage[club]["categories"].add(club_info["category"])

    # Convert sets to lists for JSON
    for club in clubs_coverage:
        clubs_coverage[club]["categories"] = sorted(list(clubs_coverage[club]["categories"]))

    manual_data["coverage"]["clubs"] = clubs_coverage
    manual_data["coverage"]["total_clubs"] = len(clubs_coverage)

    # Count positions
    total_positions = sum(len(e["clubs"]) for e in all_executives)
    manual_data["coverage"]["total_positions"] = total_positions

    # Save merged data
    print(f"\n[3/3] Saving merged data...")
    save_json(MANUAL_FILE, manual_data)

    print(f"\n✅ MERGE COMPLETE!")
    print(f"  Total executives: {len(current_executives)} → {len(all_executives)} (+{len(new_executives)})")
    print(f"  Total clubs: {manual_data['coverage']['total_clubs']}")
    print(f"  Total positions: {total_positions}")
    print(f"  Clubs added: {', '.join(clubs_added)}")
    print("=" * 70)

if __name__ == "__main__":
    main()
