#!/usr/bin/env python3
"""
Scrape playing careers for all coaches and SDs
"""

import json
import time
import requests
from pathlib import Path
from bs4 import BeautifulSoup
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CACHE_DIR = PROJECT_ROOT / "tmp" / "cache"

RATE_LIMIT = 4  # seconds between requests

def scrape_playing_career(person_name, trainer_url):
    """
    Scrape playing career from Transfermarkt player page

    Returns: {
        'name': str,
        'has_playing_career': bool,
        'playing_career': [...]
    }
    """
    # Convert trainer URL to player URL
    if '/trainer/' not in trainer_url:
        return {'name': person_name, 'has_playing_career': False, 'playing_career': []}

    player_url = trainer_url.replace('/trainer/', '/spieler/')

    # Check cache
    coach_id = trainer_url.split('/trainer/')[1].split('/')[0] if '/trainer/' in trainer_url else None
    if coach_id:
        cache_file = CACHE_DIR / f"player_{coach_id}_career.json"
        if cache_file.exists():
            with open(cache_file, 'r') as f:
                cached = json.load(f)
                if cached.get('_cached_at'):
                    print(f"  Using cached player career for {person_name}")
                    return cached

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }

    try:
        response = requests.get(player_url, headers=headers, timeout=15)

        # If 404, person has no player profile
        if response.status_code == 404:
            result = {
                'name': person_name,
                'url': player_url,
                'has_playing_career': False,
                'playing_career': [],
                '_cached_at': datetime.now().isoformat()
            }
            if coach_id:
                with open(cache_file, 'w') as f:
                    json.dump(result, f, indent=2)
            return result

        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find performance data table
        playing_career = []

        # Look for "Career stats" or "Leistungsdaten" or "Performance data" table
        tables = soup.find_all('table', class_='items')
        for table in tables:
            header = table.find_previous(['h2', 'div'], class_=['content-box-headline', 'table-header'])
            if header and ('career stats' in header.get_text().lower() or
                          'leistungsdaten' in header.get_text().lower() or
                          'performance' in header.get_text().lower() or
                          'karriere' in header.get_text().lower()):

                rows = table.find_all('tr')[1:]  # Skip header
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 3:
                        # Parse season
                        season_cell = cells[0]
                        season = season_cell.get_text(strip=True)

                        # Parse club
                        club_cell = cells[1] if len(cells) > 1 else None
                        club_link = club_cell.find('a') if club_cell else None
                        club = club_link.get_text(strip=True) if club_link else ''

                        # Parse appearances (usually in later cells)
                        appearances = 0
                        goals = 0

                        # Try to find numeric data
                        for cell in cells[2:]:
                            text = cell.get_text(strip=True)
                            if text.isdigit():
                                if appearances == 0:
                                    appearances = int(text)
                                elif goals == 0:
                                    goals = int(text)

                        if season and club:
                            playing_career.append({
                                'season': season,
                                'club': club,
                                'appearances': appearances,
                                'goals': goals
                            })

        result = {
            'name': person_name,
            'url': player_url,
            'has_playing_career': len(playing_career) > 0,
            'playing_career': playing_career,
            '_cached_at': datetime.now().isoformat()
        }

        # Cache result
        if coach_id:
            with open(cache_file, 'w') as f:
                json.dump(result, f, indent=2)

        return result

    except Exception as e:
        print(f"  ⚠️  Error scraping {person_name}: {e}")
        return {
            'name': person_name,
            'url': player_url,
            'has_playing_career': False,
            'playing_career': [],
            'error': str(e)
        }

def main():
    print("=" * 70)
    print("SCRAPE PLAYING CAREERS - BULK")
    print("=" * 70)

    # Load all profiles
    print("\n📂 Loading profiles...")
    with open(DATA_DIR / "master_coach_profiles.json", 'r') as f:
        data = json.load(f)
        profiles = data['profiles']

    # Filter to likely ex-players (current managers, assistants, etc.)
    # Skip: scouts, physios, doctors, kit managers (unlikely to have player careers)
    skip_roles = ['scout', 'physio', 'doctor', 'kit', 'member of', 'club doctor']

    candidates = [
        p for p in profiles
        if not any(skip in p.get('current_role', '').lower() for skip in skip_roles)
    ]

    print(f"  ✓ {len(profiles)} total profiles")
    print(f"  ✓ {len(candidates)} candidates for playing career scraping")
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

        if not url:
            without_career += 1
            continue

        # Progress
        if i % 50 == 0:
            elapsed = time.time() - start_time
            rate = i / (elapsed / 60) if elapsed > 0 else 0
            remaining = (len(candidates) - i) / rate if rate > 0 else 0
            print(f"  [{i}/{len(candidates)}] {name}")
            print(f"    Rate: {rate:.1f}/min | ETA: {remaining:.0f}min")

        # Scrape
        result = scrape_playing_career(name, url)
        results.append(result)

        if result.get('has_playing_career'):
            with_career += 1
            career_len = len(result.get('playing_career', []))
            print(f"  ✅ {name}: {career_len} seasons")
        else:
            without_career += 1

        if result.get('error'):
            errors += 1

        # Rate limiting
        if i < len(candidates):
            time.sleep(RATE_LIMIT)

    # Save results
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
