#!/usr/bin/env python3
"""
Batch Scraper: Players Used per Coach — Layer 3 Execution Script

Scrapes the TM "eingesetzteSpieler" page for each coach to get real
games, goals, assists, and minutes data per player.

URL: https://www.transfermarkt.de/trainer/eingesetzteSpieler/trainer/{id}/plus/1

Table columns (16 cells per player row):
  [0]  Player image area
  [1]  (inner row)
  [2]  Player name (td.hauptlink)
  [3]  Position
  [4]  Nationality flag (td.zentriert)
  [5]  Age (td.zentriert)
  [6]  Market value (td.rechts)
  [7]  Vereine / Clubs count (td.zentriert)
  [8]  Wettbewerbe / Competitions (td.zentriert)
  [9]  Saisons (td.zentriert)
  [10] Einsätze / Appearances (td.zentriert.hauptlink)
  [11] Tore / Goals (td.zentriert)
  [12] Assists (td.zentriert)
  [13] Gelbe Karten (td.zentriert)
  [14] Rote Karten (td.zentriert)
  [15] Minuten / Minutes (td.rechts)

Pagination: 25 entries per page, URL suffix /page/{n}

Output: data/players_used/{tm_id}.json per coach

Usage:
    python scrape_players_used_batch.py                    # All coaches with networks
    python scrape_players_used_batch.py --only 26099 5372  # Specific coaches
    python scrape_players_used_batch.py --skip-cached      # Only scrape uncached
"""

import argparse
import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
CACHE_DIR = BASE_DIR / "tmp" / "cache"
OUTPUT_DIR = BASE_DIR / "data" / "players_used"
NETWORKS_DIR = BASE_DIR / "data" / "networks"

TM_BASE = "https://www.transfermarkt.de"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}
REQUEST_DELAY = 3  # seconds between requests
CACHE_TTL_DAYS = 30


def ensure_dirs():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def get_cache_path(coach_id: int) -> Path:
    return CACHE_DIR / f"coach_{coach_id}_players_used_v2.json"


def is_cache_valid(cache_path: Path) -> bool:
    if not cache_path.exists():
        return False
    try:
        with open(cache_path) as f:
            data = json.load(f)
        cached_at = data.get("cached_at", "")
        if not cached_at:
            return False
        cached_date = datetime.fromisoformat(cached_at)
        return datetime.now() - cached_date < timedelta(days=CACHE_TTL_DAYS)
    except (json.JSONDecodeError, ValueError):
        return False


def load_cached(coach_id: int) -> Optional[dict]:
    cache_path = get_cache_path(coach_id)
    if is_cache_valid(cache_path):
        with open(cache_path) as f:
            return json.load(f)
    return None


def save_cache(coach_id: int, data: dict):
    cache_path = get_cache_path(coach_id)
    data["cached_at"] = datetime.now().isoformat()
    with open(cache_path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch_page(url: str) -> Optional[BeautifulSoup]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except requests.RequestException as e:
        print(f"    Fetch error: {e}")
        return None


def parse_int(text: str) -> int:
    """Parse integer, handling dots as thousands separators and apostrophes."""
    if not text or text.strip() == "-":
        return 0
    cleaned = text.strip().replace(".", "").replace("'", "").replace("'", "")
    cleaned = re.sub(r"[^\d-]", "", cleaned)
    try:
        return int(cleaned) if cleaned else 0
    except ValueError:
        return 0


def get_max_page(soup: BeautifulSoup) -> int:
    """Extract max page number from pagination."""
    pager = soup.find("div", class_="pager")
    if not pager:
        return 1
    links = pager.find_all("a")
    max_page = 1
    for link in links:
        href = link.get("href", "")
        match = re.search(r"/page/(\d+)", href)
        if match:
            page_num = int(match.group(1))
            max_page = max(max_page, page_num)
    return max_page


def parse_players_from_table(soup: BeautifulSoup) -> list:
    """Parse player rows from the eingesetzteSpieler table."""
    players = []

    table = soup.find("table", class_="items")
    if not table:
        return players

    tbody = table.find("tbody")
    if not tbody:
        return players

    rows = tbody.find_all("tr")

    for row in rows:
        cells = row.find_all("td")

        # Player rows have 16 cells; skip inner/sub rows (typically 2 cells)
        if len(cells) < 10:
            continue

        # Find player name via hauptlink
        name_cell = row.find("td", class_="hauptlink")
        if not name_cell:
            continue

        name_link = name_cell.find("a")
        if not name_link:
            continue

        name = name_link.get_text(strip=True)
        href = name_link.get("href", "")

        # Extract player_id
        player_id_match = re.search(r"/spieler/(\d+)", href)
        if not player_id_match:
            continue
        player_id = int(player_id_match.group(1))

        # Position: the cell right after the name cell, or look for it
        position = ""
        for cell in cells:
            text = cell.get_text(strip=True)
            if text and any(p in text for p in [
                "Torwart", "Verteidiger", "Mittelfeld", "Stürmer",
                "Abwehr", "Innenverteidiger", "Rechter", "Linker",
                "Defensives", "Zentrales", "Offensives", "Hängende",
                "Rechtsaußen", "Linksaußen", "Mittelstürmer", "Stopper"
            ]):
                if not cell.get("class") or "hauptlink" not in cell.get("class", []):
                    position = text
                    break

        # Nationality from flag image
        nationality = ""
        flag_imgs = row.find_all("img", class_="flaggenrahmen")
        if flag_imgs:
            # Take the first flag that has a title
            for fi in flag_imgs:
                title = fi.get("title", "")
                if title:
                    nationality = title
                    break

        # Stats: use cell index from known column structure
        # Cells with class "zentriert" in order:
        zentriert_cells = row.find_all("td", class_="zentriert")
        rechts_cells = row.find_all("td", class_="rechts")

        # The hauptlink cell within zentriert cells is the appearances cell
        appearances = 0
        goals = 0
        assists = 0
        minutes = 0

        # Find appearances: it's the zentriert cell with class "hauptlink"
        for zc in zentriert_cells:
            if "hauptlink" in (zc.get("class") or []):
                appearances = parse_int(zc.get_text(strip=True))
                # Goals and assists are the next 2 zentriert cells after appearances
                idx = zentriert_cells.index(zc)
                if idx + 1 < len(zentriert_cells):
                    goals = parse_int(zentriert_cells[idx + 1].get_text(strip=True))
                if idx + 2 < len(zentriert_cells):
                    assists = parse_int(zentriert_cells[idx + 2].get_text(strip=True))
                break

        # Minutes: last rechts cell
        if rechts_cells:
            minutes = parse_int(rechts_cells[-1].get_text(strip=True))

        players.append({
            "name": name,
            "player_id": player_id,
            "position": position,
            "nationality": nationality,
            "appearances": appearances,
            "goals": goals,
            "assists": assists,
            "minutes": minutes,
        })

    return players


def scrape_players_used(coach_id: int, coach_name: str = "") -> dict:
    """
    Scrape all pages of player appearance data for a coach.
    Handles pagination automatically.
    """
    # Check cache
    cached = load_cached(coach_id)
    if cached:
        return cached

    base_url = f"{TM_BASE}/trainer/eingesetzteSpieler/trainer/{coach_id}/plus/1"
    all_players = []
    seen_ids = set()

    # Fetch page 1
    soup = fetch_page(base_url)
    if not soup:
        result = {"coach_id": coach_id, "url": base_url, "total_players": 0, "players": []}
        save_cache(coach_id, result)
        return result

    max_page = get_max_page(soup)

    # Parse page 1
    page_players = parse_players_from_table(soup)
    for p in page_players:
        if p["player_id"] not in seen_ids:
            all_players.append(p)
            seen_ids.add(p["player_id"])

    # Fetch remaining pages
    for page_num in range(2, max_page + 1):
        time.sleep(REQUEST_DELAY)
        page_url = f"{base_url}/page/{page_num}"
        soup = fetch_page(page_url)
        if not soup:
            break

        page_players = parse_players_from_table(soup)
        if not page_players:
            break  # No more data

        for p in page_players:
            if p["player_id"] not in seen_ids:
                all_players.append(p)
                seen_ids.add(p["player_id"])

    # Sort by appearances descending
    all_players.sort(key=lambda p: -p["appearances"])

    result = {
        "coach_id": coach_id,
        "url": base_url,
        "total_players": len(all_players),
        "pages_scraped": max_page,
        "players": all_players,
    }

    save_cache(coach_id, result)
    return result


def save_output(coach_id: int, data: dict):
    out_path = OUTPUT_DIR / f"{coach_id}.json"
    with open(out_path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Batch scrape players used per coach")
    parser.add_argument("--only", nargs="+", type=int, help="Specific coach TM IDs")
    parser.add_argument("--skip-cached", action="store_true", help="Skip coaches with valid cache")
    args = parser.parse_args()

    ensure_dirs()

    if args.only:
        coach_ids = args.only
    else:
        coach_ids = sorted([int(f.stem) for f in NETWORKS_DIR.glob("*.json")])

    print(f"Scraping players used for {len(coach_ids)} coaches...")
    print(f"  Cache TTL: {CACHE_TTL_DAYS} days | Delay: {REQUEST_DELAY}s")

    success = 0
    errors = 0
    skipped = 0
    total_players = 0
    start_time = time.time()

    for i, cid in enumerate(coach_ids):
        # Load coach name from network
        net_path = NETWORKS_DIR / f"{cid}.json"
        coach_name = ""
        if net_path.exists():
            with open(net_path) as f:
                net = json.load(f)
            coach_name = net.get("center", "")

        # Skip if cached
        if args.skip_cached and is_cache_valid(get_cache_path(cid)):
            skipped += 1
            continue

        try:
            data = scrape_players_used(cid, coach_name)
            save_output(cid, data)

            n_players = data.get("total_players", 0)
            n_pages = data.get("pages_scraped", 1)
            total_players += n_players

            top = data["players"][0] if data["players"] else None
            top_str = f", top: {top['name']} ({top['appearances']} app.)" if top else ""

            success += 1
            elapsed = time.time() - start_time
            remaining = (elapsed / max(success, 1)) * (len(coach_ids) - i - 1 - skipped)

            if (i + 1) % 10 == 0 or n_players > 50:
                print(f"  [{i+1}/{len(coach_ids)}] {coach_name or cid}: {n_players} players ({n_pages}p){top_str} [{elapsed:.0f}s, ~{remaining/60:.0f}m left]")

        except Exception as e:
            errors += 1
            print(f"  [{i+1}/{len(coach_ids)}] ERROR {cid}: {e}")

    elapsed = time.time() - start_time
    print(f"\nDone in {elapsed:.0f}s: {success} scraped, {skipped} cached, {errors} errors")
    print(f"Total players: {total_players}")
    print(f"Output: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
