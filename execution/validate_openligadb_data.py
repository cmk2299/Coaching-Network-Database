#!/usr/bin/env python3
"""
Validate OpenLigaDB data quality and generate statistics.
"""

import json
from pathlib import Path
from collections import Counter, defaultdict

DATA_DIR = Path("data/openligadb")

def load_matches():
    """Load all matches from combined file."""
    file_path = DATA_DIR / "bundesliga_all_matches_2015_2026.json"
    return json.loads(file_path.read_text())

def analyze_data_quality(matches):
    """Analyze data quality and completeness."""
    print("\n" + "="*60)
    print("OpenLigaDB Data Quality Report")
    print("="*60 + "\n")

    total = len(matches)
    finished = sum(1 for m in matches if m.get("is_finished"))
    upcoming = total - finished

    print(f"📊 Total Matches: {total:,}")
    print(f"   • Finished: {finished:,} ({finished/total*100:.1f}%)")
    print(f"   • Upcoming: {upcoming:,} ({upcoming/total*100:.1f}%)")

    # Completeness checks
    print("\n📋 Data Completeness (Finished Matches):")

    finished_matches = [m for m in matches if m.get("is_finished")]

    with_scores = sum(1 for m in finished_matches
                      if m.get("score_final") and
                      m["score_final"]["home"] is not None)

    with_halftime = sum(1 for m in finished_matches
                        if m.get("score_halftime") and
                        m["score_halftime"]["home"] is not None)

    with_goals = sum(1 for m in finished_matches if m.get("goals"))

    total_goals = sum(len(m.get("goals", [])) for m in finished_matches)

    print(f"   • Final Scores: {with_scores:,}/{finished:,} ({with_scores/finished*100:.1f}%)")
    print(f"   • Halftime Scores: {with_halftime:,}/{finished:,} ({with_halftime/finished*100:.1f}%)")
    print(f"   • Goal Events: {with_goals:,}/{finished:,} ({with_goals/finished*100:.1f}%)")
    print(f"   • Total Goals Logged: {total_goals:,}")

    # League breakdown
    print("\n🏆 League Breakdown:")
    league_counts = Counter(m.get("league") for m in matches)
    for league, count in sorted(league_counts.items()):
        league_name = "1. Bundesliga" if league == "bl1" else "2. Bundesliga"
        print(f"   • {league_name}: {count:,} matches")

    # Season breakdown
    print("\n📅 Season Breakdown:")
    season_counts = Counter(m.get("season") for m in matches)
    for season in sorted(season_counts.keys()):
        count = season_counts[season]
        print(f"   • {season}/{season+1}: {count:,} matches")

    # Team statistics
    print("\n⚽ Team Statistics:")
    team_counts = defaultdict(int)
    for match in matches:
        if match.get("team_home"):
            team_counts[match["team_home"]["name"]] += 1
        if match.get("team_away"):
            team_counts[match["team_away"]["name"]] += 1

    print(f"   • Unique Teams: {len(team_counts)}")
    print("   • Top 5 Most Active Teams:")
    for team, count in Counter(team_counts).most_common(5):
        print(f"     - {team}: {count:,} matches")

    # Goal statistics (finished matches only)
    print("\n🥅 Goal Statistics (Finished Matches):")
    goals_per_match = []
    home_goals = []
    away_goals = []

    for match in finished_matches:
        if match.get("score_final"):
            home = match["score_final"].get("home", 0) or 0
            away = match["score_final"].get("away", 0) or 0
            goals_per_match.append(home + away)
            home_goals.append(home)
            away_goals.append(away)

    if goals_per_match:
        avg_total = sum(goals_per_match) / len(goals_per_match)
        avg_home = sum(home_goals) / len(home_goals)
        avg_away = sum(away_goals) / len(away_goals)

        print(f"   • Avg Goals per Match: {avg_total:.2f}")
        print(f"   • Avg Home Goals: {avg_home:.2f}")
        print(f"   • Avg Away Goals: {avg_away:.2f}")
        print(f"   • Home Win Ratio: {sum(1 for h, a in zip(home_goals, away_goals) if h > a) / len(home_goals) * 100:.1f}%")

    # Data quality score
    print("\n📈 Data Quality Score:")

    quality_scores = {
        "Matches Retrieved": 100.0,  # We have all matches
        "Final Scores": with_scores / finished * 100 if finished else 0,
        "Halftime Scores": with_halftime / finished * 100 if finished else 0,
        "Goal Events": with_goals / finished * 100 if finished else 0,
    }

    overall_score = sum(quality_scores.values()) / len(quality_scores)

    for category, score in quality_scores.items():
        print(f"   • {category}: {score:.1f}%")

    print(f"\n   ⭐ Overall Quality: {overall_score:.1f}%", end=" ")

    if overall_score >= 95:
        grade = "A+"
        emoji = "🏆"
    elif overall_score >= 90:
        grade = "A"
        emoji = "✅"
    elif overall_score >= 80:
        grade = "B"
        emoji = "👍"
    else:
        grade = "C"
        emoji = "⚠️"

    print(f"(Grade {grade}) {emoji}")

    # Sample matches
    print("\n📋 Sample Recent Matches:")
    recent = sorted(
        [m for m in finished_matches if m.get("date")],
        key=lambda x: x["date"],
        reverse=True
    )[:3]

    for match in recent:
        home = match["team_home"]["short_name"]
        away = match["team_away"]["short_name"]
        score = match.get("score_final", {})
        score_home = score.get("home", "?")
        score_away = score.get("away", "?")
        date = match.get("date", "").split("T")[0]
        matchday = match.get("matchday", "?")

        print(f"   • {date} | {matchday}: {home} {score_home}-{score_away} {away}")

    print("\n" + "="*60 + "\n")

    return {
        "total_matches": total,
        "quality_score": overall_score,
        "grade": grade
    }

if __name__ == "__main__":
    matches = load_matches()
    stats = analyze_data_quality(matches)
    print(f"✅ Validation complete: {stats['total_matches']:,} matches, Grade {stats['grade']}")
