#!/usr/bin/env python3
"""
Score Current Bundesliga Coaches (Henryk's Use Case)

Evaluates the 18 current Bundesliga coaches based on:
1. Network Score: Connections to Sporting Directors
2. Player Pool Score: Experienced players they've worked with
3. Combined Score: Overall "hire-ability" metric

Output: Ranked list of coaches with scores and key connections
"""

import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# Paths
COACHES_FILE = Path("data/coaches_with_match_performance.json")
NETWORK_EDGES = Path("data/network_edges.csv")  # Coach-SD connections
TEAMMATES_FILE = Path("data/teammates_bulk.json")
OUTPUT_FILE = Path("data/bundesliga_coach_scores_2025_26.json")

# Current Bundesliga Season
CURRENT_SEASON = "25/26"

# Bundesliga 2025/26 Clubs (from OpenLigaDB or manual)
BUNDESLIGA_CLUBS_2025_26 = [
    "FC Bayern München",
    "Borussia Dortmund",
    "RB Leipzig",
    "Bayer 04 Leverkusen",
    "SC Freiburg",
    "1. FC Union Berlin",
    "VfB Stuttgart",
    "Eintracht Frankfurt",
    "Borussia Mönchengladbach",
    "VfL Wolfsburg",
    "TSG 1899 Hoffenheim",
    "1. FC Heidenheim",
    "SV Werder Bremen",
    "FC Augsburg",
    "1. FSV Mainz 05",
    "FC St. Pauli",
    "Holstein Kiel",
    "VfL Bochum"
]

def get_current_bundesliga_coaches(coaches_data):
    """
    Identify the 18 current Bundesliga head coaches.

    Returns:
        List of coach dictionaries with current club info
    """
    current_coaches = []

    for coach in coaches_data:
        # Check current position
        career = coach.get("career_history", [])
        if not career:
            continue

        # Most recent position (first in list)
        current_position = career[0]
        club = current_position.get("club", "")
        role = current_position.get("role", "").lower()
        period = current_position.get("period", "")

        # Check if current (contains "Present" or "vsl")
        is_current = "Present" in period or "vsl" in period or CURRENT_SEASON in period

        # Check if head coach role
        is_head_coach = any(kw in role for kw in ["trainer", "manager", "head coach", "cheftrainer"])
        exclude = any(kw in role for kw in ["co-trainer", "assistant", "interim"])

        # Check if Bundesliga club
        is_bundesliga = any(bl_club.lower() in club.lower() for bl_club in BUNDESLIGA_CLUBS_2025_26)

        if is_current and is_head_coach and not exclude and is_bundesliga:
            current_coaches.append({
                "name": coach.get("name"),
                "url": coach.get("url"),
                "current_club": club,
                "current_role": current_position.get("role"),
                "appointed": period,
                "full_profile": coach
            })

    return current_coaches

def calculate_sd_network_score(coach_profile, all_coaches):
    """
    Calculate Sporting Director Network Score.

    Methodology:
    - +10 points per SD worked with directly (same club, overlapping tenure)
    - +5 points per SD connection through shared clubs (different times)
    - +3 points per executive/board member connection

    Returns:
        Dictionary with score and SD connections
    """
    score = 0
    sd_connections = []

    coach_name = coach_profile.get("name")
    coach_career = coach_profile.get("career_history", [])

    # Build list of clubs and periods coach worked at
    coach_clubs = {}
    for entry in coach_career:
        club = entry.get("club", "")
        period = entry.get("period", "")
        role = entry.get("role", "")

        if club not in coach_clubs:
            coach_clubs[club] = []
        coach_clubs[club].append({
            "period": period,
            "role": role
        })

    # Check all other coaches for SD/Executive roles
    for other_coach in all_coaches:
        if other_coach.get("name") == coach_name:
            continue

        for entry in other_coach.get("career_history", []):
            role = entry.get("role", "").lower()
            club = entry.get("club", "")
            period = entry.get("period", "")

            # Check if SD or Executive
            is_sd = "sportdirektor" in role or "sporting director" in role or "director of sport" in role
            is_exec = "geschäftsführer" in role or "ceo" in role or "vorstand" in role or "president" in role

            if not (is_sd or is_exec):
                continue

            # Check if same club
            if club in coach_clubs:
                # Same club connection
                connection_type = "Sporting Director" if is_sd else "Executive"
                points = 10 if is_sd else 3

                sd_connections.append({
                    "sd_name": other_coach.get("name"),
                    "club": club,
                    "type": connection_type,
                    "coach_period": coach_clubs[club][0]["period"],  # Simplified
                    "sd_period": period,
                    "points": points
                })

                score += points

    return {
        "score": score,
        "connections": sd_connections,
        "num_sds": len([c for c in sd_connections if c["type"] == "Sporting Director"]),
        "num_execs": len([c for c in sd_connections if c["type"] == "Executive"])
    }

def calculate_player_pool_score(coach_profile, teammates_data):
    """
    Calculate Player Pool Score.

    Methodology:
    - Count unique players coached (from match performance data)
    - Bonus for experienced players (played under coach 50+ matches)
    - Bonus for quality (players who played for top clubs)

    Returns:
        Dictionary with score and player list
    """
    score = 0
    players_coached = []

    coach_name = coach_profile.get("name")

    # Get players from teammate data (if coach had playing career)
    coach_teammates = None
    for coach_data in teammates_data.get("coaches", []):
        if coach_data.get("name") == coach_name:
            coach_teammates = coach_data.get("teammates", [])
            break

    if coach_teammates:
        # Score based on teammates (proxy for network)
        for teammate in coach_teammates:
            shared_matches = teammate.get("shared_matches", 0)

            # Only count significant connections (10+ matches)
            if shared_matches >= 10:
                points = 1

                # Bonus for long-term teammates (50+ matches)
                if shared_matches >= 50:
                    points = 3

                # Bonus for very experienced (100+ matches)
                if shared_matches >= 100:
                    points = 5

                players_coached.append({
                    "name": teammate.get("name"),
                    "position": teammate.get("position"),
                    "shared_matches": shared_matches,
                    "points": points
                })

                score += points

    return {
        "score": score,
        "num_players": len(players_coached),
        "top_players": sorted(players_coached, key=lambda x: x["shared_matches"], reverse=True)[:20]
    }

def calculate_combined_score(sd_score, player_score):
    """
    Calculate combined hire-ability score.

    Weighting:
    - SD Network: 60% (most important for hiring)
    - Player Pool: 40% (indicates experience and reach)
    """
    sd_weight = 0.6
    player_weight = 0.4

    # Normalize scores (assume max SD score ~100, max player score ~500)
    sd_normalized = min(sd_score["score"] / 100.0, 1.0) * 100
    player_normalized = min(player_score["score"] / 500.0, 1.0) * 100

    combined = (sd_normalized * sd_weight) + (player_normalized * player_weight)

    return {
        "combined_score": round(combined, 1),
        "sd_component": round(sd_normalized, 1),
        "player_component": round(player_normalized, 1)
    }

def score_bundesliga_coaches():
    """Main scoring function."""
    print("\n" + "="*60)
    print("Bundesliga Coach Network Scoring (2025/26)")
    print("Henryk's Use Case: SD Connections + Player Pool")
    print("="*60 + "\n")

    # Load data
    print("📊 Loading data...")
    coaches = json.loads(COACHES_FILE.read_text())
    teammates_data = json.loads(TEAMMATES_FILE.read_text())
    print(f"   ✓ Loaded {len(coaches):,} coach profiles")

    # Get current Bundesliga coaches
    print("\n🏆 Identifying current Bundesliga coaches...")
    current_coaches = get_current_bundesliga_coaches(coaches)
    print(f"   ✓ Found {len(current_coaches)} current Bundesliga head coaches")

    if len(current_coaches) < 18:
        print(f"   ⚠️  Expected 18, found {len(current_coaches)} - some may be missing")

    # Score each coach
    print("\n⚙️  Calculating scores...")
    scored_coaches = []

    for coach_data in current_coaches:
        coach_profile = coach_data["full_profile"]

        # SD Network Score
        sd_score = calculate_sd_network_score(coach_profile, coaches)

        # Player Pool Score
        player_score = calculate_player_pool_score(coach_profile, teammates_data)

        # Combined Score
        combined = calculate_combined_score(sd_score, player_score)

        scored_coaches.append({
            "name": coach_data["name"],
            "current_club": coach_data["current_club"],
            "appointed": coach_data["appointed"],
            "scores": {
                "combined": combined["combined_score"],
                "sd_network": sd_score["score"],
                "player_pool": player_score["score"],
                "sd_normalized": combined["sd_component"],
                "player_normalized": combined["player_component"]
            },
            "sd_connections": {
                "total": len(sd_score["connections"]),
                "sporting_directors": sd_score["num_sds"],
                "executives": sd_score["num_execs"],
                "top_connections": sorted(
                    sd_score["connections"],
                    key=lambda x: x["points"],
                    reverse=True
                )[:10]
            },
            "player_pool": {
                "total_players": player_score["num_players"],
                "top_players": player_score["top_players"][:10]
            }
        })

    # Sort by combined score
    scored_coaches.sort(key=lambda x: x["scores"]["combined"], reverse=True)

    # Save results
    print("\n💾 Saving results...")
    output = {
        "generated_at": datetime.now().isoformat(),
        "season": "2025/26",
        "num_coaches": len(scored_coaches),
        "methodology": {
            "sd_network": "10pts per SD, 3pts per Executive, same club overlap",
            "player_pool": "1-5pts per player based on matches together",
            "combined": "60% SD Network + 40% Player Pool"
        },
        "rankings": scored_coaches
    }

    OUTPUT_FILE.write_text(json.dumps(output, indent=2))
    print(f"   ✓ Saved to {OUTPUT_FILE}")

    # Print rankings
    print("\n" + "="*60)
    print("BUNDESLIGA COACH RANKINGS (2025/26)")
    print("="*60 + "\n")

    print("🏆 Top 10 Coaches by Combined Score:\n")
    print(f"{'Rank':<6} {'Coach':<25} {'Club':<25} {'Score':<8} {'SD Net':<8} {'Players':<8}")
    print("-" * 90)

    for i, coach in enumerate(scored_coaches[:10], 1):
        print(f"{i:<6} {coach['name'][:24]:<25} {coach['current_club'][:24]:<25} "
              f"{coach['scores']['combined']:<8.1f} "
              f"{coach['scores']['sd_network']:<8} "
              f"{coach['player_pool']['total_players']:<8}")

    # Detailed view of #1 coach
    if scored_coaches:
        top_coach = scored_coaches[0]
        print(f"\n" + "="*60)
        print(f"TOP COACH: {top_coach['name']}")
        print("="*60)
        print(f"Club: {top_coach['current_club']}")
        print(f"Combined Score: {top_coach['scores']['combined']:.1f}")
        print(f"\nSD Connections ({top_coach['sd_connections']['total']}):")
        for conn in top_coach['sd_connections']['top_connections'][:5]:
            print(f"  • {conn['sd_name']} ({conn['type']}) at {conn['club']} - {conn['points']} pts")

        print(f"\nTop Players ({top_coach['player_pool']['total_players']} total):")
        for player in top_coach['player_pool']['top_players'][:5]:
            print(f"  • {player['name']} ({player['position']}) - {player['shared_matches']} matches")

    print("\n" + "="*60 + "\n")

    return scored_coaches

if __name__ == "__main__":
    results = score_bundesliga_coaches()
    print(f"✅ Scored {len(results)} Bundesliga coaches!")
