#!/usr/bin/env python3
"""
Analyze Youth Coach ↔ Executive Overlaps for Bundesliga

PURPOSE: Capture relationships between coaches during their youth/assistant phase
and executives (Scouting, Academy leadership) they worked with. These early
relationships are often decisive for later head coach hiring decisions.

EXAMPLE: Alexander Blessin (2012-2018 youth coach at RB Leipzig) worked with
Johannes Spors (Head of Scouting 2015-2018). When Spors became SD elsewhere,
this relationship matters for hiring intelligence.

Input:
- Coach career histories (including youth/assistant positions)
- Club executives (Academy, Scouting leadership)

Output:
- JSON with youth coach ↔ executive overlaps
- Categorized by executive type (Scouting, Academy, Technical)
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))


def load_club_executives():
    """Load all Bundesliga club executives from JSON."""
    exec_file = Path(__file__).parent.parent / "data" / "club_executives_bundesliga.json"

    if not exec_file.exists():
        print(f"⚠️  Warning: {exec_file} not found")
        return []

    with open(exec_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return data.get("executives", [])


def load_coaches():
    """Load all Bundesliga coaches from preloaded caches."""
    coaches = []
    preload_dir = Path(__file__).parent.parent / "tmp" / "preloaded"

    # Load Bundesliga coaches mapping
    cache_file = Path(__file__).parent.parent / "tmp" / "cache" / "bundesliga_coaches.json"

    if not cache_file.exists():
        print(f"⚠️  Warning: {cache_file} not found")
        return []

    with open(cache_file, 'r', encoding='utf-8') as f:
        bl_data = json.load(f)

    for club_name, club_data in bl_data.get("clubs", {}).items():
        coach_url = club_data.get("coach_url", "")
        coach_name = club_data.get("coach_name", "")

        # Find preloaded file
        if "/profil/trainer/" in coach_url:
            coach_id = coach_url.split("/profil/trainer/")[1].split("/")[0]

            # Try to find matching preloaded file
            for preload_file in preload_dir.glob("*.json"):
                with open(preload_file, 'r', encoding='utf-8') as f:
                    coach_data = json.load(f)

                profile = coach_data.get("profile", {})
                if profile.get("url") == coach_url or str(coach_id) in str(preload_file):
                    # Extract ALL career history (including youth/assistant)
                    career_stations = []
                    for station in profile.get("career_history", []):
                        club = station.get("club", "")
                        role = station.get("role", "")

                        # Extract club from role if needed
                        if not club and role:
                            # Role format: "ClubNameRole"
                            for marker in ["Trainer", "Co-Trainer"]:
                                if marker in role:
                                    club = role.replace(marker, "").replace("Co-Trainer", "").strip()
                                    break

                        # Try to parse years from club_url
                        start_year = station.get("start_year")
                        end_year = station.get("end_year")
                        club_url = station.get("club_url", "")

                        if not start_year and "/saison_id/" in club_url:
                            try:
                                season_id = club_url.split("/saison_id/")[1].split("/")[0]
                                start_year = int(season_id)
                                # Estimate end year (assume 2-3 year tenure if not specified)
                                if not end_year:
                                    end_year = start_year + 2
                            except:
                                pass

                        # Categorize position type
                        is_head_coach = all(marker not in role for marker in [
                            "U19", "U17", "U21", "U23", " II", "Co-Trainer", "Jgd.", "Youth", "Assistant", "YL"
                        ]) and "Trainer" in role

                        position_type = "Head Coach" if is_head_coach else "Youth/Assistant"

                        if club or start_year:
                            career_stations.append({
                                "club": club,
                                "role": role,
                                "position_type": position_type,
                                "start_year": start_year,
                                "end_year": end_year,
                                "period": station.get("period", "")
                            })

                    coaches.append({
                        "name": profile.get("name", coach_name),
                        "url": coach_url,
                        "current_club": club_name,
                        "career_history": career_stations
                    })
                    break

    return coaches


def normalize_club_name(club_name):
    """Normalize club names for matching."""
    mappings = {
        "Bor. Dortmund": "Borussia Dortmund",
        "Bor. M'gladbach": "Borussia Mönchengladbach",
        "Bayern München": "FC Bayern München",
        "B. Leverkusen": "Bayer 04 Leverkusen",
        "E. Frankfurt": "Eintracht Frankfurt",
        "Hannover 96": "Hannover",
        "TSG Hoffenheim": "1899 Hoffenheim",
        "1899 Hoffenheim": "TSG Hoffenheim",
        "Union Berlin": "1. FC Union Berlin",
        "Köln": "1. FC Köln",
        "1. FC Köln": "FC Köln",
    }

    normalized = club_name.strip()

    for old, new in mappings.items():
        if old in normalized:
            normalized = new
            break

    # Remove common prefixes for fuzzy matching
    for prefix in ["FC ", "1. FC ", "VfL ", "VfB ", "TSG ", "SV "]:
        if normalized.startswith(prefix):
            return normalized[len(prefix):]

    return normalized


def clubs_match(club1, club2):
    """Check if two club names refer to the same club."""
    if not club1 or not club2:
        return False

    if club1.strip().lower() == club2.strip().lower():
        return True

    norm1 = normalize_club_name(club1).lower()
    norm2 = normalize_club_name(club2).lower()

    return norm1 == norm2 or norm1 in norm2 or norm2 in norm1


def find_overlap(coach_station, exec_station):
    """
    Check if coach and executive were at same club during overlapping period.

    Returns:
        dict or None: {
            "club": str,
            "coach_position": str,  # Youth/Assistant or Head Coach
            "coach_period": str,
            "exec_role": str,
            "exec_category": str,  # Scouting, Academy, Technical
            "overlap_years": int
        }
    """
    # Check club match
    if not clubs_match(coach_station.get("club", ""), exec_station.get("club", "")):
        return None

    # Get years
    coach_start = coach_station.get("start_year")
    coach_end = coach_station.get("end_year")
    exec_start = exec_station.get("start_year")
    exec_end = exec_station.get("end_year")

    # Skip if no year data
    if not coach_start or not exec_start:
        return None

    # Handle current positions
    if not coach_end:
        coach_end = 2026
    if not exec_end:
        exec_end = 2026

    # Check for overlap
    overlap_start = max(coach_start, exec_start)
    overlap_end = min(coach_end, exec_end)

    if overlap_start <= overlap_end:
        overlap_duration = overlap_end - overlap_start + 1

        return {
            "club": coach_station.get("club"),
            "coach_position": coach_station.get("position_type", "Unknown"),
            "coach_role": coach_station.get("role", ""),
            "coach_period": f"{coach_start}-{coach_end}",
            "exec_role": exec_station.get("role", "Unknown"),
            "exec_category": exec_station.get("category", "Unknown"),
            "overlap_start": overlap_start,
            "overlap_end": overlap_end,
            "overlap_years": overlap_duration
        }

    return None


def calculate_relationship_strength(overlaps):
    """Calculate relationship strength score."""
    if not overlaps:
        return 0

    score = 0

    # Factor 1: Multiple clubs = stronger
    num_clubs = len(set(o["club"] for o in overlaps))
    score += num_clubs * 15

    # Factor 2: Total years together
    total_years = sum(o["overlap_years"] for o in overlaps)
    score += total_years * 3

    # Factor 3: Recent collaborations (after 2015)
    recent_overlaps = [o for o in overlaps if o["overlap_start"] >= 2015]
    score += len(recent_overlaps) * 8

    # Factor 4: Youth/Assistant overlaps get bonus (these are formative relationships)
    youth_overlaps = [o for o in overlaps if o["coach_position"] != "Head Coach"]
    score += len(youth_overlaps) * 5

    return score


def main():
    """Analyze all youth coach ↔ executive overlaps."""
    print("=" * 70)
    print("YOUTH COACH ↔ EXECUTIVE OVERLAP ANALYSIS")
    print("=" * 70)

    print("\n[1/3] Loading data...")
    executives = load_club_executives()
    coaches = load_coaches()

    print(f"  ✓ Loaded {len(executives)} executives")
    print(f"  ✓ Loaded {len(coaches)} coaches")

    print("\n[2/3] Analyzing overlaps...")

    # Build executive career lookup
    exec_career_map = {}
    for exec_info in executives:
        name = exec_info.get("name", "")
        for station in exec_info.get("career_history", []):
            key = (name, station.get("club", ""))
            exec_career_map[key] = {
                "name": name,
                "role": station.get("role", exec_info.get("current_role", "")),
                "category": exec_info.get("category", "Other"),
                "club": station.get("club", ""),
                "start_year": station.get("start_year"),
                "end_year": station.get("end_year"),
                "profile_url": exec_info.get("profile_url", "")
            }

    # Find overlaps
    relationships = []

    for coach in coaches:
        coach_name = coach.get("name", "")

        for coach_station in coach.get("career_history", []):
            # Check against all executive stations
            for exec_station in exec_career_map.values():
                overlap = find_overlap(coach_station, exec_station)

                if overlap:
                    # Find or create relationship
                    rel_key = (coach_name, exec_station["name"])
                    existing_rel = next(
                        (r for r in relationships if r["coach_name"] == coach_name and r["exec_name"] == exec_station["name"]),
                        None
                    )

                    if existing_rel:
                        existing_rel["overlaps"].append(overlap)
                    else:
                        relationships.append({
                            "coach_name": coach_name,
                            "coach_current_club": coach.get("current_club", ""),
                            "exec_name": exec_station["name"],
                            "exec_current_role": exec_station.get("role", ""),
                            "exec_category": exec_station.get("category", ""),
                            "overlaps": [overlap]
                        })

    # Calculate relationship strengths
    for rel in relationships:
        rel["relationship_strength"] = calculate_relationship_strength(rel["overlaps"])

    # Sort by strength
    relationships.sort(key=lambda x: x["relationship_strength"], reverse=True)

    print(f"  ✓ Found {len(relationships)} coach-executive relationships")
    print(f"  ✓ Total overlap periods: {sum(len(r['overlaps']) for r in relationships)}")

    print("\n[3/3] Saving results...")

    # Save to file
    output_file = Path(__file__).parent.parent / "data" / "youth_executive_overlaps.json"
    output_data = {
        "analysis_date": datetime.now().isoformat(),
        "league": "Bundesliga",
        "season": "2024/25",
        "total_executives": len(executives),
        "total_coaches": len(coaches),
        "total_relationships": len(relationships),
        "total_overlap_periods": sum(len(r["overlaps"]) for r in relationships),
        "relationships": relationships
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"\n✅ COMPLETE! Saved to: {output_file}")
    print(f"📊 Total relationships: {len(relationships)}")

    # Show top 10
    print("\n🔥 Top 10 Coach ↔ Executive Relationships (by strength):")
    for i, rel in enumerate(relationships[:10], 1):
        coach_name = rel["coach_name"]
        exec_name = rel["exec_name"]
        strength = rel["relationship_strength"]
        num_clubs = len(set(o["club"] for o in rel["overlaps"]))
        total_years = sum(o["overlap_years"] for o in rel["overlaps"])
        exec_cat = rel.get("exec_category", "Unknown")

        print(f"{i}. {coach_name} ↔ {exec_name} ({exec_cat})")
        print(f"   Strength: {strength} | {num_clubs} club(s) | {total_years} years")

        # Show most recent overlap
        recent = sorted(rel["overlaps"], key=lambda x: x["overlap_start"], reverse=True)[0]
        print(f"   Most recent: {recent['club']} ({recent['overlap_start']}-{recent['overlap_end']})")
        print()

    print("=" * 70)


if __name__ == "__main__":
    main()
