#!/usr/bin/env python3
"""
Analyze SD-Coach Overlaps for Bundesliga 2024/25

Core Intelligence: "Welcher Sportdirektor hat welchen Trainer schonmal zusammengearbeitet?"

This script cross-references:
- 18 Sporting Directors (83 career stations)
- 18 Head Coaches (127 career stations)

Output: JSON with all overlaps, hiring relationships, and partnership strength scores.
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))


def load_sporting_directors():
    """Load all Bundesliga SDs from JSON."""
    sd_file = Path(__file__).parent.parent / "data" / "sporting_directors_bundesliga.json"

    with open(sd_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return data.get("sporting_directors", [])


def load_coaches():
    """Load all Bundesliga coaches from preloaded caches."""
    coaches = []
    preload_dir = Path(__file__).parent.parent / "tmp" / "preloaded"

    # Load Bundesliga coaches mapping
    cache_file = Path(__file__).parent.parent / "tmp" / "cache" / "bundesliga_coaches.json"
    with open(cache_file, 'r', encoding='utf-8') as f:
        bl_data = json.load(f)

    for club_name, club_data in bl_data.get("clubs", {}).items():
        coach_url = club_data.get("coach_url", "")
        coach_name = club_data.get("coach_name", "")

        # Find preloaded file
        # Convert URL to filename
        if "/profil/trainer/" in coach_url:
            coach_id = coach_url.split("/profil/trainer/")[1].split("/")[0]

            # Try to find matching preloaded file
            for preload_file in preload_dir.glob("*.json"):
                with open(preload_file, 'r', encoding='utf-8') as f:
                    coach_data = json.load(f)

                profile = coach_data.get("profile", {})
                if profile.get("url") == coach_url or str(coach_id) in str(preload_file):
                    # Extract career history from profile
                    career_stations = []
                    for station in profile.get("career_history", []):
                        # Parse years from period if not in start_year/end_year
                        start_year = station.get("start_year")
                        end_year = station.get("end_year")
                        period = station.get("period", "")

                        # Try to parse from club_url if available (contains /saison_id/YYYY)
                        club_url = station.get("club_url", "")
                        if not start_year and "/saison_id/" in club_url:
                            try:
                                season_id = club_url.split("/saison_id/")[1].split("/")[0]
                                start_year = int(season_id)
                            except:
                                pass

                        # Extract club from role field (format: "ClubNameRole")
                        club = station.get("club", "")
                        role = station.get("role", "")
                        if not club and role:
                            # Role contains both club and role, e.g., "FC St. PauliTrainer"
                            if "Trainer" in role:
                                club = role.replace("Trainer", "").replace("Co-Trainer", "").strip()

                        if club or start_year:
                            career_stations.append({
                                "club": club,
                                "role": "Head Coach",
                                "start_year": start_year,
                                "end_year": end_year,
                                "period": period
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
    """Normalize club names for matching (remove special chars, abbreviations)."""
    # Common mappings
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

    # Apply mappings
    for old, new in mappings.items():
        if old in normalized:
            normalized = new
            break

    # Remove common prefixes for fuzzy matching
    for prefix in ["FC ", "1. FC ", "VfL ", "VfB ", "TSG ", "SV "]:
        if normalized.startswith(prefix):
            base = normalized[len(prefix):]
            return base

    return normalized


def clubs_match(club1, club2):
    """Check if two club names refer to the same club."""
    if not club1 or not club2:
        return False

    # Exact match
    if club1.strip().lower() == club2.strip().lower():
        return True

    # Normalized match
    norm1 = normalize_club_name(club1).lower()
    norm2 = normalize_club_name(club2).lower()

    return norm1 == norm2 or norm1 in norm2 or norm2 in norm1


def find_overlap(sd_station, coach_station):
    """
    Check if SD and coach were at same club during overlapping period.

    Returns:
        dict or None: {
            "club": str,
            "sd_period": str,
            "coach_period": str,
            "sd_role": str,
            "overlap_years": int,
            "hiring_likelihood": str (high/medium/low)
        }
    """
    # Check club match
    if not clubs_match(sd_station.get("club", ""), coach_station.get("club", "")):
        return None

    # Get years (handle None values)
    sd_start = sd_station.get("start_year")
    sd_end = sd_station.get("end_year")
    coach_start = coach_station.get("start_year")
    coach_end = coach_station.get("end_year")

    # Skip if no year data
    if not sd_start or not coach_start:
        return None

    # Current positions (no end year)
    if not sd_end:
        sd_end = 2026  # Assume current
    if not coach_end:
        coach_end = 2026

    # Check for overlap
    overlap_start = max(sd_start, coach_start)
    overlap_end = min(sd_end, coach_end)

    if overlap_start <= overlap_end:
        overlap_duration = overlap_end - overlap_start

        # Determine hiring likelihood
        # If SD started before coach → likely hired by SD
        hiring_likelihood = "unknown"
        if sd_start < coach_start:
            if coach_start - sd_start <= 1:
                hiring_likelihood = "high"  # SD was there when coach hired
            else:
                hiring_likelihood = "medium"  # SD was there, but not immediately
        elif sd_start == coach_start:
            hiring_likelihood = "medium"  # Started same time
        else:
            hiring_likelihood = "low"  # Coach was there first

        return {
            "club": sd_station.get("club"),
            "sd_period": sd_station.get("start_period", f"{sd_start}-{sd_end}"),
            "coach_period": coach_station.get("period", f"{coach_start}-{coach_end}"),
            "sd_role": sd_station.get("role", "Sporting Director"),
            "overlap_start": overlap_start,
            "overlap_end": overlap_end,
            "overlap_years": overlap_duration,
            "hiring_likelihood": hiring_likelihood
        }

    return None


def calculate_relationship_strength(overlaps):
    """
    Calculate relationship strength score based on overlaps.

    Score factors:
    - Number of overlaps (different clubs)
    - Total years worked together
    - Recent vs historic (recent = higher weight)
    """
    if not overlaps:
        return 0

    score = 0

    # Factor 1: Multiple clubs = stronger relationship
    num_clubs = len(set(o["club"] for o in overlaps))
    score += num_clubs * 10

    # Factor 2: Total years together
    total_years = sum(o["overlap_years"] for o in overlaps)
    score += total_years * 2

    # Factor 3: Recent collaborations (after 2015)
    recent_overlaps = [o for o in overlaps if o["overlap_start"] >= 2015]
    score += len(recent_overlaps) * 5

    # Factor 4: High hiring likelihood
    high_likelihood = [o for o in overlaps if o["hiring_likelihood"] == "high"]
    score += len(high_likelihood) * 15

    return score


def analyze_all_overlaps():
    """Main analysis function."""
    print("=" * 70)
    print("SD-Coach Overlap Analysis - Bundesliga 2024/25")
    print("=" * 70)

    # Load data
    print("\n[1/4] Loading data...")
    sds = load_sporting_directors()
    coaches = load_coaches()

    print(f"  ✓ Loaded {len(sds)} Sporting Directors")
    print(f"  ✓ Loaded {len(coaches)} Head Coaches")

    # Analyze overlaps
    print("\n[2/4] Analyzing SD-Coach overlaps...")

    all_relationships = []
    overlap_count = 0

    for sd in sds:
        sd_name = sd.get("name", "Unknown")
        sd_career = sd.get("career_history", [])

        if sd.get("error"):
            continue

        for coach in coaches:
            coach_name = coach.get("name", "Unknown")
            coach_career = coach.get("career_history", [])

            # Find all overlaps between this SD and coach
            overlaps = []

            for sd_station in sd_career:
                for coach_station in coach_career:
                    overlap = find_overlap(sd_station, coach_station)
                    if overlap:
                        overlaps.append(overlap)
                        overlap_count += 1

            # If overlaps found, create relationship entry
            if overlaps:
                strength = calculate_relationship_strength(overlaps)

                relationship = {
                    "sd_name": sd_name,
                    "sd_current_club": sd.get("expected_club", ""),
                    "sd_current_role": sd.get("expected_role", ""),
                    "coach_name": coach_name,
                    "coach_current_club": coach.get("current_club", ""),
                    "overlaps": overlaps,
                    "total_overlaps": len(overlaps),
                    "total_clubs": len(set(o["club"] for o in overlaps)),
                    "total_years_together": sum(o["overlap_years"] for o in overlaps),
                    "relationship_strength": strength,
                    "most_recent_club": max(overlaps, key=lambda x: x["overlap_start"])["club"],
                    "most_recent_year": max(overlaps, key=lambda x: x["overlap_start"])["overlap_start"]
                }

                all_relationships.append(relationship)

    print(f"  ✓ Found {overlap_count} overlap periods")
    print(f"  ✓ Created {len(all_relationships)} SD-Coach relationships")

    # Sort by relationship strength
    all_relationships.sort(key=lambda x: x["relationship_strength"], reverse=True)

    # Generate insights
    print("\n[3/4] Generating insights...")

    insights = {
        "top_partnerships": all_relationships[:10],
        "current_bundesliga_connections": [
            r for r in all_relationships
            if "Bundesliga" in r.get("sd_current_club", "") or "Bundesliga" in r.get("coach_current_club", "")
        ],
        "hiring_patterns": defaultdict(list),
        "sd_stats": {},
        "coach_stats": {}
    }

    # SD statistics
    sd_relationship_count = defaultdict(int)
    sd_coaches_hired = defaultdict(list)

    for rel in all_relationships:
        sd = rel["sd_name"]
        coach = rel["coach_name"]
        sd_relationship_count[sd] += 1

        # Check if likely hired
        high_likelihood = [o for o in rel["overlaps"] if o["hiring_likelihood"] == "high"]
        if high_likelihood:
            for overlap in high_likelihood:
                sd_coaches_hired[sd].append({
                    "coach": coach,
                    "club": overlap["club"],
                    "year": overlap["overlap_start"]
                })

    # Most connected SDs
    insights["sd_stats"] = {
        "most_connected": sorted(
            [{"sd": sd, "relationships": count} for sd, count in sd_relationship_count.items()],
            key=lambda x: x["relationships"],
            reverse=True
        )[:5],
        "most_hirings": {
            sd: hirings for sd, hirings in sorted(
                sd_coaches_hired.items(),
                key=lambda x: len(x[1]),
                reverse=True
            )[:5]
        }
    }

    # Coach statistics
    coach_relationship_count = defaultdict(int)
    for rel in all_relationships:
        coach_relationship_count[rel["coach_name"]] += 1

    insights["coach_stats"] = {
        "most_connected": sorted(
            [{"coach": coach, "relationships": count} for coach, count in coach_relationship_count.items()],
            key=lambda x: x["relationships"],
            reverse=True
        )[:5]
    }

    print(f"  ✓ Generated insights")

    # Save output
    print("\n[4/4] Saving results...")

    output_data = {
        "analysis_date": datetime.now().isoformat(),
        "league": "Bundesliga",
        "season": "2024/25",
        "total_sds_analyzed": len([sd for sd in sds if not sd.get("error")]),
        "total_coaches_analyzed": len(coaches),
        "total_relationships": len(all_relationships),
        "total_overlap_periods": overlap_count,
        "relationships": all_relationships,
        "insights": insights
    }

    output_path = Path(__file__).parent.parent / "data" / "sd_coach_overlaps.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ COMPLETE! Saved to: {output_path}")
    print(f"📊 Total relationships: {len(all_relationships)}")
    print(f"📈 Total overlap periods: {overlap_count}")

    # Print top 5 partnerships
    print("\n🔥 Top 5 SD-Coach Partnerships (by strength):")
    for i, rel in enumerate(all_relationships[:5], 1):
        print(f"{i}. {rel['sd_name']} ↔ {rel['coach_name']}")
        print(f"   Strength: {rel['relationship_strength']} | {rel['total_clubs']} club(s) | {rel['total_years_together']} years")
        print(f"   Most recent: {rel['most_recent_club']} ({rel['most_recent_year']})")

    print("\n" + "=" * 70)

    return output_data


if __name__ == "__main__":
    analyze_all_overlaps()
