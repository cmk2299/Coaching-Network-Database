#!/usr/bin/env python3
"""
Batch-Scraper: GemeinsameSpiele für alle Coaches mit player_tm_id.

Scrapt die TM-Seite /x/gemeinsameSpiele/spieler/{player_id} für jeden Coach,
der als Spieler aktiv war. Speichert Ergebnisse als JSON pro Coach.

Usage:
    python execution/scrape_gemeinsame_spiele.py --dry-run
    python execution/scrape_gemeinsame_spiele.py --all --min-matches 5
    python execution/scrape_gemeinsame_spiele.py --all --skip-existing
    python execution/scrape_gemeinsame_spiele.py --tm-id 49850
"""

import argparse
import json
import re
import time
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ── Paths ──────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PROFILES_DIR = DATA_DIR / "person_profiles"
OUTPUT_DIR = DATA_DIR / "gemeinsame_spiele"
CACHE_DIR = PROJECT_ROOT / "tmp" / "cache" / "gemeinsame_spiele"

# ── Config ─────────────────────────────────────────────────────────────────────
REQUEST_DELAY = 3          # seconds between requests
SESSION_PAUSE_EVERY = 50   # pause after N requests
SESSION_PAUSE_DURATION = 30
CACHE_TTL_DAYS = 30

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
]

request_count = 0


def get_headers():
    """Rotate user agents."""
    global request_count
    ua = USER_AGENTS[request_count % len(USER_AGENTS)]
    return {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    }


def fetch_page(url: str, cache_key: str = None):
    """Fetch page with caching, rate limiting, and retry on 429."""
    global request_count

    # Check HTML cache first
    if cache_key:
        cache_file = CACHE_DIR / f"{cache_key}.html"
        if cache_file.exists():
            age_days = (datetime.now().timestamp() - cache_file.stat().st_mtime) / 86400
            if age_days < CACHE_TTL_DAYS:
                return BeautifulSoup(cache_file.read_text(encoding="utf-8"), "lxml")

    # Rate limiting
    time.sleep(REQUEST_DELAY)
    request_count += 1

    # Session pause every N requests
    if request_count % SESSION_PAUSE_EVERY == 0:
        print(f"  [Session pause {SESSION_PAUSE_DURATION}s after {request_count} requests]")
        time.sleep(SESSION_PAUSE_DURATION)

    try:
        resp = requests.get(url, headers=get_headers(), timeout=30)

        if resp.status_code == 429:
            print("  Rate limited — waiting 60s...")
            time.sleep(60)
            return fetch_page(url, cache_key)

        resp.raise_for_status()

        # Cache HTML
        if cache_key:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            (CACHE_DIR / f"{cache_key}.html").write_text(resp.text, encoding="utf-8")

        return BeautifulSoup(resp.text, "lxml")

    except requests.exceptions.HTTPError as e:
        print(f"  HTTP error {e.response.status_code}: {url}")
        return None
    except Exception as e:
        print(f"  Request error: {e}")
        return None


def parse_int(text: str) -> int:
    """Parse integer from text, handling German number format (1.234 → 1234)."""
    if not text:
        return 0
    cleaned = re.sub(r"[^\d]", "", str(text))
    return int(cleaned) if cleaned else 0


def get_total_pages(soup: BeautifulSoup) -> int:
    """Extract total pages from TM pagination."""
    max_page = 1
    # Try tm-pagination__list-item links
    for a in soup.find_all("a", href=re.compile(r"/page/(\d+)")):
        m = re.search(r"/page/(\d+)", a.get("href", ""))
        if m:
            max_page = max(max_page, int(m.group(1)))
    return max_page


def parse_teammates_page(soup: BeautifulSoup) -> list:
    """
    Parse one page of the gemeinsameSpiele table.

    TM table structure:
    - inline-table for player name/position
    - zentriert cells: [Spiele, Teams, Tore-Beteiligung, Torbeteiligung, Minuten]
    """
    teammates = []

    table = soup.find("table", class_="items")
    if not table:
        return teammates

    for row in table.find_all("tr"):
        inline_table = row.find("table", class_="inline-table")
        if not inline_table:
            continue

        # Name + TM-URL
        name_link = inline_table.find("a")
        if not name_link:
            continue
        name = name_link.get_text(strip=True)
        href = name_link.get("href", "")
        tm_url = href if href.startswith("/") else ""

        # TM ID from URL (e.g. /thomas-muller/profil/spieler/58358)
        tm_id = None
        id_match = re.search(r"/spieler/(\d+)", tm_url)
        if id_match:
            tm_id = int(id_match.group(1))

        # Position (second row of inline-table)
        position = ""
        rows = inline_table.find_all("tr")
        if len(rows) > 1:
            position = rows[1].get_text(strip=True)

        # Stats: Spiele | Teams | ... | Minuten
        cells = row.find_all("td", class_="zentriert")
        shared_matches = parse_int(cells[0].get_text()) if len(cells) > 0 else 0
        teams_together = parse_int(cells[1].get_text()) if len(cells) > 1 else 0
        total_minutes = parse_int(cells[4].get_text()) if len(cells) > 4 else 0

        teammates.append({
            "name": name,
            "tm_id": tm_id,
            "tm_url": tm_url,
            "position": position,
            "shared_matches": shared_matches,
            "teams_together": teams_together,
            "total_minutes": total_minutes,
        })

    return teammates


def scrape_one_coach(coach: dict, min_matches: int = 0) -> dict:
    """Scrape gemeinsameSpiele for a single coach."""
    trainer_id = coach["trainer_id"]
    player_id = coach["player_id"]
    name = coach["name"]

    print(f"\n  Scraping: {name} (trainer={trainer_id}, player={player_id})")

    base_url = f"https://www.transfermarkt.de/x/gemeinsameSpiele/spieler/{player_id}"

    # Page 1
    soup = fetch_page(base_url, f"{player_id}_p1")
    if not soup:
        print("  ✗ Failed to fetch page 1")
        return _empty_result(coach)

    # Check if redirected to homepage (amateur player)
    if soup.find("div", class_="no-data-box") or not soup.find("table", class_="items"):
        print("  ✗ No gemeinsameSpiele data (amateur/no data)")
        return _empty_result(coach)

    total_pages = get_total_pages(soup)
    print(f"  Pages: {total_pages}")

    all_teammates = parse_teammates_page(soup)
    print(f"  Page 1: {len(all_teammates)} entries")

    for page in range(2, total_pages + 1):
        page_url = f"{base_url}/page/{page}"
        page_soup = fetch_page(page_url, f"{player_id}_p{page}")
        if not page_soup:
            break
        page_entries = parse_teammates_page(page_soup)
        print(f"  Page {page}: {len(page_entries)} entries")
        all_teammates.extend(page_entries)
        if not page_entries:
            break

    # Sort by shared_matches desc
    all_teammates.sort(key=lambda x: x.get("shared_matches", 0), reverse=True)

    # Apply min_matches filter
    filtered = [t for t in all_teammates if t.get("shared_matches", 0) >= min_matches]

    result = {
        "coach_tm_id": trainer_id,
        "coach_name": name,
        "player_tm_id": player_id,
        "scraped_at": datetime.now().isoformat(),
        "total_teammates": len(all_teammates),
        "total_filtered": len(filtered),
        "min_matches_filter": min_matches,
        "pages_scraped": total_pages,
        "teammates": filtered,
    }

    print(f"  ✓ Done: {len(all_teammates)} total, {len(filtered)} with {min_matches}+ matches")
    return result


def _empty_result(coach: dict) -> dict:
    return {
        "coach_tm_id": coach["trainer_id"],
        "coach_name": coach["name"],
        "player_tm_id": coach["player_id"],
        "scraped_at": datetime.now().isoformat(),
        "total_teammates": 0,
        "total_filtered": 0,
        "min_matches_filter": 0,
        "pages_scraped": 0,
        "teammates": [],
    }


TRAINER_CACHE_DIR = PROJECT_ROOT / "tmp" / "cache" / "profiles"


def find_player_id_from_trainer_html(trainer_id: int):
    """Extract spieler TM-ID from cached trainer HTML page."""
    cache_path = TRAINER_CACHE_DIR / f"trainer_{trainer_id}.html"
    if not cache_path.exists():
        return None
    html = cache_path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r'href="/[^/]+/profil/spieler/(\d+)"', html)
    if m:
        return int(m.group(1))
    m = re.search(r"/profil/spieler/(\d+)", html)
    if m:
        return int(m.group(1))
    return None


NETWORKS_DIR = DATA_DIR / "networks"


def load_coaches_with_player_ids() -> list:
    """Load coaches with networks that have a resolvable player_tm_id.

    Only includes coaches that have a network JSON (= dashboard-relevant).
    Sources (in priority order):
    1. profile["player_tm_id"] — set by scrape_coach_playing_careers.py
    2. Cached trainer HTML — contains href to /profil/spieler/{id}
    """
    # Only coaches with networks
    network_ids = {int(f.stem) for f in NETWORKS_DIR.glob("*.json")}

    coaches = []
    seen_trainer_ids = set()

    for f in PROFILES_DIR.glob("*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            trainer_id = d.get("tm_id")
            if not trainer_id or trainer_id in seen_trainer_ids:
                continue
            # Only coaches with networks
            if trainer_id not in network_ids:
                continue

            # Source 1: explicit player_tm_id
            player_id = d.get("player_tm_id")

            # Source 2: cached trainer HTML
            if not player_id:
                player_id = find_player_id_from_trainer_html(trainer_id)

            if player_id and player_id != trainer_id:
                coaches.append({
                    "name": d.get("name", "?"),
                    "trainer_id": trainer_id,
                    "player_id": player_id,
                })
                seen_trainer_ids.add(trainer_id)

        except Exception:
            pass

    coaches.sort(key=lambda x: x["name"])
    return coaches


def is_fresh(output_file: Path, max_age_days: int = 7) -> bool:
    """Check if output file exists and is fresh."""
    if not output_file.exists():
        return False
    age_days = (datetime.now().timestamp() - output_file.stat().st_mtime) / 86400
    return age_days < max_age_days


def main():
    parser = argparse.ArgumentParser(description="Scrape gemeinsameSpiele for coaches with playing career")
    parser.add_argument("--all", action="store_true", help="Scrape all coaches with player_tm_id")
    parser.add_argument("--tm-id", type=int, help="Single coach trainer tm_id")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be scraped, don't scrape")
    parser.add_argument("--min-matches", type=int, default=0, help="Minimum shared matches to include (default: 0 = all)")
    parser.add_argument("--skip-existing", action="store_true", help="Skip coaches with fresh output (< 7 days)")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    coaches = load_coaches_with_player_ids()
    print(f"\nFound {len(coaches)} coaches with player_tm_id")

    # Filter to requested scope
    if args.tm_id:
        coaches = [c for c in coaches if c["trainer_id"] == args.tm_id]
        if not coaches:
            print(f"ERROR: No coach with trainer tm_id={args.tm_id}")
            return

    if args.dry_run:
        print(f"\n{'─'*60}")
        print(f"DRY RUN — would scrape {len(coaches)} coaches:")
        print(f"{'─'*60}")
        for c in coaches:
            out = OUTPUT_DIR / f"{c['trainer_id']}.json"
            status = "✓ exists" if out.exists() else "○ new"
            fresh = " (fresh)" if is_fresh(out) else ""
            print(f"  [{status}{fresh}] {c['name']:30s} trainer={c['trainer_id']}, player={c['player_id']}")
        print(f"\nEstimated requests: ~{len(coaches) * 8} ({len(coaches)} coaches × ~8 pages avg)")
        print(f"Estimated time: ~{len(coaches) * 8 * REQUEST_DELAY // 60} minutes")
        return

    # Run scraping
    success, failed, skipped = 0, 0, 0
    total = len(coaches)
    t_start = time.time()

    for i, coach in enumerate(coaches, 1):
        out_path = OUTPUT_DIR / f"{coach['trainer_id']}.json"
        print(f"\n[{i}/{total}] {coach['name']}")

        if args.skip_existing and is_fresh(out_path):
            print("  ↷ Skipping (fresh output exists)")
            skipped += 1
            continue

        try:
            result = scrape_one_coach(coach, min_matches=args.min_matches)
            out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            success += 1
        except Exception as e:
            print(f"  ✗ Error: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    elapsed = time.time() - t_start
    print(f"\n{'='*60}")
    print(f"  Done in {elapsed:.0f}s")
    print(f"  Success: {success}  Failed: {failed}  Skipped: {skipped}")
    print(f"  Output: {OUTPUT_DIR}")

    # Summary stats
    total_teammates = 0
    coaches_with_data = 0
    for f in OUTPUT_DIR.glob("*.json"):
        try:
            d = json.loads(f.read_text())
            n = d.get("total_teammates", 0)
            total_teammates += n
            if n > 0:
                coaches_with_data += 1
        except Exception:
            pass
    print(f"  Total teammates scraped: {total_teammates} ({coaches_with_data} coaches with data)")


if __name__ == "__main__":
    main()
