#!/usr/bin/env python3
"""
Enhanced Decision Makers Scraper
Scrapes all key decision makers for each club a coach worked at:
- Sports Directors (Sportdirektor, Geschäftsführer Sport)
- CEOs/Presidents (Vorstandsvorsitzender, Präsident)
- Technical Directors (Technischer Direktor)
- Board Members (Aufsichtsrat)
"""

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict

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


def fetch_page(url: str, delay: float = 2.0) -> Optional[BeautifulSoup]:
    """Fetch a page and return BeautifulSoup object."""
    try:
        time.sleep(delay)
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return BeautifulSoup(response.text, "lxml")
    except requests.RequestException as e:
        print(f"  Error fetching {url}: {e}")
        return None


def scrape_club_staff(club_id: int, club_name: str, season: str = None) -> Dict:
    """
    Scrape all staff members from a club's staff page.

    Args:
        club_id: Transfermarkt club ID
        club_name: Club name for display
        season: Optional season (e.g., "2023") for historical data

    Returns:
        Dict with categorized staff members
    """
    # Build URL
    if season:
        url = f"{TM_BASE}/verein/mitarbeiter/verein/{club_id}/saison_id/{season}/plus/1"
    else:
        url = f"{TM_BASE}/verein/mitarbeiter/verein/{club_id}"

    print(f"  Fetching {club_name} staff: {url}")

    soup = fetch_page(url, delay=2.0)
    if not soup:
        return {}

    staff = {
        "sports_directors": [],
        "ceos": [],
        "technical_directors": [],
        "board_members": [],
        "scouts": [],
        "other": [],
    }

    # Find staff table
    table = soup.find("table", {"class": "items"})
    if not table:
        print(f"  No staff table found for {club_name}")
        return staff

    rows = table.find_all("tr", class_=["odd", "even"])

    for row in rows:
        # Get name
        name_cell = row.find("td", class_="hauptlink")
        if not name_cell:
            continue

        name_link = name_cell.find("a")
        if not name_link:
            continue

        name = name_link.get_text(strip=True)
        profile_url = TM_BASE + name_link.get("href", "")

        # Get role
        role_cell = row.find("td", class_=lambda x: x and "pos" in str(x) if x else False)
        if not role_cell:
            continue

        role = role_cell.get_text(strip=True)

        # Categorize by role
        person = {
            "name": name,
            "role": role,
            "club_name": club_name,
            "url": profile_url,
        }

        role_lower = role.lower()

        if any(keyword in role_lower for keyword in ["sportdirektor", "geschäftsführer sport", "sporting director"]):
            staff["sports_directors"].append(person)
        elif any(keyword in role_lower for keyword in ["vorstandsvorsitzender", "ceo", "präsident", "president"]):
            staff["ceos"].append(person)
        elif any(keyword in role_lower for keyword in ["technischer direktor", "technical director"]):
            staff["technical_directors"].append(person)
        elif any(keyword in role_lower for keyword in ["aufsichtsrat", "board"]):
            staff["board_members"].append(person)
        elif any(keyword in role_lower for keyword in ["scout", "chefscout"]):
            staff["scouts"].append(person)
        else:
            staff["other"].append(person)

    return staff


def get_decision_makers_for_coach(stations: List[Dict]) -> Dict:
    """
    Get all decision makers for each station in a coach's career.

    Args:
        stations: List of coaching stations with club_id and season info

    Returns:
        Dict with all decision makers organized by role
    """
    all_sports_directors = []
    all_ceos = []
    all_technical_directors = []
    all_board_members = []

    seen_people = set()  # Track unique people

    for station in stations:
        club_id = station.get("club_id")
        club_name = station.get("club_name", "Unknown")

        if not club_id:
            continue

        # Scrape club staff
        staff = scrape_club_staff(club_id, club_name)

        # Add to collections (avoid duplicates)
        for sd in staff.get("sports_directors", []):
            key = (sd["name"], sd["role"])
            if key not in seen_people:
                seen_people.add(key)
                all_sports_directors.append(sd)

        for ceo in staff.get("ceos", []):
            key = (ceo["name"], ceo["role"])
            if key not in seen_people:
                seen_people.add(key)
                all_ceos.append(ceo)

        for td in staff.get("technical_directors", []):
            key = (td["name"], td["role"])
            if key not in seen_people:
                seen_people.add(key)
                all_technical_directors.append(td)

        for bm in staff.get("board_members", []):
            key = (bm["name"], bm["role"])
            if key not in seen_people:
                seen_people.add(key)
                all_board_members.append(bm)

    return {
        "sports_directors": all_sports_directors,
        "ceos": all_ceos,
        "technical_directors": all_technical_directors,
        "board_members": all_board_members,
        "total_decision_makers": len(seen_people),
    }


if __name__ == "__main__":
    # Test with Union SG (club_id=3948)
    print("Testing with Union SG...")
    staff = scrape_club_staff(3948, "Union SG")

    print("\n=== Results ===")
    print(f"Sports Directors: {len(staff['sports_directors'])}")
    for sd in staff['sports_directors']:
        print(f"  - {sd['name']} ({sd['role']})")

    print(f"\nCEOs: {len(staff['ceos'])}")
    for ceo in staff['ceos']:
        print(f"  - {ceo['name']} ({ceo['role']})")

    print(f"\nTechnical Directors: {len(staff['technical_directors'])}")
    for td in staff['technical_directors']:
        print(f"  - {td['name']} ({td['role']})")
