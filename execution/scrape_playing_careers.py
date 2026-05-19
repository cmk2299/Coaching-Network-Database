#!/usr/bin/env python3
"""
Scrape playing careers for BL coaches who were former professionals.
Uses the /spieler/ TM page (vs /trainer/ which we already scrape).

Architecture: Layer 3 (Execution)

Usage:
  python scrape_playing_careers.py                  # All BL coaches
  python scrape_playing_careers.py --tm-id 26099    # Single coach
  python scrape_playing_careers.py --dry-run         # Show who has player pages
"""

import json
import time
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

# ── Config ──────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
PROFILES_DIR = DATA_DIR / "person_profiles"
STAFF_DIR = DATA_DIR / "staff"
CACHE_DIR = BASE_DIR / "tmp" / "cache" / "profiles"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

TM_BASE = "https://www.transfermarkt.de"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}
REQUEST_DELAY = 3
CACHE_DAYS = 30


def fetch_page(url: str, cache_key: str) -> Optional[str]:
    """Fetch page with HTML caching and rate limiting."""
    cache_path = CACHE_DIR / f"{cache_key}.html"

    if cache_path.exists():
        age_hours = (datetime.now().timestamp() - cache_path.stat().st_mtime) / 3600
        if age_hours < CACHE_DAYS * 24:
            return cache_path.read_text(encoding="utf-8")

    time.sleep(REQUEST_DELAY)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
        # Check if TM redirected away from /spieler/ (= no player page)
        if "/spieler/" not in resp.url:
            return None
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        html = resp.text
        cache_path.write_text(html, encoding="utf-8")
        return html
    except requests.exceptions.HTTPError as e:
        if e.response and e.response.status_code == 404:
            return None
        print(f"    ERROR: {e}")
        return None
    except Exception as e:
        print(f"    ERROR: {e}")
        return None


def parse_playing_career(soup: BeautifulSoup) -> list[dict]:
    """
    Parse the /leistungsdatenverein/ page (career by club).
    Returns list of career entries with club_tm_id, club_name, appearances, goals.
    One row per club (not per season — TM only shows aggregated data here).
    """
    career = []

    tables = soup.find_all("table", class_="items")
    if not tables:
        return career

    table = tables[0]
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue

        # Skip summary row ("Insgesamt :")
        row_text = row.get_text(strip=True)
        if "Insgesamt" in row_text:
            continue

        # Find club link
        club_link = row.find("a", href=re.compile(r"/verein/\d+"))
        if not club_link:
            continue

        m = re.search(r"/verein/(\d+)", club_link["href"])
        if not m:
            continue

        club_tm_id = int(m.group(1))
        club_name = club_link.get("title") or club_link.get_text(strip=True)

        # Parse numeric cells: appearances, goals
        numbers = []
        for cell in cells:
            text = cell.get_text(strip=True).replace(".", "")
            if text and text != "-":
                try:
                    numbers.append(int(text))
                except ValueError:
                    pass

        appearances = numbers[0] if numbers else 0
        goals = numbers[1] if len(numbers) > 1 else 0

        career.append({
            "club_tm_id": club_tm_id,
            "club_name": club_name,
            "role": "Spieler",
            "appearances": appearances,
            "goals": goals,
        })

    return career


def parse_player_positions(soup: BeautifulSoup) -> list[str]:
    """Extract player position(s) from the profile header."""
    positions = []
    # Method: data-header li with position info
    for li in soup.find_all("li"):
        text = li.get_text(strip=True)
        if any(pos in text for pos in ["Mittelfeld", "Sturm", "Abwehr", "Torwart",
                                        "Angriff", "Verteidigung", "Torhüter"]):
            positions.append(text)

    # Method 2: info table
    if not positions:
        for span in soup.find_all("span", class_="info-table__content--bold"):
            text = span.get_text(strip=True)
            if any(pos in text for pos in ["Mittelfeld", "Sturm", "Abwehr", "Torwart",
                                            "Rechtsaußen", "Linksaußen", "Innenverteidiger",
                                            "Rechter Verteidiger", "Linker Verteidiger"]):
                positions.append(text)

    return list(set(positions))


def find_player_id(trainer_tm_id: int) -> Optional[int]:
    """
    Find the player TM ID from the trainer's profile page.
    TM uses DIFFERENT IDs for the same person as trainer vs player.
    The trainer page contains a link like: /name/profil/spieler/{player_id}
    """
    cache_key = f"trainer_{trainer_tm_id}"
    cache_path = CACHE_DIR / f"{cache_key}.html"

    if not cache_path.exists():
        # Need to fetch trainer page first
        url = f"{TM_BASE}/x/profil/trainer/{trainer_tm_id}"
        html = fetch_page(url, cache_key)
        if not html:
            return None
    else:
        html = cache_path.read_text(encoding="utf-8")

    soup = BeautifulSoup(html, "html.parser")
    player_link = soup.find("a", href=re.compile(r"/profil/spieler/\d+"))
    if player_link and "spieler-statistik" not in player_link["href"]:
        m = re.search(r"/profil/spieler/(\d+)", player_link["href"])
        if m:
            return int(m.group(1))
    return None


def get_bl_coaches() -> list[dict]:
    """Load all current BL1/BL2 head coaches from staff files.
    Head coach = first person in 'Trainerstab' section (same logic as generate_all_bl_coaches.py).
    """
    # Load club registry to identify BL clubs
    registry_path = DATA_DIR / "club_registry.json"
    if not registry_path.exists():
        print("ERROR: club_registry.json not found")
        return []

    with open(registry_path) as f:
        registry = json.load(f)

    # Find BL1/BL2 clubs for current season
    bl_clubs = set()
    for club in registry.get("clubs", []):
        leagues = club.get("leagues", {})
        for key in ["2025/2026", "2025"]:
            if key in leagues:
                league_list = leagues[key]
                if isinstance(league_list, str):
                    league_list = [league_list]
                if any(l in ("BL1", "BL2") for l in league_list):
                    bl_clubs.add(club["tm_id"])

    coaches = []
    for staff_file in STAFF_DIR.glob("*.json"):
        try:
            with open(staff_file) as f:
                staff = json.load(f)
            club_id = staff.get("club_tm_id")
            if club_id not in bl_clubs:
                continue

            trainerstab = [s for s in staff.get("staff", []) if s.get("section") == "Trainerstab"]
            if not trainerstab:
                continue

            head = trainerstab[0]
            coaches.append({
                "tm_id": head["tm_id"],
                "name": head.get("name", "?"),
                "club": staff.get("club_name", "?"),
            })
        except Exception:
            continue
    return coaches


def consolidate_career(raw_entries: list[dict]) -> list[dict]:
    """
    Consolidate raw career rows into unique club-season pairs.
    Multiple rows per club+season (different competitions) get merged.
    """
    club_seasons = {}
    for entry in raw_entries:
        key = (entry.get("club_tm_id"), entry.get("season_year"))
        if key[0] is None:
            continue
        if key not in club_seasons:
            club_seasons[key] = {
                "club_tm_id": entry["club_tm_id"],
                "club_name": entry.get("club_name", ""),
                "season": entry.get("season", ""),
                "season_year": entry.get("season_year"),
                "role": "Spieler",
                "appearances": 0,
                "goals": 0,
                "competitions": [],
            }
        cs = club_seasons[key]
        cs["appearances"] += entry.get("appearances", 0)
        cs["goals"] += entry.get("goals", 0)
        if entry.get("competition"):
            cs["competitions"].append(entry["competition"])

    return sorted(club_seasons.values(), key=lambda x: x.get("season_year", 0), reverse=True)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Scrape playing careers for BL coaches")
    parser.add_argument("--tm-id", type=int, help="Single coach TM ID")
    parser.add_argument("--dry-run", action="store_true", help="Only show who has player pages")
    parser.add_argument("--all-profiles", action="store_true", help="Scrape all trainers, not just BL")
    args = parser.parse_args()

    if args.tm_id:
        coaches = [{"tm_id": args.tm_id, "name": f"TM:{args.tm_id}", "club": "?"}]
    elif args.all_profiles:
        # All trainers from person_profiles
        coaches = []
        for pf in PROFILES_DIR.glob("*.json"):
            try:
                with open(pf) as f:
                    p = json.load(f)
                if p.get("type") == "trainer":
                    coaches.append({"tm_id": p["tm_id"], "name": p.get("name", "?"), "club": "?"})
            except Exception:
                continue
        print(f"Found {len(coaches)} trainer profiles")
    else:
        coaches = get_bl_coaches()

    print("=" * 60)
    print(f"PLAYING CAREER SCRAPER — {len(coaches)} coaches")
    print("=" * 60)

    results = {"has_player_page": 0, "no_player_page": 0, "errors": 0, "total_stations": 0}

    for i, coach in enumerate(coaches, 1):
        tm_id = coach["tm_id"]
        name = coach["name"]
        club = coach["club"]

        # Check if already scraped
        profile_path = PROFILES_DIR / f"{tm_id}.json"
        if profile_path.exists():
            with open(profile_path) as f:
                existing = json.load(f)
            if existing.get("playing_career") is not None:
                pc = existing["playing_career"]
                if pc:
                    print(f"[{i}/{len(coaches)}] {name} — already has playing_career ({len(pc)} stations)")
                    results["has_player_page"] += 1
                    results["total_stations"] += len(pc)
                else:
                    results["no_player_page"] += 1
                continue

        print(f"[{i}/{len(coaches)}] {name} ({club}) — TM:{tm_id}")

        # Step 1: Find player ID (different from trainer ID on TM!)
        player_id = find_player_id(tm_id)
        if player_id is None:
            print(f"  → Kein Spieler-Link auf Trainer-Seite (kein Profi)")
            if profile_path.exists():
                with open(profile_path) as f:
                    profile = json.load(f)
                profile["playing_career"] = []
                profile["was_player"] = False
                with open(profile_path, "w", encoding="utf-8") as f:
                    json.dump(profile, f, ensure_ascii=False, indent=2)
            results["no_player_page"] += 1
            continue

        print(f"  → Spieler-ID: {player_id} (Trainer-ID: {tm_id})")

        # Step 2: Fetch career-by-club page (single request, all clubs)
        url = f"{TM_BASE}/x/leistungsdatenverein/spieler/{player_id}"
        cache_key = f"spieler_verein_{player_id}"
        html = fetch_page(url, cache_key)

        if not html:
            print(f"  → Keine Spieler-Seite (kein Profi)")
            # Save empty playing_career to avoid re-checking
            if profile_path.exists():
                with open(profile_path) as f:
                    profile = json.load(f)
                profile["playing_career"] = []
                profile["was_player"] = False
                with open(profile_path, "w", encoding="utf-8") as f:
                    json.dump(profile, f, ensure_ascii=False, indent=2)
            results["no_player_page"] += 1
            continue

        if args.dry_run:
            print(f"  → HAT Spieler-Seite")
            results["has_player_page"] += 1
            continue

        # Parse
        soup = BeautifulSoup(html, "html.parser")
        career = parse_playing_career(soup)
        positions = parse_player_positions(soup)

        # Merge into profile
        if profile_path.exists():
            with open(profile_path) as f:
                profile = json.load(f)
        else:
            profile = {"tm_id": tm_id, "name": name, "type": "trainer"}

        profile["playing_career"] = career
        profile["was_player"] = len(career) > 0
        profile["player_tm_id"] = player_id
        if positions:
            profile["player_positions"] = positions

        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)

        total_apps = sum(e.get("appearances", 0) for e in career)
        print(f"  → {len(career)} Clubs, {total_apps} Einsätze")
        if career:
            for e in career[:4]:
                print(f"     {e['club_name']} — {e.get('appearances', 0)} Sp., {e.get('goals', 0)} T.")
            if len(career) > 4:
                print(f"     ... und {len(career) - 4} weitere")

        results["has_player_page"] += 1
        results["total_stations"] += len(career)

    print()
    print("=" * 60)
    print(f"Results:")
    print(f"  Spieler-Seite vorhanden: {results['has_player_page']}")
    print(f"  Kein Profi-Spieler:      {results['no_player_page']}")
    print(f"  Total Karriere-Stationen: {results['total_stations']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
