#!/usr/bin/env python3
"""Batch-build networks for all coaches in data/expansion_todo.json.

Idempotent: skips coaches whose network JSON already exists (use --force to override).
Logs progress to logs/expand_all_networks.log.

Usage:
  python3 execution/expand_all_networks.py
  python3 execution/expand_all_networks.py --force
  python3 execution/expand_all_networks.py --only 10463 1982
"""
from __future__ import annotations
import argparse, json, sys, time, traceback
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "execution"))

from build_coach_network import (build_network, generate_background_summaries,
                                  strip_internal_fields,
                                  preload_all_profiles, build_profile_index)
from generate_dashboard import generate_dashboard
from lib.normalization import slugify

NETS = BASE / "data" / "networks"
DASH = BASE / "output" / "dashboards"
TODO = BASE / "data" / "expansion_todo.json"
LOG  = BASE / "logs" / "expand_all_networks.log"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", nargs="+", type=int)
    args = ap.parse_args()

    LOG.parent.mkdir(exist_ok=True)
    todo = json.load(open(TODO))
    if args.only:
        todo = [t for t in todo if t["tm_id"] in args.only]

    print(f"Loading profiles...")
    profiles = preload_all_profiles()
    idx = build_profile_index(profiles)
    print(f"  {len(profiles)} profiles loaded")

    built = skipped = failed = 0
    t0 = time.time()

    with open(LOG, "a") as logf:
        for i, entry in enumerate(todo, 1):
            tm_id = entry["tm_id"]
            name  = entry["name"]
            net_path = NETS / f"{tm_id}.json"

            if net_path.exists() and not args.force:
                skipped += 1
                continue

            try:
                net = build_network(tm_id, profiles, idx)
                if not net:
                    failed += 1
                    msg = f"  ✗ [{i}/{len(todo)}] {name} ({tm_id}): no network returned"
                    print(msg); logf.write(msg + "\n"); logf.flush()
                    continue

                net = generate_background_summaries(net)
                strip_internal_fields(net)
                json.dump(net, open(net_path, "w"), ensure_ascii=False, indent=2)

                slug = net.get("slug") or slugify(net.get("center", str(tm_id)))
                # Skip drilldown in batch mode — regenerate_dashboards.py adds it later
                generate_dashboard(net, DASH / f"{slug}_network.html", drilldown={})

                built += 1
                elapsed = time.time() - t0
                eta = (elapsed / built) * (len(todo) - skipped - built - failed) if built else 0
                msg = (f"  ✓ [{i}/{len(todo)}] {name:30} {net.get('total_contacts')} contacts "
                       f"→ {slug}_network.html  ETA {eta/60:.0f}min")
                print(msg); logf.write(msg + "\n"); logf.flush()

            except Exception as e:
                failed += 1
                msg = f"  ✗ [{i}/{len(todo)}] {name} ({tm_id}): {e}"
                print(msg); logf.write(msg + "\n"); logf.flush()

    total_time = time.time() - t0
    summary = (f"\nDone: built={built} skipped={skipped} failed={failed} "
               f"time={total_time/60:.0f}min")
    print(summary)
    with open(LOG, "a") as logf:
        logf.write(summary + "\n")


if __name__ == "__main__":
    main()
