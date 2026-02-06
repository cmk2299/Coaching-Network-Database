#!/usr/bin/env python3
"""
Scrape current coaches from Bundesliga clubs.
Fetches live data from Transfermarkt.
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
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Request headers
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}

# Bundesliga 2024/25 clubs (without relegated teams, current season)
BUNDESLIGA_CLUBS = {
    "FC Bayern München": {"id": 27, "slug": "fc-bayern-munchen"},
    "Borussia Dortmund": {"id": 16, "slug": "borussia-dortmund"},
    "RB Leipzig": {"id": 23826, "slug": "rasenballsport-leipzig"},
    "Bayer 04 Leverkusen": {"id": 15, "slug": "bayer-04-leverkusen"},
    "VfB Stuttgart": {"id": 79, "slug": "vfb-stuttgart"},
    "Eintracht Frankfurt": {"id": 24, "slug": "eintracht-frankfurt"},
    "VfL Wolfsburg": {"id": 82, "slug": "vfl-wolfsburg"},
    "SC Freiburg": {"id": 60, "slug": "sc-freiburg"},
    "TSG Hoffenheim": {"id": 533, "slug": "tsg-1899-hoffenheim"},
    "1. FC Union Berlin": {"id": 89, "slug": "1-fc-union-berlin"},
    "Werder Bremen": {"id": 86, "slug": "sv-werder-bremen"},
    "Borussia Mönchengladbach": {"id": 18, "slug": "borussia-monchengladbach"},
    "1. FSV Mainz 05": {"id": 39, "slug": "1-fsv-mainz-05"},
    "FC Augsburg": {"id": 167, "slug": "fc-augsburg"},
    "1. FC Heidenheim": {"id": 2036, "slug": "1-fc-heidenheim-1846"},
    "FC St. Pauli": {"id": 35, "slug": "fc-st-pauli"},
    "VfL Bochum": {"id": 80, "slug": "vfl-bochum"},
    "1. FC Köln": {"id": 3, "slug": "1-fc-koln"},
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

            # Check age
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


def scrape_club_coach(club_name: str, club_id: int, club_slug: str) -> Optional[dict]:
    """Scrape current coach from a club's staff (mitarbeiter) page."""
    # Use mitarbeiter page which reliably shows all staff
    url = f"{TM_BASE}/{club_slug}/mitarbeiter/verein/{club_id}"
    print(f"  Fetching: {url}")

    soup = fetch_page(url)
    if not soup:
        return None

    coach_info = {
        "club_name": club_name,
        "club_id": club_id,
        "club_url": f"{TM_BASE}/{club_slug}/startseite/verein/{club_id}",
    }

    # Find the "Trainerstab" box - first trainer is always the head coach
    for box in soup.find_all("div", class_="box"):
        headline = box.find(class_="content-box-headline")
        if headline and "Trainerstab" in headline.get_text():
            # Get first trainer link in this box
            trainer_link = box.find("a", href=re.compile(r"/profil/trainer/\d+"))
            if trainer_link:
                href = trainer_link.get("href", "")
                coach_id_match = re.search(r"/profil/trainer/(\d+)", href)
                if coach_id_match:
                    coach_info["coach_id"] = int(coach_id_match.group(1))
                    coach_info["coach_url"] = TM_BASE + href
                    coach_info["coach_name"] = trainer_link.get_text(strip=True)
                    break

    # Fallback: just get first trainer link on page
    if "coach_name" not in coach_info:
        trainer_link = soup.find("a", href=re.compile(r"/profil/trainer/\d+"))
        if trainer_link:
            href = trainer_link.get("href", "")
            coach_id_match = re.search(r"/profil/trainer/(\d+)", href)
            if coach_id_match:
                coach_info["coach_id"] = int(coach_id_match.group(1))
                coach_info["coach_url"] = TM_BASE + href
                coach_info["coach_name"] = trainer_link.get_text(strip=True)

    # Legacy fallback - kept for compatibility
    if "coach_name" not in coach_info:
        trainer_section = soup.find("div", class_="data-header__box--big")
        if trainer_section:
            coach_link = trainer_section.find("a", href=re.compile(r"trainer"))
            if coach_link:
                coach_info["coach_name"] = coach_link.get_text(strip=True)
                coach_info["coach_url"] = TM_BASE + coach_link.get("href", "")

    return coach_info if "coach_name" in coach_info else None


def scrape_bundesliga_coaches(force_refresh: bool = False) -> dict:
    """
    Scrape all current Bundesliga coaches.
    Returns dict mapping club name to coach info.
    """
    cache_key = "bundesliga_coaches"

    # Check cache (valid for 24 hours)
    if not force_refresh:
        cached = load_from_cache(cache_key, max_age_hours=24)
        if cached:
            print("  Using cached Bundesliga coaches data")
            return cached

    print("\n" + "=" * 50)
    print("Scraping Bundesliga Coaches")
    print("=" * 50)

    coaches = {}

    for club_name, club_data in BUNDESLIGA_CLUBS.items():
        print(f"\n{club_name}...")
        coach_info = scrape_club_coach(club_name, club_data["id"], club_data["slug"])

        if coach_info:
            coaches[club_name] = coach_info
            print(f"  ✓ Coach: {coach_info.get('coach_name', 'Unknown')}")
        else:
            print(f"  ✗ Could not find coach")

    # Save to cache
    result = {
        "league": "Bundesliga",
        "season": "2024/25",
        "clubs": coaches,
        "total_clubs": len(coaches),
    }
    save_to_cache(cache_key, result)

    print(f"\n✓ Scraped {len(coaches)} coaches")
    return result


def get_coach_for_club(club_name: str) -> Optional[dict]:
    """Get current coach for a specific club."""
    data = scrape_bundesliga_coaches()
    return data.get("clubs", {}).get(club_name)


if __name__ == "__main__":
    import sys

    force = "--force" in sys.argv
    result = scrape_bundesliga_coaches(force_refresh=force)

    print("\n" + "=" * 50)
    print("BUNDESLIGA COACHES 2024/25")
    print("=" * 50)

    for club, info in result.get("clubs", {}).items():
        coach = info.get("coach_name", "Unknown")
        print(f"{club}: {coach}")
