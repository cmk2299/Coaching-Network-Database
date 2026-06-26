#!/usr/bin/env python3
"""
Identify historical BL coaches not currently in the dashboard.
Scans persons_master.json and categorizes coaches by their BL experience.

Output: data/historical_coaches_candidates.json

Categories:
  A: Letzte BL-Station seit 2020, kein aktives Dashboard → "Ehemaliger BL-Cheftrainer"
  B: Aktuell vereinslos, hat BL-Erfahrung → "Vereinslos"
  C: Aktuell Co-Trainer/Assistent bei BL-Verein → "Co-Trainer"
  D: BL-Erfahrung vor 2020 → "Historisch"
"""

import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Set, Tuple

BASE = Path(__file__).parent.parent
DATA_DIR = BASE / "data"


def slugify(name: str) -> str:
    """Convert name to URL-safe slug."""
    return re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')


def load_club_registry() -> Dict[int, dict]:
    """Load club registry and build BL TM ID set."""
    with open(DATA_DIR / "club_registry.json", "r") as f:
        registry = json.load(f)

    # Build set of all club TM IDs that have ever been in BL1 only
    bl_club_ids = set()
    for club in registry["clubs"]:
        leagues = club.get("league_set", [])
        # Also check season-based leagues dict
        if not leagues:
            leagues = set()
            for codes in club.get("leagues", {}).values():
                leagues.update(codes)
        if "BL1" in leagues:
            bl_club_ids.add(club["tm_id"])

    return bl_club_ids, registry["clubs"]


def load_persons_master() -> Dict[int, dict]:
    """Load persons_master.json."""
    with open(DATA_DIR / "persons_master.json", "r") as f:
        data = json.load(f)
    return data["persons"]


def load_active_coaches() -> Set[int]:
    """Load TM IDs of coaches with existing network dashboards."""
    network_dir = DATA_DIR / "networks"
    if not network_dir.exists():
        return set()

    active = set()
    for network_file in network_dir.glob("*.json"):
        try:
            tm_id = int(network_file.stem)
            active.add(tm_id)
        except ValueError:
            pass

    return active


def extract_season_year(season_str: str) -> int:
    """Extract year from season string like '23/24' or '2023/2024'."""
    try:
        # Handle "23/24" format
        if '/' in season_str:
            parts = season_str.split('/')
            if len(parts[0]) == 2:
                # "23/24" → 2023
                year = 2000 + int(parts[0])
            else:
                # "2023/2024" → 2023
                year = int(parts[0])
            return year
        # Handle plain year like "2023"
        return int(season_str[:4])
    except (ValueError, IndexError):
        return 0


def is_head_coach_role(role: str) -> bool:
    """Check if role is a head coach (Cheftrainer) role.

    Must match: Trainer, Cheftrainer, Interimstrainer, Spielertrainer, Nachwuchs-Cheftrainer
    Must NOT match: Co-Trainer, Torwarttrainer, Athletiktrainer, Fitnesstrainer,
                    Individualtrainer, Konditionstrainer, Mentaltrainer, Präventivtrainer,
                    Rehatrainer, Stürmertrainer, Techniktrainer, Verbindungstrainer,
                    Jugendtrainer, Trainer-Auszubildender
    """
    role_lower = role.lower().strip()

    # Exact matches for head coach roles
    HEAD_COACH_EXACT = {
        "trainer", "cheftrainer", "interimstrainer", "spielertrainer",
        "nachwuchs-cheftrainer", "chef-trainer", "head coach",
    }
    if role_lower in HEAD_COACH_EXACT:
        return True

    return False


def is_youth_or_reserve_club(club_name: str) -> bool:
    """Check if club name indicates a youth/reserve/academy team."""
    if not club_name:
        return False
    name = club_name.lower()
    # U17, U19, U21, U23, II, B, Jugend, Youth League, Reserve, Academy
    youth_markers = [
        ' u17', ' u19', ' u21', ' u23', ' ii', ' b ',
        'jugend', 'jgd.', 'youth', 'reserve', 'academy',
        'nachwuchs', ' yl', 'youth league',
    ]
    return any(m in name or name.endswith(m.strip()) for m in youth_markers)


def parse_career_date(date_str: str) -> int:
    """Parse date from career_history like '23/24 (19.03.2024)' into season start year.
    Handles both '23/24' → 2023 and '99/00' → 1999 correctly."""
    match = re.match(r'(\d{2})/(\d{2})', date_str)
    if match:
        yy = int(match.group(1))
        # 80-99 → 1980-1999, 00-79 → 2000-2079
        return (1900 + yy) if yy >= 80 else (2000 + yy)
    # Try extracting year from parenthetical date like "(19.03.2024)"
    match2 = re.search(r'\((\d{2})\.(\d{2})\.(\d{4})\)', date_str)
    if match2:
        return int(match2.group(3))
    return 0


def analyze_coach(tm_id: int, person: Dict, bl_club_ids: Set[int],
                  active_coaches: Set[int]) -> Tuple[str, Dict]:
    """
    Analyze a coach and categorize them.

    Returns: (category, coach_data)
    category: None if not a BL coach, else "A", "B", "C", or "D"
    """
    # Must have type trainer/coach
    if person.get("type") not in ["trainer", "coach"]:
        return None, {}

    # Already has active dashboard
    if tm_id in active_coaches:
        return None, {}

    career_history = person.get("career_history", [])
    if not career_history:
        return None, {}

    # Scan career for BL head coach roles
    bl_stations = []
    for entry in career_history:
        club_tm_id = entry.get("club_tm_id")
        role = entry.get("role", "")

        # Check if this is a BL club AND a head coach role (not youth/reserve)
        club_name = entry.get("club_name", "")
        if (club_tm_id in bl_club_ids and
                is_head_coach_role(role) and
                not is_youth_or_reserve_club(club_name)):
            season_year = parse_career_date(entry.get("date_from", ""))
            if season_year:
                bl_stations.append({
                    "club": entry.get("club_name", ""),
                    "club_tm_id": club_tm_id,
                    "role": role,
                    "year": season_year,
                    "date_from": entry.get("date_from", ""),
                    "date_to": entry.get("date_to", "-"),
                })

    if not bl_stations:
        return None, {}

    # Sort by year descending to get most recent
    bl_stations.sort(key=lambda x: -x["year"])
    last_bl_station = bl_stations[0]

    # Determine category based on recency and current status
    current_club = person.get("current_club")
    current_status = "unbekannt"

    # Check if recently worked at BL club (last 2 entries in history)
    is_recent_bl_coach = False
    if len(career_history) > 0:
        # Check the most recent few entries for BL work
        recent_entries = career_history[:3]
        for entry in recent_entries:
            entry_club_id = entry.get("club_tm_id")
            entry_role = entry.get("role", "")
            if (entry_club_id in bl_club_ids and
                is_head_coach_role(entry_role)):
                is_recent_bl_coach = True
                break

    # Category B: vereinslos (no current club or "-")
    if not current_club or (isinstance(current_club, dict) and not current_club.get("tm_id")):
        category = "B"
        current_status = "vereinslos"
    # Category A: Letzte BL-Station seit 2020, aber nicht aktuelle Position
    elif last_bl_station["year"] >= 2020 and not is_recent_bl_coach:
        category = "A"
        if isinstance(current_club, dict):
            current_status = f"angestellt_at_{current_club.get('name', 'Unknown')}"
        else:
            current_status = f"angestellt_at_{current_club}"
    # Category C: Scheint aktuell aktiv bei BL-Verein (aber nicht als Cheftrainer mit Dashboard)
    elif isinstance(current_club, dict) and current_club.get("tm_id") in bl_club_ids:
        category = "C"
        current_status = "co_trainer_bl"
    # Category D: Historisch (vor 2020)
    else:
        category = "D"
        if isinstance(current_club, dict):
            current_status = f"angestellt_at_{current_club.get('name', 'Unknown')}"
        else:
            current_status = f"angestellt_at_{current_club}"

    coach_data = {
        "tm_id": tm_id,
        "name": person.get("name", ""),
        "category": category,
        "last_bl_club": last_bl_station["club"],
        "last_bl_club_tm_id": last_bl_station["club_tm_id"],
        "last_bl_season": last_bl_station["date_from"].split()[0] if last_bl_station["date_from"] else "?",
        "last_bl_year": last_bl_station["year"],
        "current_status": current_status,
        "current_club": current_club.get("name") if isinstance(current_club, dict) else str(current_club),
        "bl_stations_total": len(bl_stations),
        "bl_stations": [
            {
                "club": s["club"],
                "season": s["date_from"].split()[0] if s["date_from"] else "?",
                "year": s["year"]
            }
            for s in bl_stations
        ],
        "slug": slugify(person.get("name", "")),
        "tm_url": person.get("tm_url", ""),
        "nationality": person.get("nationality", ""),
        "image_url": person.get("image_url", ""),
    }

    return category, coach_data


def main():
    print("Loading club registry...")
    bl_club_ids, all_clubs = load_club_registry()
    print(f"  Found {len(bl_club_ids)} clubs with BL1/BL2/BL3 history")

    print("\nLoading persons_master.json...")
    persons = load_persons_master()
    print(f"  Found {len(persons)} persons")

    print("\nLoading active coaches...")
    active_coaches = load_active_coaches()
    print(f"  Found {len(active_coaches)} active coaches with dashboards")

    print("\nAnalyzing coaches...")
    coaches_by_category = {"A": [], "B": [], "C": [], "D": []}

    processed = 0
    for tm_id, person in persons.items():
        category, coach_data = analyze_coach(
            int(tm_id), person, bl_club_ids, active_coaches
        )

        if category:
            coaches_by_category[category].append(coach_data)
            processed += 1

        if processed % 5000 == 0 and processed > 0:
            print(f"  Processed {processed} coaches so far...")

    # Sort each category
    for category in coaches_by_category:
        coaches_by_category[category].sort(
            key=lambda x: -x["last_bl_year"]
        )

    # Build output
    output = {
        "generated": datetime.now().isoformat(),
        "total": sum(len(v) for v in coaches_by_category.values()),
        "categories": {
            cat: len(coaches) for cat, coaches in coaches_by_category.items()
        },
        "category_labels": {
            "A": "Ehemaliger BL-Cheftrainer",
            "B": "Vereinslos",
            "C": "Co-Trainer bei BL-Verein",
            "D": "Historischer BL-Trainer",
        },
        "coaches": [],
    }

    # Add coaches in order
    for category in ["A", "B", "C", "D"]:
        output["coaches"].extend(coaches_by_category[category])

    # Save output
    output_path = DATA_DIR / "historical_coaches_candidates.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print("\n✓ Analysis complete!")
    print(f"  Total historical coaches: {output['total']}")
    for cat in ["A", "B", "C", "D"]:
        label = output["category_labels"][cat]
        count = output["categories"][cat]
        print(f"    {cat}: {count} ({label})")

    print(f"\n✓ Output saved to: {output_path}")


if __name__ == "__main__":
    main()
