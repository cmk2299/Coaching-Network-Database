#!/usr/bin/env python3
"""
Phase 3: Person Profile Scraper
Scrapes individual TM profile pages for all persons in the persons_index.
Extracts: full career history, personal info, license, image, current role.

Architecture: Layer 3 (Execution)

Usage:
  python scrape_person_profiles.py                     # All persons, coaches first
  python scrape_person_profiles.py --coaches-only      # Only /trainer/ URLs
  python scrape_person_profiles.py --players-only      # Only /spieler/ URLs
  python scrape_person_profiles.py --limit=500         # Max 500 profiles
  python scrape_person_profiles.py --merge-only        # Just rebuild master from existing profiles
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
CACHE_DIR = BASE_DIR / "tmp" / "cache" / "profiles"
PROFILES_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

TM_BASE = "https://www.transfermarkt.de"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}
REQUEST_DELAY = 3  # seconds
CACHE_DAYS = 30


# ── Fetch with caching ──────────────────────────────
def fetch_page(url: str, cache_key: str) -> Optional[str]:
    """Fetch page with HTML caching and rate limiting."""
    cache_path = CACHE_DIR / f"{cache_key}.html"

    if cache_path.exists():
        age_hours = (datetime.now().timestamp() - cache_path.stat().st_mtime) / 3600
        if age_hours < CACHE_DAYS * 24:
            return cache_path.read_text(encoding="utf-8")

    time.sleep(REQUEST_DELAY)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        html = resp.text
        cache_path.write_text(html, encoding="utf-8")
        return html
    except Exception as e:
        print(f"    ERROR: {e}")
        return None


# ── Profile Parsing ─────────────────────────────────
def parse_info_table_value(soup: BeautifulSoup, label_text: str) -> Optional[str]:
    """Extract a value from the info-table by its label."""
    target = label_text.lower()

    # Method 1: Paired spans in div.info-table (player profiles)
    # Structure: <span class="info-table__content--regular">Label:</span>
    #            <span class="info-table__content--bold">Value</span>
    for div in soup.find_all("div", class_="info-table"):
        spans = div.find_all("span", class_=lambda c: c and any("info-table__content" in cls for cls in (c if isinstance(c, list) else [c])))
        for i in range(len(spans) - 1):
            label = spans[i].get_text(strip=True).lower()
            if target in label:
                val = spans[i + 1].get_text(strip=True)
                return val if val else None

    # Method 2: Nested in li (coach profiles)
    for span in soup.find_all("span", class_="info-table__content"):
        parent = span.find_parent("li") or span.find_parent("tr")
        if parent:
            label = parent.get_text(strip=True).lower()
            if target in label:
                return span.get_text(strip=True) or None

    # Method 3: data-header__label (some profiles)
    for li in soup.find_all("li", class_="data-header__label"):
        label = li.get_text(strip=True).lower()
        if target in label:
            content = li.find("span", class_="data-header__content")
            if content:
                return content.get_text(strip=True) or None

    # Method 4: Classic table rows
    for row in soup.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) >= 2:
            label = cells[0].get_text(strip=True).lower()
            if target in label:
                val = cells[1].get_text(strip=True)
                return val if val else None
    return None


def parse_nationality(soup: BeautifulSoup) -> list[str]:
    """Extract nationality/nationalities from profile."""
    nationalities = []

    # Method 1: Flag images in info table
    for img in soup.find_all("img", class_="flaggenrahmen"):
        title = img.get("title", "").strip()
        if title and title not in nationalities:
            nationalities.append(title)

    # Method 2: Text-based fallback
    if not nationalities:
        raw = parse_info_table_value(soup, "staatsangeh")
        if raw:
            # Split concatenated nationalities (e.g. "UngarnGriechenland")
            parts = re.findall(r"[A-ZÄÖÜ][a-zäöüß]+", raw)
            nationalities = parts if parts else [raw]

    return nationalities


def parse_dob(soup: BeautifulSoup) -> Optional[str]:
    """Extract date of birth."""
    # Try data-attributes first
    for el in soup.find_all(attrs={"data-date": True}):
        return el["data-date"]  # Usually YYYY-MM-DD

    # Try info table
    raw = parse_info_table_value(soup, "geb")
    if raw:
        # Format: "09.06.1978 (46)" — extract the date part
        m = re.search(r"(\d{2}\.\d{2}\.\d{4})", raw)
        if m:
            # Convert DD.MM.YYYY to YYYY-MM-DD
            d, mo, y = m.group(1).split(".")
            return f"{y}-{mo}-{d}"
    return None


def parse_birthplace(soup: BeautifulSoup) -> Optional[str]:
    """Extract birthplace."""
    return parse_info_table_value(soup, "geburtsort")


def parse_license(soup: BeautifulSoup) -> Optional[str]:
    """Extract coaching license."""
    return parse_info_table_value(soup, "lizenz") or parse_info_table_value(soup, "trainerlizenz")


def parse_contract_until(soup: BeautifulSoup) -> Optional[str]:
    """Extract 'Vertrag bis' / 'Vertrag bis zum' field. Returns raw string like
    'vsl. 30.06.2026' or 'unbekannt'."""
    return (parse_info_table_value(soup, "vertrag bis")
            or parse_info_table_value(soup, "vertragsende"))


def parse_current_club(soup: BeautifulSoup) -> Optional[dict]:
    """Extract current club info."""
    # Look for "Aktueller Verein" or similar
    raw = parse_info_table_value(soup, "aktueller verein")
    if raw and raw != "-" and raw != "Vereinslos":
        return {"name": raw}

    # Try the header area
    for span in soup.find_all("span", class_="data-header__club"):
        link = span.find("a")
        if link:
            name = link.get_text(strip=True)
            href = link.get("href", "")
            m = re.search(r"/verein/(\d+)", href)
            club_id = int(m.group(1)) if m else None
            return {"name": name, "tm_id": club_id}

    return None


def parse_image_url(soup: BeautifulSoup) -> Optional[str]:
    """Extract profile image URL."""
    # Main profile image
    for img in soup.find_all("img", class_="data-header__profile-image"):
        src = img.get("src") or img.get("data-src")
        if src and "default" not in src.lower() and "platzhalter" not in src.lower():
            return src

    # Fallback: any portrait image
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src", "")
        if "portrait" in src and "default" not in src.lower():
            return src

    return None


def parse_career_history(soup: BeautifulSoup, is_coach: bool = False) -> list[dict]:
    """
    Extract career history (Stationen) from profile page.
    Coach rows use class='ausfallzeiten_k', 6 tds: [icon, club+role, from, to, games, pps].
    Player rows use class='odd'/'even' in performance data tables.
    """
    career = []

    if is_coach:
        # Coach Stationen table: class='items' with headers like "Amtsantritt" or "Verein & Funktion"
        # The FIRST items table is often a stats summary; the career table is typically the second.
        table = None
        for candidate in soup.find_all("table", class_="items"):
            headers_text = " ".join(th.get_text(strip=True) for th in candidate.find_all("th"))
            if any(kw in headers_text for kw in ("Amtsantritt", "Verein", "Funktion")):
                table = candidate
                break
        # Fallback: if no header match, take second items table (first is stats)
        if table is None:
            items_tables = soup.find_all("table", class_="items")
            if len(items_tables) >= 2:
                table = items_tables[1]
            elif items_tables:
                table = items_tables[0]
        if table:
            for row in table.find_all("tr"):
                if not row.find("td"):
                    continue  # skip header
                entry = _parse_coach_career_row(row)
                if entry:
                    career.append(entry)
    else:
        # Player career: performance data table (class='items')
        tables = soup.find_all("table", class_="items")
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                if not row.find("td"):
                    continue
                entry = _parse_player_career_row(row)
                if entry:
                    career.append(entry)
            if career:
                break

    return career


def _parse_coach_career_row(row) -> Optional[dict]:
    """Parse a coach career row. Structure: td[0]=icon, td[1]=Club+Role, td[2]=from, td[3]=to, td[4]=games, td[5]=pps."""
    try:
        cells = row.find_all("td")
        if len(cells) < 4:
            return None

        entry = {}

        # Club from link in td[0] or td[1]
        club_link = row.find("a", href=re.compile(r"/verein/\d+"))
        if club_link:
            href = club_link["href"]
            m = re.search(r"/verein/(\d+)", href)
            if m:
                entry["club_tm_id"] = int(m.group(1))
            # Club name: get from link title or slug
            slug_m = re.search(r"/([^/]+)/startseite/verein/", href)
            if slug_m:
                entry["club_slug"] = slug_m.group(1)

        # td[1] contains club name + role concatenated
        if len(cells) > 1:
            cell1 = cells[1]
            # Club name is usually in a link, role is loose text
            links = cell1.find_all("a")
            link_texts = [a.get_text(strip=True) for a in links]
            full_text = cell1.get_text(strip=True)

            if link_texts:
                entry["club_name"] = link_texts[0]
                # Role is the remaining text after removing club name
                role = full_text
                for lt in link_texts:
                    role = role.replace(lt, "", 1)
                role = role.strip()
                if role:
                    entry["role"] = role

        # td[2] = date from, td[3] = date to
        if len(cells) > 2:
            entry["date_from"] = cells[2].get_text(strip=True)
        if len(cells) > 3:
            entry["date_to"] = cells[3].get_text(strip=True)

        # td[4] = games (may contain link)
        if len(cells) > 4:
            games_text = cells[4].get_text(strip=True)
            if games_text and games_text != "-":
                try:
                    entry["games"] = int(games_text)
                except ValueError:
                    pass

        # td[5] = points per game
        if len(cells) > 5:
            pps_text = cells[5].get_text(strip=True)
            if pps_text and pps_text != "-":
                try:
                    entry["pps"] = float(pps_text.replace(",", "."))
                except ValueError:
                    pass

        return entry if entry.get("club_name") else None
    except Exception:
        return None


def _parse_player_career_row(row) -> Optional[dict]:
    """Parse a player career/performance row."""
    try:
        cells = row.find_all("td")
        if len(cells) < 3:
            return None

        entry = {}

        # Season from first cell
        if cells:
            season_text = cells[0].get_text(strip=True)
            if re.match(r"\d{2}/\d{2}", season_text):
                entry["season"] = season_text

        # Club from link
        club_link = row.find("a", href=re.compile(r"/verein/\d+"))
        if club_link:
            entry["club_name"] = club_link.get("title") or club_link.get_text(strip=True)
            m = re.search(r"/verein/(\d+)", club_link["href"])
            if m:
                entry["club_tm_id"] = int(m.group(1))

        # Competition from link
        comp_link = row.find("a", href=re.compile(r"/wettbewerb/"))
        if comp_link:
            entry["competition"] = comp_link.get("title") or comp_link.get_text(strip=True)

        # Appearances and goals from numeric cells (skip first few non-numeric)
        numbers = []
        for cell in cells[3:]:  # Skip season, club, competition columns
            text = cell.get_text(strip=True)
            if text == "-":
                numbers.append(0)
            elif text.isdigit():
                numbers.append(int(text))

        if len(numbers) >= 1:
            entry["appearances"] = numbers[0]
        if len(numbers) >= 2:
            entry["goals"] = numbers[1]

        return entry if entry.get("club_name") else None
    except Exception:
        return None


def parse_profile(html: str, tm_id: int, person_type: str) -> dict:
    """Parse a full TM profile page into structured data."""
    soup = BeautifulSoup(html, "html.parser")
    is_coach = person_type == "trainer"

    # Extract name — prefer <title> tag (properly spaced) over h1 (often concatenated)
    name = None

    # Primary: <title> tag has format "Jürgen Klopp - Trainerprofil | Transfermarkt"
    title_tag = soup.find("title")
    if title_tag:
        title_text = title_tag.get_text(strip=True)
        # Split on " - " or " | " to get just the name part
        name_part = title_text.split(" - ")[0].split(" | ")[0].strip()
        if name_part and len(name_part) > 1 and name_part.lower() != "transfermarkt":
            name = name_part

    # Fallback: h1 header (may concatenate first+last without space)
    if not name:
        header = soup.find("h1", class_="data-header__headline-wrapper")
        if header:
            for span in header.find_all("span", class_="data-header__shirt-number"):
                span.decompose()
            raw_name = header.get_text(strip=True)
            # Try to fix concatenation: insert space before uppercase that follows lowercase
            if raw_name and not " " in raw_name:
                raw_name = re.sub(r"([a-zäöüß])([A-ZÄÖÜ])", r"\1 \2", raw_name)
            name = raw_name

    profile = {
        "tm_id": tm_id,
        "name": name,
        "type": person_type,
        "nationality": parse_nationality(soup),
        "dob": parse_dob(soup),
        "birthplace": parse_birthplace(soup),
        "image_url": parse_image_url(soup),
        "current_club": parse_current_club(soup),
        "career_history": parse_career_history(soup, is_coach=is_coach),
        "scraped_at": datetime.now().isoformat(),
    }

    # Contract data (both trainer + spieler profiles can have "Vertrag bis")
    profile["contract_until"] = parse_contract_until(soup)

    # Coach-specific fields
    if is_coach:
        profile["license"] = parse_license(soup)

    # Player-specific: position, foot, height, agent
    if not is_coach:
        profile["position"] = parse_info_table_value(soup, "position")
        profile["foot"] = parse_info_table_value(soup, "fuß")
        height_raw = parse_info_table_value(soup, "größe")
        if height_raw:
            m = re.search(r"(\d+)", height_raw.replace(",", ""))
            profile["height_cm"] = int(m.group(1)) if m else None
        profile["agent"] = parse_info_table_value(soup, "spielerberater")

    return profile


# ── Batch Processing ────────────────────────────────
def load_persons_index() -> dict:
    """Load the persons index from Phase 2."""
    idx_path = DATA_DIR / "persons_index.json"
    with open(idx_path) as f:
        return json.load(f)


def get_profile_path(tm_id: int) -> Path:
    """Get the output path for a person's profile."""
    return PROFILES_DIR / f"{tm_id}.json"


def build_priority_queue(persons: dict, coaches_only: bool = False,
                          players_only: bool = False) -> list[tuple]:
    """
    Build a prioritized list of (tm_id, url, type) tuples.
    Priority: coaches first, then multi-season players, then rest.
    """
    coaches = []
    players_multi = []
    players_single = []

    for pid, person in persons.items():
        tm_id = person["tm_id"]
        url = person.get("tm_url", "")

        # Skip if already scraped
        if get_profile_path(tm_id).exists():
            continue

        if "/trainer/" in url:
            if not players_only:
                coaches.append((tm_id, url, "trainer"))
        elif "/spieler/" in url:
            if not coaches_only:
                # Count seasons
                seasons = set()
                for app in person.get("appearances", []):
                    if app.get("season"):
                        seasons.add(app["season"])
                if len(seasons) >= 3:
                    players_multi.append((tm_id, url, "spieler"))
                else:
                    players_single.append((tm_id, url, "spieler"))

    # Priority order
    queue = coaches + players_multi + players_single
    return queue


def main():
    # Parse CLI args
    coaches_only = False
    players_only = False
    limit = None
    merge_only = False
    single_tm_id = None
    single_type = "trainer"  # default to coach

    for arg in sys.argv[1:]:
        if arg == "--coaches-only":
            coaches_only = True
        elif arg == "--players-only":
            players_only = True
        elif arg.startswith("--limit="):
            limit = int(arg.split("=")[1])
        elif arg == "--merge-only":
            merge_only = True
        elif arg.startswith("--tm-id=") or arg == "--tm-id":
            if "=" in arg:
                single_tm_id = int(arg.split("=")[1])
            else:
                # Next arg is the ID
                idx_pos = sys.argv.index(arg)
                if idx_pos + 1 < len(sys.argv):
                    single_tm_id = int(sys.argv[idx_pos + 1])
        elif arg.startswith("--type="):
            single_type = arg.split("=")[1]

    if merge_only:
        print("Rebuilding master from existing profiles...")
        build_master_file()
        return

    # Single profile mode
    if single_tm_id is not None:
        print(f"Scraping single profile: TM:{single_tm_id} ({single_type})")
        url = f"{TM_BASE}/x/profil/{single_type}/{single_tm_id}"
        cache_key = f"{single_type}_{single_tm_id}"
        html = fetch_page(url, cache_key)
        if not html:
            print("  FAILED to fetch page")
            return
        profile = parse_profile(html, single_tm_id, single_type)
        profile_path = get_profile_path(single_tm_id)
        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)
        career_count = len(profile.get("career_history", []))
        print(f"  ✓ {profile.get('name', '?')} — {career_count} stations")
        print(f"  Saved: {profile_path}")
        return

    # Load persons index
    idx = load_persons_index()
    persons = idx["persons"]

    print("=" * 60)
    print("PHASE 3: Person Profile Scraper")
    print(f"Total persons in index: {len(persons):,}")
    print("=" * 60)

    # Build queue
    queue = build_priority_queue(persons, coaches_only, players_only)
    already_scraped = sum(1 for p in persons.values()
                         if get_profile_path(p["tm_id"]).exists())

    print(f"Already scraped: {already_scraped:,}")
    print(f"Queue size: {len(queue):,}")

    if limit:
        queue = queue[:limit]
        print(f"Limited to: {limit}")

    if not queue:
        print("Nothing to scrape!")
        build_master_file()
        return

    type_counts = {"trainer": 0, "spieler": 0}
    for _, _, t in queue:
        type_counts[t] += 1
    print(f"  Coaches: {type_counts['trainer']:,}")
    print(f"  Players: {type_counts['spieler']:,}")
    est_minutes = len(queue) * REQUEST_DELAY / 60
    print(f"Estimated time: ~{est_minutes:.0f} min")
    print()

    # Scrape
    stats = {"scraped": 0, "failed": 0, "skipped": 0}
    start_time = time.time()

    for i, (tm_id, url, person_type) in enumerate(queue, 1):
        profile_path = get_profile_path(tm_id)

        # Double-check (race condition safety)
        if profile_path.exists():
            stats["skipped"] += 1
            continue

        # Determine profile URL
        # Convert to profil page if needed
        if "/profil/" not in url:
            # Build profile URL from known pattern
            url = f"{TM_BASE}/x/profil/{person_type}/{tm_id}"

        cache_key = f"{person_type}_{tm_id}"
        elapsed = time.time() - start_time
        rate = stats["scraped"] / max(elapsed / 60, 0.1)

        print(f"  [{i}/{len(queue)}] TM:{tm_id} ({person_type})...", end=" ", flush=True)

        html = fetch_page(url, cache_key)
        if not html:
            stats["failed"] += 1
            print("FAILED")
            continue

        profile = parse_profile(html, tm_id, person_type)

        # Save individual profile
        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)

        career_count = len(profile.get("career_history", []))
        print(f"{profile.get('name', '?')} — {career_count} stations")

        stats["scraped"] += 1

        # Progress update every 50
        if stats["scraped"] % 50 == 0:
            elapsed = time.time() - start_time
            rate = stats["scraped"] / (elapsed / 60)
            remaining = (len(queue) - i) / max(rate, 0.1)
            print(f"\n    Progress: {stats['scraped']}/{len(queue)} "
                  f"({rate:.1f}/min, ~{remaining:.0f} min remaining)\n")

    # Final stats
    elapsed = time.time() - start_time
    print()
    print("=" * 60)
    print(f"PHASE 3 BATCH COMPLETE")
    print(f"Duration: {elapsed/60:.1f} min")
    print(f"Scraped: {stats['scraped']}")
    print(f"Failed: {stats['failed']}")
    print(f"Skipped: {stats['skipped']}")

    total_profiles = len(list(PROFILES_DIR.glob("*.json")))
    print(f"Total profiles on disk: {total_profiles:,}")
    print("=" * 60)

    # Build master file
    build_master_file()


def build_master_file():
    """Merge all individual profiles + persons_index into a single master file."""
    print("\nBuilding master persons file...")

    idx = load_persons_index()
    persons = idx["persons"]

    # Load all profile files
    profile_files = list(PROFILES_DIR.glob("*.json"))
    profiles_loaded = 0

    master = {}

    for pid, person in persons.items():
        tm_id = person["tm_id"]
        entry = {
            "tm_id": tm_id,
            "name": person.get("name"),
            "tm_url": person.get("tm_url"),
            "image_url": person.get("image_url"),
            "nationality": person.get("nationality"),
            "dob": person.get("dob"),
            "appearances_in_db": person.get("appearances", []),
        }

        # Merge profile data if available
        profile_path = get_profile_path(tm_id)
        if profile_path.exists():
            try:
                profile = json.load(open(profile_path))
                # Profile data overrides index data (more complete)
                entry["name"] = profile.get("name") or entry["name"]
                entry["nationality"] = profile.get("nationality") or entry.get("nationality")
                entry["dob"] = profile.get("dob") or entry.get("dob")
                entry["image_url"] = profile.get("image_url") or entry.get("image_url")
                entry["birthplace"] = profile.get("birthplace")
                entry["current_club"] = profile.get("current_club")
                entry["career_history"] = profile.get("career_history", [])
                entry["type"] = profile.get("type")
                entry["license"] = profile.get("license")
                entry["position"] = profile.get("position")
                entry["foot"] = profile.get("foot")
                entry["height_cm"] = profile.get("height_cm")
                entry["agent"] = profile.get("agent")
                entry["contract_until"] = profile.get("contract_until")
                entry["profile_scraped"] = True
                profiles_loaded += 1
            except Exception as e:
                entry["profile_scraped"] = False
        else:
            entry["profile_scraped"] = False

        master[str(tm_id)] = entry

    # Save master
    output = {
        "meta": {
            "generated_at": datetime.now().isoformat(),
            "total_persons": len(master),
            "profiles_scraped": profiles_loaded,
            "profiles_missing": len(master) - profiles_loaded,
        },
        "persons": master,
    }

    master_path = DATA_DIR / "persons_master.json"
    with open(master_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    size_mb = master_path.stat().st_size / 1024 / 1024
    print(f"Master file: {master_path}")
    print(f"  Total persons: {len(master):,}")
    print(f"  With profiles: {profiles_loaded:,}")
    print(f"  Without profiles: {len(master) - profiles_loaded:,}")
    print(f"  File size: {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
