#!/usr/bin/env python3
"""
Decision Makers Enrichment - Sustainable Architecture

Combines:
1. Manual curated data (data/manual_decision_makers.json)
2. Scraped current staff from club pages
3. Cached for performance

Usage:
    from enrich_decision_makers import get_all_decision_makers

    result = get_all_decision_makers(coach_name, stations)
    # Returns all decision makers with sources tagged
"""

import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import time
import requests
from bs4 import BeautifulSoup

# Paths
BASE_DIR = Path(__file__).parent.parent
MANUAL_DATA = BASE_DIR / "data" / "manual_decision_makers.json"
CACHE_DIR = BASE_DIR / "tmp" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

TM_BASE = "https://www.transfermarkt.de"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}


def load_manual_decision_makers() -> Dict:
    """Load manually curated decision maker data."""
    if MANUAL_DATA.exists():
        with open(MANUAL_DATA, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"relationships": []}


def get_cache_path(key: str) -> Path:
    """Get cache file path."""
    return CACHE_DIR / f"dm_{key}.json"


def load_from_cache(key: str, max_age_days: int = 7) -> Optional[Dict]:
    """Load from cache if fresh."""
    cache_path = get_cache_path(key)
    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            cached_at = datetime.fromisoformat(data.get("cached_at", "2000-01-01"))
            if datetime.now() - cached_at < timedelta(days=max_age_days):
                return data
        except:
            pass
    return None


def save_to_cache(key: str, data: Dict):
    """Save to cache."""
    data["cached_at"] = datetime.now().isoformat()
    with open(get_cache_path(key), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def scrape_club_decision_makers(club_id: int, club_name: str) -> List[Dict]:
    """
    Scrape current decision makers from club staff page.

    Returns:
        List of decision makers with role and source
    """
    cache_key = f"club_{club_id}_staff"

    # Try cache first
    cached = load_from_cache(cache_key, max_age_days=7)
    if cached:
        return cached.get("decision_makers", [])

    decision_makers = []

    try:
        url = f"{TM_BASE}/verein/mitarbeiter/verein/{club_id}"
        time.sleep(2)  # Rate limiting

        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")

        # Find staff table(s)
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

                # Get role from second td
                tds = row.find_all("td")
                role = ""
                for td in tds[1:3]:  # Check 2nd and 3rd column
                    text = td.get_text(strip=True)
                    if text and len(text) > 3:
                        role = text
                        break

                if not role:
                    continue

                # Filter for decision makers
                role_lower = role.lower()
                relevant_keywords = [
                    "sportdirektor", "geschäftsführer", "vorstand",
                    "direktor", "manager", "präsident", "president",
                    "ceo", "board", "aufsichtsrat"
                ]

                if any(kw in role_lower for kw in relevant_keywords):
                    # Determine connection type
                    if any(kw in role_lower for kw in ["sportdirektor", "sporting director"]):
                        conn_type = "sports_director"
                    elif any(kw in role_lower for kw in ["geschäftsführer", "ceo", "vorstand"]):
                        conn_type = "executive"
                    elif any(kw in role_lower for kw in ["präsident", "president"]):
                        conn_type = "president"
                    elif any(kw in role_lower for kw in ["technisch", "technical"]):
                        conn_type = "technical_director"
                    else:
                        conn_type = "management"

                    decision_makers.append({
                        "name": name,
                        "role": role,
                        "club_name": club_name,
                        "url": profile_url,
                        "connection_type": conn_type,
                        "source": "scraped_current",
                        "scraped_at": datetime.now().isoformat()
                    })

        # Cache results
        save_to_cache(cache_key, {"decision_makers": decision_makers})

    except Exception as e:
        print(f"  Error scraping {club_name} staff: {e}")

    return decision_makers


def get_all_decision_makers(coach_name: str, stations: List[Dict]) -> Dict:
    """
    Get all decision makers for a coach.

    Combines:
    1. Manual curated data
    2. Scraped current staff for each station
    3. Club news/press releases for hiring managers

    Args:
        coach_name: Coach name
        stations: List of coaching stations with club_id, club_name, start_date, end_date

    Returns:
        Dict with categorized decision makers and metadata
    """
    all_dms = []

    # 1. Load manual data
    manual_data = load_manual_decision_makers()

    for relationship in manual_data.get("relationships", []):
        if relationship.get("coach_name") == coach_name:
            for dm in relationship.get("decision_makers", []):
                dm_copy = dm.copy()
                dm_copy["club_name"] = relationship.get("club")
                dm_copy["period"] = relationship.get("period")
                dm_copy["source"] = "manual_curated"
                all_dms.append(dm_copy)

    # 2. Scrape current staff for each station
    for station in stations:
        club_id = station.get("club_id")
        club_name = station.get("club_name", "Unknown")

        if not club_id:
            continue

        scraped = scrape_club_decision_makers(club_id, club_name)
        all_dms.extend(scraped)

    # 3. Scrape club news for hiring managers (NEW!)
    try:
        from scrape_club_news import scrape_coach_announcement

        for station in stations:
            club_name = station.get("club_name", "Unknown")
            start_date = station.get("start_date", "")

            # Extract year from start_date
            year = None
            if start_date:
                import re
                year_match = re.search(r'\d{4}', start_date)
                if year_match:
                    year = int(year_match.group(0))

            # Scrape club news
            news_result = scrape_coach_announcement(club_name, coach_name, year)

            # Add hiring managers from news
            for hm in news_result.get("hiring_managers", []):
                hm["club_name"] = club_name
                if news_result.get("article_url"):
                    hm["article_url"] = news_result["article_url"]
                all_dms.append(hm)

    except Exception as e:
        print(f"  Warning: Could not scrape club news: {e}")

    # 3. Deduplicate by name
    unique_dms = {}
    for dm in all_dms:
        name = dm["name"]
        if name not in unique_dms:
            unique_dms[name] = dm
        else:
            # Prefer manual curated over scraped
            if dm.get("source") == "manual_curated":
                unique_dms[name] = dm

    # 4. Categorize
    result = {
        "sports_directors": [],
        "hiring_managers": [],
        "executives": [],
        "presidents": [],
        "technical_directors": [],
        "other": [],
        "total": len(unique_dms),
        "enriched_at": datetime.now().isoformat()
    }

    for dm in unique_dms.values():
        conn_type = dm.get("connection_type", "other")

        if conn_type == "hiring_manager":
            result["hiring_managers"].append(dm)
        elif conn_type == "sports_director":
            result["sports_directors"].append(dm)
        elif conn_type == "executive":
            result["executives"].append(dm)
        elif conn_type == "president":
            result["presidents"].append(dm)
        elif conn_type == "technical_director":
            result["technical_directors"].append(dm)
        else:
            result["other"].append(dm)

    return result


if __name__ == "__main__":
    # Test with Alexander Blessin
    print("Testing Decision Makers Enrichment...")

    stations = [
        {"club_id": 35, "club_name": "FC St. Pauli"},
        {"club_id": 3948, "club_name": "Union SG"},
        {"club_id": 252, "club_name": "Genua CFC"},
    ]

    result = get_all_decision_makers("Alexander Blessin", stations)

    print(f"\n{'='*60}")
    print(f"Decision Makers for Alexander Blessin")
    print(f"{'='*60}")
    print(f"Total: {result['total']}")

    print(f"\n🎯 Hiring Managers ({len(result['hiring_managers'])}):")
    for dm in result["hiring_managers"]:
        print(f"  - {dm['name']} ({dm['role']}) at {dm.get('club_name')}")
        print(f"    Source: {dm.get('source')} | {dm.get('notes', '')}")

    print(f"\n📋 Sports Directors ({len(result['sports_directors'])}):")
    for dm in result["sports_directors"]:
        print(f"  - {dm['name']} ({dm['role']}) at {dm.get('club_name')}")
        print(f"    Source: {dm.get('source')}")

    print(f"\n👔 Executives ({len(result['executives'])}):")
    for dm in result["executives"]:
        print(f"  - {dm['name']} ({dm['role']}) at {dm.get('club_name')}")
        print(f"    Source: {dm.get('source')}")
