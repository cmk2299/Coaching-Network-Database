#!/usr/bin/env python3
"""
Scrape ALL coaching staff from 2. Bundesliga clubs (Top 8)
Targets: Head Coaches, Co-Trainer, U23, U19 trainers
"""

import sys
import time
import json
from pathlib import Path
from scrape_transfermarkt import search_coach, scrape_coach
from preload_coach_data import save_preloaded

# Top 8 2. Bundesliga clubs (2024/25 season leaders)
BUNDESLIGA_2_CLUBS = {
    "1. FC Köln": "https://www.transfermarkt.com/1-fc-koln/startseite/verein/3",
    "Hamburger SV": "https://www.transfermarkt.com/hamburger-sv/startseite/verein/41",
    "SC Paderborn 07": "https://www.transfermarkt.com/sc-paderborn-07/startseite/verein/91",
    "Hannover 96": "https://www.transfermarkt.com/hannover-96/startseite/verein/42",
    "1. FC Magdeburg": "https://www.transfermarkt.com/1-fc-magdeburg/startseite/verein/1074",
    "Fortuna Düsseldorf": "https://www.transfermarkt.com/fortuna-dusseldorf/startseite/verein/38",
    "Karlsruher SC": "https://www.transfermarkt.com/karlsruher-sc/startseite/verein/1082",
    "1. FC Kaiserslautern": "https://www.transfermarkt.com/1-fc-kaiserslautern/startseite/verein/1303"
}

# Rate limiting
DELAY_BETWEEN_COACHES = 3  # seconds
DELAY_BETWEEN_CLUBS = 5  # seconds

def scrape_club_staff(club_name, club_url):
    """
    Scrape all coaching staff for a single club
    Returns list of coach data
    """
    print(f"\n{'='*70}")
    print(f"🏟️  {club_name}")
    print(f"{'='*70}")

    coaches = []

    # Target positions to scrape (fewer youth teams in 2. BL)
    positions = [
        "Trainer",           # Head Coach
        "Co-Trainer",        # Assistant Coach
        "U23-Trainer",       # U23 Coach
        "U19-Trainer",       # U19 Coach
    ]

    for position in positions:
        print(f"\n  Searching: {position}...")

        # Search for coaches at this club with this position
        search_query = f"{club_name} {position}"
        results = search_coach(search_query)

        if not results:
            print(f"    ⚠ No results for {position}")
            continue

        # Filter results for current position at this club
        for result in results[:3]:  # Check top 3 results
            name = result.get('name', '')
            current_club = result.get('current_club', '')
            current_position = result.get('position', '')
            url = result.get('url', '')

            # Check if this is the right club and position
            if club_name.lower() in current_club.lower() or current_club.lower() in club_name.lower():
                print(f"    ✓ Found: {name} ({current_position})")

                # Scrape full profile
                time.sleep(DELAY_BETWEEN_COACHES)
                try:
                    profile = scrape_coach(url)
                    if profile:
                        coaches.append({
                            'name': name,
                            'position': position,
                            'club': club_name,
                            'profile': profile
                        })
                        print(f"      → Scraped profile successfully")
                    else:
                        print(f"      ⚠ Failed to scrape profile")
                except Exception as e:
                    print(f"      ⚠ Error scraping: {e}")

                break  # Found the coach for this position

        time.sleep(1)  # Small delay between position searches

    return coaches

def main():
    print("=" * 70)
    print("2. BUNDESLIGA COACHING STAFF MASS SCRAPING")
    print("=" * 70)
    print(f"Target: {len(BUNDESLIGA_2_CLUBS)} clubs (Top 8)")
    print(f"Estimated coaches: ~{len(BUNDESLIGA_2_CLUBS) * 4}")
    print("=" * 70)

    all_coaches = []
    clubs_processed = 0

    for club_name, club_url in BUNDESLIGA_2_CLUBS.items():
        try:
            coaches = scrape_club_staff(club_name, club_url)
            all_coaches.extend(coaches)
            clubs_processed += 1

            print(f"\n  📊 {club_name}: {len(coaches)} coaches scraped")

            # Save after each club (in case of interruption)
            for coach_data in coaches:
                save_preloaded(
                    coach_data['name'],
                    coach_data['profile']
                )

            # Delay between clubs
            if clubs_processed < len(BUNDESLIGA_2_CLUBS):
                print(f"\n  ⏱️  Waiting {DELAY_BETWEEN_CLUBS}s before next club...")
                time.sleep(DELAY_BETWEEN_CLUBS)

        except Exception as e:
            print(f"\n  ❌ ERROR processing {club_name}: {e}")
            continue

    # Final summary
    print("\n" + "=" * 70)
    print("✅ SCRAPING COMPLETE")
    print("=" * 70)
    print(f"Clubs processed: {clubs_processed}/{len(BUNDESLIGA_2_CLUBS)}")
    print(f"Total coaches scraped: {len(all_coaches)}")
    print(f"Saved to: preload/")
    print("=" * 70)

    # Save summary
    summary_file = Path(__file__).parent.parent / "data" / "2bundesliga_staff_scrape_summary.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "clubs_processed": clubs_processed,
            "total_coaches": len(all_coaches),
            "coaches": [
                {
                    "name": c['name'],
                    "position": c['position'],
                    "club": c['club']
                }
                for c in all_coaches
            ]
        }, f, indent=2, ensure_ascii=False)

    print(f"Summary saved to: {summary_file}")

if __name__ == "__main__":
    main()
