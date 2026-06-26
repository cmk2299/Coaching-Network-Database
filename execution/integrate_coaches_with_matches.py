#!/usr/bin/env python3
"""
Integrate OpenLigaDB match data with coach profiles.

Creates timeline of coach performance by linking:
- Coach career history (clubs + periods)
- OpenLigaDB match results
- Calculate performance metrics per coach tenure

Output: Each coach gets match-level performance data
"""

import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Optional
import re

# Paths
COACHES_DIR = Path("tmp/preloaded")
MATCHES_FILE = Path("data/openligadb/bundesliga_all_matches_2015_2026.json")
OUTPUT_FILE = Path("data/coaches_with_match_performance.json")

# Team name normalization (OpenLigaDB → Transfermarkt)
TEAM_MAPPING = {
    # 1. Bundesliga
    "FC Bayern München": ["FC Bayern München", "Bayern Munich"],
    "Borussia Dortmund": ["Borussia Dortmund", "BVB"],
    "RB Leipzig": ["RB Leipzig", "Leipzig"],
    "Bayer 04 Leverkusen": ["Bayer Leverkusen", "Bayer 04 Leverkusen"],
    "SC Freiburg": ["SC Freiburg", "Freiburg"],
    "1. FC Union Berlin": ["1. FC Union Berlin", "Union Berlin"],
    "VfB Stuttgart": ["VfB Stuttgart", "Stuttgart"],
    "Eintracht Frankfurt": ["Eintracht Frankfurt", "Frankfurt"],
    "Borussia Mönchengladbach": ["Borussia Mönchengladbach", "Gladbach", "Bor. Mönchengladbach"],
    "VfL Wolfsburg": ["VfL Wolfsburg", "Wolfsburg"],
    "TSG 1899 Hoffenheim": ["TSG Hoffenheim", "Hoffenheim", "TSG 1899 Hoffenheim"],
    "1. FC Heidenheim": ["1. FC Heidenheim", "Heidenheim"],
    "SV Werder Bremen": ["Werder Bremen", "SV Werder Bremen"],
    "FC Augsburg": ["FC Augsburg", "Augsburg"],
    "1. FSV Mainz 05": ["1. FSV Mainz 05", "Mainz 05", "Mainz"],
    "1. FC Köln": ["1. FC Köln", "Köln", "FC Cologne"],
    "VfL Bochum": ["VfL Bochum", "Bochum"],
    "Hertha BSC": ["Hertha BSC", "Hertha"],
    "FC Schalke 04": ["FC Schalke 04", "Schalke 04", "Schalke"],
    "SpVgg Greuther Fürth": ["SpVgg Greuther Fürth", "Greuther Fürth"],
    "Arminia Bielefeld": ["Arminia Bielefeld", "Bielefeld"],
    "FC St. Pauli": ["FC St. Pauli", "St. Pauli"],
    "Holstein Kiel": ["Holstein Kiel", "Kiel"],
    "SV Darmstadt 98": ["SV Darmstadt 98", "Darmstadt"],

    # 2. Bundesliga (common teams)
    "Hamburger SV": ["Hamburger SV", "HSV", "Hamburg"],
    "Hannover 96": ["Hannover 96", "Hannover"],
    "1. FC Nürnberg": ["1. FC Nürnberg", "Nürnberg"],
    "Fortuna Düsseldorf": ["Fortuna Düsseldorf", "Düsseldorf"],
    "Karlsruher SC": ["Karlsruher SC", "Karlsruhe"],
    "SC Paderborn": ["SC Paderborn 07", "Paderborn"],
    "SV Sandhausen": ["SV Sandhausen", "Sandhausen"],
    "FC Ingolstadt 04": ["FC Ingolstadt 04", "Ingolstadt"],
    "SSV Jahn Regensburg": ["SSV Jahn Regensburg", "Jahn Regensburg"],
    "1. FC Kaiserslautern": ["1. FC Kaiserslautern", "Kaiserslautern"],
    "Eintracht Braunschweig": ["Eintracht Braunschweig", "Braunschweig"],
}

def normalize_team_name(team_name: str) -> str:
    """Normalize team name for matching."""
    if not team_name:
        return ""

    # Remove common abbreviations and normalize
    normalized = team_name.strip()

    # Bidirectional matching: check if either name contains the other
    for canonical, variants in TEAM_MAPPING.items():
        # Exact match
        if normalized in variants or normalized == canonical:
            return canonical

        # Fuzzy matching: check if canonical name contains input or vice versa
        canonical_lower = canonical.lower().replace(".", "").replace(" ", "")
        normalized_lower = normalized.lower().replace(".", "").replace(" ", "")

        # Special cases
        if "dortmund" in canonical_lower and "dortmund" in normalized_lower:
            return canonical
        if "bayern" in canonical_lower and "bayern" in normalized_lower:
            return canonical
        if "leverkusen" in canonical_lower and "leverkusen" in normalized_lower:
            return canonical
        if "mainz" in canonical_lower and "mainz" in normalized_lower:
            return canonical
        if "gladbach" in canonical_lower and ("gladbach" in normalized_lower or "mönchengladbach" in normalized_lower or "monchengladbach" in normalized_lower):
            return canonical
        if "hoffenheim" in canonical_lower and "hoffenheim" in normalized_lower:
            return canonical
        if "wolfsburg" in canonical_lower and "wolfsburg" in normalized_lower:
            return canonical
        if "stuttgart" in canonical_lower and "stuttgart" in normalized_lower:
            return canonical
        if "frankfurt" in canonical_lower and "frankfurt" in normalized_lower and "jugend" not in normalized_lower and "jgd" not in normalized_lower:
            return canonical
        if "bremen" in canonical_lower and "bremen" in normalized_lower:
            return canonical
        if "augsburg" in canonical_lower and "augsburg" in normalized_lower:
            return canonical
        if "köln" in canonical_lower and ("köln" in normalized_lower or "koln" in normalized_lower or "cologne" in normalized_lower):
            return canonical
        if "bochum" in canonical_lower and "bochum" in normalized_lower:
            return canonical
        if "hertha" in canonical_lower and "hertha" in normalized_lower:
            return canonical
        if "schalke" in canonical_lower and "schalke" in normalized_lower:
            return canonical
        if "leipzig" in canonical_lower and "leipzig" in normalized_lower and "rb" in normalized_lower:
            return canonical
        if "freiburg" in canonical_lower and "freiburg" in normalized_lower:
            return canonical
        if "union" in canonical_lower and "union" in normalized_lower and "berlin" in normalized_lower:
            return canonical
        if "hamburg" in canonical_lower and ("hamburg" in normalized_lower or "hsv" in normalized_lower):
            return canonical
        if "hannover" in canonical_lower and "hannover" in normalized_lower:
            return canonical
        if "nürnberg" in canonical_lower and ("nürnberg" in normalized_lower or "nurnberg" in normalized_lower):
            return canonical
        if "düsseldorf" in canonical_lower and ("düsseldorf" in normalized_lower or "dusseldorf" in normalized_lower or "fortuna" in normalized_lower):
            return canonical
        if "karlsruhe" in canonical_lower and "karlsruhe" in normalized_lower:
            return canonical
        if "paderborn" in canonical_lower and "paderborn" in normalized_lower:
            return canonical

    # Return original if no mapping found
    return normalized

def parse_career_dates(period_str: str) -> Optional[Dict]:
    """
    Parse career period string to get start/end dates.

    Examples:
    - "24/25 (01/07/2024) - Present"
    - "21/22 (01/07/2021) - 22/23 (30/06/2022)"
    - "18/19 (15/12/2018) - 18/19 (31/05/2019)"
    """
    if not period_str:
        return None

    try:
        # Extract dates in DD.MM.YYYY format (Transfermarkt uses dots!)
        date_pattern = r'(\d{2}\.\d{2}\.\d{4})'
        dates = re.findall(date_pattern, period_str)

        if not dates:
            return None

        start_str = dates[0]
        end_str = dates[1] if len(dates) > 1 else None

        # Convert to datetime
        start = datetime.strptime(start_str, "%d.%m.%Y")

        if end_str:
            end = datetime.strptime(end_str, "%d.%m.%Y")
        elif "Present" in period_str:
            end = datetime.now()
        else:
            return None

        return {
            "start": start,
            "end": end,
            "start_str": start_str,
            "end_str": end_str if end_str else "Present"
        }

    except Exception:
        return None

def match_overlaps_tenure(match_date_str: str, tenure_start: datetime, tenure_end: datetime) -> bool:
    """Check if match date falls within coach tenure."""
    try:
        # Parse match date (ISO format: "2024-08-23T20:30:00")
        match_date = datetime.fromisoformat(match_date_str.replace("Z", ""))
        return tenure_start <= match_date <= tenure_end
    except Exception:
        return False

def calculate_tenure_stats(matches: List[Dict]) -> Dict:
    """Calculate performance statistics for a tenure."""
    if not matches:
        return {
            "matches": 0,
            "wins": 0,
            "draws": 0,
            "losses": 0,
            "goals_for": 0,
            "goals_against": 0,
            "points": 0,
            "ppg": 0.0
        }

    wins = 0
    draws = 0
    losses = 0
    goals_for = 0
    goals_against = 0

    for match in matches:
        score = match.get("score_final")
        if not score:
            continue

        home_goals = score.get("home", 0) or 0
        away_goals = score.get("away", 0) or 0

        # Determine if coach's team was home or away
        is_home = match.get("is_home_team", True)

        if is_home:
            gf = home_goals
            ga = away_goals
        else:
            gf = away_goals
            ga = home_goals

        goals_for += gf
        goals_against += ga

        if gf > ga:
            wins += 1
        elif gf == ga:
            draws += 1
        else:
            losses += 1

    points = wins * 3 + draws
    ppg = points / len(matches) if matches else 0.0

    return {
        "matches": len(matches),
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "goals_for": goals_for,
        "goals_against": goals_against,
        "goal_diff": goals_for - goals_against,
        "points": points,
        "ppg": round(ppg, 2),
        "win_rate": round(wins / len(matches) * 100, 1) if matches else 0.0
    }

def integrate_coaches_with_matches():
    """Main integration function."""
    print("\n" + "="*60)
    print("Coach-Match Performance Integration")
    print("="*60 + "\n")

    # Load matches
    print("📊 Loading matches...")
    matches = json.loads(MATCHES_FILE.read_text())
    print(f"   ✓ Loaded {len(matches):,} matches")

    # Load coach profiles
    print("\n👔 Loading coach profiles...")
    coach_files = list(COACHES_DIR.glob("*.json"))
    print(f"   ✓ Found {len(coach_files):,} coach profiles")

    # Build match lookup by team and date
    print("\n🔍 Indexing matches by team...")
    team_matches = defaultdict(list)

    for match in matches:
        if not match.get("is_finished"):
            continue

        home_team = normalize_team_name(match.get("team_home", {}).get("name", ""))
        away_team = normalize_team_name(match.get("team_away", {}).get("name", ""))

        if home_team:
            match_copy = match.copy()
            match_copy["is_home_team"] = True
            team_matches[home_team].append(match_copy)

        if away_team:
            match_copy = match.copy()
            match_copy["is_home_team"] = False
            team_matches[away_team].append(match_copy)

    print(f"   ✓ Indexed {len(team_matches)} unique teams")

    # Process each coach
    print("\n⚙️  Processing coaches...")
    enriched_coaches = []
    stats = {
        "total_coaches": len(coach_files),
        "coaches_with_matches": 0,
        "total_tenures": 0,
        "tenures_with_matches": 0,
        "total_matches_linked": 0
    }

    for i, coach_file in enumerate(coach_files, 1):
        if i % 100 == 0:
            print(f"   → Processed {i}/{len(coach_files)} coaches...")

        coach = json.loads(coach_file.read_text())
        coach_tenures = []

        # Process career history
        for entry in coach.get("career_history", []):
            club = normalize_team_name(entry.get("club", ""))
            role = entry.get("role", "").lower()
            period = entry.get("period", "")

            # Only process manager/head coach roles (German and English)
            role_keywords = ["trainer", "manager", "head coach", "cheftrainer", "coach"]
            if not any(keyword in role for keyword in role_keywords):
                continue

            # Exclude assistant/co-trainer roles
            exclude_keywords = ["co-trainer", "assistant", "assistent", "interim"]
            if any(keyword in role for keyword in exclude_keywords):
                continue

            dates = parse_career_dates(period)
            if not dates:
                continue

            stats["total_tenures"] += 1

            # Find matches during this tenure
            tenure_matches = []

            if club in team_matches:
                for match in team_matches[club]:
                    if match_overlaps_tenure(
                        match.get("date", ""),
                        dates["start"],
                        dates["end"]
                    ):
                        tenure_matches.append(match)

            if tenure_matches:
                stats["tenures_with_matches"] += 1
                stats["total_matches_linked"] += len(tenure_matches)

            # Calculate performance stats
            performance = calculate_tenure_stats(tenure_matches)

            tenure_data = {
                "club": club,
                "role": entry.get("role"),
                "period": period,
                "start_date": dates["start_str"],
                "end_date": dates["end_str"],
                "performance": performance,
                "sample_matches": tenure_matches[:5] if tenure_matches else []  # First 5 matches
            }

            coach_tenures.append(tenure_data)

        # Add tenures to coach profile
        coach["match_performance"] = coach_tenures

        if any(t["performance"]["matches"] > 0 for t in coach_tenures):
            stats["coaches_with_matches"] += 1

        enriched_coaches.append(coach)

    # Save enriched data
    print("\n💾 Saving enriched profiles...")
    OUTPUT_FILE.write_text(json.dumps(enriched_coaches, indent=2))
    print(f"   ✓ Saved to {OUTPUT_FILE}")

    # Print statistics
    print("\n" + "="*60)
    print("INTEGRATION COMPLETE")
    print("="*60)
    print(f"\n✓ Total Coaches: {stats['total_coaches']:,}")
    print(f"✓ Coaches with Match Data: {stats['coaches_with_matches']:,} ({stats['coaches_with_matches']/stats['total_coaches']*100:.1f}%)")
    print(f"\n✓ Total Manager Tenures: {stats['total_tenures']:,}")
    if stats['total_tenures'] > 0:
        print(f"✓ Tenures with Matches: {stats['tenures_with_matches']:,} ({stats['tenures_with_matches']/stats['total_tenures']*100:.1f}%)")
    else:
        print("✓ Tenures with Matches: 0 (N/A)")
    print(f"\n✓ Total Matches Linked: {stats['total_matches_linked']:,}")

    # Top coaches by matches
    print("\n🏆 Top 10 Coaches by Matches Managed (2015-2026):")

    coach_match_counts = []
    for coach in enriched_coaches:
        total_matches = sum(
            t["performance"]["matches"]
            for t in coach.get("match_performance", [])
        )
        if total_matches > 0:
            coach_match_counts.append({
                "name": coach.get("name", "Unknown"),
                "matches": total_matches,
                "tenures": len([t for t in coach.get("match_performance", [])
                               if t["performance"]["matches"] > 0])
            })

    coach_match_counts.sort(key=lambda x: x["matches"], reverse=True)

    for i, coach in enumerate(coach_match_counts[:10], 1):
        print(f"   {i:2}. {coach['name']}: {coach['matches']:,} matches ({coach['tenures']} tenures)")

    print("\n" + "="*60 + "\n")

    return enriched_coaches, stats

if __name__ == "__main__":
    coaches, stats = integrate_coaches_with_matches()
    print(f"✅ Successfully integrated {stats['total_matches_linked']:,} matches!")
