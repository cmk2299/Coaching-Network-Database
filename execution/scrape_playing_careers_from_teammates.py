#!/usr/bin/env python3
"""
Playing Career Scraper - Using Teammates Data
Extracts playing career by scraping teammates and identifying all clubs played for
"""

import json
import time
import re
from pathlib import Path
from datetime import datetime

# Import from existing teammates scraper
import sys
sys.path.insert(0, str(Path(__file__).parent))
from scrape_teammates import (
    fetch_page,
    get_teammates_url,
    get_total_pages,
    parse_teammates,
    CACHE_DIR,
    ensure_dirs
)

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"

RATE_LIMIT = 4

def extract_playing_career_from_teammates_data(coach_name, coach_url, player_id, player_slug):
    """
    Scrape teammates data and extract playing career
    Returns: (career_data, was_cached)
    """
    cache_file = CACHE_DIR / f"player_{player_id}_career_from_teammates.json"

    # Check cache
    if cache_file.exists():
        with open(cache_file, 'r') as f:
            cached = json.load(f)
            if cached.get('_cached_at'):
                return cached, True

    try:
        # Scrape teammates page
        teammates_url = get_teammates_url(player_id, player_slug, page=1)
        soup = fetch_page(teammates_url, None)

        if not soup:
            result = {
                'name': coach_name,
                'player_id': player_id,
                'url': teammates_url,
                'has_playing_career': False,
                'playing_career': [],
                'error': 'Failed to fetch teammates page',
                '_cached_at': datetime.now().isoformat()
            }
            with open(cache_file, 'w') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            return result, False

        # Get total pages
        total_pages = get_total_pages(soup)

        # Parse all teammates (minimum 0 matches to get ALL clubs)
        all_teammates = []
        for page in range(1, min(total_pages + 1, 11)):  # Limit to 10 pages max
            if page > 1:
                soup = fetch_page(get_teammates_url(player_id, player_slug, page=page), None)
                if not soup:
                    break

            teammates, _ = parse_teammates(soup, min_matches=0)
            all_teammates.extend(teammates)

        # Extract clubs from teammates data
        # Each teammate has 'teams_together' count which tells us they played together
        clubs_data = {}  # club -> {teammates: [...], total_matches: X}

        for tm in all_teammates:
            # Parse teams from URL or other metadata
            # The teammates table shows which clubs they played together at
            # But we need to extract club names from somewhere...
            # Actually, the 'teams_together' field tells us HOW MANY clubs, not WHICH clubs

            # Alternative: Parse the teammate's URL to see club history
            # But that would require scraping each teammate's profile (too slow)
            pass

        # PROBLEM: The teammates table shows:
        # - Teammate name
        # - Shared matches
        # - Teams together (COUNT, not names)
        # - Minutes
        # But NOT the actual club names!

        # SOLUTION: We need to scrape the CAREER HISTORY from the player profile page
        # The player profile has "Stationen als Spieler" (Career stations as player)

        # Let's try the player profile page
        player_profile_url = f"https://www.transfermarkt.de/{player_slug}/profil/spieler/{player_id}"
        soup = fetch_page(player_profile_url, None)

        if not soup:
            result = {
                'name': coach_name,
                'player_id': player_id,
                'url': player_profile_url,
                'has_playing_career': False,
                'playing_career': [],
                'error': 'Failed to fetch player profile',
                '_cached_at': datetime.now().isoformat()
            }
            with open(cache_file, 'w') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            return result, False

        # Find career stations table
        # Look for table with "Stationen als Spieler" or similar
        playing_career = []

        # Find all boxes
        boxes = soup.find_all('div', class_='box')
        for box in boxes:
            # Look for header
            header = box.find('h2', class_='content-box-headline')
            if not header:
                header = box.find('div', class_='table-header')

            if header:
                header_text = header.get_text(strip=True).lower()
                if 'stationen als spieler' in header_text or 'career as player' in header_text:
                    # Found the career table!
                    table = box.find('table', class_='items')
                    if table:
                        rows = table.find_all('tr')
                        for row in rows[1:]:  # Skip header
                            cells = row.find_all('td')
                            if len(cells) >= 4:
                                # Parse club
                                club_cell = cells[1] if len(cells) > 1 else None
                                if club_cell:
                                    club_link = club_cell.find('a')
                                    club = club_link.get('title', club_link.get_text(strip=True)) if club_link else club_cell.get_text(strip=True)

                                    # Parse period
                                    period_cell = cells[2] if len(cells) > 2 else None
                                    period = period_cell.get_text(strip=True) if period_cell else ''

                                    # Parse matches
                                    matches_cell = cells[4] if len(cells) > 4 else None
                                    matches = matches_cell.get_text(strip=True) if matches_cell else '0'

                                    if club and period:
                                        # Extract years from period
                                        years = re.findall(r'(\d{4})', period)
                                        first_year = int(years[0]) if len(years) > 0 else None
                                        last_year = int(years[-1]) if len(years) > 1 else first_year

                                        playing_career.append({
                                            'club': club,
                                            'period': period,
                                            'first_year': first_year,
                                            'last_year': last_year,
                                            'matches': matches
                                        })

        result = {
            'name': coach_name,
            'player_id': player_id,
            'url': player_profile_url,
            'has_playing_career': len(playing_career) > 0,
            'playing_career': playing_career,
            'total_teammates': len(all_teammates),
            '_cached_at': datetime.now().isoformat()
        }

        # Cache
        with open(cache_file, 'w') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        return result, False

    except Exception as e:
        result = {
            'name': coach_name,
            'player_id': player_id if 'player_id' in locals() else None,
            'url': coach_url,
            'has_playing_career': False,
            'playing_career': [],
            'error': str(e),
            '_cached_at': datetime.now().isoformat()
        }
        if 'cache_file' in locals():
            with open(cache_file, 'w') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
        return result, False

def main():
    print("=" * 70)
    print("SCRAPE PLAYING CAREERS - From Teammates Data")
    print("Using transfermarkt.de (German version)")
    print("=" * 70)

    ensure_dirs()

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
    print(f"  ⏱️  Estimated time: ~{len(candidates) * RATE_LIMIT / 60:.0f} minutes")
    print("\n  Note: This will take 8-10 hours due to comprehensive scraping")
    print("  Each coach requires: 1 teammates page + 1 profile page")

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

        # Extract player ID and slug
        player_id = url.split('/trainer/')[1].split('/')[0]
        # Extract slug from URL
        slug_match = re.search(r'transfermarkt\.[^/]+/([^/]+)/profil', url)
        player_slug = slug_match.group(1) if slug_match else name.lower().replace(' ', '-')

        # Progress
        if i % 10 == 0:
            elapsed = time.time() - start_time
            rate = i / (elapsed / 60) if elapsed > 0 else 0
            remaining = (len(candidates) - i) / rate if rate > 0 else 0
            print(f"  [{i}/{len(candidates)}] Rate: {rate:.1f}/min | ETA: {remaining:.0f}min | With career: {with_career}")

        # Scrape
        result, was_cached = extract_playing_career_from_teammates_data(name, url, player_id, player_slug)
        results.append(result)

        if was_cached:
            if result.get('has_playing_career'):
                with_career += 1
            else:
                without_career += 1
            print(f"  ✓ Cached: {name}")
        elif result.get('has_playing_career'):
            with_career += 1
            clubs_count = len(result.get('playing_career', []))
            teammates_count = result.get('total_teammates', 0)
            print(f"  ✅ {name}: {clubs_count} clubs, {teammates_count} teammates")
        else:
            without_career += 1
            if result.get('error'):
                errors += 1
                print(f"  ❌ {name}: {result.get('error')}")

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
    print(f"Time: {elapsed_total/60:.1f} minutes ({elapsed_total/3600:.1f} hours)")
    print("=" * 70)

if __name__ == "__main__":
    main()
