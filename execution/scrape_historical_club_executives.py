#!/usr/bin/env python3
"""
Scrape Historical Club Executives for ALL clubs across time.

PURPOSE: Build a complete historical database of who held Scouting/Academy/Technical
leadership positions at each club, year by year. This enables matching coaches during
their youth/assistant phases with the executives they worked with.

STRATEGY:
1. Start with current Bundesliga club executives (from scrape_club_executives.py)
2. Scrape their FULL career histories from their Transfermarkt profiles
3. Build a year-by-year mapping: {Club → Year → [Executives]}
4. Expand to non-Bundesliga clubs that coaches worked at historically

This is a ONE-TIME data collection effort since history doesn't change.

Output:
- data/historical_club_executives.json
  Structure: {
    "clubs": {
      "RB Leipzig": {
        "2015": [
          {
            "name": "Johannes Spors",
            "role": "Leiter Scouting",
            "category": "Scouting",
            "profile_url": "..."
          }
        ],
        "2016": [...],
        ...
      }
    }
  }
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup
import requests
from collections import defaultdict

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))


def scrape_executive_career_history(profile_url: str, exec_name: str, current_category: str) -> list:
    """
    Scrape an executive's full career history from their Transfermarkt profile.

    Returns:
        [
            {
                "club": str,
                "role": str,
                "start_year": int,
                "end_year": int,
                "category": str  # Inferred from role keywords
            }
        ]
    """
    print(f"    Scraping: {exec_name}")
    print(f"    URL: {profile_url}")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }

    # Category keywords
    CATEGORY_KEYWORDS = {
        "Scouting": ["scout", "scouting"],
        "Academy": ["nachwuchs", "academy", "jugend", "nlz"],
        "Technical": ["technischer direktor", "technical director", "direktor profifußball"],
    }

    career_history = []

    try:
        response = requests.get(profile_url, headers=headers, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find career stations section
        # Look for "Stationen als Funktionär" or similar
        station_boxes = soup.find_all("div", class_="box")

        for box in station_boxes:
            header = box.find("h2", class_="content-box-headline")
            if not header:
                continue

            header_text = header.get_text(strip=True)
            if "Stationen als" not in header_text:
                continue

            # Found career section - parse table
            table = box.find("table", class_="items")
            if not table:
                continue

            rows = table.find_all("tr", class_=lambda x: x and ("odd" in x or "even" in x))

            for row in rows:
                try:
                    # Club
                    club_cell = row.find("td", class_="hauptlink")
                    if not club_cell:
                        continue
                    club_link = club_cell.find("a")
                    club_name = club_link.get_text(strip=True) if club_link else "Unknown"

                    # Role/Position
                    # The role is in a td with an image that has a title
                    role_cell = row.find("td")
                    role = "Unknown"
                    if role_cell:
                        role_img = role_cell.find("img")
                        if role_img and role_img.get("title"):
                            role = role_img.get("title")

                    # Period - look for centered cell with dates
                    period_cells = row.find_all("td", class_="zentriert")
                    start_year = None
                    end_year = None

                    for cell in period_cells:
                        cell_text = cell.get_text(strip=True)
                        # Look for year patterns (4-digit numbers)
                        years = [int(y) for y in cell_text.split() if y.isdigit() and len(y) == 4]
                        if len(years) >= 1:
                            start_year = years[0]
                        if len(years) >= 2:
                            end_year = years[-1]
                        if years and not end_year:
                            # Only one year means current position or same year
                            end_year = None  # Current

                    # Infer category from role
                    role_lower = role.lower()
                    category = current_category  # Default to current
                    for cat, keywords in CATEGORY_KEYWORDS.items():
                        if any(kw in role_lower for kw in keywords):
                            category = cat
                            break

                    if club_name and start_year:
                        career_history.append({
                            "club": club_name,
                            "role": role,
                            "start_year": start_year,
                            "end_year": end_year,
                            "category": category
                        })
                        print(f"      ✓ {club_name} ({start_year}-{end_year or 'current'}): {role}")

                except Exception as e:
                    print(f"      ⚠️  Error parsing row: {e}")
                    continue

        print(f"      → Found {len(career_history)} career stations")
        return career_history

    except Exception as e:
        print(f"      ✗ Error scraping profile: {e}")
        return []


def build_historical_mapping(executives_with_history: list) -> dict:
    """
    Build year-by-year mapping of clubs to executives.

    Returns:
        {
            "RB Leipzig": {
                2015: [exec_info, ...],
                2016: [exec_info, ...],
                ...
            }
        }
    """
    mapping = defaultdict(lambda: defaultdict(list))

    for exec_info in executives_with_history:
        name = exec_info["name"]
        profile_url = exec_info["profile_url"]

        for station in exec_info.get("career_history", []):
            club = station["club"]
            start_year = station["start_year"]
            end_year = station.get("end_year")

            # Handle current positions (no end year)
            if not end_year:
                end_year = 2026  # Assume current through 2026

            # Add to mapping for each year in tenure
            for year in range(start_year, end_year + 1):
                mapping[club][year].append({
                    "name": name,
                    "role": station["role"],
                    "category": station["category"],
                    "profile_url": profile_url,
                    "tenure": f"{start_year}-{end_year}"
                })

    return mapping


def main():
    """Build historical club executives database."""
    print("=" * 70)
    print("HISTORICAL CLUB EXECUTIVES DATABASE BUILDER")
    print("=" * 70)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Step 1: Load current Bundesliga executives
    print("[1/4] Loading current Bundesliga executives...")
    current_exec_file = Path(__file__).parent.parent / "data" / "club_executives_bundesliga.json"

    if not current_exec_file.exists():
        print(f"❌ ERROR: {current_exec_file} not found!")
        print("Please run scrape_club_executives.py first.")
        return

    with open(current_exec_file, 'r', encoding='utf-8') as f:
        current_data = json.load(f)

    current_executives = current_data.get("executives", [])
    print(f"  ✓ Loaded {len(current_executives)} current executives")

    # Step 2: Scrape career histories
    print(f"\n[2/4] Scraping career histories for all executives...")
    print(f"  (This will take ~{len(current_executives) * 2} seconds due to rate limiting)")
    print()

    executives_with_history = []

    for i, exec_info in enumerate(current_executives, 1):
        print(f"  [{i}/{len(current_executives)}] {exec_info['name']} ({exec_info['current_club']})")

        career_history = scrape_executive_career_history(
            exec_info["profile_url"],
            exec_info["name"],
            exec_info["category"]
        )

        exec_info["career_history"] = career_history
        executives_with_history.append(exec_info)

        # Rate limiting
        time.sleep(2)

    print(f"\n  ✓ Scraped {len(executives_with_history)} executive career histories")

    # Step 3: Build historical mapping
    print("\n[3/4] Building year-by-year club → executive mapping...")
    historical_mapping = build_historical_mapping(executives_with_history)

    # Convert defaultdict to regular dict for JSON serialization
    output_mapping = {}
    for club, years_dict in historical_mapping.items():
        output_mapping[club] = {str(year): execs for year, execs in sorted(years_dict.items())}

    # Calculate statistics
    total_clubs = len(output_mapping)
    total_club_years = sum(len(years) for years in output_mapping.values())

    print(f"  ✓ Built mapping for {total_clubs} clubs")
    print(f"  ✓ Total club-years: {total_club_years}")

    # Step 4: Save results
    print("\n[4/4] Saving results...")
    output_file = Path(__file__).parent.parent / "data" / "historical_club_executives.json"

    output_data = {
        "created_date": datetime.now().isoformat(),
        "description": "Historical club executives database (Scouting, Academy, Technical leadership)",
        "source": "Transfermarkt profile career histories",
        "total_executives": len(executives_with_history),
        "total_clubs": total_clubs,
        "total_club_years": total_club_years,
        "year_range": f"{min(int(y) for club in output_mapping.values() for y in club.keys())}-{max(int(y) for club in output_mapping.values() for y in club.keys())}",
        "executives": executives_with_history,  # Full executive data with career histories
        "clubs": output_mapping  # Year-by-year mapping
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"\n✅ COMPLETE!")
    print(f"📁 Saved to: {output_file}")
    print(f"📊 Coverage:")
    print(f"   - {total_clubs} clubs")
    print(f"   - {total_club_years} club-years")
    print(f"   - {len(executives_with_history)} executives")

    # Show sample clubs with most coverage
    print(f"\n🏆 Top 10 clubs by year coverage:")
    sorted_clubs = sorted(output_mapping.items(), key=lambda x: len(x[1]), reverse=True)
    for i, (club, years_dict) in enumerate(sorted_clubs[:10], 1):
        year_range = f"{min(years_dict.keys())}-{max(years_dict.keys())}"
        num_execs = len(set(e["name"] for year_execs in years_dict.values() for e in year_execs))
        print(f"   {i}. {club}: {len(years_dict)} years ({year_range}), {num_execs} executives")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
