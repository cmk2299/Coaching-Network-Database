#!/usr/bin/env python3
"""
Bulk Teammates Scraper
Scrapes all teammates for all coaches to enable:
1. Playing career reconstruction (which clubs they played for)
2. Teammate overlap identification (who played together)
"""

import json
import time
from pathlib import Path
from datetime import datetime
import re

# Import from existing scraper
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

def scrape_all_teammates_for_coach(coach_name, coach_url):
    """
    Scrape ALL teammates for a coach (no minimum matches filter)
    Returns: (result_dict, was_cached)
    """
    if '/trainer/' not in coach_url:
        return {'name': coach_name, 'has_teammates': False, 'teammates': []}, True

    player_id = coach_url.split('/trainer/')[1].split('/')[0]

    cache_file = CACHE_DIR / f"player_{player_id}_teammates.json"

    # Check cache
    if cache_file.exists():
        with open(cache_file, 'r') as f:
            cached = json.load(f)
            if cached.get('_cached_at'):
                return cached, True

    # Extract slug from URL
    slug_match = re.search(r'transfermarkt\.[^/]+/([^/]+)/profil', coach_url)
    player_slug = slug_match.group(1) if slug_match else coach_name.lower().replace(' ', '-')

    try:
        # Fetch teammates page (use .de for more data)
        teammates_url = get_teammates_url(player_id, player_slug, page=1)
        soup = fetch_page(teammates_url, None)

        if not soup:
            result = {
                'name': coach_name,
                'player_id': player_id,
                'url': teammates_url,
                'has_teammates': False,
                'teammates': [],
                'error': 'Failed to fetch page',
                '_cached_at': datetime.now().isoformat()
            }
            with open(cache_file, 'w') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            return result, False

        # Get total pages and parse ALL teammates
        total_pages = get_total_pages(soup)
        all_teammates = []

        for page in range(1, min(total_pages + 1, 6)):  # Limit to 5 pages max (performance)
            if page > 1:
                soup = fetch_page(get_teammates_url(player_id, player_slug, page=page), None)
                if not soup:
                    break

            teammates, _ = parse_teammates(soup, min_matches=10)  # 10+ matches filter
            all_teammates.extend(teammates)

        result = {
            'name': coach_name,
            'player_id': player_id,
            'url': teammates_url,
            'has_teammates': len(all_teammates) > 0,
            'teammates': all_teammates,
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
            'player_id': player_id,
            'url': coach_url,
            'has_teammates': False,
            'teammates': [],
            'error': str(e),
            '_cached_at': datetime.now().isoformat()
        }
        with open(cache_file, 'w') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        return result, False

def main():
    print("=" * 70)
    print("BULK TEAMMATES SCRAPER")
    print("Scraping teammates for network reconstruction")
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
    print(f"  ⏱️  Estimated time: ~{len(candidates) * RATE_LIMIT / 60:.0f} minutes (~{len(candidates) * RATE_LIMIT / 3600:.1f} hours)")

    # Scrape
    print(f"\n🔍 Scraping teammates...")
    results = []
    with_teammates = 0
    without_teammates = 0
    errors = 0
    total_teammates_found = 0

    start_time = time.time()

    for i, profile in enumerate(candidates, 1):
        name = profile.get('name', 'Unknown')
        url = profile.get('url', '')

        if not url:
            without_teammates += 1
            continue

        # Progress
        if i % 10 == 0:
            elapsed = time.time() - start_time
            rate = i / (elapsed / 60) if elapsed > 0 else 0
            remaining = (len(candidates) - i) / rate if rate > 0 else 0
            print(f"  [{i}/{len(candidates)}] Rate: {rate:.1f}/min | ETA: {remaining:.0f}min | With teammates: {with_teammates}")

        # Scrape
        result, was_cached = scrape_all_teammates_for_coach(name, url)
        results.append(result)

        if was_cached:
            if result.get('has_teammates'):
                with_teammates += 1
                total_teammates_found += result.get('total_teammates', 0)
            else:
                without_teammates += 1
            print(f"  ✓ Cached: {name}")
        elif result.get('has_teammates'):
            with_teammates += 1
            teammates_count = result.get('total_teammates', 0)
            total_teammates_found += teammates_count
            print(f"  ✅ {name}: {teammates_count} teammates")
        else:
            without_teammates += 1
            if result.get('error'):
                errors += 1
                print(f"  ❌ {name}: {result.get('error')}")

        # Rate limiting only for new scrapes
        if not was_cached and i < len(candidates):
            time.sleep(RATE_LIMIT)

    # Save
    print(f"\n💾 Saving results...")
    output = {
        'generated_at': datetime.now().isoformat(),
        'total_scraped': len(results),
        'with_teammates': with_teammates,
        'without_teammates': without_teammates,
        'total_teammates_found': total_teammates_found,
        'errors': errors,
        'coaches': results
    }

    output_file = DATA_DIR / "teammates_bulk.json"
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"  ✓ Saved to: {output_file}")

    # Summary
    elapsed_total = time.time() - start_time
    print("\n" + "=" * 70)
    print("✅ TEAMMATES SCRAPING COMPLETE")
    print("=" * 70)
    print(f"Total scraped: {len(results)}")
    print(f"With teammates: {with_teammates} ({with_teammates/len(results)*100:.1f}%)")
    print(f"Without teammates: {without_teammates}")
    print(f"Total teammates found: {total_teammates_found}")
    print(f"Avg teammates per coach: {total_teammates_found/with_teammates:.1f}" if with_teammates > 0 else "")
    print(f"Errors: {errors}")
    print(f"Time: {elapsed_total/60:.1f} minutes ({elapsed_total/3600:.1f} hours)")
    print("=" * 70)

if __name__ == "__main__":
    main()
