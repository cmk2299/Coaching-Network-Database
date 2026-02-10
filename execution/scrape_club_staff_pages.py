#!/usr/bin/env python3
"""
Scrape coaching staff directly from Transfermarkt club staff pages
This is more reliable than search
"""

import time
import json
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from scrape_transfermarkt import scrape_coach
from preload_coach_data import save_preloaded
from scrape_league_coaches import BUNDESLIGA_CLUBS

# Rate limiting
DELAY_BETWEEN_COACHES = 3
DELAY_BETWEEN_CLUBS = 5

def get_club_staff_page_url(club_info):
    """Convert club info to staff page URL"""
    # club_info is a dict with 'id' and 'slug'
    club_id = club_info['id']
    club_slug = club_info['slug']
    return f"https://www.transfermarkt.com/{club_slug}/mitarbeiter/verein/{club_id}"

def scrape_staff_from_club_page(club_name, club_info):
    """Scrape all coaches from a club's staff page"""
    print(f"\n{'='*70}")
    print(f"🏟️  {club_name}")
    print(f"{'='*70}")

    staff_url = get_club_staff_page_url(club_info)
    print(f"Staff page: {staff_url}")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }

    try:
        response = requests.get(staff_url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        coaches_found = []

        # Find responsive tables (Transfermarkt's staff tables)
        responsive_tables = soup.find_all('div', class_='responsive-table')
        print(f"  Found {len(responsive_tables)} staff tables")

        for table_div in responsive_tables:
            table = table_div.find('table')
            if not table:
                continue

            # Skip header row
            rows = table.find_all('tr')[1:]

            for row in rows:
                cells = row.find_all('td')
                if len(cells) < 2:
                    continue

                # Second cell usually has the name + link
                name_cell = cells[1]
                name_link = name_cell.find('a', href=True)

                # Only include if this is a trainer/coach profile
                if not name_link or '/trainer/' not in name_link.get('href', ''):
                    continue

                name = name_link.get_text(strip=True)
                profile_url = "https://www.transfermarkt.com" + name_link['href']

                # Try to find position (usually in later cells)
                position = "Staff"
                for cell in cells[2:]:
                    text = cell.get_text(strip=True)
                    if text and len(text) < 50 and text not in ['', '-']:
                        position = text
                        break

                print(f"    ✓ {name} ({position})")

                coaches_found.append({
                    'name': name,
                    'position': position,
                    'url': profile_url,
                    'club': club_name
                })

        return coaches_found

    except Exception as e:
        print(f"  ❌ Error scraping staff page: {e}")
        import traceback
        traceback.print_exc()
        return []

def main():
    print("=" * 70)
    print("BUNDESLIGA STAFF SCRAPING (via Club Pages)")
    print("=" * 70)

    all_coaches = []
    clubs_processed = 0

    for club_name, club_info in BUNDESLIGA_CLUBS.items():
        try:
            # Get staff list from club page
            staff_list = scrape_staff_from_club_page(club_name, club_info)

            print(f"\n  Found {len(staff_list)} staff members")

            # Scrape full profiles for each
            for i, staff in enumerate(staff_list, 1):
                print(f"\n  [{i}/{len(staff_list)}] Scraping {staff['name']}...")

                time.sleep(DELAY_BETWEEN_COACHES)

                try:
                    profile = scrape_coach(staff['url'])
                    if profile:
                        # Save to preload
                        save_preloaded(staff['name'], profile)
                        all_coaches.append({
                            **staff,
                            'profile_scraped': True
                        })
                        print(f"    ✓ Profile saved")
                    else:
                        all_coaches.append({
                            **staff,
                            'profile_scraped': False
                        })
                        print(f"    ⚠ Profile scraping failed")

                except Exception as e:
                    print(f"    ❌ Error: {e}")
                    all_coaches.append({
                        **staff,
                        'profile_scraped': False,
                        'error': str(e)
                    })

            clubs_processed += 1

            # Delay between clubs
            if clubs_processed < len(BUNDESLIGA_CLUBS):
                print(f"\n  ⏱️  Waiting {DELAY_BETWEEN_CLUBS}s before next club...")
                time.sleep(DELAY_BETWEEN_CLUBS)

        except Exception as e:
            print(f"\n  ❌ ERROR processing {club_name}: {e}")
            continue

    # Summary
    print("\n" + "=" * 70)
    print("✅ SCRAPING COMPLETE")
    print("=" * 70)
    print(f"Clubs processed: {clubs_processed}/{len(BUNDESLIGA_CLUBS)}")
    print(f"Total staff found: {len(all_coaches)}")
    print(f"Profiles scraped: {sum(1 for c in all_coaches if c.get('profile_scraped'))}")
    print("=" * 70)

    # Save summary
    summary_file = Path(__file__).parent.parent / "data" / "bundesliga_staff_scrape_summary.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "clubs_processed": clubs_processed,
            "total_staff": len(all_coaches),
            "profiles_scraped": sum(1 for c in all_coaches if c.get('profile_scraped')),
            "staff": all_coaches
        }, f, indent=2, ensure_ascii=False)

    print(f"Summary saved to: {summary_file}")

if __name__ == "__main__":
    main()
