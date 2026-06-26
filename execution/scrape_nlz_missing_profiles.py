#!/usr/bin/env python3
"""Scrape persons_master profiles for NLZ-Trainer that are missing.

Reads `data/nlz_trainer_registry.json` (Sprint G output) and identifies
trainers whose `tm_id` is NOT present in `data/persons_master.json`.
Then runs `execution/scrape_person_profiles.py` for each missing tm_id
(as a trainer-type profile) so they can later be picked up by
`build_all_nlz_networks.py` for additional Networks.

Usage:
  python3 execution/scrape_nlz_missing_profiles.py            # scrape all
  python3 execution/scrape_nlz_missing_profiles.py --max=50   # cap
  python3 execution/scrape_nlz_missing_profiles.py --dry-run  # list only
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).parent.parent
REG = BASE / "data" / "nlz_trainer_registry.json"
MASTER = BASE / "data" / "persons_master.json"


def collect_missing() -> list[dict]:
    if not REG.exists():
        sys.exit(f"ERR: {REG} fehlt — Sprint G Phase 1 erst laufen lassen.")
    if not MASTER.exists():
        sys.exit(f"ERR: {MASTER} fehlt.")

    reg = json.loads(REG.read_text())["trainers"]
    persons = json.loads(MASTER.read_text()).get("persons", {})

    missing = []
    for t in reg:
        p = persons.get(str(t["tm_id"]))
        # Trainer counts as "missing" if absent OR empty (no career_history).
        # Empty profiles cause build_network to skip them.
        if not p or not p.get("career_history"):
            missing.append(t)
    return missing


def scrape_one(tm_id: int, name: str, log) -> bool:
    try:
        r = subprocess.run(
            ["python3", "execution/scrape_person_profiles.py",
             "--tm-id", str(tm_id), "--type", "trainer"],
            cwd=BASE, capture_output=True, text=True, timeout=120,
        )
        if r.returncode != 0:
            log.write(f"  [{name} {tm_id}] FAIL exit={r.returncode}: "
                      f"{r.stderr[-300:]}\n")
            return False
        return True
    except subprocess.TimeoutExpired:
        log.write(f"  [{name} {tm_id}] TIMEOUT\n")
        return False
    except Exception as e:
        log.write(f"  [{name} {tm_id}] ERR {e}\n")
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max", type=int, default=0, help="cap at N (0=unlimited)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--log", type=str, default=None)
    args = parser.parse_args()

    missing = collect_missing()
    if args.max > 0:
        missing = missing[:args.max]

    print("\n=== NLZ-Profile-Backfill ===")
    print(f"Targets: {len(missing)} NLZ-Trainer ohne persons_master profile")
    from collections import Counter
    cnt = Counter(t.get("tier", "?") for t in missing)
    for tier, n in cnt.most_common():
        print(f"  {tier:<8} {n}")

    if args.dry_run:
        print("\n  (dry-run — first 8 targets:)")
        for t in missing[:8]:
            print(f"    {t['name']:<28} ({t['tm_id']}) [{t.get('tier','?')}] "
                  f"@ {t.get('parent_club','?')}")
        return

    log_path = args.log or str(
        BASE / "logs" / f"nlz_backfill_{time.strftime('%Y%m%d_%H%M')}.log"
    )
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)

    success = 0
    fail = 0
    start = time.time()
    with open(log_path, "w") as lh:
        lh.write(f"Started NLZ backfill ({len(missing)} targets) at "
                 f"{time.strftime('%H:%M:%S')}\n")
        for i, t in enumerate(missing, 1):
            elapsed = time.time() - start
            eta = (elapsed / i) * (len(missing) - i) if i > 0 else 0
            print(f"  [{i:>3}/{len(missing)}] {t['name'][:25]:<25} "
                  f"({t['tm_id']}) [{t.get('tier','?'):<7}] "
                  f"@ {t.get('parent_club','?')[:18]:<18}  ETA {eta/60:.0f}min",
                  flush=True)
            ok = scrape_one(t["tm_id"], t["name"], lh)
            if ok:
                success += 1
            else:
                fail += 1

    print(f"\n  ✓ {success} scraped, {fail} failed in "
          f"{(time.time()-start)/60:.1f} min")
    print(f"  Log: {log_path}")
    print("\nNext step: python3 execution/build_all_nlz_networks.py")


if __name__ == "__main__":
    main()
