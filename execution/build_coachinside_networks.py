#!/usr/bin/env python3
"""
build_coachinside_networks.py

Take the matched_no_network list from data/coachinside_gap_report.json and run
build_coach_network.py + generate_dashboard.py for each tm_id that does not yet
have data/networks/{tm_id}.json.

Mirrors the run_build() pattern of execution/build_trainerstab_networks.py:
  - subprocess + 180s build timeout + 60s dashboard timeout
  - capture stderr last-500-chars on failure
  - per-row ETA + counter

Usage:
  python3 execution/build_coachinside_networks.py
  python3 execution/build_coachinside_networks.py --refresh-gap
  python3 execution/build_coachinside_networks.py --dry-run
  python3 execution/build_coachinside_networks.py --max 20
  python3 execution/build_coachinside_networks.py --start-from 12345
  python3 execution/build_coachinside_networks.py --filter csv_source=vereinslos
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent.parent
DATA = BASE / "data"
NETS = DATA / "networks"
LOGS = BASE / "logs"
GAP_REPORT = DATA / "coachinside_gap_report.json"
DIFF_SCRIPT = BASE / "execution" / "diff_coachinside_csvs.py"
BUILD_SCRIPT = BASE / "execution" / "build_coach_network.py"
DASH_SCRIPT = BASE / "execution" / "generate_dashboard.py"

LOGS.mkdir(parents=True, exist_ok=True)


def refresh_gap_report() -> None:
    """Re-run diff_coachinside_csvs.py so matched_no_network reflects newly
    scraped persons + freshly built networks."""
    print("[refresh] re-running diff_coachinside_csvs.py …")
    r = subprocess.run(
        ["python3", str(DIFF_SCRIPT)],
        cwd=BASE, capture_output=True, text=True, timeout=120,
    )
    if r.returncode != 0:
        print(f"[refresh] WARN diff exit={r.returncode}\n{r.stderr[-400:]}",
              file=sys.stderr)
    else:
        print("[refresh] gap report updated.")


def load_targets(filt: dict) -> list[dict]:
    if not GAP_REPORT.exists():
        print(f"[err] {GAP_REPORT} not found — run diff_coachinside_csvs.py first",
              file=sys.stderr)
        sys.exit(1)
    gap = json.loads(GAP_REPORT.read_text(encoding="utf-8"))
    rows = gap.get("matched_no_network", [])

    # Apply filter
    if "csv_source" in filt:
        rows = [r for r in rows if r.get("file") == filt["csv_source"]]

    # Drop rows whose network now exists (race-safe)
    rows = [r for r in rows if not (NETS / f"{r['tm_id']}.json").exists()]

    # Stable order: file → name
    rows.sort(key=lambda r: (r.get("file", ""), r.get("full_name", "")))
    return rows


def parse_filter(f: str | None) -> dict:
    if not f:
        return {}
    out = {}
    for part in f.split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def run_build(tm_id: int, name: str, log_handle) -> tuple[bool, str]:
    """Build network + dashboard for one tm_id. Mirrors
    build_trainerstab_networks.run_build().
    Returns (success, fail_step)."""
    try:
        r1 = subprocess.run(
            ["python3", str(BUILD_SCRIPT), "--tm-id", str(tm_id)],
            cwd=BASE, capture_output=True, text=True, timeout=180,
        )
        log_handle.write(f"\n  [{name} {tm_id}] build exit={r1.returncode}\n")
        if r1.returncode != 0:
            log_handle.write(f"    stderr: {r1.stderr[-500:]}\n")
            return False, "build"

        net_file = NETS / f"{tm_id}.json"
        if not net_file.exists():
            log_handle.write("    network file missing after build\n")
            return False, "build-no-output"

        r2 = subprocess.run(
            ["python3", str(DASH_SCRIPT), "--network", str(net_file)],
            cwd=BASE, capture_output=True, text=True, timeout=60,
        )
        log_handle.write(f"  [{name} {tm_id}] dashboard exit={r2.returncode}\n")
        if r2.returncode != 0:
            log_handle.write(f"    stderr: {r2.stderr[-500:]}\n")
            return False, "dashboard"
        return True, ""
    except subprocess.TimeoutExpired as e:
        log_handle.write(f"  [{name} {tm_id}] TIMEOUT in {getattr(e, 'cmd', '')!s}\n")
        return False, "timeout"
    except Exception as e:
        log_handle.write(f"  [{name} {tm_id}] EXC {e!r}\n")
        return False, "exception"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--refresh-gap", action="store_true",
                    help="Re-run diff_coachinside_csvs.py first")
    ap.add_argument("--max", type=int, default=0, help="Cap N rows (0=all)")
    ap.add_argument("--start-from", type=int, default=None,
                    help="Resume after a tm_id (skips all <= this id by file order)")
    ap.add_argument("--filter", type=str, default=None,
                    help="csv_source=vereinslos|active_headcoaches|trainerstab_dach")
    ap.add_argument("--log", type=str, default=None,
                    help="Override log path")
    args = ap.parse_args()

    if args.refresh_gap:
        refresh_gap_report()

    flt = parse_filter(args.filter)
    targets = load_targets(flt)

    if args.start_from is not None:
        # cut from the first occurrence of tm_id == start-from (inclusive)
        idxs = [i for i, t in enumerate(targets) if int(t["tm_id"]) == args.start_from]
        if idxs:
            targets = targets[idxs[0]:]
            print(f"[resume] starting from tm_id={args.start_from} "
                  f"(index {idxs[0]})")

    if args.max > 0:
        targets = targets[:args.max]

    print("== Coachinside Networks Builder ==")
    print(f"  Targets: {len(targets)}  (filter={flt or 'none'})")
    if args.dry_run:
        print("  DRY RUN — first 10:")
        for t in targets[:10]:
            print(f"    {t['full_name']:<30} TM:{t['tm_id']:<8} "
                  f"[{t.get('file', '')}]  {t.get('team', '—')}")
        return 0

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = Path(args.log) if args.log else LOGS / f"coachinside_networks_{timestamp}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    success = 0
    fail = 0
    fail_reasons: dict[str, int] = {}
    start = time.time()

    with open(log_path, "w", encoding="utf-8") as lh:
        lh.write(f"# coachinside_networks {timestamp}\n")
        lh.write(f"# targets: {len(targets)}\n\n")

        for i, t in enumerate(targets, 1):
            tm_id = int(t["tm_id"])
            name = t.get("full_name") or "?"
            elapsed = time.time() - start
            eta_min = ((elapsed / i) * (len(targets) - i) / 60) if i > 0 else 0
            print(f"  [{i:3d}/{len(targets)}] {name[:28]:<28} "
                  f"TM:{tm_id:<8} {t.get('file','')[:18]:<18} "
                  f"@ {(t.get('team') or '—')[:22]:<22}  ETA {eta_min:.0f}min",
                  flush=True)
            ok, why = run_build(tm_id, name, lh)
            if ok:
                success += 1
            else:
                fail += 1
                fail_reasons[why] = fail_reasons.get(why, 0) + 1

    duration_min = (time.time() - start) / 60
    print()
    print(f"  ✓ {success} ok / ✗ {fail} fail in {duration_min:.1f} min")
    if fail_reasons:
        print(f"  Fail-Buckets: {fail_reasons}")
    print(f"  Log: {log_path}")
    return 0 if fail == 0 else (1 if success == 0 else 0)


if __name__ == "__main__":
    sys.exit(main())
