#!/usr/bin/env python3
"""
Scrape Sporting Directors for all Bundesliga clubs with complete career history.

This enriches the "welcher sportdirektor hat welchen trainer schonmal zusammengearbeitet"
intelligence requirement from projectFIVE.
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

# Bundesliga 2024/25 Clubs (we'll find SDs from staff pages)
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

SD_ROLE_KEYWORDS = [
    "Sportdirektor",
    "Sportvorstand",
    "Sportchef",
    "Geschäftsführer Sport",
    "Geschäftsführer Profifußball",
    "Managing Director Sport",
    "Direktor Profifußball",
    "Technischer Direktor",
    "Vorstandsvorsitzender"  # For clubs like Heidenheim where chairman handles sporting
]

def find_sd_from_staff_page(club_id: int, club_name: str) -> dict:
    """
    Find Sporting Director from club's staff page.

    Returns:
        {
            "name": str,
            "role": str,
            "profile_url": str,
            "club": str
        }
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
            return {"error": "No staff tables found"}

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

            # Check if this is a Sporting Director role
            if any(keyword in role for keyword in SD_ROLE_KEYWORDS):
                print(f"    ✓ Found SD: {name} ({role})")
                return {
                    "name": name,
                    "role": role,
                    "profile_url": profile_url,
                    "club": club_name
                }

        print(f"    ⚠️  No SD found for {club_name}")
        return {"error": f"No SD found for {club_name}"}

    except Exception as e:
        print(f"    ✗ Error finding SD: {e}")
        return {"error": str(e)}


def scrape_sd_profile(sd_url: str) -> dict:
    """
    Scrape complete Sporting Director profile including career stations.

    Returns:
        {
            "name": str,
            "age": int,
            "nationality": str,
            "current_club": str,
            "current_role": str,
            "career_history": [
                {
                    "club": str,
                    "role": str,
                    "period": str,
                    "start_year": int,
                    "end_year": int,
                    "coaches_worked_with": []  # Will be enriched later
                }
            ]
        }
    """
    print(f"  Fetching: {sd_url}")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }

    try:
        response = requests.get(sd_url, headers=headers, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        result = {
            "url": sd_url,
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

        # Extract career history
        career_history = []
        # Find stations table directly (SD profiles structure)
        stations_table = soup.find("table", class_="items")

        if stations_table:
            # Get all rows except header
            all_rows = stations_table.find_all("tr")

            for row in all_rows[1:]:  # Skip header row
                cells = row.find_all("td")
                if len(cells) < 4:  # Need at least 4 cells for club, role, start, end
                    continue

                station = {}

                # Cell 0: Club logo
                # Cell 1: Club name + role (separated by <br>)
                club_cell = cells[1]
                if club_cell:
                    # Extract club name
                    club_link = club_cell.find("a")
                    if club_link:
                        station["club"] = club_link.get_text(strip=True)
                        station["club_url"] = "https://www.transfermarkt.de" + club_link.get("href", "")

                    # Extract role (text after <br>)
                    # Get all text and split by newlines
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
                    # Parse year from format like "23/24 (01.03.2024)" or "08/09 (19.10.2008)"
                    if "/" in start_text:
                        try:
                            year_part = start_text.split()[0].split("/")[0]
                            # Convert 2-digit year to 4-digit
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
                    # Parse end year
                    if "/" in end_text and "vsl" not in end_text:  # Skip "vsl." (presumably) dates
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
        print(f"    ✗ Error scraping {sd_url}: {e}")
        return {"error": str(e), "url": sd_url}


def main():
    """Scrape all Bundesliga Sporting Directors."""
    print("=" * 70)
    print("Scraping Bundesliga Sporting Directors")
    print("=" * 70)
    print(f"Total clubs: {len(BUNDESLIGA_CLUBS)}\n")

    results = []

    for i, club_info in enumerate(BUNDESLIGA_CLUBS, 1):
        club_name = club_info["name"]
        club_id = club_info["club_id"]

        print(f"[{i}/{len(BUNDESLIGA_CLUBS)}] {club_name}")

        # Step 1: Find SD from staff page
        sd_info = find_sd_from_staff_page(club_id, club_name)

        if sd_info.get("error"):
            results.append({
                "club": club_name,
                "error": sd_info["error"]
            })
            time.sleep(3)
            continue

        # Step 2: Scrape full SD profile
        print(f"  Scraping profile...")
        data = scrape_sd_profile(sd_info["profile_url"])
        data["expected_club"] = club_name
        data["expected_role"] = sd_info["role"]

        results.append(data)

        if data.get("career_history"):
            print(f"    ✓ Found {len(data['career_history'])} career stations")

        # Rate limiting
        if i < len(BUNDESLIGA_CLUBS):
            time.sleep(5)  # 5 seconds between requests

    # Save results
    output_path = Path(__file__).parent.parent / "data" / "sporting_directors_bundesliga.json"
    output_path.parent.mkdir(exist_ok=True, parents=True)

    output_data = {
        "league": "Bundesliga",
        "season": "2024/25",
        "total_sds": len([r for r in results if not r.get("error")]),
        "scraped_at": datetime.now().isoformat(),
        "sporting_directors": results
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print(f"✅ COMPLETE! Saved to: {output_path}")
    print(f"📊 Total SDs: {len([r for r in results if not r.get('error')])}")
    print(f"📈 Total career stations: {sum(sd.get('total_stations', 0) for sd in results if not sd.get('error'))}")
    print("=" * 70)


if __name__ == "__main__":
    main()
