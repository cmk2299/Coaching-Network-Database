#!/usr/bin/env python3
"""
Scrape missing Bundesliga coaches and create preloaded caches.
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from scrape_transfermarkt import scrape_coach
from scrape_teammates import scrape_teammates
from scrape_players_used import scrape_players_used
from scrape_players_detail import scrape_players_for_coach_url

MISSING_COACHES = [
    {
        "name": "Lukas Kwasniok",
        "url": "https://www.transfermarkt.de/lukas-kwasniok/profil/trainer/25375",
        "club": "1. FC Köln"
    },
    {
        "name": "Uwe Rösler",
        "url": "https://www.transfermarkt.de/uwe-rosler/profil/trainer/1766",
        "club": "VfL Bochum"
    }
]

def scrape_full_profile(coach_name: str, coach_url: str):
    """Scrape complete profile for a coach."""
    print(f"\n{'='*60}")
    print(f"Scraping: {coach_name}")
    print(f"{'='*60}")

    result = {
        "_preloaded_at": datetime.now().isoformat(),
        "_preloaded": True,
    }

    # 1. Basic profile
    print("  [1/4] Profile...")
    profile = scrape_coach(url=coach_url)
    if profile:
        result["profile"] = profile
        print(f"    ✓ Name: {profile.get('name')}")
        print(f"    ✓ Age: {profile.get('age')}")
        print(f"    ✓ Current Club: {profile.get('current_club')}")
    time.sleep(3)

    # 2. Teammates (if was a player)
    print("  [2/4] Teammates...")
    try:
        teammates = scrape_teammates(coach_profile_url=coach_url)
        if teammates:
            result["teammates"] = teammates
            print(f"    ✓ Total teammates: {len(teammates.get('all_teammates', []))}")
    except Exception as e:
        print(f"    ⚠️  Teammates failed: {e}")
        result["teammates"] = {"all_teammates": []}
    time.sleep(3)

    # 3. Players used
    print("  [3/4] Players used...")
    try:
        players_used = scrape_players_used(coach_url)
        if players_used:
            result["players_used"] = players_used
            print(f"    ✓ Stations: {len(players_used.get('stations', []))}")
    except Exception as e:
        print(f"    ⚠️  Players used failed: {e}")
        result["players_used"] = {"stations": []}
    time.sleep(3)

    # 4. Players detail
    print("  [4/4] Player details...")
    try:
        players_detail = scrape_players_for_coach_url(coach_url, top_n=100)
        if players_detail:
            result["players_detail"] = players_detail
            print(f"    ✓ Players: {len(players_detail.get('players', []))}")
    except Exception as e:
        print(f"    ⚠️  Player details failed: {e}")
        result["players_detail"] = {"players": []}

    # Add empty companions and decision_makers
    result["companions"] = {}
    result["decision_makers"] = []

    return result


def main():
    """Scrape all missing coaches."""
    for coach_info in MISSING_COACHES:
        name = coach_info["name"]
        url = coach_info["url"]
        club = coach_info["club"]

        # Scrape full profile
        data = scrape_full_profile(name, url)

        # Save to preloaded
        filename = name.lower().replace(" ", "_").replace("ö", "o").replace("ü", "u").replace("ä", "a")
        output_path = Path(__file__).parent.parent / "tmp" / "preloaded" / f"{filename}.json"

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        file_size = output_path.stat().st_size / 1024  # KB
        print(f"\n✅ SAVED: {output_path.name} ({file_size:.1f} KB)")
        print(f"   Club: {club}")

        # Wait between coaches
        if coach_info != MISSING_COACHES[-1]:
            print("\n⏱️  Waiting 10 seconds before next coach...")
            time.sleep(10)

    print("\n" + "="*60)
    print("✅ ALL MISSING COACHES SCRAPED!")
    print("="*60)


if __name__ == "__main__":
    main()
