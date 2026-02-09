#!/usr/bin/env python3
"""
Scrape Club Executives (Non-SD Leadership) for all Bundesliga clubs.

This captures decision makers beyond Sporting Directors:
- Scouting Leadership (Chefscout, Leiter Scouting, etc.)
- Academy/Youth Leadership (Nachwuchskoordinator, Leiter Nachwuchs, etc.)
- Technical Directors
- Other relevant executives

PURPOSE: These contacts are critical for understanding coach networks,
especially during their youth/assistant coach phases where they build
relationships with non-SD leadership that later hire them.
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

# Role keywords for different executive categories
EXECUTIVE_ROLE_KEYWORDS = {
    "Scouting": [
        "Chefscout",
        "Leiter Scouting",
        "Head of Scouting",
        "Scouting-Chef",
        "Direktor Scouting",
        "Scout",
    ],
    "Academy": [
        "Nachwuchskoordinator",
        "Leiter Nachwuchs",
        "Nachwuchschef",
        "Head of Academy",
        "Direktor Nachwuchs",
        "Leiter Nachwuchsleistungszentrum",
        "NLZ-Leiter",
        "Akademie-Direktor",
    ],
    "Technical": [
        "Technischer Direktor",
        "Technical Director",
        "Direktor Profifußball",
    ],
    "Other": [
        "Leiter Lizenzspielerabteilung",
        "Direktor Sport",
        "Head of Football Operations",
    ]
}

def categorize_role(role: str) -> str:
    """Categorize a role based on keywords."""
    for category, keywords in EXECUTIVE_ROLE_KEYWORDS.items():
        if any(keyword.lower() in role.lower() for keyword in keywords):
            return category
    return "Other"


def find_executives_from_staff_page(club_id: int, club_name: str) -> list:
    """
    Find all relevant executives from club's staff page.

    Returns:
        [
            {
                "name": str,
                "role": str,
                "category": str,  # Scouting, Academy, Technical, Other
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

    executives = []

    try:
        response = requests.get(staff_url, headers=headers, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find all inline-table elements (staff entries)
        staff_tables = soup.find_all("table", class_="inline-table")
        if not staff_tables:
            print(f"    ⚠️  No staff tables found for {club_name}")
            return []

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

            # Check if this is a relevant executive role
            category = categorize_role(role)

            # Only include if it matches our categories
            if category in ["Scouting", "Academy", "Technical"]:
                print(f"    ✓ Found Executive: {name} ({role}) [{category}]")
                executives.append({
                    "name": name,
                    "role": role,
                    "category": category,
                    "profile_url": profile_url,
                    "club": club_name
                })

        if not executives:
            print(f"    → No relevant executives found for {club_name}")

        return executives

    except Exception as e:
        print(f"    ✗ Error finding executives: {e}")
        return []


def scrape_executive_profile(exec_url: str) -> dict:
    """
    Scrape executive profile including career stations.

    Returns:
        {
            "name": str,
            "current_club": str,
            "current_role": str,
            "career_history": [
                {
                    "club": str,
                    "role": str,
                    "start_year": int,
                    "end_year": int,
                }
            ]
        }
    """
    print(f"    Scraping profile: {exec_url}")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }

    try:
        response = requests.get(exec_url, headers=headers, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Extract name from header
        name_elem = soup.find("h1", class_="data-header__headline-wrapper")
        name = name_elem.get_text(strip=True) if name_elem else "Unknown"

        # Extract career stations
        career_history = []
        station_boxes = soup.find_all("div", class_="box")

        for box in station_boxes:
            header = box.find("h2", class_="content-box-headline")
            if not header or "Stationen als" not in header.get_text():
                continue

            # Found career section
            table = box.find("table", class_="items")
            if not table:
                continue

            rows = table.find_all("tr", class_=lambda x: x and ("odd" in x or "even" in x))

            for row in rows:
                # Club name
                club_cell = row.find("td", class_="hauptlink")
                club = club_cell.get_text(strip=True) if club_cell else "Unknown"

                # Role
                role_img = row.find("img", {"class": "tiny_wappen"})
                role = role_img.get("title", "Unknown") if role_img else "Unknown"

                # Period
                period_cell = row.find("td", class_="zentriert")
                if period_cell:
                    period_text = period_cell.get_text(strip=True)
                    # Parse years from period (e.g., "Jul 1, 2015 - Jun 30, 2018")
                    years = [y for y in period_text.split() if y.isdigit() and len(y) == 4]
                    start_year = int(years[0]) if len(years) > 0 else None
                    end_year = int(years[-1]) if len(years) > 1 else None
                else:
                    start_year = None
                    end_year = None

                career_history.append({
                    "club": club,
                    "role": role,
                    "start_year": start_year,
                    "end_year": end_year,
                })

        return {
            "name": name,
            "url": exec_url,
            "career_history": career_history
        }

    except Exception as e:
        print(f"      ✗ Error scraping profile: {e}")
        return {"error": str(e)}


def main():
    """Scrape all Bundesliga club executives."""
    print("=" * 70)
    print("SCRAPING CLUB EXECUTIVES (Academy, Scouting, Technical Leadership)")
    print("=" * 70)
    print(f"Starting at: {datetime.now().strftime('%H:%M:%S')}")
    print()

    all_executives = []

    for idx, club in enumerate(BUNDESLIGA_CLUBS, 1):
        club_name = club["name"]
        club_id = club["club_id"]

        print(f"\n[{idx}/18] {club_name}")
        print(f"Time: {datetime.now().strftime('%H:%M:%S')}")

        # Find executives from staff page
        executives = find_executives_from_staff_page(club_id, club_name)

        if executives:
            # Enrich each executive with career history
            for exec_info in executives:
                time.sleep(2)  # Rate limiting
                profile_data = scrape_executive_profile(exec_info["profile_url"])

                if "error" not in profile_data:
                    # Merge data
                    exec_info.update({
                        "current_club": club_name,
                        "current_role": exec_info["role"],
                        "career_history": profile_data.get("career_history", [])
                    })
                    all_executives.append(exec_info)

        time.sleep(3)  # Rate limiting between clubs

    # Save results
    output_file = Path(__file__).parent.parent / "data" / "club_executives_bundesliga.json"
    output_data = {
        "scraped_date": datetime.now().isoformat(),
        "league": "Bundesliga",
        "season": "2024/25",
        "total_clubs": len(BUNDESLIGA_CLUBS),
        "total_executives": len(all_executives),
        "executives": all_executives
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 70)
    print(f"✅ COMPLETE! Found {len(all_executives)} executives")
    print(f"📁 Saved to: {output_file}")
    print("=" * 70)

    # Summary by category
    categories = {}
    for exec_info in all_executives:
        cat = exec_info.get("category", "Other")
        categories[cat] = categories.get(cat, 0) + 1

    print("\n📊 Summary by Category:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")


if __name__ == "__main__":
    main()
