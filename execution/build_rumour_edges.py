#!/usr/bin/env python3
"""Turn scraped player rumours into "club wanted player" edges and attribute them
to the head coach and sporting decision-makers in office at the interested club.

Input:  data/rumours/spieler_<id>.json   (scrape_player_rumours.py)
Output: data/rumour_edges.json

An edge is an inference, not a fact: TM rumours are community-curated with press
sources, and "the club was linked with the player while X was in office" does not
prove that X personally wanted the player.

Outcome of a rumour:
  happened      player appears in the interested club's squad in the rumour
                season or the one after, or plays there now
  not_happened  the club's squads for those seasons are on disk and the player
                is not in them
  unknown       no squad coverage for that club/season, or the rumour is open
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "execution"))

from lib.normalization import current_season_year  # noqa: E402

RUMOURS_DIR = BASE / "data" / "rumours"
SQUADS_DIR = BASE / "data" / "squads"
PROFILES_DIR = BASE / "data" / "person_profiles"
NETWORKS_DIR = BASE / "data" / "networks"
OUT = BASE / "data" / "rumour_edges.json"

_DATE = re.compile(r"\((\d{2})\.(\d{2})\.(\d{4})\)")
HEAD_COACH_ROLES = {"trainer", "cheftrainer", "teamchef", "spielertrainer"}
SPORT_LEAD_KEYWORDS = ("sportdirektor", "sportvorstand", "geschäftsführer sport", "sportchef",
                       "sportlicher leiter", "direktor sport", "technischer direktor",
                       "kaderplaner", "manager", "leiter lizenz", "direktor profifußball")


def season_of(day: date) -> int:
    return day.year if day.month >= 7 else day.year - 1


def parse_tm_date(text: str) -> date | None:
    """'23/24 (04.07.2023)' → date(2023, 7, 4); '-' or missing → None."""
    found = _DATE.search(text or "")
    return date(int(found[3]), int(found[2]), int(found[1])) if found else None


def role_type(role: str) -> str | None:
    lowered = (role or "").strip().lower()
    if lowered in HEAD_COACH_ROLES:
        return "head_coach"
    if any(k in lowered for k in SPORT_LEAD_KEYWORDS):
        return "sport_lead"
    return None


def load_tenures() -> dict[int, list[dict]]:
    """club_tm_id → tenures of head coaches / sporting leads (from trainer profiles)."""
    tenures = defaultdict(list)
    today = date.today()
    for path in PROFILES_DIR.glob("trainer_*.json"):
        try:
            profile = json.load(open(path))
        except ValueError:
            continue
        for entry in profile.get("career_history") or []:
            kind = role_type(entry.get("role"))
            start = parse_tm_date(entry.get("date_from"))
            if not kind or not start or not entry.get("club_tm_id"):
                continue
            tenures[int(entry["club_tm_id"])].append({
                "tm_id": int(profile["tm_id"]), "name": profile.get("name"),
                "role": entry.get("role"), "role_type": kind,
                "from": start, "to": parse_tm_date(entry.get("date_to")) or today,
            })
    return tenures


class Squads:
    """Lazy lookup of player ids per (club, season)."""

    def __init__(self):
        self._cache: dict[tuple[int, int], set[int] | None] = {}

    def players(self, club_id: int, season: int) -> set[int] | None:
        key = (club_id, season)
        if key not in self._cache:
            path = SQUADS_DIR / f"{club_id}_{season}.json"
            if path.exists():
                squad = json.load(open(path)).get("players", [])
                # An empty file is a placeholder, not evidence that nobody played there.
                self._cache[key] = {int(p["tm_id"]) for p in squad if p.get("tm_id")} or None
            else:
                self._cache[key] = None
        return self._cache[key]


def outcome(rumour: dict, player_id: int, current_club_id: int | None,
            squads: Squads, this_season: int) -> str:
    if rumour["status"] == "open" or not rumour.get("last_source_date"):
        return "unknown"
    club_id = rumour["club_tm_id"]
    if current_club_id == club_id:
        return "happened"
    season = season_of(date.fromisoformat(rumour["last_source_date"]))
    checked = 0
    for s in (season, season + 1):
        if s > this_season:
            continue
        ids = squads.players(club_id, s)
        if ids is None:
            return "unknown"
        if player_id in ids:
            return "happened"
        checked += 1
    return "not_happened" if checked else "unknown"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    tenures = load_tenures()
    squads = Squads()
    this_season = current_season_year()
    network_ids = {int(p.stem) for p in NETWORKS_DIR.glob("*.json") if p.stem.isdigit()}

    stats = Counter()
    edges = []
    for path in sorted(RUMOURS_DIR.glob("spieler_*.json")):
        record = json.load(open(path))
        player_id = int(record["tm_id"])
        stats["players"] += 1
        stats["players_with_rumours"] += bool(record["rumours"])
        profile_path = PROFILES_DIR / f"spieler_{player_id}.json"
        current_club = (json.load(open(profile_path)).get("current_club")
                        if profile_path.exists() else None)
        current_club_id = current_club.get("tm_id") if isinstance(current_club, dict) else None

        seen = set()
        for rumour in record["rumours"]:
            # TM lists re-opened rumours for the same club more than once.
            key = (rumour["club_tm_id"], rumour.get("last_source_date"))
            if key in seen:
                continue
            seen.add(key)
            stats["rumours"] += 1
            result = outcome(rumour, player_id, current_club_id, squads, this_season)
            stats[f"outcome_{result}"] += 1
            if result != "not_happened":
                continue
            day = date.fromisoformat(rumour["last_source_date"])
            in_office = [t for t in tenures.get(rumour["club_tm_id"], [])
                         if t["from"] <= day <= t["to"]]
            stats["not_happened_with_attribution"] += bool(in_office)
            for t in in_office:
                edges.append({
                    "person_tm_id": t["tm_id"], "person_name": t["name"],
                    "person_role": t["role"], "role_type": t["role_type"],
                    "has_network": t["tm_id"] in network_ids,
                    "club": rumour["club"], "club_tm_id": rumour["club_tm_id"],
                    "player_tm_id": player_id, "player_name": record.get("name"),
                    "date": rumour["last_source_date"],
                    "thread_url": rumour.get("thread_url"),
                })

    stats["edges"] = len(edges)
    stats["edges_head_coach"] = sum(e["role_type"] == "head_coach" for e in edges)
    stats["edges_sport_lead"] = sum(e["role_type"] == "sport_lead" for e in edges)
    stats["persons_with_edges"] = len({e["person_tm_id"] for e in edges})
    stats["persons_with_edges_and_network"] = len({e["person_tm_id"] for e in edges
                                                   if e["has_network"]})
    OUT.write_text(json.dumps({"generated_at": date.today().isoformat(),
                               "stats": dict(stats), "edges": edges},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    if not args.quiet:
        for k, v in stats.items():
            print(f"  {k}: {v}")
        top = Counter((e["person_name"], e["role_type"]) for e in edges if e["has_network"])
        print("  Top persons with a network:")
        for (name, kind), n in top.most_common(12):
            print(f"    {n:4d}  {name} ({kind})")
    print(f"→ {OUT}")


if __name__ == "__main__":
    main()
