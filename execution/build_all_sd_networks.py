#!/usr/bin/env python3
"""Builds Networks für alle SDs aus sd_registry.json + Dashboards.

Output:
  data/networks/{tm_id}.json (gleiche Struktur wie Coach-Networks)
  output/dashboards/{slug}_sd_network.html (Suffix _sd_network um
                    Coach-/SD-Slug-Kollisionen zu vermeiden)

Usage:
  python3 execution/build_all_sd_networks.py
  python3 execution/build_all_sd_networks.py --only 3223 34524
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
    ap.add_argument("--include-tier-2", action="store_true",
                    help="Include Tier-2 DMs (Sportkoordinator, Chefscout, Kaderplaner)")
    ap.add_argument("--include-nlz", action="store_true",
                    help="Include NLZ-Leiter as own networks")
    ap.add_argument("--include-tier-3", action="store_true",
                    help="Include Tier-3 DMs (Vorstand/Präsident/CEO)")
    args = ap.parse_args()

    # When tier-flags are set, prefer decision_makers.json over sd_registry.json
    use_dm_registry = args.include_tier_2 or args.include_nlz or args.include_tier_3
    dm_path = BASE / "data/decision_makers.json"

    if use_dm_registry and dm_path.exists():
        dms = json.load(open(dm_path))["decision_makers"]
        allowed_tiers = {"1"}
        if args.include_tier_2: allowed_tiers.add("2")
        if args.include_tier_3: allowed_tiers.add("3")
        if args.include_nlz: allowed_tiers.add("nlz")
        sds = [
            {"tm_id": d["tm_id"], "name": d["name"], "club_name": d.get("club_name", ""),
             "tier": d.get("tier")}
            for d in dms if d["tier"] in allowed_tiers
        ]
        # Dedupe by tm_id (DMs can theoretically span multiple clubs)
        seen = {}
        for s in sds:
            seen[s["tm_id"]] = s
        sds = list(seen.values())
        print(f"  Using decision_makers.json — {len(sds)} DMs across tiers {sorted(allowed_tiers)}")
    else:
        sds = json.load(open(BASE / "data/sd_registry.json"))["sds"]

    if args.only:
        only = set(args.only)
        sds = [s for s in sds if s["tm_id"] in only]

    print(f"Loading profile index ({len(sds)} SDs to process)...")
    profiles = preload_all_profiles()
    profile_index = build_profile_index(profiles)

    success = 0
    failed = 0
    skipped = 0
    t0 = time.time()
    for i, sd in enumerate(sds, 1):
        tm_id = sd["tm_id"]
        name = sd["name"]
        slug = slugify(name)
        prefix = f"  [{i:>2}/{len(sds)}] {name:<26} ({sd['club_name']:<24})"
        sys.stdout.write(prefix + " ... ")
        sys.stdout.flush()

        try:
            net = build_network(tm_id, profiles, profile_index)
            if not net:
                print("✗ no profile")
                failed += 1
                continue
            net = generate_background_summaries(net)
            drilldown = build_drilldown(net, profiles, profile_index)
            strip_internal_fields(net)

            net_path = OUTPUT_DIR / f"{tm_id}.json"
            json.dump(net, open(net_path, "w"), ensure_ascii=False, indent=2)

            dash_path = DASHBOARDS_DIR / f"{slug}_sd_network.html"
            generate_dashboard(net, dash_path, drilldown=drilldown)
            print(f"✓ {net['total_contacts']} contacts")
            success += 1
        except Exception as e:
            print(f"✗ {e}")
            failed += 1

    print(f"\nDone: {success} ok, {failed} failed, {skipped} skipped ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
