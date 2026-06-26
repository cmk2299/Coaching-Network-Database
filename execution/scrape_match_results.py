#!/usr/bin/env python3
"""
Scrape match results & standings from openligadb for BL1/BL2/BL3.

Powers Hot-Seat-Prediction (next: calc_hot_seat_score.py).

Output:
  data/match_results/bl1_2025.json — full season match list
  data/match_results/bl2_2025.json
  data/match_results/bl3_2025.json
  data/match_results/standings_bl1_2025.json — current Tabelle
  data/match_results/club_form_2025.json — derived per-club: last_5_ppg, position, streak

Usage:
  python3 execution/scrape_match_results.py
  python3 execution/scrape_match_results.py --leagues bl1 bl2
  python3 execution/scrape_match_results.py --season 2025
"""
import argparse
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent.parent
DATA = BASE / "data" / "match_results"
DATA.mkdir(parents=True, exist_ok=True)

LEAGUES = ["bl1", "bl2", "bl3"]
DEFAULT_SEASON = 2025  # 2025/26 season

API_BASE = "https://api.openligadb.de"


def fetch(url: str, timeout: int = 20) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": "projectFIVE/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def fetch_matches(league: str, season: int) -> list:
    return fetch(f"{API_BASE}/getmatchdata/{league}/{season}")


def fetch_table(league: str, season: int) -> list:
    """Current Tabelle. Returns list of {teamName, teamId, points, won, lost, ...}."""
    return fetch(f"{API_BASE}/getbltable/{league}/{season}")


def parse_match(m: dict) -> dict:
    """Compact form of a match. Picks final result from matchResults."""
    final = next(
        (r for r in m.get("matchResults", []) if r.get("resultOrderID") == 2),
        None,
    ) or (m.get("matchResults", [{}])[-1] if m.get("matchResults") else {})
    return {
        "match_id": m["matchID"],
        "date": m["matchDateTime"],
        "matchday": m.get("group", {}).get("groupOrderID"),
        "team1_id": m["team1"]["teamId"],
        "team1_name": m["team1"]["teamName"],
        "team2_id": m["team2"]["teamId"],
        "team2_name": m["team2"]["teamName"],
        "score1": final.get("pointsTeam1") if final else None,
        "score2": final.get("pointsTeam2") if final else None,
        "finished": m.get("matchIsFinished", False),
    }


def compute_club_form(matches: list, club_id: int) -> dict:
    """Per-club form metrics needed for hot-seat scoring."""
    finished = [m for m in matches if m["finished"] and (
        m["team1_id"] == club_id or m["team2_id"] == club_id
    )]
    finished.sort(key=lambda m: m["date"])

    # Last 5 finished matches
    last5 = finished[-5:] if len(finished) >= 5 else finished

    points = 0
    wins = 0; draws = 0; losses = 0
    goals_for = 0; goals_against = 0
    for m in last5:
        if m["team1_id"] == club_id:
            gf, ga = m["score1"], m["score2"]
        else:
            gf, ga = m["score2"], m["score1"]
        goals_for += gf; goals_against += ga
        if gf > ga: points += 3; wins += 1
        elif gf == ga: points += 1; draws += 1
        else: losses += 1

    last5_ppg = (points / len(last5)) if last5 else 0.0
    last5_gd = goals_for - goals_against

    # Days since last win
    days_since_win = None
    for m in reversed(finished):
        own = m["score1"] if m["team1_id"] == club_id else m["score2"]
        opp = m["score2"] if m["team1_id"] == club_id else m["score1"]
        if own > opp:
            try:
                wd = datetime.fromisoformat(m["date"].replace("Z", "+00:00"))
                if wd.tzinfo is None:
                    wd = wd.replace(tzinfo=timezone.utc)
                days_since_win = (datetime.now(timezone.utc) - wd).days
            except Exception:
                pass
            break

    # Winless streak
    winless = 0
    for m in reversed(finished):
        own = m["score1"] if m["team1_id"] == club_id else m["score2"]
        opp = m["score2"] if m["team1_id"] == club_id else m["score1"]
        if own > opp:
            break
        winless += 1

    return {
        "matches_played": len(finished),
        "last5_ppg": round(last5_ppg, 2),
        "last5_record": f"{wins}W-{draws}D-{losses}L",
        "last5_goal_diff": last5_gd,
        "days_since_win": days_since_win,
        "winless_streak": winless,
        "last5_dates": [m["date"][:10] for m in last5],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--leagues", nargs="+", default=LEAGUES,
                        help="Ligen (bl1/bl2/bl3). Default: alle.")
    parser.add_argument("--season", type=int, default=DEFAULT_SEASON,
                        help="Season (Jahr des Saison-Starts). Default: 2025.")
    args = parser.parse_args()

    club_form = {}  # {teamId: {league, name, ...form metrics}}
    for league in args.leagues:
        print(f"\n=== {league.upper()} {args.season}/{args.season+1} ===")
        try:
            raw_matches = fetch_matches(league, args.season)
        except Exception as e:
            print(f"  ✗ Fetch failed: {e}")
            continue
        matches = [parse_match(m) for m in raw_matches]
        finished_n = sum(1 for m in matches if m["finished"])
        print(f"  Matches: {len(matches)} total, {finished_n} finished")

        # Save raw match list (compacted)
        with open(DATA / f"{league}_{args.season}.json", "w") as f:
            json.dump(matches, f, ensure_ascii=False, indent=2)

        # Standings
        try:
            table = fetch_table(league, args.season)
        except Exception as e:
            print(f"  ⚠ Table fetch failed: {e}")
            table = []
        with open(DATA / f"standings_{league}_{args.season}.json", "w") as f:
            json.dump(table, f, ensure_ascii=False, indent=2)

        # Per-club form
        teams_by_id = {}
        for m in matches:
            teams_by_id.setdefault(m["team1_id"], m["team1_name"])
            teams_by_id.setdefault(m["team2_id"], m["team2_name"])

        for tid, tname in teams_by_id.items():
            form = compute_club_form(matches, tid)
            # Find table position
            pos = None
            for i, row in enumerate(table, 1):
                if row.get("teamInfoId") == tid or row.get("teamId") == tid:
                    pos = i; break
            club_form[str(tid)] = {
                "league": league.upper(),
                "season": args.season,
                "name": tname,
                "position": pos,
                "table_size": len(table) or None,
                **form,
            }
        print(f"  Saved {league}_{args.season}.json + standings_{league}_{args.season}.json")

    # Combined form file
    with open(DATA / f"club_form_{args.season}.json", "w") as f:
        json.dump({
            "_meta": {
                "season": args.season,
                "scraped_at": datetime.now(timezone.utc).isoformat(),
                "source": "openligadb.de",
                "leagues": args.leagues,
            },
            "clubs": club_form,
        }, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Combined form: {len(club_form)} clubs → {DATA}/club_form_{args.season}.json")
    # Show preview of clubs with worst PPG (potential hot-seats)
    sorted_clubs = sorted(
        club_form.items(),
        key=lambda kv: (kv[1].get("last5_ppg", 0), -(kv[1].get("position") or 99))
    )
    print("\nWorst recent form (last 5 PPG):")
    for tid, c in sorted_clubs[:8]:
        pos = f"#{c['position']}" if c['position'] else "?"
        print(f"  {c['league']:<3}  {pos:<4}  {c['name']:<28}  PPG={c['last5_ppg']:.2f}  "
              f"({c['last5_record']})  GD={c['last5_goal_diff']:+d}  winless={c['winless_streak']}")


if __name__ == "__main__":
    main()
