#!/usr/bin/env python3
"""
Playing Career Scraper V2 - Using gemeinsameSpiele (teammates) page
Extracts playing career from the clubs/seasons shown in teammates data
"""

import json
import time
import re
import requests
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CACHE_DIR = PROJECT_ROOT / "tmp" / "cache"

RATE_LIMIT = 4
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
}

def extract_playing_career_from_teammates(player_id, player_name):
    """
    Scrape gemeinsameSpiele page to extract playing career
    Returns list of {club, seasons[]}
    """
    # Check cache
    cache_file = CACHE_DIR / f"player_{player_id}_career.json"
    if cache_file.exists():
        with open(cache_file, 'r') as f:
            cached = json.load(f)
            if cached.get('_cached_at'):
                return cached, True

    # Build URL
    url = f'https://www.transfermarkt.com/-/gemeinsameSpiele/spieler/{player_id}'

    try:
        response = requests.get(url, headers=HEADERS, timeout=15)

        # 404 = no player profile
        if response.status_code == 404:
            result = {
                'name': player_name,
                'url': url,
                'has_playing_career': False,
                'playing_career': [],
                '_cached_at': datetime.now().isoformat()
            }
            with open(cache_file, 'w') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            return result, False

        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find all rows in teammates table
        playing_career = {}  # club -> {seasons: set(), first_year, last_year}

        rows = soup.find_all('tr', class_=['odd', 'even'])
        for row in rows:
            cells = row.find_all('td')
            if len(cells) < 4:
                continue

            # Cell structure:
            # 0: Player name
            # 1: Position
            # 2: Club (with logo)
            # 3: Season

            club_cell = cells[2] if len(cells) > 2 else None
            season_cell = cells[3] if len(cells) > 3 else None

            if not club_cell or not season_cell:
                continue

            # Extract club name
            club_link = club_cell.find('a')
            if club_link:
                club = club_link.get('title', club_link.get_text(strip=True))
            else:
                club = club_cell.get_text(strip=True)

            # Extract season (e.g., "2010/2011")
            season = season_cell.get_text(strip=True)

            if club and season:
                if club not in playing_career:
                    playing_career[club] = {'seasons': set(), 'first_year': 9999, 'last_year': 0}

                playing_career[club]['seasons'].add(season)

                # Extract year from season (e.g., "2010/2011" -> 2010)
                year_match = re.search(r'(\d{4})', season)
                if year_match:
                    year = int(year_match.group(1))
                    playing_career[club]['first_year'] = min(playing_career[club]['first_year'], year)
                    playing_career[club]['last_year'] = max(playing_career[club]['last_year'], year + 1)

        # Convert to list format
        career_list = []
        for club, data in playing_career.items():
            career_list.append({
                'club': club,
                'seasons': sorted(list(data['seasons'])),
                'first_year': data['first_year'],
                'last_year': data['last_year'],
                'total_seasons': len(data['seasons'])
            })

        # Sort by first_year
        career_list.sort(key=lambda x: x['first_year'])

        result = {
            'name': player_name,
            'url': url,
            'has_playing_career': len(career_list) > 0,
            'playing_career': career_list,
            '_cached_at': datetime.now().isoformat()
        }

        # Cache
        with open(cache_file, 'w') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        return result, False

    except Exception as e:
        print(f"  ⚠️  Error: {e}")
        result = {
            'name': player_name,
            'url': url,
            'has_playing_career': False,
            'playing_career': [],
            'error': str(e),
            '_cached_at': datetime.now().isoformat()
        }
        with open(cache_file, 'w') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        return result, False

def main():
    print("=" * 70)
    print("SCRAPE PLAYING CAREERS V2 - Using Teammates Data")
    print("=" * 70)

    # Load profiles
    print("\n📂 Loading profiles...")
    with open(DATA_DIR / "master_coach_profiles.json", 'r') as f:
        data = json.load(f)
        profiles = data['profiles']

    # Filter to likely ex-players
    skip_roles = ['scout', 'physio', 'doctor', 'kit', 'member of', 'club doctor']
    candidates = [
        p for p in profiles
        if not any(skip in p.get('current_role', '').lower() for skip in skip_roles)
    ]

    print(f"  ✓ {len(profiles)} total profiles")
    print(f"  ✓ {len(candidates)} candidates")
    print(f"  ⏱️  Estimated time: {len(candidates) * RATE_LIMIT / 60:.0f} minutes")

    # Scrape
    print("\n🔍 Scraping playing careers...")
    results = []
    with_career = 0
    without_career = 0
    errors = 0

    start_time = time.time()

    for i, profile in enumerate(candidates, 1):
        name = profile.get('name', 'Unknown')
        url = profile.get('url', '')

        if not url or '/trainer/' not in url:
            without_career += 1
            continue

        # Extract player ID from trainer URL
        player_id = url.split('/trainer/')[1].split('/')[0]

        # Progress
        if i % 25 == 0:
            elapsed = time.time() - start_time
            rate = i / (elapsed / 60) if elapsed > 0 else 0
            remaining = (len(candidates) - i) / rate if rate > 0 else 0
            print(f"  [{i}/{len(candidates)}] Rate: {rate:.1f}/min | ETA: {remaining:.0f}min")

        # Scrape
        result, was_cached = extract_playing_career_from_teammates(player_id, name)
        results.append(result)

        if was_cached:
            print(f"  ✓ Cached: {name}")
        elif result.get('has_playing_career'):
            with_career += 1
            clubs_count = len(result.get('playing_career', []))
            print(f"  ✅ {name}: {clubs_count} clubs")
        else:
            without_career += 1

        if result.get('error'):
            errors += 1

        # Rate limiting only for new scrapes
        if not was_cached and i < len(candidates):
            time.sleep(RATE_LIMIT)

    # Save
    print("\n💾 Saving results...")
    output = {
        'generated_at': datetime.now().isoformat(),
        'total_scraped': len(results),
        'with_playing_career': with_career,
        'without_playing_career': without_career,
        'errors': errors,
        'careers': results
    }

    output_file = DATA_DIR / "playing_careers.json"
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"  ✓ Saved to: {output_file}")

    # Summary
    elapsed_total = time.time() - start_time
    print("\n" + "=" * 70)
    print("✅ PLAYING CAREER SCRAPING COMPLETE")
    print("=" * 70)
    print(f"Total scraped: {len(results)}")
    print(f"With playing career: {with_career} ({with_career/len(results)*100:.1f}%)")
    print(f"Without playing career: {without_career}")
    print(f"Errors: {errors}")
    print(f"Time: {elapsed_total/60:.1f} minutes")
    print("=" * 70)

if __name__ == "__main__":
    main()
