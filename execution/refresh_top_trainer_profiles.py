#!/usr/bin/env python3
"""
Refresh TM profiles for top BL Cheftrainer + prominent coaches.

Strategy:
- `scrape_person_profiles.py` has 30-day cache (CACHE_DAYS=30) and no --force flag.
- This helper script deletes the cache file for each tm_id, then invokes the scraper.
- Sandbox-friendly: 45s bash timeout → process max ~10 profiles per run (rate-limit 3s).
  Default batch size 10. Use --batch=N --offset=K to stage runs.

Usage:
  python execution/refresh_top_trainer_profiles.py --list           # print full target list
  python execution/refresh_top_trainer_profiles.py --dry-run        # show what would be done
  python execution/refresh_top_trainer_profiles.py --batch=10       # refresh first 10
  python execution/refresh_top_trainer_profiles.py --batch=10 --offset=10  # next 10
  python execution/refresh_top_trainer_profiles.py --tm-id=40267    # single ID (Tedesco)

After cache delete the existing scraper writes fresh HTML + JSON via:
  python execution/scrape_person_profiles.py --tm-id <id> --type trainer
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
DATA = BASE / "data"
CACHE_DIR = BASE / "tmp" / "cache" / "profiles"
PROFILES_DIR = DATA / "person_profiles"
CURRENT_SEASON = "2025/2026"

# ── Prominent additions (Coachinside / pitch-relevant) ──────────────────
# (tm_id, name, why)
PROMINENT = [
    (40267, "Domenico Tedesco", "Ex-Fenerbahce; stale status — KEY refresh"),
    (16739, "Sebastian Hoeneß", "VfB Stuttgart head coach"),
    (45033, "Merlin Polzin", "HSV head coach (LG 70)"),
    (118097, "Marie-Louise Eta", "Union Berlin head coach"),
    (49850, "Miroslav Klose", "1.FC Nürnberg head coach"),
    (28288, "Tim Walter", "Ex-HSV, free agent / candidate"),
    (24009, "Bo Henriksen", "FSV Mainz head coach (current)"),
    (54858, "Fabian Hürzeler", "Brighton head coach, German DACH candidate"),
    (10565, "Markus Krösche", "Eintracht Frankfurt SD"),
    (47286, "Marcus Sorg", "Coach/SD"),
    (47973, "Andreas Bornemann", "St. Pauli SD"),
    (10063, "Max Eberl", "Bayern SD"),
    (4895, "Sven Mislintat", "SD"),
    (28428, "Jörg Schmadtke", "SD/GF"),
    (3690, "Andreas Rettig", "DFB Akademie"),
    (33329, "Christian Heidel", "Mainz SD"),
    (44195, "Klaus Schicker", "Hertha SD"),
    (50032, "Markus Wagner", "FC Augsburg head coach"),
]


def load_bl_coaches():
    """Load current BL1/BL2/BL3 head coaches via staff files."""
    cr = json.load(open(DATA / "club_registry.json"))
    clubs = cr if isinstance(cr, list) else cr.get("clubs", [])
    bl_clubs = [
        c for c in clubs
        if CURRENT_SEASON in c.get("leagues", {})
        and any(lg in ("BL1", "BL2", "BL3") for lg in c.get("leagues", {}).get(CURRENT_SEASON, []))
    ]
    coaches = []
    for c in bl_clubs:
        sf = DATA / "staff" / f"{c.get('tm_id')}.json"
        if not sf.exists():
            continue
        try:
            sd = json.load(open(sf))
        except Exception:
            continue
        for s in sd.get("staff", []):
            if s.get("role") == "head_coach":
                coaches.append({
                    "tm_id": s.get("tm_id"),
                    "name": s.get("name"),
                    "club": c.get("name"),
                    "reason": "BL Cheftrainer",
                })
                break
    return coaches


def build_target_list():
    """Merge BL coaches + prominent extras, dedupe by tm_id."""
    seen = set()
    targets = []
    # 1) Prominent first (priority)
    for tid, name, why in PROMINENT:
        if tid in seen:
            continue
        seen.add(tid)
        targets.append({"tm_id": tid, "name": name, "club": "—", "reason": why})
    # 2) BL coaches
    for c in load_bl_coaches():
        if c["tm_id"] in seen:
            continue
        seen.add(c["tm_id"])
        targets.append(c)
    return targets


def delete_cache(tm_id: int) -> bool:
    """Delete trainer + spieler cache files for tm_id. Returns True if any were deleted."""
    deleted = False
    for prefix in ("trainer", "spieler"):
        p = CACHE_DIR / f"{prefix}_{tm_id}.html"
        if p.exists():
            p.unlink()
            deleted = True
    return deleted


def refresh_one(tm_id: int, ptype: str = "trainer", dry_run: bool = False) -> bool:
    """Delete cache for tm_id and re-invoke scraper."""
    if dry_run:
        existing = [
            f"{prefix}_{tm_id}.html"
            for prefix in ("trainer", "spieler")
            if (CACHE_DIR / f"{prefix}_{tm_id}.html").exists()
        ]
        print(f"  [DRY] tm_id={tm_id} type={ptype} | cached: {existing or 'none'}")
        return True
    delete_cache(tm_id)
    cmd = [
        sys.executable,
        str(BASE / "execution" / "scrape_person_profiles.py"),
        f"--tm-id={tm_id}",
        f"--type={ptype}",
    ]
    print(f"  → scraping tm_id={tm_id} ({ptype})")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=40)
        if r.returncode != 0:
            print(f"    ERR rc={r.returncode}: {r.stderr.strip()[:200]}")
            return False
        # Print last line of output (status)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        print(f"    {last[:160]}")
        return True
    except subprocess.TimeoutExpired:
        print("    TIMEOUT (>40s) — re-run later")
        return False
    except Exception as e:
        print(f"    EXC: {e}")
        return False


def main():
    ap = argparse.ArgumentParser(description="Refresh TM profiles for top BL/Coachinside coaches")
    ap.add_argument("--list", action="store_true", help="Print target list and exit")
    ap.add_argument("--dry-run", action="store_true", help="Show what would be done, no scrape")
    ap.add_argument("--batch", type=int, default=10, help="Max profiles to scrape this run (default 10)")
    ap.add_argument("--offset", type=int, default=0, help="Skip first N targets (for staged runs)")
    ap.add_argument("--tm-id", type=int, help="Refresh single tm_id only")
    ap.add_argument("--type", default="trainer", choices=["trainer", "spieler"])
    args = ap.parse_args()

    if args.tm_id:
        ok = refresh_one(args.tm_id, args.type, dry_run=args.dry_run)
        sys.exit(0 if ok else 1)

    targets = build_target_list()
    print(f"Total targets: {len(targets)}")

    if args.list:
        for i, t in enumerate(targets):
            print(f"  [{i:>3}] {t['tm_id']:>8} | {t['name']:35} | {t['club']:30} | {t['reason']}")
        return

    batch = targets[args.offset:args.offset + args.batch]
    print(f"Processing batch: offset={args.offset} batch={args.batch} → {len(batch)} items")
    print(f"Mode: {'DRY-RUN' if args.dry_run else 'LIVE'}")
    ok = 0
    for t in batch:
        success = refresh_one(t["tm_id"], "trainer", dry_run=args.dry_run)
        if success:
            ok += 1
    print(f"\nDone. {ok}/{len(batch)} refreshed.")
    print(f"Next batch: --offset={args.offset + args.batch} --batch={args.batch}")


if __name__ == "__main__":
    main()
