#!/usr/bin/env python3
"""Phase A1: Detect TM-Namespace Collisions (Sprint A).

TM uses separate ID-namespaces for /spieler/<id> and /trainer/<id>. Same numeric
tm_id can refer to TWO different people (e.g. tm_id 104: Walter Junghans as
trainer, Fredi Bobic as spieler).

`persons_master` is keyed only on tm_id (string) — last scrape wins, so
"Frankenstein profiles" appear: persons_master[104] = Walter Junghans + Bobic's
fields mixed.

This script:
  1. Scans tmp/cache/profiles/ for IDs with BOTH `spieler_X.html` and `trainer_X.html`
  2. Cross-checks against persons_master.json[<id>].type
  3. Output: data/namespace_collisions.json — list of every dual-namespace ID
     with currently-stored type, name, plus a "needs_rescrape" flag if the
     other-typed cache is missing.

Usage:
  python3 execution/detect_namespace_collisions.py
  python3 execution/detect_namespace_collisions.py --quick    # first 100 only
"""
import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent.parent
CACHE = BASE / "tmp" / "cache" / "profiles"
MASTER = BASE / "data" / "persons_master.json"
PROFILES = BASE / "data" / "person_profiles"
OUT = BASE / "data" / "namespace_collisions.json"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--quick", action="store_true",
                    help="First 100 cache files only (smoke test).")
    args = ap.parse_args()

    if not MASTER.exists():
        sys.exit(f"ERR: {MASTER} not found.")

    print("Loading persons_master…")
    master = json.load(open(MASTER))["persons"]
    print(f"  {len(master):,} entries")

    # Index cache by type
    print("\nScanning cache files…")
    by_id: dict[int, set[str]] = defaultdict(set)
    files = sorted(CACHE.glob("*.html"))
    if args.quick:
        files = files[:100]
    for p in files:
        # filename: {type}_{id}.html (e.g. spieler_104.html, trainer_122791.html)
        # also: spieler_verein_X, leistungsdatendetails_spieler_X — skip those
        parts = p.stem.split("_")
        if len(parts) != 2:
            continue
        person_type, id_str = parts
        if person_type not in ("spieler", "trainer") or not id_str.isdigit():
            continue
        by_id[int(id_str)].add(person_type)

    print(f"  {len(by_id):,} distinct tm_ids in cache")

    # Find dual-namespace collisions
    dual_in_cache = {tm: types for tm, types in by_id.items() if len(types) == 2}
    print(f"  {len(dual_in_cache):,} dual-namespace IDs (both spieler+trainer cached)")

    # Cross-check with persons_master + identify "needs rescrape" (only ONE cached
    # but persons_master holds wrong type, indicating a dropped variant)
    print("\nCross-referencing with persons_master…")
    collisions = []
    rescrape_needed = []
    for tm_id, types in sorted(by_id.items()):
        stored = master.get(str(tm_id), {}) or {}
        stored_name = stored.get("name") or ""
        stored_type = stored.get("type") or "unknown"
        record = {
            "tm_id": tm_id,
            "types_in_cache": sorted(types),
            "stored_type": stored_type,
            "stored_name": stored_name,
            "needs_rescrape": len(types) == 1 and stored_type != "unknown"
                              and stored_type not in types,
        }
        if len(types) == 2:
            collisions.append(record)
        if record["needs_rescrape"]:
            rescrape_needed.append(record)

    print(f"  Dual-cache (clean migration target): {len(collisions):,}")
    print(f"  Single-cache + mismatch (needs rescrape): {len(rescrape_needed):,}")

    # Save
    out_data = {
        "_meta": {
            "generated_at": datetime.now().isoformat(),
            "cache_dir": str(CACHE),
            "master_entries": len(master),
            "dual_namespace_count": len(collisions),
            "rescrape_needed_count": len(rescrape_needed),
        },
        "dual_namespace": collisions,
        "rescrape_needed": rescrape_needed,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out_data, f, ensure_ascii=False, indent=2)
    print(f"\n✓ Wrote {OUT}")
    print(f"  Total collisions to migrate: {len(collisions)}")
    print(f"  Rescrapes required (Phase A4): {len(rescrape_needed)}")


if __name__ == "__main__":
    main()
