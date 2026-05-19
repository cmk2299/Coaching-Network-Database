#!/usr/bin/env python3
"""
Coverage Gap Analysis — Phase 1 of Systematic Expansion

Scans all 34,513 person profiles, extracts every club_tm_id from career histories,
and compares against the club registry to find gaps.

Output:
  - Console report with top missing clubs/leagues
  - data/coverage_gaps.json with full structured results

Usage:
    python execution/analyze_coverage_gaps.py                    # Full analysis
    python execution/analyze_coverage_gaps.py --bl-coaches-only  # Only BL coach networks
    python execution/analyze_coverage_gaps.py --min-refs 5       # Filter low-reference clubs
    python execution/analyze_coverage_gaps.py --top 100          # Show top N missing clubs
"""

import argparse
import json
import re
import time
from pathlib import Path
from collections import defaultdict, Counter
from typing import Dict, Set, List, Tuple, Optional

# ── Paths ──────────────────────────────────────────────────────────────
BASE = Path(__file__).parent.parent
DATA = BASE / "data"
PROFILES_DIR = DATA / "person_profiles"
STAFF_DIR = DATA / "staff"
SQUADS_DIR = DATA / "squads"
CLUB_REGISTRY = DATA / "club_registry.json"
OUTPUT_FILE = DATA / "coverage_gaps.json"

# ── Youth/Reserve detection patterns ───────────────────────────────────
YOUTH_RESERVE_PATTERNS = [
    r"\bU\d{2}\b",          # U19, U17, U16, U15, U14
    r"\bU-\d{2}\b",         # U-19
    r"\bII\b",              # Reserve team
    r"\bIII\b",             # Third team
    r"\bJgd\.",             # Jugend abbreviation
    r"\bJugend\b",          # Jugend
    r"\bB-Junioren\b",
    r"\bA-Junioren\b",
    r"\bC-Junioren\b",
    r"\bJunior",
    r"\bYouth\b",
    r"\bReserve\b",
    r"\bAmateur",
]
_youth_re = re.compile("|".join(YOUTH_RESERVE_PATTERNS), re.IGNORECASE)


def is_youth_or_reserve(club_name: str) -> bool:
    """Check if a club name indicates a youth or reserve team."""
    return bool(_youth_re.search(club_name or ""))


# ── Known country indicators in club names ─────────────────────────────
# TM sometimes includes country in career data. These help classify.
COUNTRY_HINTS = {
    "england": "ENG", "vereinigtes königreich": "ENG",
    "spanien": "ESP", "spain": "ESP",
    "italien": "ITA", "italy": "ITA",
    "frankreich": "FRA", "france": "FRA",
    "niederlande": "NED", "netherlands": "NED", "holland": "NED",
    "belgien": "BEL", "belgium": "BEL",
    "türkei": "TUR", "turkey": "TUR", "türkiye": "TUR",
    "schweiz": "SUI", "switzerland": "SUI",
    "österreich": "AUT", "austria": "AUT",
    "dänemark": "DEN", "denmark": "DEN",
    "portugal": "POR",
    "griechenland": "GRE", "greece": "GRE",
    "schottland": "SCO", "scotland": "SCO",
    "russland": "RUS", "russia": "RUS",
    "ukraine": "UKR",
    "polen": "POL", "poland": "POL",
    "tschechien": "CZE", "czech": "CZE",
    "kroatien": "CRO", "croatia": "CRO",
    "serbien": "SRB", "serbia": "SRB",
    "ungarn": "HUN", "hungary": "HUN",
    "rumänien": "ROU", "romania": "ROU",
    "schweden": "SWE", "sweden": "SWE",
    "norwegen": "NOR", "norway": "NOR",
    "israel": "ISR",
    "usa": "USA", "vereinigte staaten": "USA",
    "china": "CHN",
    "japan": "JPN",
    "südkorea": "KOR",
    "brasilien": "BRA", "brazil": "BRA",
    "argentinien": "ARG", "argentina": "ARG",
    "mexiko": "MEX",
    "saudi-arabien": "KSA",
    "katar": "QAT", "qatar": "QAT",
    "deutschland": "GER", "germany": "GER",
}


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_club_registry() -> Dict[int, dict]:
    """Load club registry and return {tm_id: club_dict}."""
    data = load_json(CLUB_REGISTRY)
    clubs_raw = data.get("clubs", [])
    if isinstance(clubs_raw, list):
        return {int(c["tm_id"]): c for c in clubs_raw}
    return {int(k): v for k, v in clubs_raw.items()}


def load_all_profiles() -> Dict[int, dict]:
    """Load all person profiles from individual JSON files."""
    print(f"  Loading profiles from {PROFILES_DIR}...")
    t0 = time.time()
    profiles = {}
    for pf in sorted(PROFILES_DIR.glob("*.json")):
        try:
            tm_id = int(pf.stem)
            profiles[tm_id] = load_json(pf)
        except (ValueError, json.JSONDecodeError):
            continue
    print(f"  ✓ {len(profiles):,} profiles loaded in {time.time()-t0:.1f}s")
    return profiles


def get_bl_head_coaches(registry: Dict[int, dict], season: int = 2025) -> Set[int]:
    """Get tm_ids of current BL1+BL2 head coaches from staff files."""
    coaches = set()
    for club_id, club in registry.items():
        # Check if club is in BL1 or BL2 for given season
        season_key = f"{season}/{season+1}"
        leagues = club.get("leagues", {}).get(season_key, [])
        if not any(l in ["BL1", "BL2"] for l in leagues):
            continue

        # Load staff file and get head coach
        staff_path = STAFF_DIR / f"{club_id}.json"
        if not staff_path.exists():
            continue
        staff = load_json(staff_path)
        trainerstab = [s for s in staff.get("staff", []) if s.get("section") == "Trainerstab"]
        if trainerstab:
            coaches.add(trainerstab[0].get("tm_id"))

    return coaches


def extract_career_clubs(profiles: Dict[int, dict],
                          filter_ids: Optional[Set[int]] = None
                          ) -> Tuple[Dict[int, dict], Dict[int, Set[int]]]:
    """
    Extract all unique clubs from career histories.

    Returns:
        club_info: {club_tm_id: {"name": str, "names_seen": set, "person_count": int, ...}}
        person_clubs: {person_tm_id: {club_tm_id, ...}} — which persons reference which clubs
    """
    club_info = defaultdict(lambda: {
        "names_seen": set(),
        "person_count": 0,
        "person_ids": set(),
        "roles_seen": set(),
        "seasons_seen": set(),
    })
    person_clubs = defaultdict(set)

    for tm_id, profile in profiles.items():
        if filter_ids and tm_id not in filter_ids:
            continue

        for entry in profile.get("career_history", []):
            club_id = entry.get("club_tm_id")
            if not club_id:
                continue

            club_name = entry.get("club_name", entry.get("club", "Unknown"))
            role = entry.get("role", "")
            date_from = entry.get("date_from", "")

            club_info[club_id]["names_seen"].add(club_name)
            club_info[club_id]["person_count"] += 1  # Will deduplicate later
            club_info[club_id]["person_ids"].add(tm_id)
            if role:
                club_info[club_id]["roles_seen"].add(role)
            if date_from:
                # Extract season year
                m = re.match(r"(\d{2})/(\d{2})", date_from)
                if m:
                    yy = int(m.group(1))
                    club_info[club_id]["seasons_seen"].add(2000 + yy if yy < 80 else 1900 + yy)

            person_clubs[tm_id].add(club_id)

    # Deduplicate person_count
    for club_id in club_info:
        club_info[club_id]["person_count"] = len(club_info[club_id]["person_ids"])

    return dict(club_info), dict(person_clubs)


def classify_club(club_name: str, registry: Dict[int, dict], club_tm_id: int) -> str:
    """Classify a missing club into categories."""
    if club_tm_id in registry:
        return "in_registry"
    if is_youth_or_reserve(club_name):
        return "youth_reserve"
    # Check if name contains German geography indicators (rough heuristic)
    german_indicators = ["FC ", "SV ", "TSV ", "VfB ", "VfL ", "SC ", "SpVgg ",
                          "FSV ", "Fortuna ", "Eintracht ", "Alemannia ", "Arminia ",
                          "SSV ", "TuS ", "Kickers ", "Viktoria ", "Preußen ",
                          "Energie ", "Dynamo ", "Hansa ", "Rot-Weiß ", "Rot-Weiss "]
    name_lower = club_name.lower()
    for indicator in german_indicators:
        if indicator.lower() in name_lower:
            return "lower_german"
    return "international"


def infer_country_from_career_context(club_id: int, profiles: Dict[int, dict],
                                        club_info: dict) -> Optional[str]:
    """
    Try to infer a club's country from the profile data.
    Some TM career entries include country info in the club name or context.
    """
    names = club_info.get("names_seen", set())
    for name in names:
        name_lower = name.lower()
        for hint, country in COUNTRY_HINTS.items():
            if hint in name_lower:
                return country
    return None


def analyze_staff_coverage(registry: Dict[int, dict]) -> Dict[int, bool]:
    """Check which registry clubs actually have staff files."""
    coverage = {}
    for club_id in registry:
        coverage[club_id] = (STAFF_DIR / f"{club_id}.json").exists()
    return coverage


def analyze_squad_coverage(registry: Dict[int, dict]) -> Dict[int, int]:
    """Check how many squad files each registry club has."""
    coverage = {}
    for club_id in registry:
        count = len(list(SQUADS_DIR.glob(f"{club_id}_*.json")))
        coverage[club_id] = count
    return coverage


def build_league_groups(missing_clubs: Dict[int, dict],
                         bl_coach_clubs: Set[int]) -> Dict[str, dict]:
    """
    Group missing clubs into inferred leagues/regions.
    Returns league groups with stats.
    """
    groups = defaultdict(lambda: {
        "clubs": [],
        "total_person_refs": 0,
        "bl_coach_refs": 0,
        "club_count": 0,
    })

    for club_id, info in missing_clubs.items():
        category = info.get("category", "unknown")
        group_key = category  # Default grouping

        # Further refine international clubs by country hint
        if category == "international":
            country = info.get("inferred_country")
            if country:
                group_key = f"international_{country}"
            else:
                group_key = "international_unknown"

        groups[group_key]["clubs"].append({
            "tm_id": club_id,
            "name": info.get("primary_name", "Unknown"),
            "person_count": info.get("person_count", 0),
            "in_bl_coach_career": club_id in bl_coach_clubs,
        })
        groups[group_key]["total_person_refs"] += info.get("person_count", 0)
        if club_id in bl_coach_clubs:
            groups[group_key]["bl_coach_refs"] += 1
        groups[group_key]["club_count"] += 1

    return dict(groups)


def main():
    parser = argparse.ArgumentParser(description="Analyze coverage gaps in person career data")
    parser.add_argument("--bl-coaches-only", action="store_true",
                        help="Only analyze clubs in BL head coaches' careers")
    parser.add_argument("--min-refs", type=int, default=1,
                        help="Minimum person references to include a club (default: 1)")
    parser.add_argument("--top", type=int, default=50,
                        help="Show top N missing clubs (default: 50)")
    parser.add_argument("--output", type=str, default=str(OUTPUT_FILE),
                        help="Output JSON path")
    args = parser.parse_args()

    print("=" * 70)
    print("  COVERAGE GAP ANALYSIS — Football Coaches DB")
    print("=" * 70)

    # ── Load data ──────────────────────────────────────────────────────
    registry = load_club_registry()
    print(f"\n  Registry: {len(registry):,} clubs")

    profiles = load_all_profiles()

    # Get BL head coaches
    bl_coaches = get_bl_head_coaches(registry)
    print(f"  BL1+BL2 head coaches: {len(bl_coaches)}")

    # ── Extract career clubs ───────────────────────────────────────────
    print("\n  Extracting career clubs from all profiles...")
    t0 = time.time()

    filter_ids = None
    if args.bl_coaches_only:
        # Get all persons in BL coaches' networks (not just coaches themselves)
        # For now, just use all profiles — the network builder would be needed for full filtering
        print("  (--bl-coaches-only: filtering to BL coach career clubs)")
        filter_ids = bl_coaches

    club_info, person_clubs = extract_career_clubs(profiles, filter_ids)
    print(f"  ✓ {len(club_info):,} unique clubs found in {time.time()-t0:.1f}s")

    # ── Compute coverage ───────────────────────────────────────────────
    registry_ids = set(registry.keys())
    all_career_ids = set(club_info.keys())
    missing_ids = all_career_ids - registry_ids
    covered_ids = all_career_ids & registry_ids

    # BL coach career clubs
    bl_coach_career_clubs = set()
    for coach_id in bl_coaches:
        bl_coach_career_clubs.update(person_clubs.get(coach_id, set()))

    print(f"\n{'─' * 70}")
    print(f"  COVERAGE SUMMARY")
    print(f"{'─' * 70}")
    print(f"  Total unique clubs in career data:  {len(all_career_ids):>6,}")
    print(f"  Clubs in registry:                  {len(covered_ids):>6,}  ({100*len(covered_ids)/len(all_career_ids):.1f}%)")
    print(f"  Clubs MISSING from registry:        {len(missing_ids):>6,}  ({100*len(missing_ids)/len(all_career_ids):.1f}%)")
    print(f"  BL coach career clubs (total):      {len(bl_coach_career_clubs):>6,}")
    bl_missing = bl_coach_career_clubs - registry_ids
    print(f"  BL coach career clubs (missing):    {len(bl_missing):>6,}  ({100*len(bl_missing)/max(len(bl_coach_career_clubs),1):.1f}%)")

    # ── Classify missing clubs ─────────────────────────────────────────
    print(f"\n  Classifying {len(missing_ids):,} missing clubs...")
    missing_clubs = {}
    category_counts = Counter()

    for club_id in missing_ids:
        info = club_info[club_id]
        primary_name = sorted(info["names_seen"], key=len)[-1] if info["names_seen"] else "Unknown"
        category = classify_club(primary_name, registry, club_id)
        country = infer_country_from_career_context(club_id, profiles, info)

        category_counts[category] += 1
        if info["person_count"] >= args.min_refs:
            missing_clubs[club_id] = {
                "primary_name": primary_name,
                "all_names": sorted(info["names_seen"]),
                "person_count": info["person_count"],
                "category": category,
                "inferred_country": country,
                "in_bl_coach_career": club_id in bl_coach_career_clubs,
                "seasons": sorted(info["seasons_seen"]) if info["seasons_seen"] else [],
            }

    print(f"\n  Classification breakdown:")
    for cat, count in category_counts.most_common():
        print(f"    {cat:25s}: {count:>5,}")

    # ── Top missing clubs ──────────────────────────────────────────────
    sorted_missing = sorted(missing_clubs.items(),
                             key=lambda x: x[1]["person_count"], reverse=True)

    print(f"\n{'─' * 70}")
    print(f"  TOP {args.top} MISSING CLUBS (by person references)")
    print(f"{'─' * 70}")
    print(f"  {'#':>3}  {'Club':40s} {'TM ID':>8}  {'Refs':>6}  {'Cat':15s} {'BL?':>4}")
    print(f"  {'─'*3}  {'─'*40} {'─'*8}  {'─'*6}  {'─'*15} {'─'*4}")

    for i, (club_id, info) in enumerate(sorted_missing[:args.top], 1):
        bl_flag = "★" if info["in_bl_coach_career"] else ""
        print(f"  {i:>3}. {info['primary_name'][:40]:40s} {club_id:>8}  {info['person_count']:>6,}  "
              f"{info['category']:15s} {bl_flag:>4}")

    # ── League grouping ────────────────────────────────────────────────
    league_groups = build_league_groups(missing_clubs, bl_coach_career_clubs)

    print(f"\n{'─' * 70}")
    print(f"  MISSING CLUBS BY CATEGORY/REGION")
    print(f"{'─' * 70}")
    sorted_groups = sorted(league_groups.items(),
                            key=lambda x: x[1]["total_person_refs"], reverse=True)

    for group_key, group in sorted_groups[:25]:
        bl_flag = f" (BL: {group['bl_coach_refs']})" if group['bl_coach_refs'] else ""
        print(f"  {group_key:30s}: {group['club_count']:>4} clubs, "
              f"{group['total_person_refs']:>7,} person-refs{bl_flag}")

    # ── BL Coach specific gaps ─────────────────────────────────────────
    print(f"\n{'─' * 70}")
    print(f"  BL COACH CAREER GAPS (clubs in their careers with no staff data)")
    print(f"{'─' * 70}")

    for coach_id in sorted(bl_coaches):
        profile = profiles.get(coach_id)
        if not profile:
            continue
        coach_name = profile.get("name", f"ID:{coach_id}")
        career_clubs = person_clubs.get(coach_id, set())
        missing = career_clubs - registry_ids
        if missing:
            missing_names = []
            for cid in missing:
                names = club_info.get(cid, {}).get("names_seen", {f"ID:{cid}"})
                missing_names.append(sorted(names, key=len)[-1] if names else f"ID:{cid}")
            print(f"  {coach_name:30s}: {len(missing):>2} missing — {', '.join(sorted(missing_names)[:5])}"
                  + (f" (+{len(missing_names)-5} more)" if len(missing_names) > 5 else ""))

    # ── Save results ───────────────────────────────────────────────────
    output = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "summary": {
            "total_career_clubs": len(all_career_ids),
            "registry_clubs": len(covered_ids),
            "missing_clubs": len(missing_ids),
            "coverage_pct": round(100 * len(covered_ids) / max(len(all_career_ids), 1), 1),
            "bl_coach_career_clubs": len(bl_coach_career_clubs),
            "bl_coach_missing_clubs": len(bl_missing),
        },
        "category_breakdown": dict(category_counts),
        "top_missing_clubs": [
            {"tm_id": cid, **info}
            for cid, info in sorted_missing[:200]  # Save top 200
        ],
        "league_groups": {
            k: {**v, "clubs": v["clubs"][:50]}  # Cap at 50 clubs per group
            for k, v in sorted_groups
        },
        "bl_coach_gaps": {
            str(coach_id): {
                "name": profiles.get(coach_id, {}).get("name", ""),
                "missing_club_ids": sorted(person_clubs.get(coach_id, set()) - registry_ids),
            }
            for coach_id in bl_coaches
            if person_clubs.get(coach_id, set()) - registry_ids
        },
    }

    # Convert sets to lists for JSON serialization
    output_path = Path(args.output)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=lambda x: sorted(x) if isinstance(x, set) else str(x))

    print(f"\n  ✓ Results saved to {output_path}")
    print(f"\n{'=' * 70}")
    print(f"  NEXT STEPS:")
    print(f"  1. Review top missing clubs — identify P0 leagues to add")
    print(f"  2. Run: python execution/scrape_foreign_staff.py --all-bl-coaches")
    print(f"  3. Add P0 leagues to registry, scrape staff/squads")
    print(f"  4. Regenerate dashboards and measure improvement")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
