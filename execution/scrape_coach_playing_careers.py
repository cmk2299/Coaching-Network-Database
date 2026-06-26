#!/usr/bin/env python3
"""
Scrape playing careers for coaches who have a separate spieler profile on TM.

Problem: Many coaches (239 of 396 with networks) have a TM player profile under
a different ID, but scrape_person_profiles.py only scraped their trainer page.
This script:
  1. Scans cached trainer HTML for /profil/spieler/{id} links
  2. Fetches the player profile page (with caching + rate limiting)
  3. Extracts playing career history
  4. Patches the existing person_profile JSON with playing_career + was_player

Usage:
  python scrape_coach_playing_careers.py                  # All coaches with networks
  python scrape_coach_playing_careers.py --coach 5372     # Single coach by trainer ID
  python scrape_coach_playing_careers.py --dry-run        # Show what would be scraped
"""

import json
import re
import sys
import time
import random
from pathlib import Path
from datetime import datetime

try:
    from bs4 import BeautifulSoup
    import requests
except ImportError:
    print("pip install beautifulsoup4 requests --break-system-packages")
    sys.exit(1)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = BASE_DIR / "tmp" / "cache" / "profiles"
NETWORKS_DIR = DATA_DIR / "networks"
PROFILES_DIR = DATA_DIR / "person_profiles"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}
BASE_URL = "https://www.transfermarkt.de"


def find_spieler_info_in_html(trainer_id: str):
    """Extract spieler profile ID and slug from cached trainer HTML.
    Returns (spieler_id, slug) or None.
    """
    cache_path = CACHE_DIR / f"trainer_{trainer_id}.html"
    if not cache_path.exists():
        return None
    html = cache_path.read_text(encoding="utf-8", errors="replace")
    # Match full path like /kasper-hjulmand/profil/spieler/766199
    match = re.search(r"href=\"/([^/]+)/profil/spieler/(\d+)\"", html)
    if match:
        return (match.group(2), match.group(1))
    # Fallback: just the ID
    match = re.search(r"/profil/spieler/(\d+)", html)
    if match:
        return (match.group(1), None)
    return None


def find_coaches_needing_playing_career() -> list[tuple[str, str, str]]:
    """Find coaches with networks but no playing_career, who have a spieler ID on TM.
    Returns: [(trainer_id, coach_name, spieler_id, slug), ...]
    """
    results = []
    network_ids = [f.stem for f in NETWORKS_DIR.glob("*.json")]

    for tid in network_ids:
        prof_path = PROFILES_DIR / f"{tid}.json"
        if not prof_path.exists():
            continue
        profile = json.loads(prof_path.read_text())
        if profile.get("type") != "trainer":
            continue
        if profile.get("playing_career"):
            continue  # Already has data

        info = find_spieler_info_in_html(tid)
        if info:
            spieler_id, slug = info
            results.append((tid, profile.get("name", "?"), spieler_id, slug))

    return sorted(results, key=lambda x: x[1])


def fetch_spieler_page(spieler_id: str, slug=None):
    """Fetch player leistungsdatendetails page with caching and rate limiting.
    Uses /leistungsdatendetails/ which has per-season career data.
    """
    cache_path = CACHE_DIR / f"spieler_{spieler_id}.html"

    # Check cache (30-day TTL)
    if cache_path.exists():
        age_days = (time.time() - cache_path.stat().st_mtime) / 86400
        if age_days < 30:
            return cache_path.read_text(encoding="utf-8", errors="replace")

    if not slug:
        print(f"    No slug for spieler/{spieler_id}, skipping")
        return None

    # Use leistungsdatendetails — has per-season per-competition career data
    url = f"{BASE_URL}/{slug}/leistungsdatendetails/spieler/{spieler_id}"

    try:
        time.sleep(2 + random.random() * 2)  # 2-4s delay
        resp = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        if resp.status_code == 200:
            # Verify we got a real page (not homepage redirect)
            if "leistungsdaten" in resp.url.lower() or "Leistungsdaten" in resp.text[:5000]:
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(resp.text, encoding="utf-8")
                return resp.text
            else:
                print(f"    Redirected to wrong page: {resp.url[:80]}")
                return None
        else:
            print(f"    HTTP {resp.status_code} for spieler/{spieler_id}")
            return None
    except Exception as e:
        print(f"    Error fetching spieler/{spieler_id}: {e}")
        return None


def parse_playing_career(html: str) -> list[dict]:
    """Extract unique career stations (club + season) from leistungsdatendetails page.

    Table format: td[0]=season(YY/YY), td[1]=competition_img, td[2]=competition_link,
                  td[3]=club_link(with img title=club_name), td[4..]=stats

    Returns deduplicated list of {season, club_name, club_tm_id, club_slug}.
    """
    soup = BeautifulSoup(html, "html.parser")
    seen = set()  # (season, club_id) dedup key
    career = []

    table = soup.find("table", class_="items")
    if not table:
        return career

    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 4:
            continue

        # Skip summary row ("Insgesamt :")
        first_text = cells[0].get_text(strip=True) + cells[1].get_text(strip=True)
        if "Insgesamt" in first_text or "insgesamt" in first_text:
            continue

        # Season from td[0] — format "00/01" meaning 2000/2001
        season_raw = cells[0].get_text(strip=True)
        if not re.match(r"\d{2}/\d{2}", season_raw):
            continue

        # Club from td[3] — link to /verein/{id}
        club_link = cells[3].find("a", href=re.compile(r"/verein/\d+"))
        if not club_link:
            continue

        href = club_link["href"]
        m = re.search(r"/verein/(\d+)", href)
        if not m:
            continue
        club_id = int(m.group(1))

        # Club name: from link title, img alt, img title, or slug
        club_name = ""
        # Priority 1: link title attribute (most reliable)
        club_name = club_link.get("title", "")
        # Priority 2: img alt attribute
        if not club_name or club_name.strip() in ("", "\xa0"):
            img = cells[3].find("img")
            if img:
                club_name = img.get("alt", "") or img.get("title", "")
        # Priority 3: link text
        if not club_name or club_name.strip() in ("", "\xa0"):
            club_name = club_link.get_text(strip=True)

        # Club slug from URL
        slug_m = re.search(r"/([^/]+)/startseite/verein/", href)
        club_slug = slug_m.group(1) if slug_m else None

        # Dedup: one entry per (season, club)
        key = (season_raw, club_id)
        if key in seen:
            continue
        seen.add(key)

        career.append({
            "season": season_raw,
            "club_name": club_name.strip(),
            "club_tm_id": club_id,
            "club_slug": club_slug,
        })

    return career


def patch_profile(trainer_id: str, playing_career: list[dict]) -> bool:
    """Patch existing profile JSON with playing career data."""
    prof_path = PROFILES_DIR / f"{trainer_id}.json"
    if not prof_path.exists():
        return False

    profile = json.loads(prof_path.read_text())
    profile["playing_career"] = playing_career
    profile["was_player"] = True
    profile["playing_career_scraped_at"] = datetime.now().isoformat()

    prof_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2))
    return True


def main():
    dry_run = "--dry-run" in sys.argv
    single_coach = None
    for i, arg in enumerate(sys.argv):
        if arg == "--coach" and i + 1 < len(sys.argv):
            single_coach = sys.argv[i + 1]

    coaches = find_coaches_needing_playing_career()
    if single_coach:
        coaches = [c for c in coaches if c[0] == single_coach]

    print(f"Found {len(coaches)} coaches needing playing career data")

    if dry_run:
        for tid, name, sid, slug in coaches:
            print(f"  {name} (trainer/{tid} → spieler/{sid}, slug={slug})")
        return

    patched = 0
    failed = 0
    already_cached = 0

    for i, (tid, name, sid, slug) in enumerate(coaches):
        print(f"[{i+1}/{len(coaches)}] {name} (trainer/{tid} → spieler/{sid})")

        # Check if already cached
        cache_path = CACHE_DIR / f"spieler_{sid}.html"
        if cache_path.exists():
            html = cache_path.read_text(encoding="utf-8", errors="replace")
            already_cached += 1
        else:
            html = fetch_spieler_page(sid, slug)

        if not html:
            print("  → Failed to fetch")
            failed += 1
            continue

        career = parse_playing_career(html)
        print(f"  → {len(career)} career entries")

        if career:
            if patch_profile(tid, career):
                patched += 1
            else:
                print("  → Failed to patch profile")
                failed += 1
        else:
            # Mark as checked (empty playing career — maybe amateur)
            patch_profile(tid, [])
            print("  → Empty career (amateur/no data)")

    print(f"\nDone: {patched} patched, {failed} failed, {already_cached} from cache")


if __name__ == "__main__":
    main()
