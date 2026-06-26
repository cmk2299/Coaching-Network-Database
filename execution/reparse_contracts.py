#!/usr/bin/env python3
"""Re-parse cached TM HTML to extract contract_until for trainer + spieler profiles.

This avoids hitting TM live — just runs the (now-extended) parser against
existing tmp/cache/profiles/*.html files.

Updates:
  - data/person_profiles/{tm_id}.json  (adds contract_until)
  - data/persons_master.json           (rebuild via merge)

Usage:
  python3 execution/reparse_contracts.py
  python3 execution/reparse_contracts.py --only 3223 34524
  python3 execution/reparse_contracts.py --type trainer  # only trainer profiles
"""
import argparse
import json
import sys
from pathlib import Path
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent))
from scrape_person_profiles import parse_contract_until, build_master_file

BASE = Path(__file__).parent.parent
CACHE = BASE / "tmp" / "cache" / "profiles"
PROFILES = BASE / "data" / "person_profiles"


def reparse(tm_id: int, person_type: str) -> bool:
    """Re-parse cached HTML and update profile JSON. Returns True if updated."""
    cache_path = CACHE / f"{person_type}_{tm_id}.html"
    if not cache_path.exists():
        return False
    profile_path = PROFILES / f"{tm_id}.json"
    if not profile_path.exists():
        return False
    try:
        html = cache_path.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")
        contract = parse_contract_until(soup)
        profile = json.load(open(profile_path))
        if contract:
            profile["contract_until"] = contract
            json.dump(profile, open(profile_path, "w"), ensure_ascii=False, indent=2)
            return True
        elif "contract_until" not in profile:
            # Mark as scanned (None) so we don't re-try
            profile["contract_until"] = None
            json.dump(profile, open(profile_path, "w"), ensure_ascii=False, indent=2)
        return False
    except Exception as e:
        print(f"  ✗ {tm_id}: {e}")
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", type=int, nargs="+", help="Only re-parse these tm_ids")
    ap.add_argument("--type", choices=["trainer", "spieler", "both"], default="both")
    ap.add_argument("--skip-merge", action="store_true", help="Skip persons_master rebuild")
    args = ap.parse_args()

    # Build target list
    if args.only:
        targets = [(tm_id, "trainer") for tm_id in args.only] + \
                  [(tm_id, "spieler") for tm_id in args.only]
    else:
        targets = []
        types = ["trainer", "spieler"] if args.type == "both" else [args.type]
        for t in types:
            for f in CACHE.glob(f"{t}_*.html"):
                m = f.stem.split("_", 1)
                if len(m) == 2 and m[1].isdigit():
                    targets.append((int(m[1]), t))

    print(f"Targets: {len(targets)} cached HTML files")

    updated = 0
    none = 0
    skipped = 0
    for i, (tm_id, t) in enumerate(targets, 1):
        if i % 500 == 0:
            print(f"  Progress: {i}/{len(targets)} (updated={updated}, none={none}, skipped={skipped})")
        result = reparse(tm_id, t)
        if result:
            updated += 1
        else:
            cache_path = CACHE / f"{t}_{tm_id}.html"
            profile_path = PROFILES / f"{tm_id}.json"
            if cache_path.exists() and profile_path.exists():
                none += 1
            else:
                skipped += 1

    print("\nDone:")
    print(f"  Updated with contract: {updated}")
    print(f"  No contract field:     {none}")
    print(f"  Skipped (no profile):  {skipped}")

    if not args.skip_merge and updated > 0:
        print("\nRebuilding persons_master.json...")
        build_master_file()
        print("✓ Done")


if __name__ == "__main__":
    main()
