#!/usr/bin/env python3
"""
Scrape all Bundesliga squad pages 2015-2026 to get player URLs
"""

import json
import time
from pathlib import Path
import requests
from bs4 import BeautifulSoup

# Configuration
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = DATA_DIR / "bundesliga_players_2015_2026"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TM_BASE = "https://www.transfermarkt.de"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9",
}

# Bundesliga clubs (will be dynamically discovered)
BUNDESLIGA_CLUBS = {
    "FC Bayern München": {"id": 27, "slug": "fc-bayern-munchen"},
    "Borussia Dortmund": {"id": 16, "slug": "borussia-dortmund"},
    "RB Leipzig": {"id": 23826, "slug": "rasenballsport-leipzig"},
    "Bayer Leverkusen": {"id": 15, "slug": "bayer-04-leverkusen"},
    "Union Berlin": {"id": 89, "slug": "1-fc-union-berlin"},
    "SC Freiburg": {"id": 60, "slug": "sc-freiburg"},
    "Eintracht Frankfurt": {"id": 24, "slug": "eintracht-frankfurt"},
    "VfL Wolfsburg": {"id": 82, "slug": "vfl-wolfsburg"},
    "Borussia Mönchengladbach": {"id": 18, "slug": "borussia-monchengladbach"},
    "FSV Mainz 05": {"id": 39, "slug": "1-fsv-mainz-05"},
    "FC Augsburg": {"id": 167, "slug": "fc-augsburg"},
    "VfB Stuttgart": {"id": 79, "slug": "vfb-stuttgart"},
    "TSG Hoffenheim": {"id": 533, "slug": "tsg-1899-hoffenheim"},
    "Werder Bremen": {"id": 86, "slug": "sv-werder-bremen"},
    "VfL Bochum": {"id": 80, "slug": "vfl-bochum"},
    "FC St. Pauli": {"id": 35, "slug": "fc-st-pauli"},
    "Holstein Kiel": {"id": 1121, "slug": "holstein-kiel"},
    "1.FC Köln": {"id": 3, "slug": "1-fc-koln"},
}

SEASONS = list(range(2015, 2027))  # 2015-2026

def fetch_squad_page(club_id, season):
    """Fetch squad page for a club in a season"""
    url = f"{TM_BASE}/unknown/kader/verein/{club_id}/saison_id/{season}/plus/1"
    time.sleep(4)  # Rate limiting

    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return BeautifulSoup(response.text, 'lxml')
    except Exception as e:
        print(f"      ERROR fetching {url}: {e}")
        return None

def extract_player_urls(soup):
    """Extract all player profile URLs from squad page"""
    players = []

    if not soup:
        return players

    # Find all player links in squad table
    # Pattern: /player-name/profil/spieler/12345
    for link in soup.find_all('a', href=True):
        href = link['href']
        if '/profil/spieler/' in href:
            # Extract player ID and build URL
            parts = href.split('/')
            if len(parts) >= 5:
                player_id = parts[-1]
                player_slug = parts[-4]

                full_url = f"{TM_BASE}{href}" if href.startswith('/') else href

                # Get player name
                player_name = link.get_text(strip=True)
                if player_name and len(player_name) > 2:
                    players.append({
                        'name': player_name,
                        'url': full_url,
                        'player_id': player_id,
                        'slug': player_slug
                    })

    # Deduplicate by player_id
    seen = set()
    unique = []
    for p in players:
        if p['player_id'] not in seen:
            seen.add(p['player_id'])
            unique.append(p)

    return unique

def main():
    print("=" * 70)
    print("BUNDESLIGA SQUAD SCRAPING (2015-2026)")
    print("=" * 70)
    print()

    print(f"Clubs: {len(BUNDESLIGA_CLUBS)}")
    print(f"Seasons: {len(SEASONS)} ({SEASONS[0]}-{SEASONS[-1]})")
    print(f"Total squad pages: {len(BUNDESLIGA_CLUBS) * len(SEASONS)}")
    print()

    all_players = {}
    squad_count = 0
    total_squads = len(BUNDESLIGA_CLUBS) * len(SEASONS)

    start_time = time.time()

    for season in SEASONS:
        print(f"\n{'='*70}")
        print(f"SEASON {season}/{season+1}")
        print(f"{'='*70}\n")

        for club_name, club_data in BUNDESLIGA_CLUBS.items():
            club_id = club_data['id']
            squad_count += 1

            print(f"  [{squad_count}/{total_squads}] {club_name} ({season}/{season+1})")

            soup = fetch_squad_page(club_id, season)
            players = extract_player_urls(soup)

            print(f"      Found {len(players)} players")

            # Add to master list
            for player in players:
                player_id = player['player_id']
                if player_id not in all_players:
                    all_players[player_id] = player
                    all_players[player_id]['seasons'] = []

                all_players[player_id]['seasons'].append({
                    'season': f"{season}/{season+1}",
                    'club': club_name,
                    'club_id': club_id
                })

    # Summary
    elapsed = time.time() - start_time

    print("\n" + "=" * 70)
    print("SCRAPING COMPLETE")
    print("=" * 70)
    print(f"Squad pages scraped: {squad_count}")
    print(f"Unique players found: {len(all_players)}")
    print(f"Duration: {elapsed/60:.1f} minutes")
    print()

    # Save results
    output_file = OUTPUT_DIR / "players_master_urls.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "seasons": [f"{s}/{s+1}" for s in SEASONS],
            "total_players": len(all_players),
            "players": list(all_players.values())
        }, f, indent=2, ensure_ascii=False)

    print(f"📄 Saved to: {output_file}")
    print(f"   {len(all_players)} unique players")
    print()

    # Print statistics
    print("=" * 70)
    print("STATISTICS")
    print("=" * 70)

    # Players by number of seasons
    season_counts = {}
    for player in all_players.values():
        count = len(player['seasons'])
        season_counts[count] = season_counts.get(count, 0) + 1

    print("\nPlayers by number of seasons:")
    for num_seasons in sorted(season_counts.keys(), reverse=True):
        count = season_counts[num_seasons]
        print(f"  {num_seasons} seasons: {count} players")

if __name__ == "__main__":
    main()
