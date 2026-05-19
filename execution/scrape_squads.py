#!/usr/bin/env python3
"""
Phase 2: Squad & Staff Crawler
Scrapes player squads and coaching staff for all clubs × seasons from the club registry.

Input:  data/club_registry.json
Output: data/squads/{tm_id}_{season}.json  (one file per club-season)
        data/staff/{tm_id}.json            (one file per club — current staff)
        data/persons_index.json            (master index of all discovered persons)

Architecture: Layer 3 (Execution)
Resumable: Skips already-scraped club-seasons. Safe to interrupt and restart.

Strategy:
  - Squad pages (/kader/) → players per season with TM IDs, positions, DOB, nationality, images
  - Mitarbeiter pages → current staff per club (coaches, SDs, scouts, analysts, etc.)
  - Historical coach assignment → handled in Phase 3 via individual coach career histories
"""

import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

# ── Config ──────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
SQUADS_DIR = DATA_DIR / "squads"
STAFF_DIR = DATA_DIR / "staff"
CACHE_DIR = BASE_DIR / "tmp" / "cache" / "squads"

SQUADS_DIR.mkdir(parents=True, exist_ok=True)
STAFF_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

TM_BASE = "https://www.transfermarkt.de"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Cache-Control": "no-cache",
}
REQUEST_DELAY = 3  # seconds between requests


# ── HTTP Fetching ─────────────────────────────────
def fetch_page(url: str, cache_key: str, cache_days: int = 30) -> Optional[str]:
    """Fetch page with HTML caching and rate limiting."""
    cache_path = CACHE_DIR / f"{cache_key}.html"

    # Check cache
    if cache_path.exists():
        age_hours = (datetime.now().timestamp() - cache_path.stat().st_mtime) / 3600
        if age_hours < cache_days * 24:
            return cache_path.read_text(encoding="utf-8")

    time.sleep(REQUEST_DELAY)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        html = resp.text
        cache_path.write_text(html, encoding="utf-8")
        return html
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            print(f"    RATE LIMITED — waiting 60s...")
            time.sleep(60)
            return fetch_page(url, cache_key, cache_days)  # Retry once
        print(f"    ERROR {e.response.status_code}: {url}")
        return None
    except Exception as e:
        print(f"    ERROR fetching {url}: {e}")
        return None


# ── Squad Page Parser ─────────────────────────────
def parse_squad_page(html: str, club_tm_id: int, club_name: str, season: int) -> list[dict]:
    """
    Parse a TM squad page (Kader + Details view).
    URL pattern: /{slug}/kader/verein/{id}/saison_id/{season}/plus/1

    Returns list of player dicts with: tm_id, name, slug, position,
    shirt_number, dob, nationality, image_url
    """
    soup = BeautifulSoup(html, "lxml")
    persons = []
    seen_ids = set()

    # Find the main squad table(s) — class="items" is TM standard
    tables = soup.find_all("table", class_="items")

    for table in tables:
        rows = table.find_all("tr", class_=["odd", "even"])

        for row in rows:
            person = _parse_player_row(row)
            if person and person["tm_id"] not in seen_ids:
                person["club_tm_id"] = club_tm_id
                person["club_name"] = club_name
                person["season"] = season
                person["role"] = "player"
                seen_ids.add(person["tm_id"])
                persons.append(person)

    return persons


def _parse_player_row(row) -> Optional[dict]:
    """Extract player data from a squad table row."""
    # Find player profile link: /player-slug/profil/spieler/12345
    link = row.find("a", href=re.compile(r"/profil/spieler/\d+"))
    if not link:
        return None

    href = link["href"]
    m = re.search(r"/([^/]+)/profil/spieler/(\d+)", href)
    if not m:
        return None

    slug = m.group(1)
    tm_id = int(m.group(2))
    name = link.get("title", "") or link.get_text(strip=True)

    if not name or len(name) < 2:
        return None

    person = {
        "tm_id": tm_id,
        "slug": slug,
        "name": name,
        "tm_url": f"{TM_BASE}/{slug}/profil/spieler/{tm_id}",
    }

    # Profile image — TM uses data-src for lazy loading
    img = row.find("img", {"data-src": re.compile(r"img\.a\.transfermarkt")})
    if not img:
        # Fallback: any img with data-src
        img = row.find("img", {"data-src": True})
    if img:
        src = img.get("data-src") or img.get("src", "")
        if src and "default_avatar" not in src and "/header/" not in src:
            person["image_url"] = src

    # Shirt number
    shirt_cell = row.find("div", class_="rn_nummer")
    if shirt_cell:
        num = shirt_cell.get_text(strip=True)
        if num.isdigit():
            person["shirt_number"] = int(num)

    # Position — look for known position strings in cells
    cells = row.find_all("td")
    for cell in cells:
        text = cell.get_text(strip=True)
        if text in _POSITIONS:
            person["position"] = text
            break

    # Date of birth — pattern dd.mm.yyyy
    for cell in cells:
        text = cell.get_text(strip=True)
        dob_match = re.search(r"(\d{2}\.\d{2}\.\d{4})", text)
        if dob_match:
            person["dob"] = dob_match.group(1)
            age_match = re.search(r"\((\d+)\)", text)
            if age_match:
                person["age"] = int(age_match.group(1))
            break

    # Nationality — from flag images
    flags = row.find_all("img", class_="flaggenrahmen")
    if flags:
        nationalities = []
        for flag in flags:
            nat = flag.get("title", "")
            if nat:
                nationalities.append(nat)
        if nationalities:
            person["nationality"] = ", ".join(nationalities)

    return person


# Known TM positions (German)
_POSITIONS = {
    "Torwart", "Innenverteidiger", "Linker Verteidiger", "Rechter Verteidiger",
    "Defensives Mittelfeld", "Zentrales Mittelfeld", "Offensives Mittelfeld",
    "Linkes Mittelfeld", "Rechtes Mittelfeld", "Linksaußen", "Rechtsaußen",
    "Hängende Spitze", "Mittelstürmer", "Sturm",
    "Abwehr", "Mittelfeld",
}


# ── Staff Page Parser ─────────────────────────────
def parse_staff_page(html: str, club_tm_id: int, club_name: str) -> list[dict]:
    """
    Parse a TM Mitarbeiter page.
    URL pattern: /{slug}/mitarbeiter/verein/{id}

    Shows CURRENT staff organized by sections:
    Trainerstab, Management, Vorstand, Scoutingabteilung, Medizinische Abteilung, etc.

    Returns list of staff dicts with: tm_id, name, slug, role, section, image_url
    """
    soup = BeautifulSoup(html, "lxml")
    persons = []
    seen_ids = set()

    # The page is organized in sections with h2.content-box-headline headers
    sections = soup.find_all("h2", class_="content-box-headline")

    for section_header in sections:
        section_name = section_header.get_text(strip=True)
        role = _section_to_role(section_name)

        # Find the content container after this header
        container = section_header.find_parent("div", class_="box")
        if not container:
            container = section_header.find_next_sibling()
        if not container:
            continue

        # Find all trainer profile links in this section
        for link in container.find_all("a", href=re.compile(r"/profil/trainer/\d+")):
            href = link["href"]
            m = re.search(r"/([^/]+)/profil/trainer/(\d+)", href)
            if not m:
                continue

            slug = m.group(1)
            tm_id = int(m.group(2))
            if tm_id in seen_ids:
                continue
            seen_ids.add(tm_id)

            name = link.get("title", "") or link.get_text(strip=True)
            if not name or len(name) < 2:
                continue

            person = {
                "tm_id": tm_id,
                "slug": slug,
                "name": name,
                "tm_url": f"{TM_BASE}/{slug}/profil/trainer/{tm_id}",
                "club_tm_id": club_tm_id,
                "club_name": club_name,
                "role": role,
                "section": section_name,
            }

            # Image — look in parent container
            parent = link.find_parent("div", class_=re.compile(r"container|mitarbeiter|inline"))
            if not parent:
                parent = link.find_parent("td")
            if parent:
                img = parent.find("img", {"data-src": True})
                if img:
                    src = img.get("data-src", "")
                    if src and "default_avatar" not in src:
                        person["image_url"] = src

            # Try to get sub-role from the text near the link
            # TM shows role labels like "Cheftrainer", "Co-Trainer" near names
            # Structure: <table class="inline-table"><tr><td>Name</td></tr><tr><td>Role</td></tr></table>
            inline_table = link.find_parent("table", class_="inline-table")
            if inline_table:
                text_around = inline_table.get_text(" ", strip=True)
            else:
                parent_text_elem = link.find_parent("td") or link.find_parent("div")
                text_around = parent_text_elem.get_text(strip=True) if parent_text_elem else ""
            if text_around:
                specific_role = _detect_specific_role(text_around)
                if specific_role:
                    person["role"] = specific_role

            persons.append(person)

    return persons


def _section_to_role(section_name: str) -> str:
    """Map Mitarbeiter section header to role taxonomy.

    Bug E fix (2026-05-15): "Management"-Section enthält BÄHE Sport-DMs (Bornemann)
    UND commercial Direktoren (Schreitt "Direktor Marketing und Vertrieb"). Blindes
    Mapping auf sporting_director hatte ~60 commercial Manager als SDs hochgepromoted.
    Lösung: Management/Vorstand fallback auf other_staff — die spezifische Rolle wird
    in _detect_specific_role(title) ermittelt (Sportdirektor/Sportvorstand keywords).
    """
    s = section_name.lower()
    if "trainerstab" in s:
        return "other_staff"  # Will be refined by _detect_specific_role
    elif "management" in s:
        return "other_staff"  # Refined by _detect_specific_role; SD-titles get caught there
    elif "vorstand" in s:
        return "other_staff"
    elif "scout" in s:
        return "scout"
    elif "medizin" in s:
        return "other_staff"
    elif "jugend" in s:
        return "nlz_coach"
    elif "öffentlichkeit" in s or "kommunikation" in s:
        return "other_staff"
    else:
        return "other_staff"


def _detect_specific_role(text: str) -> Optional[str]:
    """Detect specific coach/staff role from surrounding text."""
    t = text.lower()
    # "Interimstrainer" / "Interimstrainerin" / "Interimscheftrainer" → head_coach
    # (These are full head coaches on interim basis — e.g. René Wagner @ Köln,
    # Marie-Louise Eta @ Union. Check BEFORE the \btrainer\b regex because
    # "Interimstrainer" has no word boundary before "trainer".)
    if "interimstrainer" in t or "interimscheftrainer" in t:
        return "head_coach"
    if "cheftrainer" in t or "head coach" in t:
        return "head_coach"
    elif "co-trainer" in t or "assistenztrainer" in t or "assistant" in t:
        # Must check co-trainer BEFORE the generic "trainer" below
        pass  # fall through to return below
    elif re.search(r'\btrainer\b', t) and "co-" not in t and "torwart" not in t and "athletik" not in t and "fitness" not in t and "kondition" not in t and "u19" not in t and "u17" not in t and "jugend" not in t and "nachwuchs" not in t:
        # Plain "Trainer" on TM = Cheftrainer (head coach)
        return "head_coach"
    if "co-trainer" in t or "assistenztrainer" in t or "assistant" in t:
        return "assistant_coach"
    elif "torwarttrainer" in t or "goalkeeper" in t:
        return "goalkeeper_coach"
    elif "athletiktrainer" in t or "fitnesstrainer" in t or "konditionstrainer" in t:
        return "fitness_coach"
    elif "sportdirektor" in t or "sportvorstand" in t or "sporting director" in t:
        return "sporting_director"
    elif "scout" in t or "kaderplaner" in t:
        return "scout"
    elif "analyst" in t or "video" in t:
        return "analyst"
    elif "u19" in t or "u17" in t or "jugend" in t or "nachwuchs" in t:
        return "nlz_coach"
    return None


# ── Persons Index ─────────────────────────────────
def build_persons_index(squads_dir: Path, staff_dir: Path) -> dict:
    """
    Build a master index of all discovered persons across all squad and
    staff files. Merges duplicate TM IDs.

    Returns: {tm_id: {name, slug, tm_url, appearances: [...], image_url}}
    """
    index = {}

    # Process squad files (players)
    for f in sorted(squads_dir.glob("*.json")):
        with open(f) as fh:
            data = json.load(fh)
        for p in data.get("players", []):
            _merge_person(index, p, "player")

    # Process staff files
    for f in sorted(staff_dir.glob("*.json")):
        with open(f) as fh:
            data = json.load(fh)
        for p in data.get("staff", []):
            _merge_person(index, p, p.get("role", "other_staff"))

    return index


def _merge_person(index: dict, person: dict, role: str):
    """Merge a person entry into the index."""
    tm_id = person.get("tm_id")
    if not tm_id:
        return

    if tm_id not in index:
        index[tm_id] = {
            "tm_id": tm_id,
            "name": person.get("name", ""),
            "slug": person.get("slug", ""),
            "tm_url": person.get("tm_url", ""),
            "image_url": person.get("image_url"),
            "nationality": person.get("nationality"),
            "dob": person.get("dob"),
            "appearances": [],
        }

    entry = index[tm_id]

    # Update fields if we got better data
    if person.get("image_url") and not entry.get("image_url"):
        entry["image_url"] = person["image_url"]
    if person.get("nationality") and not entry.get("nationality"):
        entry["nationality"] = person["nationality"]
    if person.get("dob") and not entry.get("dob"):
        entry["dob"] = person["dob"]
    # Prefer longer name (more complete)
    if person.get("name") and len(person["name"]) > len(entry.get("name", "")):
        entry["name"] = person["name"]

    # Add appearance
    appearance = {
        "role": role,
        "club_tm_id": person.get("club_tm_id"),
        "club_name": person.get("club_name"),
        "season": person.get("season"),
    }
    if person.get("position"):
        appearance["position"] = person["position"]
    if person.get("shirt_number"):
        appearance["shirt_number"] = person["shirt_number"]
    if person.get("section"):
        appearance["section"] = person["section"]

    entry["appearances"].append(appearance)


def _refresh_single_club(club_tm_id: int):
    """Force re-scrape staff for a single club (deletes cache + existing file)."""
    registry_path = DATA_DIR / "club_registry.json"
    with open(registry_path) as f:
        registry = json.load(f)

    club = None
    for c in registry["clubs"]:
        if c["tm_id"] == club_tm_id:
            club = c
            break

    if not club:
        print(f"  Club {club_tm_id} not found in registry")
        return

    slug = club["slug"]
    name = club["name"]
    print(f"  Refreshing staff: {name} (ID: {club_tm_id})")

    # Delete cache to force fresh fetch
    cache_path = CACHE_DIR / f"staff_{club_tm_id}.html"
    if cache_path.exists():
        cache_path.unlink()
        print(f"  Cleared cache: {cache_path.name}")

    # Fetch fresh
    html = fetch_page(
        f"{TM_BASE}/{slug}/mitarbeiter/verein/{club_tm_id}",
        f"staff_{club_tm_id}",
        cache_days=0,  # Force fresh
    )

    if not html:
        print(f"  FAILED to fetch staff page")
        return

    staff = parse_staff_page(html, club_tm_id, name)
    staff_path = STAFF_DIR / f"{club_tm_id}.json"
    with open(staff_path, "w", encoding="utf-8") as f:
        json.dump({
            "club_tm_id": club_tm_id,
            "club_name": name,
            "scraped_at": datetime.now().isoformat(),
            "staff_count": len(staff),
            "staff": staff,
        }, f, ensure_ascii=False, indent=2)

    head_coach = staff[0]["name"] if staff else "?"
    print(f"  Done: {len(staff)} staff members. Head coach: {head_coach}")


def _run_staff_only():
    """Run only Part B (staff pages) for all clubs.

    Re-scrapes files older than `--max-age-days` (default 7). Pass `--force`
    to re-scrape everything.
    """
    import sys
    start_from = 0
    limit = None
    max_age_days = 7
    force = False
    for arg in sys.argv[1:]:
        if arg.startswith("--start="):
            start_from = int(arg.split("=")[1])
        elif arg.startswith("--limit="):
            limit = int(arg.split("=")[1])
        elif arg.startswith("--max-age-days="):
            max_age_days = int(arg.split("=")[1])
        elif arg == "--force":
            force = True

    registry_path = DATA_DIR / "club_registry.json"
    with open(registry_path) as f:
        registry = json.load(f)

    clubs = registry["clubs"]
    if limit:
        clubs = clubs[start_from:start_from + limit]
    elif start_from:
        clubs = clubs[start_from:]

    max_age_seconds = max_age_days * 86400
    now = time.time()

    print("=" * 60)
    print(f"STAFF-ONLY MODE: {len(clubs)} clubs")
    print(f"  max-age: {max_age_days}d  force: {force}")
    print("=" * 60)

    done = 0
    skipped = 0
    total_staff = 0
    start_time = time.time()

    for i, club in enumerate(clubs, 1):
        tm_id = club["tm_id"]
        slug = club["slug"]
        staff_path = STAFF_DIR / f"{tm_id}.json"

        if staff_path.exists() and not force:
            age = now - staff_path.stat().st_mtime
            if age < max_age_seconds:
                skipped += 1
                continue

        print(f"  [{i}/{len(clubs)}] {club['name']}...", end=" ", flush=True)
        # Force fresh HTML when `--force` is used or TTL is shorter than default cache
        html_cache_days = 0 if force else min(7, max_age_days)
        html = fetch_page(
            f"{TM_BASE}/{slug}/mitarbeiter/verein/{tm_id}",
            f"staff_{tm_id}",
            cache_days=html_cache_days,
        )
        if html:
            staff = parse_staff_page(html, tm_id, club["name"])
            with open(staff_path, "w", encoding="utf-8") as f:
                json.dump({
                    "club_tm_id": tm_id,
                    "club_name": club["name"],
                    "scraped_at": datetime.now().isoformat(),
                    "staff_count": len(staff),
                    "staff": staff,
                }, f, ensure_ascii=False, indent=2)
            total_staff += len(staff)
            done += 1
            print(f"{len(staff)} staff members")
        else:
            print("FAILED")

    elapsed = time.time() - start_time
    print(f"\nDone in {elapsed/60:.1f} min — scraped: {done}, skipped: {skipped}, staff found: {total_staff}")

    # Rebuild index
    print("\nRebuilding persons index...")
    index = build_persons_index(SQUADS_DIR, STAFF_DIR)
    _save_index(index)


# ── Main Orchestration ────────────────────────────
def main():
    # Parse CLI args
    start_from = 0
    limit = None
    league_filter = None  # e.g. --leagues=POR,SCO,GRE
    for arg in sys.argv[1:]:
        if arg.startswith("--start="):
            start_from = int(arg.split("=")[1])
        elif arg.startswith("--limit="):
            limit = int(arg.split("=")[1])
        elif arg.startswith("--leagues="):
            league_filter = set(arg.split("=")[1].split(","))
        elif arg == "--index-only":
            # Just rebuild the index from existing files
            print("Rebuilding persons index from existing files...")
            index = build_persons_index(SQUADS_DIR, STAFF_DIR)
            _save_index(index)
            return
        elif arg == "--staff-only":
            # Only run Part B (staff pages) for all clubs
            _run_staff_only()
            return
        elif arg.startswith("--club="):
            # Refresh a single club's staff (force re-scrape)
            _refresh_single_club(int(arg.split("=")[1]))
            return

    print("=" * 60)
    print("PHASE 2: Squad & Staff Crawler")
    print("=" * 60)

    # Load club registry
    registry_path = DATA_DIR / "club_registry.json"
    if not registry_path.exists():
        print("ERROR: club_registry.json not found. Run Phase 1 first.")
        return

    with open(registry_path) as f:
        registry = json.load(f)

    clubs = registry["clubs"]

    # Filter by league short codes if specified
    if league_filter:
        filtered = []
        for c in clubs:
            club_leagues = set()
            for leagues_list in c.get("leagues", {}).values():
                for short in leagues_list:
                    club_leagues.add(short)
            if club_leagues & league_filter:
                filtered.append(c)
        clubs = filtered
        print(f"League filter: {', '.join(sorted(league_filter))}")

    if limit:
        clubs = clubs[start_from:start_from + limit]
    elif start_from:
        clubs = clubs[start_from:]

    # Calculate total work
    total_combos = sum(len(c["leagues"]) for c in clubs)
    print(f"Clubs: {len(clubs)} (of {registry['meta']['total_clubs']})")
    print(f"Club-Season combinations: {total_combos}")
    print(f"Estimated time: ~{(total_combos + len(clubs)) * 3 / 60:.0f} min")
    print()

    # Track progress
    stats = {
        "done_squads": 0, "skipped_squads": 0,
        "done_staff": 0, "skipped_staff": 0,
        "total_players": 0, "total_staff": 0,
        "errors": [],
    }

    start_time = time.time()

    # ── Part A: Scrape squad pages ────────────────
    print("─" * 60)
    print("PART A: Squad Pages (Players per Season)")
    print("─" * 60)

    for i, club in enumerate(clubs):
        tm_id = club["tm_id"]
        slug = club["slug"]
        name = club["name"]

        seasons = sorted(club["leagues"].keys())
        pending = []
        for sk in seasons:
            sy = int(sk.split("/")[0])
            output_file = SQUADS_DIR / f"{tm_id}_{sy}.json"
            if output_file.exists():
                stats["skipped_squads"] += 1
            else:
                pending.append((sk, sy))

        if not pending:
            continue

        print(f"\n[{i+1}/{len(clubs)}] {name} (TM:{tm_id}) — {len(pending)}/{len(seasons)} seasons to scrape")

        for season_key, season_year in pending:
            leagues_str = ", ".join(club["leagues"][season_key])
            print(f"  {season_key} ({leagues_str})...", end=" ", flush=True)

            # Fetch squad page (Kader + details)
            url = f"{TM_BASE}/{slug}/kader/verein/{tm_id}/saison_id/{season_year}/plus/1"
            cache_key = f"squad_{tm_id}_{season_year}"
            html = fetch_page(url, cache_key, cache_days=30)

            players = []
            if html:
                players = parse_squad_page(html, tm_id, name, season_year)
                print(f"{len(players)} players")
                stats["total_players"] += len(players)
            else:
                stats["errors"].append(f"squad_{tm_id}_{season_year}")
                print("FAILED")

            # Save squad file
            squad_data = {
                "club_tm_id": tm_id,
                "club_name": name,
                "club_slug": slug,
                "season": season_year,
                "season_display": season_key,
                "leagues": club["leagues"][season_key],
                "scraped_at": datetime.now().isoformat(),
                "player_count": len(players),
                "players": players,
            }

            output_file = SQUADS_DIR / f"{tm_id}_{season_year}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(squad_data, f, ensure_ascii=False, indent=2)

            stats["done_squads"] += 1

    # ── Part B: Staff Pages (Current) ─────────────
    print("\n" + "─" * 60)
    print("PART B: Staff Pages (Current Mitarbeiter)")
    print("─" * 60)

    for i, club in enumerate(clubs):
        tm_id = club["tm_id"]
        slug = club["slug"]
        name = club["name"]

        # Check if already scraped
        output_file = STAFF_DIR / f"{tm_id}.json"
        if output_file.exists():
            stats["skipped_staff"] += 1
            continue

        print(f"  [{i+1}/{len(clubs)}] {name}...", end=" ", flush=True)

        url = f"{TM_BASE}/{slug}/mitarbeiter/verein/{tm_id}"
        cache_key = f"staff_{tm_id}"
        html = fetch_page(url, cache_key, cache_days=7)

        staff = []
        if html:
            staff = parse_staff_page(html, tm_id, name)
            print(f"{len(staff)} staff members")
            stats["total_staff"] += len(staff)
        else:
            stats["errors"].append(f"staff_{tm_id}")
            print("FAILED")

        # Save
        staff_data = {
            "club_tm_id": tm_id,
            "club_name": name,
            "club_slug": slug,
            "scraped_at": datetime.now().isoformat(),
            "staff_count": len(staff),
            "staff": staff,
        }

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(staff_data, f, ensure_ascii=False, indent=2)

        stats["done_staff"] += 1

    # ── Summary ───────────────────────────────────
    elapsed = time.time() - start_time
    _print_summary(stats, elapsed)

    # ── Build persons index ───────────────────────
    print("\n" + "─" * 60)
    print("Building persons index...")
    index = build_persons_index(SQUADS_DIR, STAFF_DIR)
    _save_index(index)


def _save_index(index: dict):
    """Save the persons index and detect career transitions."""
    # Detect career transitions (player who also appears as coach/staff)
    transitions = []
    for tm_id, person in index.items():
        roles = set(a["role"] for a in person["appearances"])
        if "player" in roles and len(roles) > 1:
            non_player_roles = roles - {"player"}
            for new_role in non_player_roles:
                player_seasons = [a["season"] for a in person["appearances"]
                                  if a["role"] == "player" and a.get("season")]
                new_seasons = [a["season"] for a in person["appearances"]
                               if a["role"] == new_role and a.get("season")]
                transitions.append({
                    "tm_id": tm_id,
                    "name": person["name"],
                    "from_role": "player",
                    "to_role": new_role,
                    "last_player_season": max(player_seasons) if player_seasons else None,
                    "first_new_role_season": min(new_seasons) if new_seasons else None,
                })

    # Compute stats
    all_roles = set()
    for p in index.values():
        for a in p["appearances"]:
            all_roles.add(a["role"])

    role_counts = {}
    for role in sorted(all_roles):
        count = sum(1 for p in index.values()
                    if any(a["role"] == role for a in p["appearances"]))
        role_counts[role] = count

    # Save
    index_data = {
        "meta": {
            "generated_at": datetime.now().isoformat(),
            "total_persons": len(index),
            "role_counts": role_counts,
            "career_transitions": len(transitions),
        },
        "persons": {str(k): v for k, v in sorted(index.items())},
        "career_transitions": transitions,
    }

    index_path = DATA_DIR / "persons_index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)

    print(f"\nPersons index: {index_path}")
    print(f"  Total persons: {len(index)}")
    print(f"  Roles: {role_counts}")
    print(f"  Career transitions: {len(transitions)}")

    if transitions:
        print(f"\n  Sample transitions:")
        for t in transitions[:10]:
            print(f"    {t['name']}: {t['from_role']} → {t['to_role']}")


def _print_summary(stats: dict, elapsed: float):
    """Print crawl summary."""
    print("\n" + "=" * 60)
    print("PHASE 2 SUMMARY")
    print("=" * 60)
    print(f"Duration: {elapsed/60:.1f} min")
    print(f"\nSquad pages:")
    print(f"  Scraped: {stats['done_squads']}")
    print(f"  Skipped (cached): {stats['skipped_squads']}")
    print(f"  Players found: {stats['total_players']}")
    print(f"\nStaff pages:")
    print(f"  Scraped: {stats['done_staff']}")
    print(f"  Skipped (cached): {stats['skipped_staff']}")
    print(f"  Staff found: {stats['total_staff']}")
    print(f"\nErrors: {len(stats['errors'])}")
    if stats["errors"]:
        for e in stats["errors"][:10]:
            print(f"  - {e}")


if __name__ == "__main__":
    main()
