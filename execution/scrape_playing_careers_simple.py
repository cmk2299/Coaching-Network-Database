#!/usr/bin/env python3
"""
Simple approach: Reuse the coach career scraper for player URLs
The HTML structure is identical for player profiles
"""

import json
import time
from pathlib import Path
from datetime import datetime

# Import the working scraper from scrape_transfermarkt
import sys
sys.path.insert(0, str(Path(__file__).parent))
from scrape_transfermarkt import scrape_coach

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CACHE_DIR = PROJECT_ROOT / "tmp" / "cache"

RATE_LIMIT = 4  # seconds

def scrape_playing_career_simple(name, trainer_url):
    """
    Scrape playing career by converting trainer URL to player URL
    and reusing the coach profile scraper

    Returns: (result_dict, was_cached)
    """
    if '/trainer/' not in trainer_url:
        return {'name': name, 'has_playing_career': False, 'playing_career': []}, True

    # Convert to player URL
    player_url = trainer_url.replace('/trainer/', '/spieler/')

    # Extract ID for caching
    coach_id = trainer_url.split('/trainer/')[1].split('/')[0]
    cache_file = CACHE_DIR / f"player_{coach_id}_career.json"

    # Check cache
    if cache_file.exists():
        with open(cache_file, 'r') as f:
            cached = json.load(f)
            if cached.get('_cached_at'):
                print(f"  ✓ Cached: {name}")
                return cached, True

    # Scrape using existing coach scraper (works for players too!)
    try:
        profile = scrape_coach(url=player_url)

        result = {
            'name': name,
            'url': player_url,
            'has_playing_career': len(profile.get('career_history', [])) > 0,
            'playing_career': profile.get('career_history', []),
            '_cached_at': datetime.now().isoformat()
        }

        # Cache
        with open(cache_file, 'w') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        return result, False

    except Exception as e:
        print(f"  ⚠️  Error scraping {name}: {e}")
        result = {
            'name': name,
            'url': player_url,
            'has_playing_career': False,
            'playing_career': [],
            'error': str(e),
            '_cached_at': datetime.now().isoformat()
        }

        # Cache error too (avoid re-scraping failures)
        with open(cache_file, 'w') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        return result, False

def main():
    print("=" * 70)
    print("SCRAPE PLAYING CAREERS - SIMPLE APPROACH")
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

        if not url:
            without_career += 1
            continue

        # Progress
        if i % 25 == 0:
            elapsed = time.time() - start_time
            rate = i / (elapsed / 60) if elapsed > 0 else 0
            remaining = (len(candidates) - i) / rate if rate > 0 else 0
            print(f"  [{i}/{len(candidates)}] Rate: {rate:.1f}/min | ETA: {remaining:.0f}min")

        # Scrape
        result, was_cached = scrape_playing_career_simple(name, url)
        results.append(result)

        if result.get('has_playing_career'):
            with_career += 1
            career_len = len(result.get('playing_career', []))
            print(f"  ✅ {name}: {career_len} clubs")
        else:
            without_career += 1

        if result.get('error'):
            errors += 1

        # Rate limiting ONLY for new scrapes (not cached)
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
