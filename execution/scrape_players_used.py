#!/usr/bin/env python3
"""
Transfermarkt Players Used Scraper - Layer 3 Execution Script
Scrapes statistics about players a coach has used.
Filters for significant relationships (20+ games, 70+ avg minutes).
"""

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Paths
BASE_DIR = Path(__file__).parent.parent
TMP_DIR = BASE_DIR / "tmp"
CACHE_DIR = TMP_DIR / "cache"
RAW_HTML_DIR = TMP_DIR / "raw_html"

# Transfermarkt base URL
TM_BASE = "https://www.transfermarkt.de"

# Request settings
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}

REQUEST_DELAY = 3

# Filter thresholds (set to 0 for complete data)
MIN_GAMES = 0
MIN_AVG_MINUTES = 0


def extract_base_club_name(club_name: str) -> str:
    """
    Extract the base club name without youth team suffixes.
    Also normalizes common club name variations.

    Examples:
        "Karlsruhe U19" -> "karlsruhe"
        "Karlsruher SC" -> "karlsruhe"
        "Karlsruhe U17" -> "karlsruhe"
        "Bayern II" -> "bayern"
        "Dortmund U23" -> "dortmund"
        "VfB Stuttgart II" -> "stuttgart"
    """
    # Patterns to remove (youth/reserve team indicators)
    # Order matters: check more specific patterns first
    patterns = [
        r'\s+U\d{2}$',           # U19, U17, U23, etc.
        r'\s+II$',               # Second team (Roman numeral)
        r'\s+2$',                # Second team (Arabic numeral)
        r'\s+B$',                # B team
        r'\s+Jugend$',           # Youth (German)
        r'\s+Youth$',            # Youth (English)
        r'\s+Amateure$',         # Amateurs
        r'\s+Reserve$',          # Reserve
    ]

    base_name = club_name.strip()
    for pattern in patterns:
        base_name = re.sub(pattern, '', base_name, flags=re.IGNORECASE)

    # Normalize: remove common suffixes and prefixes for grouping
    # This helps match "Karlsruhe" with "Karlsruher SC"
    normalizations = [
        (r'r\s+SC$', ''),        # Karlsruher SC -> Karlsruhe (remove "r SC")
        (r'\s+SC$', ''),         # ... SC -> ...
        (r'\s+FC$', ''),         # ... FC -> ...
        (r'^FC\s+', ''),         # FC ... -> ...
        (r'^1\.\s*FC\s+', ''),   # 1.FC ... -> ...
        (r'^SC\s+', ''),         # SC ... -> ...
        (r'^VfB\s+', ''),        # VfB ... -> ...
        (r'^VfL\s+', ''),        # VfL ... -> ...
        (r'^TSV\s+', ''),        # TSV ... -> ...
        (r'^SV\s+', ''),         # SV ... -> ...
        (r'^SpVgg\s+', ''),      # SpVgg ... -> ...
        (r'^Bor\.\s*', ''),      # Bor. ... -> ...
        (r'^Borussia\s+', ''),   # Borussia ... -> ...
        (r'\s+04$', ''),         # ... 04 -> ...
        (r'\s+05$', ''),         # ... 05 -> ...
        (r'\s+07$', ''),         # ... 07 -> ...
        (r'\s+09$', ''),         # ... 09 -> ...
        (r'\s+1860$', ''),       # ... 1860 -> ...
        (r'\s+1899$', ''),       # ... 1899 -> ...
    ]

    normalized = base_name.lower().strip()
    for pattern, replacement in normalizations:
        normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)

    return normalized.strip()


def count_unique_clubs(stations: list) -> int:
    """
    Count unique base clubs from a list of stations.
    Groups youth teams with their parent club.

    Returns number of unique clubs (not stations).
    """
    unique_clubs = set()
    for station in stations:
        club_name = station.get("club", "")
        base_name = extract_base_club_name(club_name)  # Already lowercased
        if base_name:
            unique_clubs.add(base_name)
    return len(unique_clubs)


def ensure_dirs():
    """Create necessary directories."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    RAW_HTML_DIR.mkdir(parents=True, exist_ok=True)


def get_cached(cache_key: str) -> Optional[dict]:
    """Load from cache if exists and fresh."""
    cache_file = CACHE_DIR / f"{cache_key}.json"
    if cache_file.exists():
        with open(cache_file, "r") as f:
            data = json.load(f)
            cached_at = datetime.fromisoformat(data.get("_cached_at", "2000-01-01"))
            if (datetime.now() - cached_at).total_seconds() < 86400:
                print(f"  Using cached data for {cache_key}")
                return data
    return None


def save_cache(cache_key: str, data: dict):
    """Save data to cache."""
    data["_cached_at"] = datetime.now().isoformat()
    cache_file = CACHE_DIR / f"{cache_key}.json"
    with open(cache_file, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def fetch_page(url: str, save_as: str = None) -> Optional[BeautifulSoup]:
    """Fetch a page with proper headers and rate limiting."""
    print(f"  Fetching: {url}")
    time.sleep(REQUEST_DELAY)

    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()

        if save_as:
            html_file = RAW_HTML_DIR / f"{save_as}.html"
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(response.text)

        return BeautifulSoup(response.text, "lxml")

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            print(f"  Rate limited. Waiting 60 seconds...")
            time.sleep(60)
            return fetch_page(url, save_as)
        print(f"  ERROR: HTTP {e.response.status_code}")
        return None

    except requests.exceptions.RequestException as e:
        print(f"  ERROR: Request failed: {e}")
        return None


def get_players_used_url(coach_profile_url: str) -> str:
    """Convert coach profile URL to career stations page URL."""
    # The detailed player stats are on the "stationen" (stations/career) page
    # Pattern: /name/profil/trainer/12345 -> /name/stationen/trainer/12345/plus/1
    # The /plus/1 shows detailed statistics
    url = coach_profile_url.replace("/profil/trainer/", "/stationen/trainer/")
    return url + "/plus/1"


def parse_int(text: str) -> int:
    """Parse integer from text, handling various formats."""
    if not text:
        return 0
    # Remove non-numeric characters except minus
    cleaned = re.sub(r"[^\d-]", "", text)
    try:
        return int(cleaned) if cleaned else 0
    except ValueError:
        return 0


def parse_date_from_cell(text: str) -> str:
    """Extract date from cell text like '24/25 (01.07.2024)' -> '07.2024'"""
    if not text or text == "-":
        return None
    # Look for date pattern DD.MM.YYYY
    match = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", text)
    if match:
        day, month, year = match.groups()
        return f"{month}.{year}"
    return None


def parse_career_stations(soup: BeautifulSoup) -> list:
    """
    Parse career stations page and extract coaching history with stats.
    Returns list of stations with club, games, players used count, W/D/L, dates.

    HTML structure per row (14 cells):
    [0] Logo, [1] Club+Role, [2] Start, [3] End, [4] Period, [5] Days,
    [6] Games, [7] Wins, [8] Draws, [9] Losses, [10] Players,
    [11] Goals ratio, [12] PPG, [13] Summary
    """
    stations = []

    # Find the main table
    table = soup.find("table", class_="items")
    if not table:
        print("  No stations table found")
        return stations

    rows = table.find_all("tr")
    print(f"  Found {len(rows)} table rows")

    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 10:
            continue

        # Club name from hauptlink cell
        club_cell = row.find("td", class_="hauptlink")
        if not club_cell:
            continue

        club_link = club_cell.find("a")
        if not club_link:
            continue

        club_name = club_link.get_text(strip=True)

        # Get all zentriert cells for stats
        zentriert_cells = row.find_all("td", class_="zentriert")

        if len(zentriert_cells) < 8:
            continue

        # Parse dates from cells [1] (Start) and [2] (End)
        start_text = zentriert_cells[1].get_text(strip=True) if len(zentriert_cells) > 1 else ""
        end_text = zentriert_cells[2].get_text(strip=True) if len(zentriert_cells) > 2 else ""

        start_date = parse_date_from_cell(start_text)
        end_date = parse_date_from_cell(end_text)

        # If end is "-", it means current position
        is_current = end_text == "-" or not end_date

        # Stats are in cells [4]=Games, [5]=Wins, [6]=Draws, [7]=Losses, [8]=Players
        games = parse_int(zentriert_cells[4].get_text(strip=True)) if len(zentriert_cells) > 4 else 0
        wins = parse_int(zentriert_cells[5].get_text(strip=True)) if len(zentriert_cells) > 5 else 0
        draws = parse_int(zentriert_cells[6].get_text(strip=True)) if len(zentriert_cells) > 6 else 0
        losses = parse_int(zentriert_cells[7].get_text(strip=True)) if len(zentriert_cells) > 7 else 0
        players_count = parse_int(zentriert_cells[8].get_text(strip=True)) if len(zentriert_cells) > 8 else 0

        # Build period string
        if start_date:
            if is_current:
                period = f"{start_date} - current"
            elif end_date:
                period = f"{start_date} - {end_date}"
            else:
                period = start_date
        else:
            period = ""

        station = {
            "club": club_name,
            "club_url": TM_BASE + club_link["href"] if club_link.get("href") else None,
            "period": period,
            "start_date": start_date,
            "end_date": end_date if not is_current else "current",
            "is_current": is_current,
            "games": games,
            "wins": wins,
            "draws": draws,
            "losses": losses,
            "players_used": players_count,
        }

        if games > 0 or players_count > 0:
            stations.append(station)
            print(f"    {club_name}: {games} games (W{wins}/D{draws}/L{losses}), {players_count} players, {period}")

    return stations


def parse_players_used(soup: BeautifulSoup) -> list:
    """Parse players used table (when fetching specific club's players)."""
    players = []

    table = soup.find("table", class_="items")
    if not table:
        return players

    rows = table.find_all("tr", class_=["odd", "even"])

    for row in rows:
        name_cell = row.find("td", class_="hauptlink")
        if not name_cell:
            continue

        name_link = name_cell.find("a")
        if not name_link:
            continue

        player = {
            "name": name_link.get_text(strip=True),
            "url": TM_BASE + name_link["href"] if name_link.get("href") else None,
        }

        # Get stats from zentriert cells
        stats_cells = row.find_all("td", class_="zentriert")
        if len(stats_cells) >= 2:
            player["games"] = parse_int(stats_cells[0].get_text())
            player["minutes_avg"] = parse_int(stats_cells[1].get_text()) if len(stats_cells) > 1 else 0

        players.append(player)

    return players


def filter_significant_players(players: list) -> list:
    """Filter for players with significant playing time under this coach."""
    significant = []

    for player in players:
        games = player.get("games", 0)
        minutes_avg = player.get("minutes_avg", 0)

        if games >= MIN_GAMES and minutes_avg >= MIN_AVG_MINUTES:
            player["significant"] = True
            significant.append(player)

    # Sort by games played
    significant.sort(key=lambda x: x.get("games", 0), reverse=True)

    return significant


def scrape_players_used(coach_profile_url: str) -> Optional[dict]:
    """
    Scrape career stations and players used statistics for a coach.
    First gets the stations overview, then extracts player counts per club.
    """
    ensure_dirs()

    print(f"\n{'=' * 50}")
    print(f"Scraping Players Used")
    print(f"{'=' * 50}")

    # Build URL for stations page
    stations_url = get_players_used_url(coach_profile_url)
    coach_id_match = re.search(r"/trainer/(\d+)", stations_url)
    coach_id = coach_id_match.group(1) if coach_id_match else "unknown"

    # Check cache
    cache_key = f"coach_{coach_id}_players_used"
    cached = get_cached(cache_key)
    if cached:
        return cached

    # Fetch stations page
    soup = fetch_page(stations_url, f"coach_{coach_id}_players_used")

    if not soup:
        print("  No stations page found")
        return {"stations": [], "total_games": 0, "total_players_used": 0}

    # Parse career stations (this gives us an overview with player counts)
    stations = parse_career_stations(soup)

    # Calculate totals
    total_games = sum(s.get("games", 0) for s in stations)
    total_players = sum(s.get("players_used", 0) for s in stations)

    # Count unique clubs (groups youth teams with parent club)
    unique_clubs = count_unique_clubs(stations)

    result = {
        "coach_id": coach_id,
        "stations_url": stations_url,
        "stations": stations,
        "total_games": total_games,
        "total_players_used": total_players,
        "stations_count": len(stations),      # Total career stations
        "unique_clubs": unique_clubs,          # Unique clubs (youth teams grouped)
        "clubs_coached": len(stations)         # Legacy field for backwards compatibility
    }

    # Save to cache
    save_cache(cache_key, result)

    print(f"\n{'=' * 50}")
    print(f"Stations scraped!")
    print(f"Stations: {len(stations)} bei {unique_clubs} Vereinen")
    print(f"Total games: {total_games}")
    print(f"Total players used: {total_players}")

    return result


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Scrape Transfermarkt players used")
    parser.add_argument("--url", "-u", required=True, help="Coach profile URL")
    parser.add_argument("--output", "-o", help="Output JSON file")

    args = parser.parse_args()

    result = scrape_players_used(coach_profile_url=args.url)

    if result and args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\nSaved to: {args.output}")

    return result


if __name__ == "__main__":
    main()
