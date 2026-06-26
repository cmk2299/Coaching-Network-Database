#!/usr/bin/env python3
"""Audit all generated network JSONs for stale/generic contact roles.

Scans data/networks/*.json and flags any contact whose `role` is a generic
placeholder ("Trainer", "Mitspieler", "Lehrgangs-Kollege", "", etc.) while
the underlying person profile actually has a usable career_history[0].role
or a player position.

This is the Schuhen-Pattern regression detector. Run after every bulk scrape
or builder change. Output: a sorted list of network tm_ids that need rebuild.

Usage:
    python3 execution/audit_all_networks.py                  # report only
    python3 execution/audit_all_networks.py --rebuild        # also re-run builder
    python3 execution/audit_all_networks.py --out FILE       # write tm_ids to file
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent))
from lib.normalization import is_generic_role, resolve_contact_role

ROOT = Path(__file__).resolve().parents[1]
NETWORKS_DIR = ROOT / "data" / "networks"
PROFILES_DIR = ROOT / "data" / "person_profiles"


def load_profiles_lazy(tm_ids):
    """Load only the profiles we actually need to check (faster than full load)."""
    out = {}
    for tid in tm_ids:
        p = PROFILES_DIR / f"{tid}.json"
        if p.exists():
            try:
                out[int(tid)] = json.loads(p.read_text())
            except Exception:
                pass
    return out


def audit():
    network_files = sorted(NETWORKS_DIR.glob("*.json"))
    print(f"Auditing {len(network_files)} networks...", flush=True)

    flagged_networks = []  # [(network_tm_id, [bad_contacts])]
    cat_counter = Counter()
    total_bad = 0

    for nf in network_files:
        try:
            n = json.loads(nf.read_text())
        except Exception as e:
            print(f"  ! {nf.name}: {e}")
            continue

        contacts = n.get("contacts", [])
        suspects = [c for c in contacts if is_generic_role(c.get("role", ""))
                    and c.get("tm_id")]
        if not suspects:
            continue

        profiles = load_profiles_lazy([c["tm_id"] for c in suspects])
        bad = []
        for c in suspects:
            canonical = resolve_contact_role(c["tm_id"], profiles, fallback="__NONE__")
            if canonical == "__NONE__":
                continue  # profile genuinely has no signal — not a bug
            if is_generic_role(canonical):
                continue  # canonical also generic — nothing better to write
            bad.append({
                "tm_id": c["tm_id"],
                "name": c.get("name"),
                "current_role": c.get("role"),
                "canonical_role": canonical,
                "category": c.get("category"),
            })
            cat_counter[c.get("category", "unknown")] += 1

        if bad:
            net_id = nf.stem
            flagged_networks.append((net_id, bad))
            total_bad += len(bad)

    return flagged_networks, cat_counter, total_bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true",
                    help="re-run build_coach_network.py for each flagged network")
    ap.add_argument("--out", type=Path, help="write flagged tm_ids (one per line) to file")
    ap.add_argument("--limit", type=int, help="(with --rebuild) only rebuild first N")
    args = ap.parse_args()

    flagged, cat_counter, total_bad = audit()

    print("\n=== Audit Result ===")
    print(f"Networks with stale contacts : {len(flagged)}")
    print(f"Total stale-role contacts    : {total_bad}")
    print(f"By category                  : {dict(cat_counter)}")

    if flagged:
        print("\nTop 10 affected networks:")
        for net_id, bad in sorted(flagged, key=lambda x: -len(x[1]))[:10]:
            print(f"  {net_id}: {len(bad)} stale "
                  f"(e.g. {bad[0]['name']} '{bad[0]['current_role']}' "
                  f"→ '{bad[0]['canonical_role']}')")

    if args.out:
        args.out.write_text("\n".join(nid for nid, _ in flagged) + "\n")
        print(f"\n✓ Wrote {len(flagged)} tm_ids to {args.out}")

    if args.rebuild and flagged:
        targets = flagged[:args.limit] if args.limit else flagged
        print(f"\nRebuilding {len(targets)} networks...")
        for i, (net_id, _) in enumerate(targets, 1):
            print(f"  [{i}/{len(targets)}] {net_id}", flush=True)
            subprocess.run(
                ["python3", str(Path(__file__).parent / "build_coach_network.py"),
                 "--tm-id", net_id],
                stdout=subprocess.DEVNULL, timeout=300,
            )
        print("✓ Rebuild done")

    return 0 if not flagged else 1


if __name__ == "__main__":
    sys.exit(main())
