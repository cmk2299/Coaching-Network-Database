#!/usr/bin/env python3
"""
Discover U19/U17/U18/II Sub-Vereine pro BL-Mutter-Club via TM Vereinsprofil-Page.

Background: TM listet U19-Bundesliga-Vereine als Mutter-Club-IDs (siehe Bug
2026-05-04: scrape_club_registry.py + Junioren-Staffeln gab keine neuen Clubs).
Stattdessen hat jede Mutter-Club-Seite Links zu ihren Sub-Mannschaften wie:

  /sv-werder-bremen-u19/startseite/verein/2491
  /sv-werder-bremen-u17/startseite/verein/21079
  /sv-werder-bremen-ii/startseite/verein/87

Diese tm_ids extrahieren + in club_registry mergen → staff-Files können
gescrapt werden → active_staff_index erfasst auch NLZ-Trainer wie Makiadi.

Output: data/youth_teams_discovered.json
  {
    "_meta": {generated_at, mother_clubs_scanned, sub_clubs_found},
    "sub_clubs": [
      {tm_id, slug, name, type: "U19"|"U17"|"U18"|"II", parent_tm_id, parent_name}
    ]
  }

Usage:
  python3 execution/discover_youth_teams.py
  python3 execution/discover_youth_teams.py --leagues BL1 BL2 BL3
  python3 execution/discover_youth_teams.py --only-tm-id 86  # test single
"""
import argparse
import json
import re
import time
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent.parent
REGISTRY = BASE / "data" / "club_registry.json"
OUTPUT = BASE / "data" / "youth_teams_discovered.json"
CACHE = BASE / "tmp" / "cache" / "mother_pages"
CACHE.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/122.0.0.0 Safari/537.36",
}
DELAY = 3  # seconds — TM rate-limit hygiene

# Sub-team types we want (most useful for projectFIVE)
TYPES_OF_INTEREST = {"u19", "u17", "u18", "ii"}

# Regex to match sub-team hrefs in mother-club page HTML
# Examples that match:
#   /sv-werder-bremen-u19/startseite/verein/2491
#   /sv-werder-bremen-ii/startseite/verein/87
# Doesn't match the mother-club itself (no -u19/-u17/-ii/-iii suffix)
SUB_TEAM_RE = re.compile(
    r'href="/([a-z0-9-]+)-(u\d+|ii|iii|iv|jugend)/startseite/verein/(\d+)"',
    re.IGNORECASE,
)


def fetch(url: str, cache_key: str, max_age_days: int = 30) -> str:
    """Fetch URL with disk-cache. Returns HTML text."""
    cache_file = CACHE / f"{cache_key}.html"
    if cache_file.exists():
        age = (time.time() - cache_file.stat().st_mtime) / 86400
        if age < max_age_days:
            return cache_file.read_text(encoding="utf-8")
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    cache_file.write_text(html, encoding="utf-8")
    return html


def discover_for_club(club: dict) -> list:
    """Fetch mother-club page, extract U19/U17/U18/II sub-teams.
    Returns list of {tm_id, slug, type, parent_tm_id, parent_name}."""
    tm_id = club["tm_id"]
    slug = club.get("slug") or club["name"].lower().replace(" ", "-")
    parent_name = club["name"]

    url = f"https://www.transfermarkt.de/{slug}/startseite/verein/{tm_id}"
    cache_key = f"verein_{tm_id}"
    try:
        html = fetch(url, cache_key)
    except Exception as e:
        print(f"    ✗ fetch failed: {e}")
        return []

    # All sub-team hrefs found on the page
    found = SUB_TEAM_RE.findall(html)
    seen = {}  # dedupe by (slug-with-suffix, tm_id)
    for parent_slug, suffix, sub_id in found:
        suffix_l = suffix.lower()
        if suffix_l not in TYPES_OF_INTEREST:
            continue
        # Verify parent_slug matches our mother-club slug (avoids picking up
        # e.g. another club's U19 mentioned somewhere on the page)
        # We allow loose match — TM uses "sv-werder-bremen" for slug "sv-werder-bremen"
        if parent_slug.lower() != slug.lower():
            # Try without "sv-" / "fc-" prefixes
            ps_strip = re.sub(r"^(sv|fc|tsg|vfb|vfl|spvgg|sc|tsv|sg|spvg|hsv)-", "", parent_slug.lower())
            slug_strip = re.sub(r"^(sv|fc|tsg|vfb|vfl|spvgg|sc|tsv|sg|spvg|hsv)-", "", slug.lower())
            if ps_strip != slug_strip:
                continue
        key = (parent_slug + "-" + suffix_l, int(sub_id))
        if key in seen:
            continue
        seen[key] = {
            "tm_id": int(sub_id),
            "slug": f"{parent_slug}-{suffix_l}",
            "name": f"{parent_name} {suffix.upper()}",
            "type": suffix.upper(),
            "parent_tm_id": tm_id,
            "parent_name": parent_name,
        }
    return list(seen.values())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--leagues", nargs="+", default=["BL1", "BL2", "BL3"],
                        help="Mother-club Ligen (default: BL1 BL2 BL3)")
    parser.add_argument("--only-tm-id", type=int, help="Test single club")
    parser.add_argument("--season", default="2025/2026")
    args = parser.parse_args()

    registry = json.load(open(REGISTRY))["clubs"]

    if args.only_tm_id:
        mother_clubs = [c for c in registry if c["tm_id"] == args.only_tm_id]
    else:
        mother_clubs = [
            c for c in registry
            if any(l in args.leagues for l in c.get("leagues", {}).get(args.season, []))
        ]

    print(f"Discovering sub-teams for {len(mother_clubs)} mother-clubs ({args.leagues})\n")

    all_sub_clubs = []
    by_type = {}
    for i, c in enumerate(mother_clubs, 1):
        print(f"  [{i:>2}/{len(mother_clubs)}] {c['name']:<28} (tm_id={c['tm_id']})")
        subs = discover_for_club(c)
        for s in subs:
            print(f"      → {s['type']:<3} {s['name']:<35} tm_id={s['tm_id']}")
            by_type[s["type"]] = by_type.get(s["type"], 0) + 1
        all_sub_clubs.extend(subs)
        time.sleep(DELAY)

    # Save
    out = {
        "_meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mother_clubs_scanned": len(mother_clubs),
            "sub_clubs_found": len(all_sub_clubs),
            "by_type": by_type,
            "leagues_scanned": args.leagues,
        },
        "sub_clubs": all_sub_clubs,
    }
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2))

    print(f"\n=== Summary ===")
    print(f"  Mother clubs scanned: {len(mother_clubs)}")
    print(f"  Sub-clubs discovered: {len(all_sub_clubs)}")
    for t, n in sorted(by_type.items()):
        print(f"    {t}: {n}")
    print(f"\n  → {OUTPUT}")


if __name__ == "__main__":
    main()
