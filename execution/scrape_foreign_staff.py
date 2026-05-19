#!/usr/bin/env python3
"""
Scrape Foreign Club Staff — Fill network gaps for international stations

Scrapes Mitarbeiter pages from TM for clubs OUTSIDE the BL registry.
Reuses parse_staff_page() from scrape_squads.py.

Usage:
    python execution/scrape_foreign_staff.py --for-coach 26099        # Blessin's foreign clubs
    python execution/scrape_foreign_staff.py --all-bl-coaches         # All BL coaches' foreign clubs
    python execution/scrape_foreign_staff.py --clubs 3948 252 2861    # Specific club IDs
    python execution/scrape_foreign_staff.py --dry-run --for-coach 26099  # Just list what would be scraped
"""

import argparse
import json
import time
from pathlib import Path
from typing import List, Dict, Set, Optional

import sys
sys.path.insert(0, str(Path(__file__).parent))

from scrape_squads import fetch_page, parse_staff_page, STAFF_DIR, TM_BASE, CACHE_DIR
from build_coach_network import (
    load_club_registry, preload_all_profiles, normalize_club,
)

BASE = Path(__file__).parent.parent
DATA = BASE / "data"
PROFILES_DIR = DATA / "person_profiles"

# Cache for foreign staff pages
FOREIGN_CACHE = BASE / "tmp" / "cache" / "foreign_staff"
FOREIGN_CACHE.mkdir(parents=True, exist_ok=True)


def get_foreign_clubs_for_coach(tm_id: int, registry_ids: Set[int]) -> List[dict]:
    """Find clubs in a coach's career that are NOT in the BL registry."""
    profile_path = PROFILES_DIR / f"{tm_id}.json"
    if not profile_path.exists():
        return []

    with open(profile_path) as f:
        profile = json.load(f)

    foreign = []
    seen = set()
    for entry in profile.get("career_history", []):
        club_id = entry.get("club_tm_id")
        club_slug = entry.get("club_slug", "")
        club_name = entry.get("club_name", "")

        if not club_id or club_id in registry_ids or club_id in seen:
            continue
        seen.add(club_id)

        # Skip youth/reserve teams of registry clubs (they share similar IDs)
        # But include them if they have their own slug
        foreign.append({
            "club_tm_id": club_id,
            "club_slug": club_slug,
            "club_name": club_name,
        })

    return foreign


def get_all_bl_coach_ids() -> List[int]:
    """Get tm_ids of all current BL1+BL2 head coaches."""
    registry = load_club_registry()
    coach_ids = []

    for club_id, club in registry.items():
        leagues = club.get("leagues") or club.get("league_history", {})
        is_bl = False
        for key, vals in leagues.items():
            if "2025" in key or key == "2025":
                if isinstance(vals, str):
                    vals = [vals]
                if "BL1" in vals or "BL2" in vals:
                    is_bl = True
                    break
        if not is_bl:
            continue

        staff_path = STAFF_DIR / f"{club_id}.json"
        if not staff_path.exists():
            continue
        with open(staff_path) as f:
            staff = json.load(f)
        trainerstab = [s for s in staff.get("staff", []) if s.get("section") == "Trainerstab"]
        if trainerstab:
            coach_ids.append(trainerstab[0]["tm_id"])

    return coach_ids


def scrape_club_staff(club: dict) -> Optional[dict]:
    """Scrape a single club's Mitarbeiter page."""
    club_id = club["club_tm_id"]
    slug = club["club_slug"]
    name = club["club_name"]

    if not slug:
        print(f"    ! No slug for {name} (ID {club_id}) — skipping")
        return None

    # Check if we already have this staff file
    staff_path = STAFF_DIR / f"{club_id}.json"
    if staff_path.exists():
        return None  # Already scraped

    url = f"{TM_BASE}/{slug}/mitarbeiter/verein/{club_id}"
    cache_key = f"foreign_{club_id}"

    html = fetch_page(url, cache_key, cache_days=30)
    if not html:
        print(f"    ! Failed to fetch {name}")
        return None

    staff_list = parse_staff_page(html, club_id, name)
    if not staff_list:
        print(f"    ! No staff found for {name}")
        return None

    result = {
        "club_tm_id": club_id,
        "club_name": name,
        "club_slug": slug,
        "source": "foreign_staff_scrape",
        "scraped_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "staff_count": len(staff_list),
        "staff": staff_list,
    }

    # Save to standard staff directory
    with open(staff_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result


def main():
    parser = argparse.ArgumentParser(description="Scrape foreign club staff")
    parser.add_argument("--for-coach", type=int, help="Coach tm_id")
    parser.add_argument("--all-bl-coaches", action="store_true")
    parser.add_argument("--clubs", type=int, nargs="+", help="Specific club IDs")
    parser.add_argument("--dry-run", action="store_true", help="Just list, don't scrape")
    args = parser.parse_args()

    registry = load_club_registry()
    registry_ids = set(int(k) for k in registry.keys())

    # Determine which clubs to scrape
    clubs_to_scrape = []

    if args.clubs:
        # Specific clubs — need to find their slugs
        profiles = preload_all_profiles()
        for cid in args.clubs:
            # Find slug from any career entry referencing this club
            for p in profiles.values():
                for entry in p.get("career_history", []):
                    if entry.get("club_tm_id") == cid:
                        clubs_to_scrape.append({
                            "club_tm_id": cid,
                            "club_slug": entry.get("club_slug", ""),
                            "club_name": entry.get("club_name", ""),
                        })
                        break
                else:
                    continue
                break

    elif args.for_coach:
        clubs_to_scrape = get_foreign_clubs_for_coach(args.for_coach, registry_ids)

    elif args.all_bl_coaches:
        coach_ids = get_all_bl_coach_ids()
        print(f"  Found {len(coach_ids)} BL coaches")

        all_foreign = {}
        for cid in coach_ids:
            for club in get_foreign_clubs_for_coach(cid, registry_ids):
                key = club["club_tm_id"]
                if key not in all_foreign:
                    all_foreign[key] = club
        clubs_to_scrape = list(all_foreign.values())

    else:
        parser.print_help()
        return

    # Filter out already-scraped
    to_scrape = []
    already = 0
    for club in clubs_to_scrape:
        if (STAFF_DIR / f"{club['club_tm_id']}.json").exists():
            already += 1
        else:
            to_scrape.append(club)

    print(f"\n{'='*60}")
    print(f"  Foreign Staff Scraper")
    print(f"  Total foreign clubs: {len(clubs_to_scrape)}")
    print(f"  Already scraped: {already}")
    print(f"  To scrape: {len(to_scrape)}")
    print(f"  Est. time: ~{len(to_scrape) * 4}s ({len(to_scrape) * 4 // 60}min)")
    print(f"{'='*60}\n")

    if args.dry_run:
        for club in to_scrape:
            print(f"  Would scrape: {club['club_name']} ({club['club_tm_id']}) — /{club['club_slug']}/mitarbeiter/verein/{club['club_tm_id']}")
        return

    # Scrape
    success = 0
    failed = 0
    total_staff = 0

    for i, club in enumerate(to_scrape, 1):
        print(f"  [{i}/{len(to_scrape)}] {club['club_name']}...", end=" ", flush=True)
        result = scrape_club_staff(club)
        if result:
            count = result["staff_count"]
            total_staff += count
            print(f"{count} staff")
            success += 1
        else:
            print("skipped/failed")
            failed += 1

    print(f"\n{'='*60}")
    print(f"  Done: {success} scraped, {failed} failed")
    print(f"  Total new staff contacts: {total_staff}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
