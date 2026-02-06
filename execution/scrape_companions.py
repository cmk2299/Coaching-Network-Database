#!/usr/bin/env python3
"""
Scrape companion data for coaches (Weggefährten).
Extracts former bosses from career page (Assistant Manager of: ...)
"""

import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict

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


def scrape_career_with_bosses(coach_id: int) -> Dict:
    """
    Scrape coach career page and extract:
    - Assistant positions with their head coaches (from "Assistant Manager of: ...")
    - Head coach positions with their assistants

    Returns dict with career stations and relationships.
    """
    cache_key = f"coach_{coach_id}_career_companions"

    cached = load_from_cache(cache_key, max_age_hours=168)  # 7 days
    if cached:
        print(f"  Using cached career data for coach {coach_id}")
        return cached

    # Fetch career page
    url = f"{TM_BASE}/trainer/stationen/trainer/{coach_id}/plus/1"
    print(f"  Fetching career page: {url}")

    soup = fetch_page(url, delay=1.0)
    if not soup:
        return {"coach_id": coach_id, "former_bosses": [], "own_assistants": []}

    # Save HTML for debugging
    html_path = RAW_HTML_DIR / f"coach_{coach_id}_career.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(str(soup))

    result = {
        "coach_id": coach_id,
        "former_bosses": [],      # People this coach worked under
        "assistant_positions": [], # Positions where coach was assistant
    }

    # Find the career table
    table = soup.find("table", class_="items")
    if not table:
        print("  No career table found")
        return result

    # Collect all rows
    all_rows = table.find_all("tr")

    # Two-pass approach: first collect stations, then match with boss rows
    stations_list = []
    boss_rows = []

    for i, row in enumerate(all_rows):
        # Check for "Co-Trainer unter:" extrarow (German format)
        extrarow = row.find("td", class_="extrarow")
        if extrarow:
            row_text = extrarow.get_text(strip=True)
            if "Co-Trainer unter:" in row_text or "Assistant Manager of:" in row_text:
                boss_rows.append({"row_index": i, "cell": extrarow})
            continue

        # Check if this is a station row (has hauptlink with club info)
        hauptlink = row.find("td", class_="hauptlink")
        if hauptlink:
            station = {"row_index": i}

            # Get club name and link
            club_link = hauptlink.find("a", href=re.compile(r"/verein/\d+"))
            if club_link:
                station["club_name"] = club_link.get_text(strip=True)

            # Get position from text (e.g., "RB Leipzig U19\nCo-Trainer")
            full_text = hauptlink.get_text(strip=True)
            if "Co-Trainer" in full_text:
                station["position"] = "Co-Trainer"
            elif "Trainer" in full_text:
                station["position"] = "Trainer"

            # Get dates from zentriert cells
            zentriert = row.find_all("td", class_="zentriert")
            if len(zentriert) >= 2:
                station["start"] = zentriert[0].get_text(strip=True)
                station["end"] = zentriert[1].get_text(strip=True)

            stations_list.append(station)

            # Check if position is assistant
            pos_lower = station.get("position", "").lower()
            if "co-trainer" in pos_lower or "assistent" in pos_lower:
                result["assistant_positions"].append(station)

    # Now match boss rows with the NEXT station row (boss row comes BEFORE its station)
    for boss_row in boss_rows:
        # Find the next station after this boss row
        next_station = None
        for station in stations_list:
            if station["row_index"] > boss_row["row_index"]:
                next_station = station
                break

        if not next_station:
            continue

        # Extract boss names from the extrarow
        extrarow = boss_row["cell"]
        links = extrarow.find_all("a", href=re.compile(r"/profil/trainer/\d+"))

        for link in links:
            boss_name = link.get_text(strip=True)
            boss_url = TM_BASE + link.get("href", "")

            # Try to extract games count - look for "(XX Spiele)" or "(XX Games)"
            games = None
            next_text = link.next_sibling
            if next_text:
                games_match = re.search(r"\((\d+)\s*(?:Spiele|Games?)\)", str(next_text))
                if games_match:
                    games = int(games_match.group(1))

            result["former_bosses"].append({
                "name": boss_name,
                "url": boss_url,
                "games_together": games,
                "club_name": next_station.get("club_name", ""),
                "period": f"{next_station.get('start', '')} - {next_station.get('end', '')}",
            })

    save_to_cache(cache_key, result)
    print(f"  Found {len(result['former_bosses'])} former bosses, {len(result['assistant_positions'])} assistant positions")

    return result


def scrape_current_staff(club_id: int, club_slug: str) -> Dict:
    """
    Scrape current staff from club's mitarbeiter page.
    Returns co-trainers and sports directors with their start dates.
    """
    cache_key = f"club_{club_id}_current_staff"

    cached = load_from_cache(cache_key, max_age_hours=24)  # 1 day for current staff
    if cached:
        return cached

    url = f"{TM_BASE}/{club_slug}/mitarbeiter/verein/{club_id}"
    print(f"  Fetching current staff: {url}")

    soup = fetch_page(url, delay=1.0)
    if not soup:
        return {"club_id": club_id, "co_trainers": [], "sports_directors": [], "all_management": []}

    result = {
        "club_id": club_id,
        "co_trainers": [],
        "sports_directors": [],
        "all_management": [],  # All management/executive roles
    }

    # Management role keywords
    management_keywords = [
        "geschäftsführer", "direktor", "director", "vorstand", "leiter",
        "chairman", "president", "ceo", "cfo", "managing", "executive",
        "sportvorstand", "sportchef", "technischer"
    ]

    # Find all table rows that contain staff members
    # Each row has: inline-table (name/role), age, nationality, start_date, end_date
    for row in soup.find_all("tr"):
        inline = row.find("table", class_="inline-table")
        if not inline:
            continue

        person = {}

        # Get name from link
        name_link = inline.find("a", href=re.compile(r"/(trainer|spieler|profil)/"))
        if name_link:
            person["name"] = name_link.get_text(strip=True)
            person["url"] = TM_BASE + name_link.get("href", "")

        # Get role from second row of inline-table
        rows = inline.find_all("tr")
        if len(rows) > 1:
            person["role"] = rows[1].get_text(strip=True)

        if not person.get("name"):
            continue

        # Get start date from zentriert cells (usually 4th cell: start date)
        zentriert_cells = row.find_all("td", class_="zentriert")
        if len(zentriert_cells) >= 3:
            # Cell order: age, nationality, start_date, [end_date], [previous_club]
            start_date_text = zentriert_cells[2].get_text(strip=True)
            # Parse date like "10.12.2025" to MM.YYYY
            date_match = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", start_date_text)
            if date_match:
                day, month, year = date_match.groups()
                person["start_date"] = f"{month}.{year}"
                person["start_date_full"] = start_date_text

        role_lower = person.get("role", "").lower()

        # Categorize by role
        # Co-trainers
        if "co-trainer" in role_lower or ("assistent" in role_lower and "trainer" in role_lower):
            result["co_trainers"].append(person)

        # Sports directors - various titles
        if any(term in role_lower for term in [
            "geschäftsführer sport",
            "sportdirektor",
            "managing director sport",
            "sportlicher leiter",
            "technischer direktor",
            "sportvorstand"
        ]):
            result["sports_directors"].append(person)
            print(f"    Found sports director: {person.get('name')} - {person.get('role')} (since {person.get('start_date', '?')})")

        # All management roles
        if any(term in role_lower for term in management_keywords):
            result["all_management"].append(person)

    save_to_cache(cache_key, result)
    return result


def scrape_historical_directors_for_club(club_id: int, club_slug: str, club_name: str,
                                          coach_start: str, coach_end: str) -> List[Dict]:
    """
    Try to find who was sports director at a club during a specific period.
    This scrapes the current staff and checks start dates.

    Note: This only finds directors who are STILL at the club.
    For historical accuracy, we'd need to scrape each director's career page.
    """
    staff = scrape_current_staff(club_id, club_slug)

    matching_directors = []

    for person in staff.get("all_management", []):
        sd_start = person.get("start_date")

        # Check if this person was there during coach's tenure
        if check_date_overlap(coach_start, coach_end, sd_start):
            matching_directors.append({
                "name": person.get("name"),
                "role": person.get("role"),
                "url": person.get("url"),
                "club_name": club_name,
                "start_date": sd_start,
            })

    return matching_directors


def check_date_overlap(coach_start: str, coach_end: str, sd_start: str) -> bool:
    """
    Check if sports director was at club during coach's tenure.
    Dates in MM.YYYY format. coach_end can be "current" or None.

    For overlap to exist:
    - SD must have started BEFORE or DURING coach's tenure (sd_start <= coach_end)
    - If coach has left (coach_end is not current), SD must have started BEFORE coach left

    Since we only have SD's start date (not end date), we can only check:
    - SD started before coach left
    """
    def to_comparable(date_str: str) -> int:
        if not date_str or date_str == "current" or date_str == "":
            return 999999  # Far future
        try:
            parts = date_str.split(".")
            if len(parts) == 2:
                month, year = parts
                return int(year) * 100 + int(month)
            elif len(parts) == 3:
                # Handle DD.MM.YYYY format
                day, month, year = parts
                return int(year) * 100 + int(month)
        except ValueError:
            pass
        return 0

    coach_start_val = to_comparable(coach_start)
    coach_end_val = to_comparable(coach_end) if coach_end else 999999
    sd_start_val = to_comparable(sd_start)

    # For a valid overlap:
    # 1. SD must have started before or when coach left
    # 2. If coach has already left (coach_end is not current/999999),
    #    SD must have started BEFORE coach left, not after

    if coach_end_val < 999999:
        # Coach has left - SD must have started before coach left
        return sd_start_val <= coach_end_val
    else:
        # Coach is still there - any SD who started is valid
        return True


def get_companions_for_coach(coach_id: int, coach_url: str, stations: List[Dict]) -> Dict:
    """
    Main function to get all companion data for a coach.

    Args:
        coach_id: Transfermarkt coach ID
        coach_url: Coach profile URL
        stations: List of coaching stations (used for current club lookup)

    Returns:
        Dict with former_bosses, current_co_trainers, current_sports_director, all_sports_directors, all_management
    """
    print(f"\nFetching companions for coach {coach_id}...")

    # Get career data with former bosses
    career_data = scrape_career_with_bosses(coach_id)

    result = {
        "coach_id": coach_id,
        "former_bosses": career_data.get("former_bosses", []),
        "assistant_positions": career_data.get("assistant_positions", []),
        "current_co_trainers": [],
        "current_sports_director": None,
        "all_sports_directors": [],  # Sports directors from all career stations
        "all_management": [],  # All management/executive contacts from career
    }

    seen_directors = set()  # Avoid duplicates
    seen_management = set()  # Avoid duplicate management

    # Process ALL stations to get sports directors from each club
    for i, station in enumerate(stations):
        club_id = station.get("club_id")
        club_slug = station.get("club_slug", "")
        club_name = station.get("club_name", "Unknown")
        coach_start = station.get("start_date")
        coach_end = station.get("end_date")

        if not club_id or not club_slug:
            continue

        print(f"  Fetching staff for {club_name} (coach: {coach_start} - {coach_end})...")
        staff = scrape_current_staff(club_id, club_slug)

        # Add sports directors with club context - only if there's overlap
        for sd in staff.get("sports_directors", []):
            sd_name = sd.get("name", "")
            sd_start = sd.get("start_date")

            # Check for temporal overlap
            has_overlap = check_date_overlap(coach_start, coach_end, sd_start)

            if not has_overlap:
                print(f"    Skipping {sd_name} - no overlap (SD started {sd_start}, coach left {coach_end})")
                continue

            if sd_name and sd_name not in seen_directors:
                seen_directors.add(sd_name)
                sd_entry = {
                    "name": sd.get("name"),
                    "role": sd.get("role"),
                    "url": sd.get("url"),
                    "club_name": club_name,
                    "club_id": club_id,
                    "sd_start": sd_start,
                    "coach_period": f"{coach_start} - {coach_end}",
                }
                result["all_sports_directors"].append(sd_entry)

                # First station is current - mark current sports director
                if i == 0:
                    result["current_sports_director"] = sd_entry

        # Add all management contacts with overlap check
        for mgmt in staff.get("all_management", []):
            mgmt_name = mgmt.get("name", "")
            mgmt_start = mgmt.get("start_date")

            # Check for temporal overlap
            has_overlap = check_date_overlap(coach_start, coach_end, mgmt_start)

            if not has_overlap:
                continue

            if mgmt_name and mgmt_name not in seen_management:
                seen_management.add(mgmt_name)
                mgmt_entry = {
                    "name": mgmt.get("name"),
                    "role": mgmt.get("role"),
                    "url": mgmt.get("url"),
                    "club_name": club_name,
                    "club_id": club_id,
                    "start_date": mgmt_start,
                    "coach_period": f"{coach_start} - {coach_end}",
                }
                result["all_management"].append(mgmt_entry)
                print(f"    ✓ {mgmt_name} - {mgmt.get('role', '?')} (overlap confirmed)")

        # Get co-trainers only from current club (first station)
        if i == 0:
            result["current_co_trainers"] = staff.get("co_trainers", [])

    print(f"  Found {len(result['all_sports_directors'])} sports directors, {len(result['all_management'])} management contacts")
    return result


if __name__ == "__main__":
    # Test with Alexander Blessin
    test_stations = [
        {
            "club_id": 35,
            "club_slug": "fc-st-pauli",
            "club_name": "FC St. Pauli",
            "start_date": "07.2024",
            "end_date": "current",
        },
    ]

    # Clear cache for fresh test
    cache_path = get_cache_path("coach_26099_career_companions")
    if cache_path.exists():
        cache_path.unlink()

    result = get_companions_for_coach(26099, "", test_stations)

    print("\n" + "=" * 60)
    print("COMPANIONS (Weggefährten)")
    print("=" * 60)

    print("\n🎯 Former Bosses (worked under):")
    for boss in result.get("former_bosses", []):
        games = f" ({boss['games_together']} Games)" if boss.get("games_together") else ""
        print(f"  - {boss['name']}{games}")
        print(f"    at {boss['club_name']} ({boss['period']})")

    print("\n📋 Assistant Positions:")
    for pos in result.get("assistant_positions", []):
        print(f"  - {pos.get('position', '')} at {pos.get('club_name', '')}")
        print(f"    {pos.get('start', '')} - {pos.get('end', '')}")

    print("\n👥 Current Co-Trainers:")
    for ct in result.get("current_co_trainers", []):
        print(f"  - {ct['name']} ({ct.get('role', '')})")

    print("\n📋 Current Sports Director:")
    sd = result.get("current_sports_director")
    if sd:
        print(f"  - {sd['name']} ({sd.get('role', '')})")
    else:
        print("  - Not found")
