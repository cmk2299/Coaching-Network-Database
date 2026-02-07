#!/usr/bin/env python3
"""
Scrape historical club staff to find who was in charge when a coach was hired.

Strategy:
1. Get coach's start date at club from career history
2. Scrape club's staff history around that date
3. Find Sports Director/CEO who was there when coach arrived = Hiring Manager!

This is fully automated using only Transfermarkt structured data.
"""

import json
import re
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
import requests

# Cache directory
CACHE_DIR = Path(__file__).resolve().parent.parent / "tmp" / "cache" / "staff_history"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

TM_BASE = "https://www.transfermarkt.de"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}


def get_cache_path(club_id: int, person_type: str = "staff") -> Path:
    """Get cache file path."""
    return CACHE_DIR / f"club_{club_id}_{person_type}_history.json"


def load_from_cache(club_id: int, person_type: str = "staff") -> Optional[Dict]:
    """Load cached staff history."""
    cache_path = get_cache_path(club_id, person_type)

    if cache_path.exists():
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Staff history is relatively stable, cache for 30 days
            cached_at = datetime.fromisoformat(data.get("cached_at", "2000-01-01"))
            if (datetime.now() - cached_at).days < 30:
                return data.get("staff", [])
        except:
            pass

    return None


def save_to_cache(club_id: int, staff: List[Dict], person_type: str = "staff"):
    """Save staff history to cache."""
    cache_path = get_cache_path(club_id, person_type)

    cache_data = {
        "cached_at": datetime.now().isoformat(),
        "club_id": club_id,
        "staff": staff
    }

    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(cache_data, f, indent=2, ensure_ascii=False)


def scrape_club_staff_history(club_id: int) -> List[Dict]:
    """
    Scrape club staff history including Sports Directors, CEOs, etc.

    Returns list of staff members with their tenure periods.
    """
    # Check cache
    cached = load_from_cache(club_id, "staff")
    if cached:
        return cached

    staff_members = []

    try:
        # The staff page shows current + some historical staff
        url = f"{TM_BASE}/verein/mitarbeiter/verein/{club_id}"

        print(f"  Scraping staff history for club {club_id}...")
        time.sleep(2)

        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')

        # Find all staff tables
        tables = soup.find_all("table", class_="items")

        for table in tables:
            rows = table.find_all("tr", class_=["odd", "even"])

            for row in rows:
                # Get name
                name_cell = row.find("td", class_="hauptlink")
                if not name_cell:
                    continue

                name_link = name_cell.find("a", href=True)
                if not name_link:
                    continue

                name = name_link.get_text(strip=True)
                profile_url = TM_BASE + name_link.get("href", "")

                # Get role
                tds = row.find_all("td")
                role = ""
                for td in tds[1:3]:
                    text = td.get_text(strip=True)
                    if text and len(text) > 3:
                        role = text
                        break

                # Get tenure period (if available)
                # Look for date ranges in the row
                tenure_start = None
                tenure_end = None

                # Check for date columns
                for td in tds:
                    text = td.get_text(strip=True)
                    # Match date patterns like "seit 01.07.2021" or "01.07.2020 - 30.06.2023"
                    date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', text)
                    if date_match:
                        if 'seit' in text.lower():
                            tenure_start = date_match.group(1)
                            tenure_end = "current"
                        elif '-' in text:
                            dates = re.findall(r'(\d{2}\.\d{2}\.\d{4})', text)
                            if len(dates) >= 2:
                                tenure_start = dates[0]
                                tenure_end = dates[1]
                        else:
                            tenure_start = date_match.group(1)

                # Only include decision makers
                role_lower = role.lower()
                decision_keywords = [
                    "sportdirektor", "geschäftsführer", "vorstand",
                    "präsident", "president", "ceo", "direktor"
                ]

                if any(kw in role_lower for kw in decision_keywords):
                    staff_members.append({
                        "name": name,
                        "role": role,
                        "tenure_start": tenure_start,
                        "tenure_end": tenure_end,
                        "url": profile_url
                    })

        # Cache results
        save_to_cache(club_id, staff_members, "staff")

        print(f"    Found {len(staff_members)} staff members")

    except Exception as e:
        print(f"    Error scraping staff history: {e}")

    return staff_members


def parse_date(date_str: str) -> Optional[datetime]:
    """Parse German date format (DD.MM.YYYY) to datetime."""
    if not date_str or date_str == "current":
        return None

    try:
        # Handle "MM.YYYY" format
        if re.match(r'^\d{2}\.\d{4}$', date_str):
            return datetime.strptime(f"01.{date_str}", "%d.%m.%Y")
        # Handle "DD.MM.YYYY" format
        elif re.match(r'^\d{2}\.\d{2}\.\d{4}$', date_str):
            return datetime.strptime(date_str, "%d.%m.%Y")
    except:
        pass

    return None


def find_hiring_manager_at_club(club_id: int, club_name: str, coach_start_date: str) -> List[Dict]:
    """
    Find who was in charge when a coach was hired.

    Args:
        club_id: Club ID on Transfermarkt
        club_name: Club name
        coach_start_date: When the coach started (format: MM.YYYY or DD.MM.YYYY)

    Returns:
        List of potential hiring managers (Sports Directors/CEOs who overlapped)
    """
    # Get staff history
    staff_history = scrape_club_staff_history(club_id)

    if not staff_history:
        return []

    # Parse coach start date
    coach_date = parse_date(coach_start_date)
    if not coach_date:
        return []

    hiring_managers = []

    for person in staff_history:
        tenure_start = parse_date(person.get("tenure_start"))
        tenure_end_str = person.get("tenure_end")

        # If tenure_end is "current", use today's date
        if tenure_end_str == "current":
            tenure_end = datetime.now()
        else:
            tenure_end = parse_date(tenure_end_str)

        # Check if this person was there when coach arrived
        # Person started before coach AND (person still there OR person left after coach arrived)
        if tenure_start and tenure_start <= coach_date:
            if tenure_end is None or tenure_end >= coach_date:
                # This person was there when coach was hired!

                # Determine connection type based on role
                role_lower = person["role"].lower()
                if "sportdirektor" in role_lower or "sporting director" in role_lower:
                    conn_type = "hiring_manager"
                elif "geschäftsführer" in role_lower or "ceo" in role_lower:
                    conn_type = "hiring_manager"  # CEOs also hire
                elif "präsident" in role_lower or "president" in role_lower:
                    conn_type = "executive"
                else:
                    conn_type = "management"

                hiring_managers.append({
                    "name": person["name"],
                    "role": person["role"],
                    "club_name": club_name,
                    "url": person.get("url"),
                    "connection_type": conn_type,
                    "source": "historical_staff_match",
                    "tenure_at_hiring": f"{person.get('tenure_start')} - {tenure_end_str or 'ongoing'}"
                })

    return hiring_managers


if __name__ == "__main__":
    # Test with Blessin at Genua
    print("\n=== Testing Historical Staff Scraper ===\n")

    tests = [
        (252, "Genua CFC", "01.2022", "Alexander Blessin"),
        (35, "FC St. Pauli", "07.2024", "Alexander Blessin"),
        (24, "Eintracht Frankfurt", "12.2024", "Albert Riera"),
        (27, "Bayern München", "05.2024", "Vincent Kompany"),
    ]

    for club_id, club_name, start_date, coach_name in tests:
        print(f"\n--- {coach_name} at {club_name} (started {start_date}) ---")
        hiring_managers = find_hiring_manager_at_club(club_id, club_name, start_date)

        if hiring_managers:
            print(f"✅ Found {len(hiring_managers)} decision maker(s) who were there at hiring:")
            for hm in hiring_managers:
                print(f"  - {hm['name']} ({hm['role']})")
                print(f"    Tenure: {hm['tenure_at_hiring']}")
        else:
            print(f"❌ No decision makers found")
