#!/usr/bin/env python3
"""
Merge discovered youth teams into club_registry.json.

Reads data/youth_teams_discovered.json and adds new entries for U19/U17/U18/II
sub-clubs that don't already exist. Preserves parent_tm_id reference for
traceability + tags appropriate league (U19-N/W/S, U17-N/W/S, II=Reserve).

Usage:
  python3 execution/merge_youth_into_registry.py --dry-run
  python3 execution/merge_youth_into_registry.py
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent.parent
REGISTRY = BASE / "data" / "club_registry.json"
DISCOVERED = BASE / "data" / "youth_teams_discovered.json"

# Map sub-team type → liga-tag for current season
TYPE_TO_LEAGUE = {
    "U19": "U19-NLZ",   # placeholder; specific Staffel unknown without scraping
    "U17": "U17-NLZ",
    "U18": "U18-NLZ",
    "II": "RES",         # Reserve / 2. Mannschaft
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--season", default="2025/2026")
    args = parser.parse_args()

    if not DISCOVERED.exists():
        print(f"✗ {DISCOVERED} not found — run discover_youth_teams.py first")
        return

    registry_data = json.load(open(REGISTRY))
    clubs = registry_data["clubs"]
    existing_ids = {c["tm_id"] for c in clubs}

    discovered = json.load(open(DISCOVERED))["sub_clubs"]

    new_clubs = []
    updated = []
    for sub in discovered:
        tm_id = sub["tm_id"]
        league_tag = TYPE_TO_LEAGUE.get(sub["type"])
        if not league_tag:
            continue

        if tm_id in existing_ids:
            # Already in registry — just append league-tag if missing
            for c in clubs:
                if c["tm_id"] == tm_id:
                    leagues_for_season = c.setdefault("leagues", {}).setdefault(args.season, [])
                    if league_tag not in leagues_for_season:
                        leagues_for_season.append(league_tag)
                        updated.append(c["name"])
                    if "parent_tm_id" not in c and sub.get("parent_tm_id"):
                        c["parent_tm_id"] = sub["parent_tm_id"]
                        c["parent_name"] = sub.get("parent_name")
                    break
        else:
            # New entry
            new_entry = {
                "tm_id": tm_id,
                "slug": sub["slug"],
                "name": sub["name"],
                "leagues": {args.season: [league_tag]},
                "team_type": sub["type"],
                "parent_tm_id": sub["parent_tm_id"],
                "parent_name": sub["parent_name"],
            }
            clubs.append(new_entry)
            new_clubs.append(new_entry)
            existing_ids.add(tm_id)

    # Update meta
    if "_meta" in registry_data:
        registry_data["_meta"]["last_youth_merge_at"] = datetime.now(timezone.utc).isoformat()
        registry_data["_meta"]["youth_clubs_added"] = registry_data["_meta"].get("youth_clubs_added", 0) + len(new_clubs)

    print("=== Youth-Teams Merge Summary ===")
    print(f"  Discovered: {len(discovered)}")
    print(f"  New clubs added: {len(new_clubs)}")
    print(f"  Existing clubs updated (league-tag): {len(updated)}")

    if new_clubs[:8]:
        print("\n  Sample new clubs:")
        for c in new_clubs[:8]:
            print(f"    tm_id={c['tm_id']:<7} {c['name']:<35} parent={c['parent_name']}")

    # Type breakdown
    by_type = {}
    for c in new_clubs:
        by_type[c["team_type"]] = by_type.get(c["team_type"], 0) + 1
    print("\n  Breakdown:")
    for t, n in sorted(by_type.items()):
        print(f"    {t}: {n}")

    if not args.dry_run:
        json.dump(registry_data, open(REGISTRY, "w"), ensure_ascii=False, indent=2)
        print(f"\n  ✓ Merged into {REGISTRY}")
    else:
        print("\n  Dry-run only — re-run without --dry-run to persist.")


if __name__ == "__main__":
    main()
