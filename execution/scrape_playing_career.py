#!/usr/bin/env python3
"""
Scrape playing career and achievements for coaches.
Gets data from Transfermarkt player profile page.
"""

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List

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


def fetch_page(url: str, delay: float = 1.5) -> Optional[BeautifulSoup]:
    """Fetch a page and return BeautifulSoup object."""
    try:
        time.sleep(delay)
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return BeautifulSoup(response.text, "lxml")
    except requests.RequestException as e:
        print(f"  Error fetching {url}: {e}")
        return None


def get_cache_path(cache_key: str) -> Path:
    """Get path for cache file."""
    return CACHE_DIR / f"{cache_key}.json"


def load_from_cache(cache_key: str, max_age_hours: int = 168) -> Optional[dict]:
    """Load data from cache if fresh enough (default 7 days)."""
    cache_path = get_cache_path(cache_key)
    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            cached_at = datetime.fromisoformat(data.get("_cached_at", "2000-01-01"))
            age = (datetime.now() - cached_at).total_seconds() / 3600
            if age < max_age_hours:
                return data
        except (json.JSONDecodeError, ValueError):
            pass
    return None


def save_to_cache(cache_key: str, data: dict):
    """Save data to cache."""
    data["_cached_at"] = datetime.now().isoformat()
    cache_path = get_cache_path(cache_key)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def extract_player_id_from_coach_profile(coach_url: str) -> Optional[tuple]:
    """
    Extract player ID and slug from coach profile page.
    Returns (player_id, player_slug) or None if no playing career.
    """
    soup = fetch_page(coach_url)
    if not soup:
        return None

    # Look for link to player profile
    player_link = soup.find("a", href=re.compile(r"/[\w-]+/profil/spieler/\d+"))
    if player_link:
        href = player_link.get("href", "")
        match = re.search(r"/([\w-]+)/profil/spieler/(\d+)", href)
        if match:
            return (match.group(2), match.group(1))  # (player_id, slug)

    return None


def scrape_playing_career(player_id: str, player_slug: str) -> Dict:
    """
    Scrape playing career stations from player profile.
    URL: /name/leistungsdatendetails/spieler/ID
    """
    cache_key = f"player_{player_id}_career"

    cached = load_from_cache(cache_key)
    if cached:
        print(f"  Using cached playing career for player {player_id}")
        return cached

    # Build URL for career page
    url = f"{TM_BASE}/{player_slug}/leistungsdatendetails/spieler/{player_id}"
    print(f"  Fetching playing career: {url}")

    soup = fetch_page(url, delay=1.5)
    if not soup:
        return {"player_id": player_id, "stations": [], "total_appearances": 0}

    result = {
        "player_id": player_id,
        "player_slug": player_slug,
        "stations": [],
        "total_appearances": 0,
        "total_goals": 0,
    }

    # Parse career table - find main stats table
    table = soup.find("table", class_="items")
    if not table:
        print("  No career table found")
        return result

    # Parse rows
    for row in table.find_all("tr", class_=["odd", "even"]):
        station = {}

        # Get season
        season_cell = row.find("td", class_="zentriert")
        if season_cell:
            station["season"] = season_cell.get_text(strip=True)

        # Get club from hauptlink
        club_cell = row.find("td", class_="hauptlink")
        if club_cell:
            club_link = club_cell.find("a")
            if club_link:
                station["club"] = club_link.get_text(strip=True)
                station["club_url"] = TM_BASE + club_link.get("href", "")

        # Get stats from rechts cells (appearances, goals, etc.)
        rechts_cells = row.find_all("td", class_="rechts")
        zentriert_cells = row.find_all("td", class_="zentriert")

        # Stats are typically: appearances, goals, assists, minutes
        if len(rechts_cells) >= 1:
            apps = rechts_cells[0].get_text(strip=True)
            apps_digits = re.sub(r"\D", "", apps)
            station["appearances"] = int(apps_digits) if apps_digits else 0
        if len(rechts_cells) >= 2:
            goals = rechts_cells[1].get_text(strip=True)
            goals_digits = re.sub(r"\D", "", goals)
            station["goals"] = int(goals_digits) if goals_digits else 0

        if station.get("club"):
            result["stations"].append(station)
            result["total_appearances"] += station.get("appearances", 0)
            result["total_goals"] += station.get("goals", 0)

    save_to_cache(cache_key, result)
    print(f"  Found {len(result['stations'])} career stations, {result['total_appearances']} appearances")

    return result


def scrape_titles(coach_id: str, coach_url: str = None) -> Dict:
    """
    Scrape titles/achievements from coach's PROFILE page.
    Titles are shown as icons in the header with class 'data-header__success-data'
    """
    cache_key = f"coach_{coach_id}_titles"

    cached = load_from_cache(cache_key)
    if cached:
        print(f"  Using cached titles for coach {coach_id}")
        return cached

    result = {
        "coach_id": coach_id,
        "titles": [],
        "total_titles": 0,
    }

    if not coach_url:
        print("  No coach URL provided for titles")
        return result

    # Fetch the coach profile page (titles are shown there as icons)
    print(f"  Fetching profile for titles: {coach_url}")
    soup = fetch_page(coach_url, delay=1.5)

    if not soup:
        print("  Could not fetch profile page")
        return result

    # Method 1: Parse trophy icons from header (data-header__success-data)
    success_links = soup.find_all("a", class_="data-header__success-data")
    for link in success_links:
        title = {}

        # Get title name from the title attribute or img alt
        title_name = link.get("title", "")
        if not title_name:
            img = link.find("img")
            if img:
                title_name = img.get("alt", "") or img.get("title", "")

        if title_name:
            title["name"] = title_name

            # Get count from success-number span
            count_span = link.find("span", class_="data-header__success-number")
            if count_span:
                count_text = count_span.get_text(strip=True)
                count_digits = re.sub(r"\D", "", count_text)
                title["count"] = int(count_digits) if count_digits else 1
            else:
                title["count"] = 1

            # Get erfolge URL for details
            erfolge_href = link.get("href", "")
            if erfolge_href:
                title["url"] = TM_BASE + erfolge_href if not erfolge_href.startswith("http") else erfolge_href

            result["titles"].append(title)
            print(f"    Found title: {title_name} x{title.get('count', 1)}")

    # Method 2: Check for "Weitere Erfolge" text section (additional achievements)
    weitere_erfolge = soup.find(string=re.compile(r"Weitere Erfolge:"))
    if weitere_erfolge:
        # Get the parent element and extract text
        parent = weitere_erfolge.find_parent()
        if parent:
            full_text = parent.get_text()
            # Extract years and titles from text like "2017/18: Meister Junioren-Bundesliga..."
            matches = re.findall(r"(\d{4}/\d{2}):\s*([^,]+)", full_text)
            for year, title_text in matches:
                result["titles"].append({
                    "name": title_text.strip(),
                    "count": 1,
                    "years": year,
                    "type": "youth/other"
                })

    result["total_titles"] = sum(t.get("count", 1) for t in result["titles"])

    save_to_cache(cache_key, result)
    print(f"  Found {len(result['titles'])} title categories, {result['total_titles']} total titles")

    return result


def scrape_coach_achievements(coach_url: str, coach_id: str) -> Dict:
    """
    Main function to get playing career and titles for a coach.

    Args:
        coach_url: URL to coach's Transfermarkt profile
        coach_id: Transfermarkt coach ID

    Returns:
        Dict with playing_career and titles
    """
    print(f"\nFetching achievements for coach {coach_id}...")

    result = {
        "coach_id": coach_id,
        "has_playing_career": False,
        "playing_career": None,
        "titles": None,
    }

    # Try to get player ID from coach profile
    player_info = extract_player_id_from_coach_profile(coach_url)

    if player_info:
        player_id, player_slug = player_info
        print(f"  Found player ID: {player_id} ({player_slug})")
        result["has_playing_career"] = True
        result["player_id"] = player_id
        result["player_slug"] = player_slug

        # Scrape playing career
        result["playing_career"] = scrape_playing_career(player_id, player_slug)
    else:
        print("  No playing career found")

    # Scrape titles
    result["titles"] = scrape_titles(coach_id, coach_url)

    return result


if __name__ == "__main__":
    # Test with Alexander Blessin
    test_url = "https://www.transfermarkt.de/alexander-blessin/profil/trainer/26099"
    result = scrape_coach_achievements(test_url, "26099")

    print("\n" + "=" * 60)
    print("ACHIEVEMENTS")
    print("=" * 60)

    if result.get("has_playing_career"):
        career = result.get("playing_career", {})
        print(f"\n⚽ Playing Career: {career.get('total_appearances', 0)} appearances, {career.get('total_goals', 0)} goals")
        for station in career.get("stations", [])[:5]:
            print(f"  - {station.get('season', '')}: {station.get('club', '')} ({station.get('appearances', 0)} apps)")

    titles = result.get("titles", {})
    print(f"\n🏆 Titles: {titles.get('total_titles', 0)}")
    for title in titles.get("titles", []):
        print(f"  - {title.get('name', '')} x{title.get('count', 1)}")
