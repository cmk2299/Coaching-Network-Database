#!/usr/bin/env python3
"""
Build Player-Coach Connection Network

Identifies which players played under which coaches by matching:
- Player career periods at clubs
- Coach tenure periods at same clubs

Output: Player-Coach edges for network graph
"""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Optional
import re
from collections import defaultdict

# Paths
COACHES_FILE = Path("data/coaches_with_match_performance.json")
PLAYERS_DIR = Path("data/bundesliga_players_2015_2026/profiles")
OUTPUT_FILE = Path("data/player_coach_connections.json")

def normalize_team_name(team_name: str) -> str:
    """Normalize team name for matching (reuse logic from coach integration)."""
    if not team_name:
        return ""

    normalized = team_name.strip()

    # Common normalizations
    mappings = {
        "bayern": "FC Bayern München",
        "dortmund": "Borussia Dortmund",
        "leipzig": "RB Leipzig",
        "leverkusen": "Bayer 04 Leverkusen",
        "freiburg": "SC Freiburg",
        "union berlin": "1. FC Union Berlin",
        "stuttgart": "VfB Stuttgart",
        "frankfurt": "Eintracht Frankfurt",
        "gladbach": "Borussia Mönchengladbach",
        "mönchengladbach": "Borussia Mönchengladbach",
        "wolfsburg": "VfL Wolfsburg",
        "hoffenheim": "TSG 1899 Hoffenheim",
        "heidenheim": "1. FC Heidenheim",
        "bremen": "SV Werder Bremen",
        "augsburg": "FC Augsburg",
        "mainz": "1. FSV Mainz 05",
        "köln": "1. FC Köln",
        "bochum": "VfL Bochum",
        "hertha": "Hertha BSC",
        "schalke": "FC Schalke 04",
    }

    normalized_lower = normalized.lower()

    # Check for keyword matches
    for keyword, canonical in mappings.items():
        if keyword in normalized_lower:
            # Exclude youth teams
            if any(x in normalized_lower for x in ['u19', 'u23', 'u21', 'u17', 'ii', 'jgd', 'jugend']):
                continue
            return canonical

    return normalized

def parse_season_to_years(season: str) -> Optional[tuple]:
    """
    Parse season string to start/end years.

    Examples:
    - "2015/2016" -> (2015, 2016)
    - "15/16" -> (2015, 2016)
    """
    if not season:
        return None

    # Extract year patterns
    pattern = r'(\d{2,4})[/\-](\d{2,4})'
    match = re.search(pattern, season)

    if not match:
        return None

    start_str, end_str = match.groups()

    # Convert to full years
    start = int(start_str)
    end = int(end_str)

    # Handle 2-digit years
    if start < 100:
        start = 2000 + start if start < 50 else 1900 + start
    if end < 100:
        end = 2000 + end if end < 50 else 1900 + end

    return (start, end)

def parse_coach_tenure_dates(period_str: str) -> Optional[tuple]:
    """Parse coach tenure period to start/end years."""
    if not period_str:
        return None

    try:
        # Extract dates in DD.MM.YYYY format
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
        elif "Present" in period_str or "vsl" in period_str:
            end = datetime.now()
        else:
            return None

        return (start.year, end.year)

    except Exception:
        return None

def seasons_overlap(player_seasons: List[tuple], coach_years: tuple) -> List[str]:
    """
    Check which seasons a player and coach overlapped.

    Args:
        player_seasons: List of (start_year, end_year) tuples
        coach_years: (start_year, end_year) tuple

    Returns:
        List of overlapping season strings (e.g., ["2015/16", "2016/17"])
    """
    overlapping = []
    coach_start, coach_end = coach_years

    for player_start, player_end in player_seasons:
        # Check if years overlap
        if player_end >= coach_start and player_start <= coach_end:
            # Determine overlapping years
            overlap_start = max(player_start, coach_start)
            overlap_end = min(player_end, coach_end)

            for year in range(overlap_start, overlap_end + 1):
                season = f"{year}/{year+1}"
                if season not in overlapping:
                    overlapping.append(season)

    return overlapping

def build_connections():
    """Main function to build player-coach connections."""
    print("\n" + "="*60)
    print("Building Player-Coach Connection Network")
    print("="*60 + "\n")

    # Load coaches
    print("📊 Loading coach data...")
    coaches = json.loads(COACHES_FILE.read_text())
    print(f"   ✓ Loaded {len(coaches):,} coaches")

    # Build coach tenure index by club
    print("\n🔍 Indexing coach tenures by club...")
    coach_by_club = defaultdict(list)

    for coach in coaches:
        for entry in coach.get("career_history", []):
            club = normalize_team_name(entry.get("club", ""))
            role = entry.get("role", "").lower()
            period = entry.get("period", "")

            # Only head coaches/trainers
            if not any(kw in role for kw in ["trainer", "manager", "coach"]):
                continue
            if any(kw in role for kw in ["co-trainer", "assistant", "assistent", "interim"]):
                continue

            years = parse_coach_tenure_dates(period)
            if not years or not club:
                continue

            coach_by_club[club].append({
                "coach_name": coach.get("name"),
                "coach_url": coach.get("url"),
                "role": entry.get("role"),
                "period": period,
                "years": years
            })

    print(f"   ✓ Indexed {len(coach_by_club)} clubs")

    # Load players
    print("\n👥 Loading player profiles...")
    player_files = list(PLAYERS_DIR.glob("*.json"))
    print(f"   ✓ Found {len(player_files):,} player profiles")

    # Build connections
    print("\n⚙️  Matching players with coaches...")
    connections = []
    stats = {
        "players_processed": 0,
        "players_with_connections": 0,
        "total_connections": 0,
        "clubs_matched": set()
    }

    for i, player_file in enumerate(player_files, 1):
        if i % 200 == 0:
            print(f"   → Processed {i:,}/{len(player_files):,} players...")

        try:
            player = json.loads(player_file.read_text())
            stats["players_processed"] += 1

            player_name = player.get("name", "Unknown")
            player_url = player.get("url", "")

            player_connections_found = False

            # Check each career entry
            for career_entry in player.get("career_history", []):
                club = normalize_team_name(career_entry.get("club", ""))
                season = career_entry.get("season", "")

                if not club or not season:
                    continue

                # Parse player season
                season_years = parse_season_to_years(season)
                if not season_years:
                    continue

                # Check if club has coaches
                if club not in coach_by_club:
                    continue

                # Match with coaches at same club
                for coach_tenure in coach_by_club[club]:
                    overlapping_seasons = seasons_overlap([season_years], coach_tenure["years"])

                    if overlapping_seasons:
                        connection = {
                            "player_name": player_name,
                            "player_url": player_url,
                            "coach_name": coach_tenure["coach_name"],
                            "coach_url": coach_tenure["coach_url"],
                            "club": club,
                            "seasons": overlapping_seasons,
                            "num_seasons": len(overlapping_seasons),
                            "player_season": season,
                            "coach_period": coach_tenure["period"],
                            "coach_role": coach_tenure["role"]
                        }

                        connections.append(connection)
                        stats["total_connections"] += 1
                        stats["clubs_matched"].add(club)
                        player_connections_found = True

            if player_connections_found:
                stats["players_with_connections"] += 1

        except Exception as e:
            print(f"   ⚠️  Error processing {player_file.name}: {e}")
            continue

    # Save connections
    print("\n💾 Saving connections...")
    OUTPUT_FILE.write_text(json.dumps(connections, indent=2))
    print(f"   ✓ Saved to {OUTPUT_FILE}")

    # Print statistics
    print("\n" + "="*60)
    print("CONNECTION BUILD COMPLETE")
    print("="*60)
    print(f"\n✓ Players Processed: {stats['players_processed']:,}")
    print(f"✓ Players with Coach Connections: {stats['players_with_connections']:,} ({stats['players_with_connections']/stats['players_processed']*100:.1f}%)")
    print(f"\n✓ Total Player-Coach Connections: {stats['total_connections']:,}")
    print(f"✓ Clubs Matched: {len(stats['clubs_matched'])}")

    # Top connections
    print("\n🏆 Top Players by Coach Connections:")
    player_conn_counts = defaultdict(int)
    for conn in connections:
        player_conn_counts[conn["player_name"]] += 1

    top_players = sorted(player_conn_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    for i, (player, count) in enumerate(top_players, 1):
        print(f"   {i:2}. {player}: {count} connections")

    print("\n🏆 Top Coaches by Player Connections:")
    coach_conn_counts = defaultdict(int)
    for conn in connections:
        coach_conn_counts[conn["coach_name"]] += 1

    top_coaches = sorted(coach_conn_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    for i, (coach, count) in enumerate(top_coaches, 1):
        print(f"   {i:2}. {coach}: {count} players")

    # Sample connections
    print("\n📋 Sample Connections:")
    for conn in connections[:5]:
        seasons_str = ", ".join(conn["seasons"][:3])
        if len(conn["seasons"]) > 3:
            seasons_str += f" (+{len(conn['seasons'])-3} more)"
        print(f"   • {conn['player_name']} under {conn['coach_name']}")
        print(f"     at {conn['club']} ({seasons_str})")

    print("\n" + "="*60 + "\n")

    return connections, stats

if __name__ == "__main__":
    connections, stats = build_connections()
    print(f"✅ Built {stats['total_connections']:,} player-coach connections!")
