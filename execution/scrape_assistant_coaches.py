#!/usr/bin/env python3
"""
Scrape Assistant Coaches (Co-Trainer) for all Bundesliga clubs.

This enriches the coach network intelligence by identifying who worked
together as assistants and can map assistant-to-head-coach transitions.
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup
import requests

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

# Bundesliga 2024/25 Clubs
BUNDESLIGA_CLUBS = [
    {"name": "FC Bayern München", "club_id": 27},
    {"name": "Borussia Dortmund", "club_id": 16},
    {"name": "RB Leipzig", "club_id": 23826},
    {"name": "Bayer 04 Leverkusen", "club_id": 15},
    {"name": "VfB Stuttgart", "club_id": 79},
    {"name": "Eintracht Frankfurt", "club_id": 24},
    {"name": "VfL Wolfsburg", "club_id": 82},
    {"name": "SC Freiburg", "club_id": 60},
    {"name": "TSG Hoffenheim", "club_id": 533},
    {"name": "1. FC Union Berlin", "club_id": 89},
    {"name": "Werder Bremen", "club_id": 86},
    {"name": "Borussia Mönchengladbach", "club_id": 18},
    {"name": "1. FSV Mainz 05", "club_id": 39},
    {"name": "FC Augsburg", "club_id": 167},
    {"name": "1. FC Heidenheim", "club_id": 2036},
    {"name": "FC St. Pauli", "club_id": 35},
    {"name": "VfL Bochum", "club_id": 80},
    {"name": "1. FC Köln", "club_id": 3},
]

ASSISTANT_ROLE_KEYWORDS = [
    "Co-Trainer",
    "Co-Trainerin",
    "Assistent",
    "Assistentin",
    "Assistant Coach",
    "Assistant Manager"
]


def find_assistants_from_staff_page(club_id: int, club_name: str) -> list:
    """
    Find all Assistant Coaches from club's staff page.

    Returns:
        [
            {
                "name": str,
                "role": str,
                "profile_url": str,
                "club": str
            }
        ]
    """
    staff_url = f"https://www.transfermarkt.de/-/mitarbeiter/verein/{club_id}"
    print(f"  Checking staff page: {staff_url}")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }

    try:
        response = requests.get(staff_url, headers=headers, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find all inline-table elements (staff entries)
        staff_tables = soup.find_all("table", class_="inline-table")
        if not staff_tables:
            return []

        assistants = []

        for table in staff_tables:
            # Each inline-table has 2 rows: name row and role row
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue

            # Row 1: Name and link
            name_row = rows[0]
            name_cell = name_row.find("td", class_="hauptlink")
            if not name_cell:
                continue

            link = name_cell.find("a")
            if not link:
                continue

            name = link.get_text(strip=True)
            profile_url = "https://www.transfermarkt.de" + link["href"]

            # Row 2: Role
            role_row = rows[1]
            role_cell = role_row.find("td")
            if not role_cell:
                continue

            role = role_cell.get_text(strip=True)

            # Check if this is an Assistant Coach role
            if any(keyword in role for keyword in ASSISTANT_ROLE_KEYWORDS):
                assistants.append({
                    "name": name,
                    "role": role,
                    "profile_url": profile_url,
                    "club": club_name
                })

        if assistants:
            print(f"    ✓ Found {len(assistants)} assistant(s): {', '.join([a['name'] for a in assistants])}")
        else:
            print(f"    ⚠️  No assistants found for {club_name}")

        return assistants

    except Exception as e:
        print(f"    ✗ Error finding assistants: {e}")
        return []


def scrape_assistant_profile(assistant_url: str) -> dict:
    """
    Scrape basic assistant coach profile.

    Returns:
        {
            "name": str,
            "age": int,
            "nationality": str,
            "current_club": str,
            "current_role": str,
            "career_history": [...]
        }
    """
    print(f"    Fetching: {assistant_url}")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }

    try:
        response = requests.get(assistant_url, headers=headers, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        result = {
            "url": assistant_url,
            "scraped_at": datetime.now().isoformat()
        }

        # Extract name
        name_elem = soup.find("h1", class_="data-header__headline-wrapper")
        if name_elem:
            result["name"] = name_elem.get_text(strip=True)

        # Extract current club and role from data header
        current_club_elem = soup.find("span", class_="data-header__club")
        if current_club_elem:
            club_link = current_club_elem.find("a")
            if club_link:
                result["current_club"] = club_link.get_text(strip=True)

        current_role_elem = soup.find("span", class_="data-header__label")
        if current_role_elem:
            result["current_role"] = current_role_elem.get_text(strip=True)

        # Extract age, nationality from info table
        info_table = soup.find("div", class_="info-table")
        if info_table:
            rows = info_table.find_all("span", class_="info-table__content")
            for row in rows:
                text = row.get_text(strip=True)
                # Age extraction
                if "Jahre" in text or "years" in text:
                    try:
                        age = int(text.split()[0])
                        result["age"] = age
                    except:
                        pass
                # Nationality
                flag = row.find("img", class_="flaggenrahmen")
                if flag and "alt" in flag.attrs:
                    result["nationality"] = flag["alt"]

        # Extract career history (same structure as SDs)
        career_history = []
        stations_table = soup.find("table", class_="items")

        if stations_table:
            # Get all rows except header
            all_rows = stations_table.find_all("tr")

            for row in all_rows[1:]:  # Skip header row
                cells = row.find_all("td")
                if len(cells) < 4:
                    continue

                station = {}

                # Cell 1: Club name + role
                club_cell = cells[1]
                if club_cell:
                    club_link = club_cell.find("a")
                    if club_link:
                        station["club"] = club_link.get_text(strip=True)
                        station["club_url"] = "https://www.transfermarkt.de" + club_link.get("href", "")

                    # Extract role
                    full_text = club_cell.get_text(separator="|", strip=True)
                    if "|" in full_text:
                        parts = full_text.split("|")
                        if len(parts) >= 2:
                            station["role"] = parts[1].strip()

                # Cell 2: Start period
                start_cell = cells[2]
                if start_cell:
                    start_text = start_cell.get_text(strip=True)
                    station["start_period"] = start_text
                    if "/" in start_text:
                        try:
                            year_part = start_text.split()[0].split("/")[0]
                            if len(year_part) == 2:
                                year_num = int(year_part)
                                station["start_year"] = 2000 + year_num if year_num < 50 else 1900 + year_num
                        except:
                            pass

                # Cell 3: End period
                end_cell = cells[3]
                if end_cell:
                    end_text = end_cell.get_text(strip=True)
                    station["end_period"] = end_text
                    if "/" in end_text and "vsl" not in end_text:
                        try:
                            year_part = end_text.split()[0].split("/")[0]
                            if len(year_part) == 2:
                                year_num = int(year_part)
                                station["end_year"] = 2000 + year_num if year_num < 50 else 1900 + year_num
                        except:
                            pass

                if station.get("club"):
                    career_history.append(station)

        result["career_history"] = career_history
        result["total_stations"] = len(career_history)

        return result

    except Exception as e:
        print(f"      ✗ Error scraping {assistant_url}: {e}")
        return {"error": str(e), "url": assistant_url}


def main():
    """Scrape all Bundesliga Assistant Coaches."""
    print("=" * 70)
    print("Scraping Bundesliga Assistant Coaches")
    print("=" * 70)
    print(f"Total clubs: {len(BUNDESLIGA_CLUBS)}\n")

    all_assistants = []

    for i, club_info in enumerate(BUNDESLIGA_CLUBS, 1):
        club_name = club_info["name"]
        club_id = club_info["club_id"]

        print(f"[{i}/{len(BUNDESLIGA_CLUBS)}] {club_name}")

        # Step 1: Find assistants from staff page
        assistants = find_assistants_from_staff_page(club_id, club_name)

        if not assistants:
            time.sleep(2)
            continue

        # Step 2: Scrape each assistant's profile
        for assistant_info in assistants:
            print(f"  → Scraping {assistant_info['name']}...")
            data = scrape_assistant_profile(assistant_info["profile_url"])
            data["expected_club"] = club_name
            data["expected_role"] = assistant_info["role"]

            all_assistants.append(data)

            if data.get("career_history"):
                print(f"      ✓ Found {len(data['career_history'])} career stations")

            time.sleep(3)  # Rate limiting between profiles

        # Wait between clubs
        if i < len(BUNDESLIGA_CLUBS):
            time.sleep(3)

    # Save results
    output_path = Path(__file__).parent.parent / "data" / "assistant_coaches_bundesliga.json"
    output_path.parent.mkdir(exist_ok=True, parents=True)

    output_data = {
        "league": "Bundesliga",
        "season": "2024/25",
        "total_assistants": len([a for a in all_assistants if not a.get("error")]),
        "scraped_at": datetime.now().isoformat(),
        "assistant_coaches": all_assistants
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print(f"✅ COMPLETE! Saved to: {output_path}")
    print(f"📊 Total Assistants: {len([a for a in all_assistants if not a.get('error')])}")
    print(f"📈 Total career stations: {sum(a.get('total_stations', 0) for a in all_assistants if not a.get('error'))}")
    print(f"🏟️  Clubs with assistants: {len(set(a['expected_club'] for a in all_assistants if not a.get('error')))}/18")
    print("=" * 70)


if __name__ == "__main__":
    main()
