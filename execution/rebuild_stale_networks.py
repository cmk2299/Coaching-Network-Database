#!/usr/bin/env python3
"""Rebuild network JSONs for a given list of tm_ids using the CURRENT builder.

Motivation: networks built before the 2026-06-04 current_club lambda fix carry a
stale/station-stamped current_club on player_coached contacts (C9 finding). The
current build_network() reads the player's real current_club from their profile.
Re-running build_network for the affected ids + re-saving the JSON fixes it. The
dashboards are then refreshed via regenerate_dashboards.py (which reads the JSON).

Preserves any existing `_nlz_meta` (and other `_*meta` keys) from the on-disk JSON
so NLZ tier/parent-club cross-links keep working.

Usage:
  python3 execution/rebuild_stale_networks.py --ids-file /tmp/stale_networks.txt
  python3 execution/rebuild_stale_networks.py --ids 35878 8402
"""
import sys, json, time, argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_coach_network import (
    build_network, generate_background_summaries, build_drilldown,
    strip_internal_fields, preload_all_profiles, build_profile_index, OUTPUT_DIR,
)
from generate_dashboard import generate_dashboard
from lib.normalization import slugify

BASE = Path(__file__).resolve().parents[1]
NETS = BASE / "data" / "networks"
DASHBOARDS_DIR = BASE / "output" / "dashboards"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids-file")
    ap.add_argument("--ids", type=int, nargs="+")
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    ids = args.ids or []
    if args.ids_file:
        ids += [int(x) for x in Path(args.ids_file).read_text().split()]
    if args.limit:
        ids = ids[:args.limit]
    ids = list(dict.fromkeys(ids))  # dedupe, keep order

    print(f"Rebuilding {len(ids)} stale networks...")
    print("Loading profiles into memory (one-time)...")
    profiles = preload_all_profiles()
    profile_index = build_profile_index(profiles)

    ok = fail = 0
    t0 = time.time()
    for i, tid in enumerate(ids, 1):
        nf = NETS / f"{tid}.json"
        # capture preserved meta from the existing JSON
        preserved = {}
        if nf.exists():
            try:
                old = json.loads(nf.read_text())
                for k, v in old.items():
                    if k.startswith("_") and k.endswith("meta"):
                        preserved[k] = v
            except Exception:
                pass
        try:
            net = build_network(tid, profiles, profile_index)
            if not net:
                print(f"  [{i}/{len(ids)}] {tid} ✗ no profile")
                fail += 1
                continue
            net = generate_background_summaries(net)
            drilldown = build_drilldown(net, profiles, profile_index)
            strip_internal_fields(net)
            net.update(preserved)  # restore _nlz_meta etc.
            json.dump(net, open(nf, "w"), ensure_ascii=False, indent=2)
            # regenerate EVERY dashboard variant that exists on disk for this id
            # (a coach can have both {slug}_network and {slug}_nlz_network).
            base = net.get("slug") or slugify(net.get("center", ""))
            written = []
            # NOTE: _sd_network is built by build_all_sd_networks.py (SD-centric,
            # different center+contacts) — must NOT be regenerated from this coach build.
            for suffix in ("_network.html", "_nlz_network.html"):
                dp = DASHBOARDS_DIR / f"{base}{suffix}"
                if dp.exists():
                    generate_dashboard(net, dp, drilldown=drilldown)
                    written.append(dp.name)
            if not written:  # nothing on disk yet → default coach variant
                dp = DASHBOARDS_DIR / f"{base}_network.html"
                generate_dashboard(net, dp, drilldown=drilldown)
                written.append(dp.name)
            eta = (time.time() - t0) / i * (len(ids) - i)
            print(f"  [{i}/{len(ids)}] {tid} ✓ {net.get('total_contacts')} contacts "
                  f"→ {', '.join(written)} (ETA {eta/60:.0f}min)")
            ok += 1
        except Exception as e:
            print(f"  [{i}/{len(ids)}] {tid} ✗ {e}")
            fail += 1

    print(f"\nDone: {ok} rebuilt, {fail} failed ({(time.time()-t0)/60:.1f} min)")


if __name__ == "__main__":
    main()
