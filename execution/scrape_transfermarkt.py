#!/usr/bin/env python3
"""
Transfermarkt Coach Profile Scraper - Layer 3 Execution Script
Scrapes coach profiles from Transfermarkt.de with proper rate limiting.
"""

import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote

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
DATA_DIR = BASE_DIR / "data"

# Transfermarkt base URL
TM_BASE = "https://www.transfermarkt.de"

# Request settings
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

# Rate limiting
REQUEST_DELAY = 3  # seconds between requests


def ensure_dirs():
    """Create necessary directories."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    RAW_HTML_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_cached(cache_key: str) -> Optional[dict]:
    """Load from cache if exists and fresh (< 24h)."""
    cache_file = CACHE_DIR / f"{cache_key}.json"
    if cache_file.exists():
        with open(cache_file, "r") as f:
            data = json.load(f)
            # Check if cache is fresh (less than 24 hours old)
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


def save_raw_html(filename: str, html: str):
    """Save raw HTML for debugging."""
    html_file = RAW_HTML_DIR / f"{filename}.html"
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html)


def fetch_page(url: str, save_as: str = None) -> Optional[BeautifulSoup]:
    """Fetch a page with proper headers and rate limiting."""
    print(f"  Fetching: {url}")
    time.sleep(REQUEST_DELAY)

    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()

        if save_as:
            save_raw_html(save_as, response.text)

        return BeautifulSoup(response.text, "lxml")

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"  ERROR: Page not found (404)")
        elif e.response.status_code == 429:
            print(f"  ERROR: Rate limited (429). Waiting 60 seconds...")
            time.sleep(60)
            return fetch_page(url, save_as)  # Retry
        else:
            print(f"  ERROR: HTTP {e.response.status_code}")
        return None

    except requests.exceptions.RequestException as e:
        print(f"  ERROR: Request failed: {e}")
        return None


def search_coach(name: str) -> list:
    """
    Search for a coach by name.
    Returns list of matches with name, url, current_club.
    """
    search_url = f"{TM_BASE}/schnellsuche/ergebnis/schnellsuche?query={quote(name)}"
    soup = fetch_page(search_url, f"search_{name.replace(' ', '_')}")

    if not soup:
        return []

    results = []

    # Method 1: Find all links to trainer profiles directly
    # This is the most reliable method based on actual HTML structure
    for link in soup.find_all("a", href=re.compile(r"/[\w-]+/profil/trainer/\d+")):
        href = link.get("href", "")
        link_text = link.get_text(strip=True)

        # Skip empty links or image-only links
        if not link_text or len(link_text) < 3:
            continue

        # Try to find club info from parent row
        current_club = "Unknown"
        parent_row = link.find_parent("tr")
        if parent_row:
            # Look for club link
            club_link = parent_row.find("a", href=re.compile(r"/[\w-]+/startseite/verein/"))
            if club_link:
                current_club = club_link.get_text(strip=True)

        # Avoid duplicates
        full_url = TM_BASE + href
        if not any(r["url"] == full_url for r in results):
            results.append({
                "name": link_text,
                "url": full_url,
                "current_club": current_club
            })

    return results


def parse_coach_profile(soup: BeautifulSoup, url: str) -> dict:
    """Parse coach profile page and extract all data."""
    profile = {
        "url": url,
        "scraped_at": datetime.now().isoformat()
    }

    # Name - get text and clean up whitespace
    name_elem = soup.find("h1", class_="data-header__headline-wrapper")
    if name_elem:
        # Get all text, normalize whitespace
        name_text = " ".join(name_elem.get_text().split())
        profile["name"] = name_text

    # Profile image
    img = soup.find("img", class_="data-header__profile-image")
    if img:
        profile["image_url"] = img.get("src", "")

    # Method 1: Parse from info table rows (th/td structure)
    for row in soup.find_all("tr"):
        th = row.find("th")
        td = row.find("td")
        if th and td:
            label = th.get_text(strip=True).lower()
            value = td.get_text(strip=True)

            if "nationalität" in label:
                profile["nationality"] = value.replace("\xa0", " ").strip()
            elif "geburtsdatum" in label or "geb./alter" in label:
                profile["dob"] = value
                age_match = re.search(r"\((\d+)\)", value)
                if age_match:
                    profile["age"] = int(age_match.group(1))
            elif "geburtsort" in label:
                profile["birthplace"] = value
            elif "lizenz" in label:
                profile["license"] = value
            elif "berater" in label:
                # Agent/Berater info
                profile["agent"] = value
                agent_link = td.find("a")
                if agent_link and agent_link.get("href"):
                    profile["agent_url"] = TM_BASE + agent_link["href"]
            elif "vertrag" in label or "contract" in label:
                # Contract end date
                profile["contract_until"] = value

    # Method 2: Parse from data-header section for license
    for item in soup.find_all("li", class_="data-header__label"):
        text = item.get_text(strip=True)
        if "Lizenz" in text:
            content = item.find("span", class_="data-header__content")
            if content:
                profile["license"] = content.get_text(strip=True)

    # Method 3: Parse from premium-profil-text divs
    for div in soup.find_all("div", class_="premium-profil-text"):
        text = div.get_text()
        if "Nationalität" in text:
            span = div.find("span")
            if span:
                profile["nationality"] = span.get_text(strip=True).replace("\xa0", " ")
        elif "Alter" in text:
            # Extract age from text like "Alter\n51"
            age_match = re.search(r"Alter\s*(\d+)", text)
            if age_match:
                profile["age"] = int(age_match.group(1))

    # Current position from header
    position_elem = soup.find("span", class_="data-header__label")
    if position_elem:
        role_text = position_elem.get_text(strip=True)
        # Clean up role text
        if role_text and not role_text.startswith("Lizenz"):
            profile["current_role"] = role_text

    # Current club from header
    club_elem = soup.find("span", class_="data-header__club")
    if club_elem:
        club_link = club_elem.find("a")
        if club_link:
            profile["current_club"] = club_link.get_text(strip=True)
            profile["current_club_url"] = TM_BASE + club_link["href"]

    # Career history table
    career = []
    career_table = soup.find("div", {"data-viewport": "Karriere"})
    if not career_table:
        career_table = soup.find("div", class_="grid tm-player-career")

    if career_table:
        rows = career_table.find_all("div", class_="grid__cell")
        # Parse career rows - structure varies

    # Alternative: look for standard career table
    tables = soup.find_all("table", class_="items")
    for table in tables:
        header = table.find_previous(["h2", "div"], class_=["content-box-headline", "table-header"])
        if header and any(x in header.get_text().lower() for x in ["karriere", "career", "stationen"]):
            for row in table.find_all("tr")[1:]:  # Skip header
                cells = row.find_all("td")
                if len(cells) >= 3:
                    club_cell = cells[0]
                    role_cell = cells[1] if len(cells) > 1 else None
                    date_cell = cells[-1]

                    club_link = club_cell.find("a")
                    career_entry = {
                        "club": club_link.get_text(strip=True) if club_link else club_cell.get_text(strip=True),
                        "club_url": TM_BASE + club_link["href"] if club_link and club_link.get("href") else None,
                        "role": role_cell.get_text(strip=True) if role_cell else "Unknown",
                        "period": date_cell.get_text(strip=True) if date_cell else "Unknown"
                    }
                    career.append(career_entry)

    profile["career_history"] = career

    return profile


def scrape_coach(name: str = None, url: str = None) -> Optional[dict]:
    """
    Scrape a coach profile by name or direct URL.
    Returns full profile data or None if not found.
    """
    ensure_dirs()

    print(f"\n{'=' * 50}")
    print(f"Scraping Coach Profile")
    print(f"{'=' * 50}")

    # If URL provided, use it directly
    if url:
        # Extract coach ID from URL for caching
        coach_id_match = re.search(r"/trainer/(\d+)", url)
        coach_id = coach_id_match.group(1) if coach_id_match else "unknown"
    else:
        # Search for coach by name
        print(f"\nSearching for: {name}")
        results = search_coach(name)

        if not results:
            print(f"No coach found with name '{name}'")
            return None

        if len(results) > 1:
            print(f"\nFound {len(results)} matches:")
            for i, r in enumerate(results, 1):
                print(f"  {i}. {r['name']} ({r['current_club']})")
            print("\nUsing first match. Provide direct URL for specific coach.")

        url = results[0]["url"]
        coach_id_match = re.search(r"/trainer/(\d+)", url)
        coach_id = coach_id_match.group(1) if coach_id_match else "unknown"

    # Check cache
    cache_key = f"coach_{coach_id}_profile"
    cached = get_cached(cache_key)
    if cached:
        return cached

    # Fetch profile page
    print(f"\nFetching profile: {url}")
    soup = fetch_page(url, f"coach_{coach_id}_profile")

    if not soup:
        return None

    # Parse profile
    profile = parse_coach_profile(soup, url)
    profile["coach_id"] = coach_id

    # Save to cache
    save_cache(cache_key, profile)

    print(f"\n{'=' * 50}")
    print(f"Profile scraped successfully!")
    print(f"Name: {profile.get('name', 'Unknown')}")
    print(f"Club: {profile.get('current_club', 'Unknown')}")
    print(f"Cache: {cache_key}.json")

    return profile


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Scrape Transfermarkt coach profiles")
    parser.add_argument("--name", "-n", help="Coach name to search")
    parser.add_argument("--url", "-u", help="Direct Transfermarkt URL")
    parser.add_argument("--output", "-o", help="Output JSON file")

    args = parser.parse_args()

    if not args.name and not args.url:
        parser.print_help()
        print("\nExample: python scrape_transfermarkt.py --name 'Alexander Blessin'")
        return

    profile = scrape_coach(name=args.name, url=args.url)

    if profile and args.output:
        with open(args.output, "w") as f:
            json.dump(profile, f, indent=2, ensure_ascii=False)
        print(f"\nSaved to: {args.output}")

    return profile


if __name__ == "__main__":
    main()
