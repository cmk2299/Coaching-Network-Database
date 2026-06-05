#!/usr/bin/env python3
"""Restore trainer profiles overwritten by spieler-namesakes during full reparse.

Root cause:
  TM Dual-ID — same numeric tm_id maps to DIFFERENT persons via
  /profil/trainer/X vs /profil/spieler/X. The full reparse iterated both
  queue entries for the same tm_id and BOTH wrote to data/person_profiles/{tm_id}.json
  (no type namespace in the filename). Spieler always wrote last → 1,717
  trainer profiles got clobbered by player namesakes (e.g. Blessin → Lino,
  Hansi Flick → Markus Daun, Hecking → Marek Heinz).

Fix:
  For each tm_id where persons_index says "trainer" but person_profiles
  says "spieler", re-parse the cached trainer HTML and overwrite the JSON.
  Cache key is `trainer_{tm_id}.html` (separate from spieler cache).

Then build_master_file() reads the corrected profiles.

Usage:
  python3 execution/fix_dual_id_overwrites.py            # heal all
  python3 execution/fix_dual_id_overwrites.py --dry-run  # report only
"""
import argparse
import json
import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent))
from scrape_person_profiles import parse_profile, build_master_file  # noqa

BASE = Path(__file__).parent.parent
CACHE = BASE / "tmp" / "cache" / "profiles"
PROFILES = BASE / "data" / "person_profiles"
INDEX = BASE / "data" / "persons_index.json"


def collect_overwrites():
    """Return list of tm_ids where index says trainer but profile says spieler."""
    idx = json.load(open(INDEX))["persons"]
    out = []
    for k, v in idx.items():
        url = v.get("tm_url") or ""
        m = re.search(r"/profil/(trainer|spieler)/", url)
        if not m:
            continue
        if m.group(1) != "trainer":
            continue
        pf = PROFILES / f"{k}.json"
        if not pf.exists():
            continue
        try:
            p = json.load(open(pf))
        except Exception:
            continue
        if p.get("type") != "trainer":
            out.append((int(k), v.get("name"), p.get("name")))
    return out


def restore(tm_id: int):
    cache_path = CACHE / f"trainer_{tm_id}.html"
    if not cache_path.exists():
        return False, "no cached trainer HTML"
    try:
        html = cache_path.read_text(encoding="utf-8")
        profile = parse_profile(html, tm_id, "trainer")
        out_path = PROFILES / f"{tm_id}.json"
        json.dump(profile, open(out_path, "w"), ensure_ascii=False, indent=2)
        return True, None
    except Exception as e:
        return False, str(e)[:100]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-merge", action="store_true",
                    help="Skip persons_master rebuild")
    args = ap.parse_args()

    overwrites = collect_overwrites()
    print(f"Found {len(overwrites)} overwritten trainer profiles")
    if not overwrites:
        return
    if args.dry_run:
        for tm_id, idx_name, pf_name in overwrites[:20]:
            print(f"  {tm_id:>8} {idx_name:<28} ← was overwritten by {pf_name}")
        print(f"  ... ({len(overwrites)} total)")
        return

    restored = 0
    no_cache = 0
    errored = 0
    for i, (tm_id, idx_name, pf_name) in enumerate(overwrites, 1):
        if i % 200 == 0:
            print(f"  Progress: {i}/{len(overwrites)} restored={restored}")
        ok, err = restore(tm_id)
        if ok:
            restored += 1
        elif err == "no cached trainer HTML":
            no_cache += 1
        else:
            errored += 1
            if errored <= 5:
                print(f"  ✗ {tm_id} ({idx_name}): {err}")

    print(f"\n✓ Restored: {restored}")
    print(f"  Missing cache: {no_cache}")
    print(f"  Errored: {errored}")

    if not args.no_merge and restored > 0:
        print("\nRebuilding persons_master.json...")
        build_master_file()
        print("✓ Done")


if __name__ == "__main__":
    main()
