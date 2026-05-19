#!/usr/bin/env python3
"""
OpenLigaDB Scraper - Bundesliga Match Data 2015-2026

Fetches comprehensive match data from OpenLigaDB API:
- Match results (home/away, scores)
- Match dates and times
- Teams (IDs, names, icons)
- Goals (minute, scorer, penalty/own goal flags)
- Matchday (Spieltag)

API Docs: https://api.openligadb.de/
"""

import requests
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# Configuration
API_BASE = "https://api.openligadb.de"
LEAGUES = {
    "bl1": "1. Bundesliga",
    "bl2": "2. Bundesliga"
}
START_SEASON = 2015
END_SEASON = 2025  # 2025/26 season
OUTPUT_DIR = Path("data/openligadb")
CACHE_DIR = Path("tmp/cache/openligadb")

# Create directories
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

def fetch_matches(league: str, season: int) -> Optional[List[Dict]]:
    """
    Fetch all matches for a league and season.

    Args:
        league: League shortcut (bl1, bl2)
        season: Season year (e.g., 2024 for 2024/25)

    Returns:
        List of match dictionaries or None if failed
    """
    url = f"{API_BASE}/getmatchdata/{league}/{season}"
    cache_file = CACHE_DIR / f"{league}_{season}_matches.json"

    # Check cache first
    if cache_file.exists():
        print(f"  ✓ Loading from cache: {league} {season}/{season+1}")
        return json.loads(cache_file.read_text())

    try:
        print(f"  → Fetching {league.upper()} {season}/{season+1}...", end=" ")
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        matches = response.json()

        # Cache the response
        cache_file.write_text(json.dumps(matches, indent=2))

        print(f"✓ {len(matches)} matches")
        time.sleep(0.5)  # Be nice to the API

        return matches

    except requests.exceptions.RequestException as e:
        print(f"✗ ERROR: {e}")
        return None

def parse_match(match_data: Dict) -> Dict:
    """
    Parse raw match data into simplified format.

    Args:
        match_data: Raw match dict from API

    Returns:
        Simplified match dictionary
    """
    # Extract final result
    final_result = next(
        (r for r in match_data.get("matchResults", [])
         if r.get("resultName") == "Endergebnis"),
        None
    )

    # Extract halftime result
    halftime_result = next(
        (r for r in match_data.get("matchResults", [])
         if r.get("resultName") == "Halbzeitergebnis"),
        None
    )

    parsed = {
        "match_id": match_data.get("matchID"),
        "date": match_data.get("matchDateTime"),
        "date_utc": match_data.get("matchDateTimeUTC"),
        "league": match_data.get("leagueShortcut"),
        "league_name": match_data.get("leagueName"),
        "season": match_data.get("leagueSeason"),
        "matchday": match_data.get("group", {}).get("groupName"),
        "matchday_order": match_data.get("group", {}).get("groupOrderID"),

        # Teams
        "team_home": {
            "id": match_data.get("team1", {}).get("teamId"),
            "name": match_data.get("team1", {}).get("teamName"),
            "short_name": match_data.get("team1", {}).get("shortName"),
            "icon_url": match_data.get("team1", {}).get("teamIconUrl")
        },
        "team_away": {
            "id": match_data.get("team2", {}).get("teamId"),
            "name": match_data.get("team2", {}).get("teamName"),
            "short_name": match_data.get("team2", {}).get("shortName"),
            "icon_url": match_data.get("team2", {}).get("teamIconUrl")
        },

        # Results
        "is_finished": match_data.get("matchIsFinished"),
        "score_final": {
            "home": final_result.get("pointsTeam1") if final_result else None,
            "away": final_result.get("pointsTeam2") if final_result else None
        } if final_result else None,
        "score_halftime": {
            "home": halftime_result.get("pointsTeam1") if halftime_result else None,
            "away": halftime_result.get("pointsTeam2") if halftime_result else None
        } if halftime_result else None,

        # Goals
        "goals": [
            {
                "minute": goal.get("matchMinute"),
                "score_home": goal.get("scoreTeam1"),
                "score_away": goal.get("scoreTeam2"),
                "scorer_id": goal.get("goalGetterID"),
                "scorer_name": goal.get("goalGetterName"),
                "is_penalty": goal.get("isPenalty"),
                "is_own_goal": goal.get("isOwnGoal"),
                "is_overtime": goal.get("isOvertime"),
                "comment": goal.get("comment")
            }
            for goal in match_data.get("goals", [])
        ],

        "last_updated": match_data.get("lastUpdateDateTime")
    }

    return parsed

def scrape_all_matches():
    """
    Scrape all Bundesliga matches from 2015-2026.
    """
    print("\n" + "="*60)
    print("OpenLigaDB Scraper - Bundesliga Match Data")
    print("="*60 + "\n")

    all_matches = []
    stats = {
        "total_seasons": 0,
        "total_matches": 0,
        "leagues": {}
    }

    # Scrape each league and season
    for league_code, league_name in LEAGUES.items():
        print(f"\n📊 {league_name}")
        print("-" * 40)

        league_matches = []

        for season in range(START_SEASON, END_SEASON + 1):
            matches = fetch_matches(league_code, season)

            if matches:
                # Parse each match
                for match in matches:
                    parsed = parse_match(match)
                    parsed["league_full_name"] = league_name
                    league_matches.append(parsed)

                stats["total_seasons"] += 1
                stats["total_matches"] += len(matches)

        # Save league-specific file
        league_file = OUTPUT_DIR / f"{league_code}_matches_2015_2026.json"
        league_file.write_text(json.dumps(league_matches, indent=2))
        print(f"\n  ✓ Saved {len(league_matches)} matches to {league_file.name}")

        stats["leagues"][league_code] = {
            "name": league_name,
            "matches": len(league_matches)
        }

        all_matches.extend(league_matches)

    # Save combined file
    combined_file = OUTPUT_DIR / "bundesliga_all_matches_2015_2026.json"
    combined_file.write_text(json.dumps(all_matches, indent=2))

    # Generate summary
    print("\n" + "="*60)
    print("SCRAPING COMPLETE")
    print("="*60)
    print(f"\n✓ Total Seasons Scraped: {stats['total_seasons']}")
    print(f"✓ Total Matches: {stats['total_matches']:,}")
    print(f"\n📁 Output Files:")
    print(f"   • Combined: {combined_file}")

    for league_code, league_stats in stats["leagues"].items():
        print(f"   • {league_stats['name']}: {league_stats['matches']:,} matches")

    # Calculate match statistics
    finished_matches = [m for m in all_matches if m.get("is_finished")]
    upcoming_matches = [m for m in all_matches if not m.get("is_finished")]

    print(f"\n📈 Match Status:")
    print(f"   • Finished: {len(finished_matches):,}")
    print(f"   • Upcoming: {len(upcoming_matches):,}")

    # Save summary
    summary = {
        "scrape_date": datetime.now().isoformat(),
        "seasons": f"{START_SEASON}-{END_SEASON}",
        "leagues": stats["leagues"],
        "total_matches": stats["total_matches"],
        "finished_matches": len(finished_matches),
        "upcoming_matches": len(upcoming_matches),
        "files": {
            "combined": str(combined_file),
            "by_league": {
                league_code: f"{league_code}_matches_2015_2026.json"
                for league_code in LEAGUES.keys()
            }
        }
    }

    summary_file = OUTPUT_DIR / "scrape_summary.json"
    summary_file.write_text(json.dumps(summary, indent=2))
    print(f"\n📄 Summary saved to: {summary_file}")

    print("\n" + "="*60 + "\n")

    return all_matches, summary

if __name__ == "__main__":
    matches, summary = scrape_all_matches()
    print(f"✅ Successfully scraped {len(matches):,} matches!")
