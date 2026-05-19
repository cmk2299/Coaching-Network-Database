#!/usr/bin/env python3
"""Builds reduced-scope Networks für alle NLZ-Trainer.

Output:
  data/networks/{tm_id}.json
  output/dashboards/{slug}_nlz_network.html

Usage:
  python3 execution/build_all_nlz_networks.py
  python3 execution/build_all_nlz_networks.py --only 12345 67890
  python3 execution/build_all_nlz_networks.py --tier U19
  python3 execution/build_all_nlz_networks.py --max 50
"""
import argparse
import json
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from build_coach_network import (
    build_network, generate_background_summaries,
    build_drilldown, preload_all_profiles, build_profile_index,
    strip_internal_fields, OUTPUT_DIR,
)
from generate_dashboard import generate_dashboard
from lib.normalization import slugify

BASE = Path(__file__).parent.parent
DASHBOARDS_DIR = BASE / "output" / "dashboards"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", type=int, nargs="+", help="Only build these tm_ids")
    ap.add_argument("--tier", choices=["U10-13", "U14-17", "U19", "U23"],
                    help="Only build trainers in this tier")
    ap.add_argument("--max", type=int, help="Cap to first N trainers (sorted by tier-priority)")
    args = ap.parse_args()

    reg = json.load(open(BASE / "data/nlz_trainer_registry.json"))["trainers"]

    # Tier priority for sorting (U23/U19 are most pipeline-relevant)
    TIER_PRIO = {"U23": 0, "U19": 1, "U14-17": 2, "U10-13": 3}
    reg.sort(key=lambda t: (TIER_PRIO.get(t["tier"], 9), t["name"]))

    if args.tier:
        reg = [t for t in reg if t["tier"] == args.tier]
    if args.only:
        only = set(args.only)
        reg = [t for t in reg if t["tm_id"] in only]
    if args.max:
        reg = reg[:args.max]

    print(f"Building {len(reg)} NLZ-Networks...")
    print("Loading profiles into memory (one-time)...")
    profiles = preload_all_profiles()
    profile_index = build_profile_index(profiles)

    success = 0
    failed = 0
    skipped = 0
    t0 = time.time()
    for i, t in enumerate(reg, 1):
        elapsed = time.time() - t0
        eta = (elapsed / i) * (len(reg) - i) if i > 0 else 0
        prefix = (f"  [{i:>4}/{len(reg)}] {t['name'][:24]:<24} ({t['tier']:<7}) "
                  f"@ {(t.get('parent_club') or '?')[:18]:<18} ETA {eta/60:.0f}min")
        sys.stdout.write(prefix + " ... ")
        sys.stdout.flush()

        try:
            net = build_network(t["tm_id"], profiles, profile_index)
            if not net:
                print("✗ no profile")
                skipped += 1
                continue
            net = generate_background_summaries(net)
            drilldown = build_drilldown(net, profiles, profile_index)
            strip_internal_fields(net)
            # Mark as NLZ in metadata for cross-link detection
            net["_nlz_meta"] = {
                "tier": t["tier"],
                "club_name": t.get("club_name"),
                "parent_club": t.get("parent_club"),
                "age_group_label": t.get("age_group_label"),
            }

            net_path = OUTPUT_DIR / f"{t['tm_id']}.json"
            json.dump(net, open(net_path, "w"), ensure_ascii=False, indent=2)

            slug = slugify(t["name"])
            dash_path = DASHBOARDS_DIR / f"{slug}_nlz_network.html"
            generate_dashboard(net, dash_path, drilldown=drilldown)
            print(f"✓ {net['total_contacts']} contacts")
            success += 1
        except Exception as e:
            print(f"✗ {e}")
            failed += 1

    print(f"\nDone: {success} ok, {failed} failed, {skipped} skipped ({(time.time()-t0)/60:.1f} min)")


if __name__ == "__main__":
    main()
