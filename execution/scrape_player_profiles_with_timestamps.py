#!/usr/bin/env python3
"""
Scrape Bundesliga player profiles with career history timestamps
Optimized for overnight bulk scraping
"""

import json
import time
import re
from pathlib import Path
from datetime import datetime
import requests
from bs4 import BeautifulSoup

# Configuration
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
PLAYERS_DIR = DATA_DIR / "bundesliga_players_2015_2026"
PROFILES_DIR = PLAYERS_DIR / "profiles"
PROFILES_DIR.mkdir(parents=True, exist_ok=True)

TM_BASE = "https://www.transfermarkt.de"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9",
}

DELAY = 4  # seconds between requests

def fetch_player_profile(url):
    """Fetch player profile page"""
    time.sleep(DELAY)

    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return BeautifulSoup(response.text, 'lxml')
    except Exception:
        return None

def parse_player_profile(soup, url):
    """Parse player profile and extract all data including career history"""
    profile = {
        "url": url,
        "scraped_at": datetime.now().isoformat()
    }

    if not soup:
        return None

    # Name
    name_elem = soup.find("h1", class_="data-header__headline-wrapper")
    if name_elem:
        profile["name"] = " ".join(name_elem.get_text().split())

    # Extract player ID from URL
    if '/spieler/' in url:
        profile["player_id"] = url.split('/spieler/')[-1].split('/')[0] if '/spieler/' in url else url.split('/')[-1]

    # Demographics from info table
    for row in soup.find_all("tr"):
        th = row.find("th")
        td = row.find("td")
        if th and td:
            label = th.get_text(strip=True).lower()
            value = td.get_text(strip=True)

            if "nationalität" in label or "citizenship" in label:
                profile["nationality"] = value.replace("\xa0", " ").strip()
            elif "geburtsdatum" in label or "date of birth" in label:
                profile["dob"] = value
                age_match = re.search(r"\((\d+)\)", value)
                if age_match:
                    profile["age"] = int(age_match.group(1))
            elif "geburtsort" in label or "place of birth" in label:
                profile["birthplace"] = value
            elif "position" in label:
                profile["position"] = value
            elif "größe" in label or "height" in label:
                profile["height"] = value
            elif "fuß" in label or "foot" in label:
                profile["foot"] = value

    # Career History (CRITICAL!)
    career = []

    # Find career/stations table
    tables = soup.find_all("table", class_="items")
    for table in tables:
        header = table.find_previous(["h2", "div"], class_=["content-box-headline", "table-header"])

        if header and any(x in header.get_text().lower() for x in ["stationen", "karriere", "vereinsstationen"]):
            rows = table.find_all("tr")[1:]  # Skip header

            for row in rows:
                cells = row.find_all("td")
                if len(cells) >= 4:
                    try:
                        # Structure varies, try to extract:
                        # Season | Club | Games | Goals

                        # Season (usually first or second cell)
                        season_cell = cells[0] if cells[0].get_text(strip=True) else cells[1]
                        season = season_cell.get_text(strip=True)

                        # Club (find link to club)
                        club_name = "Unknown"
                        club_id = None
                        for cell in cells:
                            club_link = cell.find("a", href=re.compile(r"/[\w-]+/startseite/verein/"))
                            if club_link:
                                club_name = club_link.get_text(strip=True)
                                club_href = club_link.get('href', '')
                                if '/verein/' in club_href:
                                    club_id = club_href.split('/verein/')[-1].split('/')[0]
                                break

                        # Games (usually has a number)
                        games = 0
                        goals = 0
                        assists = 0

                        for cell in cells:
                            text = cell.get_text(strip=True)
                            # Games cell (just a number, not "-")
                            if text.isdigit():
                                games = int(text)
                                break

                        # Try to find goals/assists
                        for i, cell in enumerate(cells):
                            text = cell.get_text(strip=True)
                            if text.isdigit() and i > 0:
                                # Could be goals or assists
                                num = int(text)
                                if goals == 0:
                                    goals = num
                                elif assists == 0:
                                    assists = num

                        # Only add if we have meaningful data
                        if season and club_name != "Unknown":
                            career.append({
                                "season": season,
                                "club": club_name,
                                "club_id": club_id,
                                "games": games,
                                "goals": goals,
                                "assists": assists
                            })

                    except Exception:
                        continue

    # Filter career to 2015+
    career_since_2015 = []
    for entry in career:
        season = entry.get('season', '')
        # Extract year from season string like "2015/16" or "15/16"
        year_match = re.search(r'(\d{2,4})', season)
        if year_match:
            year = int(year_match.group(1))
            if year < 100:  # Two digit year
                year = 2000 + year if year < 50 else 1900 + year
            if year >= 2015:
                career_since_2015.append(entry)

    profile["career_history"] = career_since_2015

    return profile

def main():
    print("=" * 70)
    print("BUNDESLIGA PLAYER PROFILE SCRAPING (WITH TIMESTAMPS)")
    print("=" * 70)
    print()

    # Load player URLs
    urls_file = PLAYERS_DIR / "players_master_urls.json"
    if not urls_file.exists():
        print(f"❌ ERROR: {urls_file} not found!")
        print("   Run scrape_bundesliga_squads_2015_2026.py first!")
        return

    with open(urls_file, encoding='utf-8') as f:
        data = json.load(f)

    players = data.get('players', [])
    total = len(players)

    print(f"📊 Total players to scrape: {total}")
    print(f"⏱️  Estimated time: {total * DELAY / 60:.0f} minutes ({total * DELAY / 3600:.1f} hours)")
    print(f"📁 Output directory: {PROFILES_DIR}")
    print()

    # Track progress
    success_count = 0
    failed_count = 0
    with_career = 0
    failed_players = []

    start_time = time.time()

    for i, player_data in enumerate(players, 1):
        try:
            name = player_data.get('name', 'Unknown')
            url = player_data.get('url')
            player_id = player_data.get('player_id')

            if not url:
                print(f"[{i}/{total}] ⚠️  {name} - No URL")
                failed_count += 1
                continue

            # Progress indicator
            elapsed = time.time() - start_time
            rate = i / (elapsed / 60) if elapsed > 0 else 0
            remaining_mins = (total - i) / rate if rate > 0 else 0

            print(f"[{i}/{total}] {name}")
            print(f"   Rate: {rate:.1f}/min | ETA: {remaining_mins/60:.1f}h")

            # Fetch and parse
            soup = fetch_player_profile(url)
            profile = parse_player_profile(soup, url)

            if profile:
                # Check if career history exists
                career_count = len(profile.get('career_history', []))

                if career_count > 0:
                    with_career += 1
                    print(f"   ✅ Success! {career_count} career entries (2015+)")
                else:
                    print("   ⚠️  Scraped but no career since 2015")

                # Save profile
                safe_name = re.sub(r'[^\w\-]', '_', name.lower())
                profile_file = PROFILES_DIR / f"{safe_name}_{player_id}.json"

                with open(profile_file, 'w', encoding='utf-8') as f:
                    json.dump(profile, f, indent=2, ensure_ascii=False)

                success_count += 1

                # Save progress checkpoint every 100 players
                if i % 100 == 0:
                    checkpoint = {
                        "progress": i,
                        "total": total,
                        "success": success_count,
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    with open(PLAYERS_DIR / "progress_checkpoint.json", 'w') as f:
                        json.dump(checkpoint, f, indent=2)

            else:
                print("   ❌ Scraping failed")
                failed_count += 1
                failed_players.append((name, "Parse failed"))

        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user!")
            print(f"Progress saved: {success_count}/{total} completed")
            break
        except Exception as e:
            print(f"   ❌ Error: {e}")
            failed_count += 1
            failed_players.append((name, str(e)))
            continue

    # Final summary
    elapsed_total = time.time() - start_time

    print("\n" + "=" * 70)
    print("✅ SCRAPING COMPLETE")
    print("=" * 70)
    print(f"Total processed: {success_count + failed_count}/{total}")
    print(f"Success: {success_count}")
    print(f"With career (2015+): {with_career} ({with_career/success_count*100 if success_count > 0 else 0:.1f}%)")
    print(f"Failed: {failed_count}")
    print(f"Total time: {elapsed_total/3600:.1f} hours")
    print(f"Average rate: {(success_count + failed_count)/(elapsed_total/60):.1f} players/min")
    print("=" * 70)

    # Save summary
    summary = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total": total,
        "success": success_count,
        "failed": failed_count,
        "with_career_since_2015": with_career,
        "duration_hours": elapsed_total / 3600,
        "failed_players": [{"name": n, "reason": r} for n, r in failed_players[:50]]
    }

    summary_file = PLAYERS_DIR / "scraping_summary.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"\n📄 Summary saved to: {summary_file}")

if __name__ == "__main__":
    main()
