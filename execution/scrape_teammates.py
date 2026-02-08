#!/usr/bin/env python3
"""
Transfermarkt Teammates Scraper - Layer 3 Execution Script
Scrapes a coach's former teammates from their playing career.
Identifies teammates who became coaches or sporting directors.
"""

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

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

# Transfermarkt base URL
TM_BASE = "https://www.transfermarkt.de"

# Request settings
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}

REQUEST_DELAY = 3


def ensure_dirs():
    """Create necessary directories."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    RAW_HTML_DIR.mkdir(parents=True, exist_ok=True)


def get_cached(cache_key: str) -> Optional[dict]:
    """Load from cache if exists and fresh."""
    cache_file = CACHE_DIR / f"{cache_key}.json"
    if cache_file.exists():
        with open(cache_file, "r") as f:
            data = json.load(f)
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


def fetch_page(url: str, save_as: str = None) -> Optional[BeautifulSoup]:
    """Fetch a page with proper headers and rate limiting."""
    print(f"  Fetching: {url}")
    time.sleep(REQUEST_DELAY)

    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()

        if save_as:
            html_file = RAW_HTML_DIR / f"{save_as}.html"
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(response.text)

        return BeautifulSoup(response.text, "lxml")

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            print(f"  Rate limited. Waiting 60 seconds...")
            time.sleep(60)
            return fetch_page(url, save_as)
        print(f"  ERROR: HTTP {e.response.status_code}")
        return None

    except requests.exceptions.RequestException as e:
        print(f"  ERROR: Request failed: {e}")
        return None


def get_teammates_url(player_id: str, player_name_slug: str, page: int = 1) -> str:
    """Build teammates page URL from player ID."""
    # Correct URL: /name/gemeinsameSpiele/spieler/12345
    # Pagination: /name/gemeinsameSpiele/spieler/12345/page/2
    base_url = f"https://www.transfermarkt.de/{player_name_slug}/gemeinsameSpiele/spieler/{player_id}"
    if page > 1:
        return f"{base_url}/page/{page}"
    return base_url


def get_total_pages(soup: BeautifulSoup) -> int:
    """Extract total number of pages from pagination."""
    # Look for pagination links
    pager = soup.find("div", class_="pager")
    if not pager:
        # Also check for li.tm-pagination__list-item
        pagination = soup.find("ul", class_="tm-pagination")
        if pagination:
            page_links = pagination.find_all("a", class_="tm-pagination__link")
            max_page = 1
            for link in page_links:
                href = link.get("href", "")
                match = re.search(r"/page/(\d+)", href)
                if match:
                    max_page = max(max_page, int(match.group(1)))
            return max_page
        return 1

    # Find all page links
    page_links = pager.find_all("a")
    max_page = 1
    for link in page_links:
        href = link.get("href", "")
        match = re.search(r"/page/(\d+)", href)
        if match:
            max_page = max(max_page, int(match.group(1)))

    return max_page


def extract_player_id_from_profile(soup: BeautifulSoup) -> tuple:
    """
    Extract player ID and slug from coach profile page.
    Returns (player_id, player_name_slug) or (None, None) if not found.
    """
    # Look for link to player profile
    player_link = soup.find("a", href=re.compile(r"/[\w-]+/profil/spieler/\d+"))
    if player_link:
        href = player_link.get("href", "")
        match = re.search(r"/([\w-]+)/profil/spieler/(\d+)", href)
        if match:
            return match.group(2), match.group(1)  # player_id, slug
    return None, None


def parse_int(text: str) -> int:
    """Parse integer from text."""
    if not text:
        return 0
    import re
    cleaned = re.sub(r"[^\d]", "", text)
    return int(cleaned) if cleaned else 0


def parse_teammates(soup: BeautifulSoup, min_matches: int = 0) -> tuple:
    """
    Parse teammates table from gemeinsameSpiele page.
    Columns: Name/Position | Matches | Teams | PPG | Joint Goals | Minutes

    Args:
        soup: BeautifulSoup of the page
        min_matches: Minimum shared matches to include (default 10)

    Returns:
        tuple: (filtered_teammates_list, total_unfiltered_count)
    """
    teammates = []

    # Find the main table
    table = soup.find("table", class_="items")
    if not table:
        print("  No teammates table found")
        return teammates, 0

    # Find all rows - they don't have odd/even classes on this page
    all_rows = table.find_all("tr")

    # Filter to data rows (those with inline-table for player info)
    data_rows = []
    for row in all_rows:
        inline_table = row.find("table", class_="inline-table")
        if inline_table:
            data_rows.append(row)

    total_unfiltered = len(data_rows)
    print(f"  Found {total_unfiltered} total teammates")

    for row in data_rows:
        # Find inline-table which contains name and position
        inline_table = row.find("table", class_="inline-table")

        # Name is in hauptlink
        name_link = inline_table.find("a", class_=None)
        if not name_link:
            name_cell = inline_table.find("td", class_="hauptlink")
            if name_cell:
                name_link = name_cell.find("a")

        if not name_link:
            continue

        name = name_link.get_text(strip=True)
        url = TM_BASE + name_link["href"] if name_link.get("href") else None

        # Position is usually in the second row of inline-table
        position = ""
        pos_rows = inline_table.find_all("tr")
        if len(pos_rows) > 1:
            position = pos_rows[1].get_text(strip=True)

        # Get stats from zentriert cells
        # Order: Matches | Teams | PPG | Joint Goal Participation | Minutes
        zentriert_cells = row.find_all("td", class_="zentriert")

        matches = 0
        teams = 0
        minutes = 0

        if len(zentriert_cells) >= 1:
            matches = parse_int(zentriert_cells[0].get_text())
        if len(zentriert_cells) >= 2:
            teams = parse_int(zentriert_cells[1].get_text())
        if len(zentriert_cells) >= 5:
            # Minutes is in the last zentriert cell, format like "5.614"
            minutes_text = zentriert_cells[4].get_text(strip=True).replace(".", "").replace(",", "")
            minutes = parse_int(minutes_text)

        # Filter: only include teammates with 10+ shared matches
        if matches < min_matches:
            continue

        teammate = {
            "name": name,
            "position": position,
            "url": url,
            "shared_matches": matches,
            "teams_together": teams,
            "total_minutes": minutes
        }

        teammates.append(teammate)

    # Sort by shared matches descending
    teammates.sort(key=lambda x: x.get("shared_matches", 0), reverse=True)

    print(f"  Filtered to {len(teammates)} teammates with {min_matches}+ shared matches")
    return teammates, total_unfiltered


def scrape_current_role(player_url: str) -> dict:
    """
    Scrape the current role/position of a former player.
    Returns dict with current_role, current_club, is_coach, is_director.
    """
    if not player_url:
        return {}

    # Convert to profile URL if needed
    profile_url = player_url
    if "/profil/spieler/" not in profile_url:
        profile_url = re.sub(r"/leistungsdatendetails/spieler/", "/profil/spieler/", profile_url)
        profile_url = re.sub(r"/leistungsdaten/spieler/", "/profil/spieler/", profile_url)

    soup = fetch_page(profile_url, None)
    if not soup:
        return {}

    result = {
        "current_role": None,
        "current_club": None,
        "is_coach": False,
        "is_director": False,
    }

    # Look for "Aktueller Status" or current position info
    # Check for trainer profile link (indicates they're now a coach)
    trainer_link = soup.find("a", href=re.compile(r"/profil/trainer/"))
    if trainer_link:
        result["is_coach"] = True
        # Try to get their coaching role
        parent = trainer_link.find_parent("div") or trainer_link.find_parent("span")
        if parent:
            result["current_role"] = clean_role_text(parent.get_text(strip=True))

    # Look for current position in data header
    data_header = soup.find("div", class_="data-header__details")
    if data_header:
        # Look for role/position text
        items = data_header.find_all("li")
        for item in items:
            text = item.get_text(strip=True).lower()
            if "trainer" in text or "coach" in text or "manager" in text:
                result["is_coach"] = True
                result["current_role"] = clean_role_text(item.get_text(strip=True))
            if "direktor" in text or "director" in text:
                result["is_director"] = True
                result["current_role"] = clean_role_text(item.get_text(strip=True))

    # Look for current club
    current_club = soup.find("span", class_="data-header__club")
    if current_club:
        club_link = current_club.find("a")
        if club_link:
            result["current_club"] = club_link.get_text(strip=True)

    return result


def enrich_teammates_with_current_roles(teammates: list, max_to_enrich: int = None, progress_callback=None) -> list:
    """
    Enrich teammates with their current role (coach/director/player).

    Args:
        teammates: List of teammate dicts
        max_to_enrich: Max number to check. None = ALL teammates
        progress_callback: Optional function(current, total, name) for progress updates
    """
    to_check = teammates if max_to_enrich is None else teammates[:max_to_enrich]
    total = len(to_check)

    print(f"\n  Enriching {total} teammates with current roles...")

    enriched_count = 0
    coaches_found = []
    directors_found = []

    for i, tm in enumerate(to_check):
        url = tm.get("url")
        if not url:
            continue

        # Progress update
        if progress_callback:
            progress_callback(i + 1, total, tm.get("name", ""))
        elif i % 25 == 0:
            print(f"    Progress: {i}/{total} checked, {enriched_count} found...")

        # Quick check: fetch profile and look for trainer link
        try:
            soup = fetch_page(url, None)
            if soup:
                # Check for "Zur Trainerseite" link or similar
                trainer_link = soup.find("a", href=re.compile(r"/profil/trainer/\d+"))

                if trainer_link:
                    # This person is now a coach!
                    trainer_url = TM_BASE + trainer_link.get("href", "")
                    tm["is_coach"] = True
                    tm["trainer_url"] = trainer_url

                    # Try to get their current coaching position
                    trainer_soup = fetch_page(trainer_url, None)
                    if trainer_soup:
                        # Find current club from data header
                        club_span = trainer_soup.find("span", class_="data-header__club")
                        if club_span:
                            club_link = club_span.find("a")
                            if club_link:
                                tm["current_club"] = club_link.get_text(strip=True)

                        # Find role from label
                        label = trainer_soup.find("span", class_="data-header__label")
                        if label:
                            tm["current_role"] = clean_role_text(label.get_text(strip=True))

                        # Also check data-header__items for more details
                        items = trainer_soup.find("ul", class_="data-header__items")
                        if items:
                            for li in items.find_all("li"):
                                text = li.get_text(strip=True)
                                if "Cheftrainer" in text or "Head Coach" in text or "Manager" in text:
                                    tm["current_role"] = clean_role_text(text.split(":")[0] if ":" in text else text)

                    enriched_count += 1
                    coaches_found.append(tm["name"])
                    print(f"    ✓ [{i+1}/{total}] {tm['name']}: Coach at {tm.get('current_club', '?')}")

                else:
                    # Check if they're in management (sportdirektor, etc.)
                    mgmt_keywords = ["direktor", "director", "sportvorstand", "leiter", "geschäftsführer"]
                    header_info = soup.find("div", class_="data-header__info-box")
                    if header_info:
                        text = header_info.get_text(strip=True).lower()
                        if any(kw in text for kw in mgmt_keywords):
                            tm["is_director"] = True
                            tm["current_role"] = clean_role_text(header_info.get_text(strip=True))
                            enriched_count += 1
                            directors_found.append(tm["name"])
                            print(f"    ✓ [{i+1}/{total}] {tm['name']}: Director/Manager")

        except Exception as e:
            print(f"    Error enriching {tm.get('name', '?')}: {e}")
            continue

    print(f"\n  ✅ Completed! Found {enriched_count} in coaching/management roles:")
    print(f"     - Coaches: {len(coaches_found)}")
    print(f"     - Directors: {len(directors_found)}")

    return teammates


def clean_role_text(text: str) -> str:
    """
    Clean role text by adding spaces between words.
    Transfermarkt sometimes concatenates words without spaces.

    Examples:
        "Letzter Posten:TorwarttrainerVfB LübeckAmtsende:30.06.2012"
        -> "Letzter Posten: Torwarttrainer VfB Lübeck Amtsende: 30.06.2012"
    """
    import re

    # Add space after colon if missing
    text = re.sub(r':([A-ZÄÖÜ])', r': \1', text)

    # Add space before "Amtsende" specifically
    text = re.sub(r'([a-zäöü])(Amtsende)', r'\1 \2', text)

    # Simple approach: Add space before any capital letter that follows a lowercase letter
    # This will split "TorwarttrainerVfB" -> "Torwarttrainer VfB"
    text = re.sub(r'([a-zäöü])([A-ZÄÖÜ])', r'\1 \2', text)

    # Clean up multiple spaces
    text = re.sub(r'\s+', ' ', text)

    return text.strip()


def identify_coaches_and_directors(teammates: list) -> dict:
    """
    Filter teammates who became coaches or sporting directors.
    Returns dict with 'coaches' and 'sporting_directors' lists.
    """
    coach_keywords = ["trainer", "coach", "manager", "co-trainer", "assistant", "cheftrainer"]
    director_keywords = ["direktor", "director", "sportdirektor", "sporting director", "technical director"]

    coaches = []
    directors = []
    players = []

    for tm in teammates:
        # Check explicit flags first
        if tm.get("is_coach"):
            coaches.append(tm)
        elif tm.get("is_director"):
            directors.append(tm)
        else:
            # Fallback to role text
            role = tm.get("current_role", "").lower()
            if any(kw in role for kw in director_keywords):
                directors.append(tm)
            elif any(kw in role for kw in coach_keywords):
                coaches.append(tm)
            else:
                players.append(tm)

    return {
        "coaches": coaches,
        "sporting_directors": directors,
        "players": players[:20]  # Limit players to top 20
    }


def scrape_teammates(coach_profile_url: str = None, player_id: str = None, player_slug: str = None) -> Optional[dict]:
    """
    Scrape teammates for a coach who had a playing career.

    Args:
        coach_profile_url: URL to coach's trainer profile (will extract player ID from page)
        player_id: Direct player ID (e.g., "1731" for Blessin)
        player_slug: Player name slug (e.g., "alexander-blessin")
    """
    ensure_dirs()

    print(f"\n{'=' * 50}")
    print(f"Scraping Teammates")
    print(f"{'=' * 50}")

    # If we have player_id and slug directly, use them
    if player_id and player_slug:
        teammates_url = get_teammates_url(player_id, player_slug)
    elif coach_profile_url:
        # First fetch the coach profile to find the player ID
        print("  Checking coach profile for player career link...")
        coach_soup = fetch_page(coach_profile_url, None)
        if coach_soup:
            player_id, player_slug = extract_player_id_from_profile(coach_soup)

        if not player_id:
            print("  No player profile found (coach may not have played professionally)")
            return {"teammates": [], "coaches": [], "sporting_directors": [], "players": [], "has_playing_career": False}

        print(f"  Found player ID: {player_id} ({player_slug})")
        teammates_url = get_teammates_url(player_id, player_slug)
    else:
        print("  ERROR: Provide coach_profile_url or (player_id + player_slug)")
        return None

    # Check cache
    cache_key = f"player_{player_id}_teammates"
    cached = get_cached(cache_key)
    if cached:
        return cached

    # Fetch first page to get total pages
    teammates_url = get_teammates_url(player_id, player_slug, page=1)
    soup = fetch_page(teammates_url, f"player_{player_id}_teammates_p1")

    if not soup:
        print("  No teammates page found")
        return {"teammates": [], "coaches": [], "sporting_directors": [], "players": [], "has_playing_career": False}

    # Check pagination
    total_pages = get_total_pages(soup)
    print(f"  Found {total_pages} page(s) of teammates")

    # Parse first page
    all_teammates, _ = parse_teammates(soup)
    print(f"  Page 1: {len(all_teammates)} teammates")

    # Fetch remaining pages
    for page_num in range(2, total_pages + 1):
        page_url = get_teammates_url(player_id, player_slug, page=page_num)
        page_soup = fetch_page(page_url, f"player_{player_id}_teammates_p{page_num}")
        if page_soup:
            page_teammates, _ = parse_teammates(page_soup)
            print(f"  Page {page_num}: {len(page_teammates)} teammates")
            all_teammates.extend(page_teammates)

    # Sort all by shared matches
    all_teammates.sort(key=lambda x: x.get("shared_matches", 0), reverse=True)
    total_unfiltered = len(all_teammates)
    print(f"  Total: {total_unfiltered} teammates across {total_pages} pages")

    # Categorize
    categorized = identify_coaches_and_directors(all_teammates)

    result = {
        "player_id": player_id,
        "teammates_url": teammates_url,
        "total_teammates": len(all_teammates),  # Filtered count (10+ matches)
        "total_teammates_unfiltered": total_unfiltered,  # Total before filtering
        "all_teammates": all_teammates,
        **categorized
    }

    # Save to cache
    save_cache(cache_key, result)

    print(f"\n{'=' * 50}")
    print(f"Teammates scraped!")
    print(f"Total: {len(all_teammates)}")
    print(f"Coaches: {len(categorized['coaches'])}")
    print(f"Directors: {len(categorized['sporting_directors'])}")

    return result


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Scrape Transfermarkt teammates")
    parser.add_argument("--url", "-u", help="Coach profile URL")
    parser.add_argument("--output", "-o", help="Output JSON file")

    args = parser.parse_args()

    if not args.url:
        parser.print_help()
        print("\nExample: python scrape_teammates.py --url 'https://www.transfermarkt.de/...'")
        return

    result = scrape_teammates(coach_profile_url=args.url)

    if result and args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\nSaved to: {args.output}")

    return result


if __name__ == "__main__":
    main()
