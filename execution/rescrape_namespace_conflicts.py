#!/usr/bin/env python3
"""Phase A4: Re-scrape missing namespace variants.

After detect_namespace_collisions.py identifies "needs_rescrape" entries
(single-cached IDs where persons_master's stored type doesn't match the cached
type), this script fetches the missing variant from TM.

Reads `data/namespace_collisions.json[rescrape_needed]`.
Calls execution/scrape_person_profiles.py per id+type.

Usage:
  python3 execution/rescrape_namespace_conflicts.py --dry-run
  python3 execution/rescrape_namespace_conflicts.py --batch-size 50
  python3 execution/rescrape_namespace_conflicts.py --batch-size 50 --max 200
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).parent.parent
COLLISIONS = BASE / "data" / "namespace_collisions.json"
SCRAPE = BASE / "execution" / "scrape_person_profiles.py"
LOG_DIR = BASE / "logs"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--batch-size", type=int, default=50,
                    help="Pause between batches (seconds-per-id rate-limit is built into scraper)")
    ap.add_argument("--max", type=int, default=0, help="Cap total scrapes (0=unlimited)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not COLLISIONS.exists():
        sys.exit(f"ERR: {COLLISIONS} not found")

    doc = json.load(open(COLLISIONS))
    targets = doc.get("rescrape_needed", [])
    print(f"Targets: {len(targets):,} IDs need missing-variant rescrape")

    if args.max > 0:
        targets = targets[:args.max]
        print(f"  Capped to {len(targets)}")

    if args.dry_run:
        print("\nDRY-RUN — first 10 targets:")
        for t in targets[:10]:
            cached = ",".join(t["types_in_cache"])
            need = "spieler" if "trainer" in t["types_in_cache"] else "trainer"
            print(f"  {t['tm_id']:>8} (cached: {cached:<8}) → fetch {need}  [{t['stored_name'][:30]}]")
        return

    LOG_DIR.mkdir(exist_ok=True)
    log_path = LOG_DIR / f"namespace_rescrape_{time.strftime('%Y%m%d_%H%M')}.log"
    print(f"\nLogging to {log_path}\n")

    ok = 0
    fail = 0
    start = time.time()
    with open(log_path, "w") as log:
        for i, t in enumerate(targets, 1):
            need = "spieler" if "trainer" in t["types_in_cache"] else "trainer"
            tm_id = t["tm_id"]
            if i % 25 == 1 or i == len(targets):
                elapsed = time.time() - start
                eta = elapsed / i * (len(targets) - i) if i else 0
                print(f"  [{i:>4}/{len(targets)}] tm={tm_id} type={need}  "
                      f"({t['stored_name'][:25]})  ETA {eta/60:.0f}min", flush=True)
            try:
                r = subprocess.run(
                    ["python3", str(SCRAPE), "--tm-id", str(tm_id), "--type", need],
                    cwd=BASE, capture_output=True, text=True, timeout=90,
                )
                if r.returncode == 0:
                    ok += 1
                    log.write(f"OK tm={tm_id} type={need}\n")
                else:
                    fail += 1
                    log.write(f"FAIL tm={tm_id} type={need} stderr={r.stderr[-200:]}\n")
            except subprocess.TimeoutExpired:
                fail += 1
                log.write(f"TIMEOUT tm={tm_id} type={need}\n")
            except Exception as e:
                fail += 1
                log.write(f"ERR tm={tm_id} type={need} {e}\n")

    elapsed = (time.time() - start) / 60
    print(f"\n✓ {ok:,} scraped, {fail} failed in {elapsed:.1f} min")
    print(f"  Log: {log_path}")
    print(f"\nNext: python3 execution/scrape_person_profiles.py --merge-only")


if __name__ == "__main__":
    main()
