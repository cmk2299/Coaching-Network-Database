#!/usr/bin/env python3
"""Pre-deploy pipeline validation gate.

Audit 2026-06-20 root cause: nothing validated the data volume between
scrape → master → DB → deploy, so a wipe / mass parse-failure could ship. This
compares cheap artifact metrics against a stored baseline
(data/.pipeline_baseline.json) and FAILS if any drops below tolerance — catching
the catastrophic-regression class (the 2026-05-21 wipe) before a deploy.

  python3 execution/validate_pipeline.py                  # gate: exit 1 if regressed
  python3 execution/validate_pipeline.py --update-baseline # accept current as new baseline
  python3 execution/validate_pipeline.py --tolerance 0.10  # allow 10% drop (default 5%)
"""
import argparse
import glob
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
BASELINE = BASE / "data" / ".pipeline_baseline.json"


def metrics() -> dict:
    """Cheap, filesystem-level health metrics (no 289MB master load)."""
    pm = BASE / "data" / "persons_master.json"
    return {
        "networks": len(glob.glob(str(BASE / "data" / "networks" / "*.json"))),
        "person_profiles": len(glob.glob(str(BASE / "data" / "person_profiles" / "*.json"))),
        "dashboards": len(glob.glob(str(BASE / "output" / "dashboards" / "*_network.html"))),
        "staff_files": len(glob.glob(str(BASE / "data" / "staff" / "*.json"))),
        "persons_master_bytes": pm.stat().st_size if pm.exists() else 0,
        "index_exists": int((BASE / "output" / "index.html").exists()),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--update-baseline", action="store_true")
    ap.add_argument("--tolerance", type=float, default=0.05,
                    help="fraction a metric may drop before failing (default 0.05)")
    args = ap.parse_args()

    cur = metrics()

    if args.update_baseline:
        json.dump(cur, open(BASELINE, "w"), indent=2)
        print(f"✓ Baseline updated: {cur}")
        return

    if not BASELINE.exists():
        json.dump(cur, open(BASELINE, "w"), indent=2)
        print(f"⚠ No baseline existed — seeded from current state: {cur}")
        return

    base = json.load(open(BASELINE))
    failures = []
    for k, cur_v in cur.items():
        base_v = base.get(k, 0)
        if k == "index_exists":
            if cur_v < 1:
                failures.append(f"{k}: output/index.html MISSING")
            continue
        floor = base_v * (1 - args.tolerance)
        if cur_v < floor:
            pct = (1 - cur_v / base_v) * 100 if base_v else 100
            failures.append(f"{k}: {cur_v} < {floor:.0f} (baseline {base_v}, -{pct:.0f}%)")
        else:
            print(f"  ✓ {k}: {cur_v} (baseline {base_v})")

    if failures:
        print("\n✗ PIPELINE VALIDATION FAILED — deploy should be blocked:")
        for f in failures:
            print(f"    {f}")
        print("  If this drop is intentional, re-baseline: "
              "python3 execution/validate_pipeline.py --update-baseline")
        sys.exit(1)
    print("\n✓ Pipeline validation passed (all artifacts within tolerance)")


if __name__ == "__main__":
    main()
