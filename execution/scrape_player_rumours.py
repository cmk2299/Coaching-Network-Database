#!/usr/bin/env python3
"""Scrape Transfermarkt rumour pages (open rumours + Gerüchtearchiv) per player.

TM only has rumours for players (there is no rumour page for coaches), and the
archive of past rumours exists only on the player page — one request per player.

Output: data/rumours/spieler_<id>.json
Resumable: players whose output file is younger than --max-age-days are skipped.

Usage:
  python3 execution/scrape_player_rumours.py --leagues BL1,BL2,BL3
  python3 execution/scrape_player_rumours.py --ids 598577 679423
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "execution"))

import scrape_person_profiles as SPP  # noqa: E402
from lib.normalization import current_season_label, current_season_year  # noqa: E402

# We apply our own randomized delay; fixed intervals are a detectable pattern.
SPP.REQUEST_DELAY = 0

OUT_DIR = BASE / "data" / "rumours"
SQUADS_DIR = BASE / "data" / "squads"
DELAY_MIN, DELAY_MAX = 6.0, 12.0
BLOCK_STREAK = 10  # consecutive failures → assume IP block, stop the run

_CLUB_ID = re.compile(r"/geruechte/verein/(\d+)")
_THREAD_ID = re.compile(r"/thread_id/(\d+)")


def _first_int(pattern: re.Pattern, href: str) -> int | None:
    found = pattern.findall(href)
    return int(found[0]) if found else None


def _iso(date_str: str) -> str | None:
    """'13.09.2026' → '2026-09-13'."""
    try:
        return datetime.strptime(date_str.strip(), "%d.%m.%Y").date().isoformat()
    except ValueError:
        return None


def parse_rumour_page(html: str) -> dict:
    """Return {"name": str|None, "rumours": [...]} from a player rumour page.

    Each rumour: club, club_tm_id, status ("open" | "archived"),
    last_source_date, last_reply_date, probability (int percent or None),
    thread_id, thread_url.
    """
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""
    name = title.split(" - Gerüchte")[0].strip() if " - Gerüchte" in title else None

    rumours = []
    for box in soup.select("div.box"):
        headline = box.select_one("h2, .content-box-headline")
        table = box.select_one("table.items")
        if not headline or not table:
            continue
        label = headline.get_text(" ", strip=True)
        if label == "Gerüchtearchiv":
            status = "archived"
        elif label == "Gerüchte":
            status = "open"
        else:
            continue
        for row in table.select("tbody > tr"):
            cells = row.find_all("td", recursive=False)
            if len(cells) < 5:
                continue
            club_link = cells[1].find("a", href=_CLUB_ID)
            if not club_link:
                continue
            thread_link = row.find("a", href=_THREAD_ID)
            thread_id = _first_int(_THREAD_ID, thread_link["href"]) if thread_link else None
            probability = re.match(r"(\d+)\s*%", cells[4].get_text(strip=True))
            rumours.append({
                "club": club_link.get("title") or club_link.get_text(strip=True),
                "club_tm_id": _first_int(_CLUB_ID, club_link["href"]),
                "status": status,
                "last_source_date": _iso(cells[2].get_text(strip=True)),
                "last_reply_date": _iso(cells[3].get_text(strip=True)),
                "probability": int(probability.group(1)) if probability else None,
                "thread_id": thread_id,
                "thread_url": (thread_link["href"].split("/post_id/")[0].split("/page/")[0]
                               if thread_link else None),
            })
    return {"name": name, "rumours": rumours}


def current_squad_player_ids(leagues: set[str]) -> list[int]:
    """Player ids in the current-season squads of clubs in the given leagues."""
    reg = json.load(open(BASE / "data" / "club_registry.json"))
    clubs = reg.get("clubs", reg) if isinstance(reg, dict) else reg
    season, year = current_season_label(), current_season_year()
    ids = set()
    for club in clubs:
        if not set(club.get("leagues", {}).get(season, [])) & leagues:
            continue
        squad_file = SQUADS_DIR / f"{club['tm_id']}_{year}.json"
        if not squad_file.exists():
            continue
        for player in json.load(open(squad_file)).get("players", []):
            if player.get("tm_id"):
                ids.add(int(player["tm_id"]))
    return sorted(ids)


def is_fresh(path: Path, max_age_days: int) -> bool:
    return path.exists() and time.time() - path.stat().st_mtime < max_age_days * 86400


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--leagues", help="Comma-separated league codes; scrapes their current squads")
    ap.add_argument("--ids", type=int, nargs="+", help="Explicit spieler tm_ids")
    ap.add_argument("--ids-file", help="JSON list of spieler tm_ids")
    ap.add_argument("--max-age-days", type=int, default=30)
    ap.add_argument("--limit", type=int, help="Stop after N scraped players")
    args = ap.parse_args()

    ids = list(args.ids or [])
    if args.ids_file:
        ids += json.load(open(args.ids_file))
    if args.leagues:
        ids += current_squad_player_ids(set(args.leagues.split(",")))
    ids = list(dict.fromkeys(ids))
    if not ids:
        ap.error("no players selected (use --leagues, --ids or --ids-file)")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    todo = [i for i in ids if not is_fresh(OUT_DIR / f"spieler_{i}.json", args.max_age_days)]
    print(f"Players: {len(ids)} | fresh: {len(ids) - len(todo)} | to scrape: {len(todo)} "
          f"(~{len(todo) * (DELAY_MIN + DELAY_MAX) / 2 / 3600:.1f}h)", flush=True)

    ok = with_rumours = total_rumours = streak = 0
    for n, tm_id in enumerate(todo, 1):
        if args.limit and ok >= args.limit:
            break
        time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
        html = SPP.fetch_page(f"{SPP.TM_BASE}/x/geruechte/spieler/{tm_id}", f"geruechte_{tm_id}")
        if not html:
            streak += 1
            if streak >= BLOCK_STREAK:
                print(f"  {streak} failures in a row — assuming a block, stopping.", flush=True)
                break
            continue
        streak = 0
        parsed = parse_rumour_page(html)
        record = {"tm_id": tm_id, "name": parsed["name"],
                  "scraped_at": datetime.now().isoformat(timespec="seconds"),
                  "rumours": parsed["rumours"]}
        out = OUT_DIR / f"spieler_{tm_id}.json"
        tmp = out.with_suffix(".tmp")
        tmp.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(out)
        ok += 1
        with_rumours += bool(parsed["rumours"])
        total_rumours += len(parsed["rumours"])
        if n % 25 == 0:
            print(f"  [{n}/{len(todo)}] ok={ok} with_rumours={with_rumours} "
                  f"rumours={total_rumours}", flush=True)

    print(f"Done: scraped={ok} with_rumours={with_rumours} rumours={total_rumours}", flush=True)


if __name__ == "__main__":
    main()
