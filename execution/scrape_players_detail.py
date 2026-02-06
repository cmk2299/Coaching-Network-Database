#!/usr/bin/env python3
"""
Scrape detailed player statistics for a coach.
Extracts top players by minutes played from eingesetzteSpieler page.
"""

import json
import os
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

# Base URL
TM_BASE = "https://www.transfermarkt.de"

# Directories
BASE_DIR = Path(__file__).parent.parent
CACHE_DIR = BASE_DIR / "tmp" / "cache"
RAW_HTML_DIR = BASE_DIR / "tmp" / "raw_html"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
RAW_HTML_DIR.mkdir(parents=True, exist_ok=True)

# Request headers
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}


def get_cache_path(cache_key: str) -> Path:
    """Get path for cache file."""
    return CACHE_DIR / f"{cache_key}.json"


def load_from_cache(cache_key: str, max_age_hours: int = 24) -> Optional[dict]:
    """Load data from cache if fresh enough."""
    cache_path = get_cache_path(cache_key)
    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            cached_at = datetime.fromisoformat(data.get("cached_at", "2000-01-01"))
            if datetime.now() - cached_at < timedelta(hours=max_age_hours):
                return data
        except (json.JSONDecodeError, ValueError):
            pass
    return None


def save_to_cache(cache_key: str, data: dict):
    """Save data to cache."""
    data["cached_at"] = datetime.now().isoformat()
    cache_path = get_cache_path(cache_key)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def fetch_page(url: str) -> Optional[BeautifulSoup]:
    """Fetch a page and return BeautifulSoup object."""
    try:
        time.sleep(2)  # Rate limiting
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return BeautifulSoup(response.text, "lxml")
    except requests.RequestException as e:
        print(f"  Error fetching {url}: {e}")
        return None


def parse_minutes(minutes_str: str) -> int:
    """Parse minutes string like \"7.665'\" to integer 7665."""
    if not minutes_str:
        return 0
    # Remove quotes, dots, apostrophes
    clean = minutes_str.replace("'", "").replace(".", "").replace(",", "").strip()
    try:
        return int(clean)
    except ValueError:
        return 0


def parse_market_value(value_str: str) -> str:
    """Clean up market value string."""
    if not value_str:
        return "-"
    return value_str.strip()


def get_total_pages(soup: BeautifulSoup) -> int:
    """Extract total number of pages from pagination."""
    # Look for pagination div
    pager = soup.find("div", class_="pager")
    if pager:
        page_links = pager.find_all("a")
        max_page = 1
        for link in page_links:
            href = link.get("href", "")
            match = re.search(r"/page/(\d+)", href)
            if match:
                max_page = max(max_page, int(match.group(1)))
        return max_page

    # Alternative: look for tm-pagination
    pagination = soup.find("ul", class_="tm-pagination")
    if pagination:
        page_links = pagination.find_all("a")
        max_page = 1
        for link in page_links:
            href = link.get("href", "")
            match = re.search(r"/page/(\d+)", href)
            if match:
                max_page = max(max_page, int(match.group(1)))
        return max_page

    # Check for next link
    next_link = soup.find("link", rel="next")
    if next_link:
        href = next_link.get("href", "")
        match = re.search(r"/page/(\d+)", href)
        if match:
            # There's at least one more page
            return int(match.group(1))

    return 1


def parse_players_from_table(soup: BeautifulSoup) -> list:
    """Parse players from a single page's table."""
    players = []

    table = soup.find("table", class_="items")
    if not table:
        return players

    rows = table.find_all("tr")

    for row in rows[1:]:  # Skip header row
        # Skip separator rows
        if row.find("td", class_="extrarow"):
            continue

        player_data = {}

        # Find player info via inline-table
        inline = row.find("table", class_="inline-table")
        if not inline:
            continue

        # Player name and URL - look in hauptlink cell first
        hauptlink = inline.find("td", class_="hauptlink")
        if hauptlink:
            name_link = hauptlink.find("a")
        else:
            name_link = inline.find("a", href=re.compile(r"/profil/spieler/"))

        if not name_link:
            # Fallback: any link with player profile
            name_link = inline.find("a", href=re.compile(r"/spieler/"))

        if name_link:
            player_data["name"] = name_link.get_text(strip=True)
            href = name_link.get("href", "")
            if href and href != "#":
                player_data["url"] = TM_BASE + href

            # Extract player ID
            id_match = re.search(r"/spieler/(\d+)", href)
            if id_match:
                player_data["player_id"] = int(id_match.group(1))

        if not player_data.get("name"):
            continue  # Skip if no name found

        # Position (second row in inline-table)
        pos_rows = inline.find_all("tr")
        if len(pos_rows) > 1:
            player_data["position"] = pos_rows[1].get_text(strip=True)

        # Nationality flag
        flag_img = row.find("img", class_="flaggenrahmen")
        if flag_img:
            player_data["nationality"] = flag_img.get("title", "")

        # Stats from zentriert cells
        zentriert = row.find_all("td", class_="zentriert")

        if len(zentriert) >= 2:
            # Age (first zentriert after flag is age)
            for cell in zentriert:
                text = cell.get_text(strip=True)
                if text.isdigit() and 15 <= int(text) <= 50:
                    player_data["age"] = int(text)
                    break

        # Find appearances - it's in zentriert[5]
        if len(zentriert) >= 6:
            apps_text = zentriert[5].get_text(strip=True)
            try:
                player_data["appearances"] = int(apps_text)
            except ValueError:
                player_data["appearances"] = 0

            # Goals (index 6), Assists (index 7)
            if len(zentriert) >= 7:
                try:
                    player_data["goals"] = int(zentriert[6].get_text(strip=True) or 0)
                except ValueError:
                    player_data["goals"] = 0
            if len(zentriert) >= 8:
                try:
                    player_data["assists"] = int(zentriert[7].get_text(strip=True) or 0)
                except ValueError:
                    player_data["assists"] = 0

        # Market value and minutes from rechts cells
        rechts = row.find_all("td", class_="rechts")
        if len(rechts) >= 1:
            player_data["market_value"] = parse_market_value(rechts[0].get_text(strip=True))
        if len(rechts) >= 2:
            player_data["minutes"] = parse_minutes(rechts[1].get_text(strip=True))
        else:
            player_data["minutes"] = 0

        if player_data.get("name"):
            players.append(player_data)

    return players


def scrape_players_used_detail(coach_id: int, top_n: int = None) -> dict:
    """
    Scrape detailed player statistics from eingesetzteSpieler page.
    Fetches ALL pages of players (pagination support).

    Args:
        coach_id: Transfermarkt coach ID
        top_n: Number of top players to return (by minutes). None = all players.

    Returns:
        Dict with player list sorted by minutes
    """
    cache_key = f"coach_{coach_id}_players_detail_full"

    # Check cache
    cached = load_from_cache(cache_key, max_age_hours=24)
    if cached:
        print(f"  Using cached data for {cache_key}")
        return cached

    # Build URL for detailed players used page
    base_url = f"{TM_BASE}/trainer/eingesetzteSpieler/trainer/{coach_id}/plus/1"
    print(f"  Fetching: {base_url}")

    soup = fetch_page(base_url)
    if not soup:
        return {"players": [], "total_players": 0, "coach_id": coach_id}

    # Get total pages
    total_pages = get_total_pages(soup)
    print(f"  Found {total_pages} page(s) of players")

    # Parse first page
    all_players = parse_players_from_table(soup)
    print(f"  Page 1: {len(all_players)} players")

    # Fetch remaining pages
    for page_num in range(2, total_pages + 1):
        page_url = f"{base_url}/page/{page_num}"
        print(f"  Fetching: {page_url}")
        page_soup = fetch_page(page_url)
        if page_soup:
            page_players = parse_players_from_table(page_soup)
            print(f"  Page {page_num}: {len(page_players)} players")
            all_players.extend(page_players)

    # Sort by minutes (descending)
    all_players.sort(key=lambda x: x.get("minutes", 0), reverse=True)

    # Apply top_n limit if specified
    if top_n:
        return_players = all_players[:top_n]
    else:
        return_players = all_players

    print(f"  Total: {len(all_players)} players across {total_pages} pages")

    result = {
        "coach_id": coach_id,
        "url": base_url,
        "total_players": len(all_players),
        "players": return_players,
    }

    # Cache result
    save_to_cache(cache_key, result)

    return result


def scrape_players_for_coach_url(coach_profile_url: str, top_n: int = None) -> Optional[dict]:
    """
    Scrape players used given a coach profile URL.
    Extracts coach ID and calls scrape_players_used_detail.

    Args:
        coach_profile_url: URL to coach profile
        top_n: Number of players to return. None = all players.
    """
    # Extract coach ID from URL
    match = re.search(r"/trainer/(\d+)", coach_profile_url)
    if not match:
        print(f"  Could not extract coach ID from {coach_profile_url}")
        return None

    coach_id = int(match.group(1))
    return scrape_players_used_detail(coach_id, top_n)


if __name__ == "__main__":
    import sys

    # Default test with Alexander Blessin
    coach_id = 26099
    if len(sys.argv) > 1:
        coach_id = int(sys.argv[1])

    result = scrape_players_used_detail(coach_id, top_n=None)  # Get ALL players

    print(f"\n{'='*60}")
    print(f"ALL PLAYERS BY MINUTES (Coach ID: {coach_id})")
    print(f"Total: {result.get('total_players', 0)} players")
    print(f"{'='*60}")

    for i, player in enumerate(result.get("players", [])[:30], 1):
        name = player.get("name", "Unknown")
        pos = player.get("position", "")
        minutes = player.get("minutes", 0)
        appearances = player.get("appearances", 0)
        market = player.get("market_value", "-")

        print(f"{i:2}. {name:<25} {pos:<20} {appearances:>4} apps  {minutes:>6}' {market:>12}")
