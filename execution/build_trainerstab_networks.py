#!/usr/bin/env python3
"""
Build networks for ALL BL1/BL2/BL3 Trainerstab-Members without networks.

Sprint A+: Mass-Coverage für Co-Trainer / Torwart-Trainer / Analysten / Fitness.
Coachinside listet die — nach Stakeholder-Pivot ist das Tier 1 Fokus.

Tier strategy:
  T1 (priority): assistant_coach + goalkeeper_coach  (~170 Networks)
  T2 (medium):   analyst                              (~75 Networks)
  T3 (low):      fitness_coach + other_staff          (~80 Networks)

Usage:
  python3 execution/build_trainerstab_networks.py --tier 1
  python3 execution/build_trainerstab_networks.py --all --max=50
  python3 execution/build_trainerstab_networks.py --dry-run
"""
import argparse
import json
import subprocess
import time
from pathlib import Path

BASE = Path(__file__).parent.parent
REG = BASE / "data" / "club_registry.json"
STAFF = BASE / "data" / "staff"
NETS = BASE / "data" / "networks"
OUT_DASH = BASE / "output" / "dashboards"

TIER_ROLES = {
    1: {"assistant_coach", "goalkeeper_coach"},
    2: {"analyst"},
    3: {"fitness_coach", "other_staff"},
}
ALL_ROLES = TIER_ROLES[1] | TIER_ROLES[2] | TIER_ROLES[3]
SEASON = "2025/2026"


def collect_targets(roles: set) -> list[dict]:
    """Find unique BL1/BL2/BL3 Trainerstab-Members with given roles + missing network."""
    reg = json.loads(REG.read_text())["clubs"]
    bl_clubs = [
        c for c in reg
        if any(lg in ("BL1", "BL2", "BL3") for lg in c.get("leagues", {}).get(SEASON, []))
    ]
    seen = set()
    out = []
    for c in bl_clubs:
        path = STAFF / f"{c['tm_id']}.json"
        if not path.exists():
            continue
        try:
            sd = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        for entry in sd.get("staff", []):
            tid = entry.get("tm_id")
            if not tid or tid in seen:
                continue
            sec = entry.get("section") or ""
            role = entry.get("role") or ""
            if sec != "Trainerstab":
                continue
            if role not in roles:
                continue
            net = NETS / f"{tid}.json"
            if net.exists():
                continue
            out.append({
                "tm_id": int(tid),
                "name": entry.get("name") or "",
                "role": role,
                "club": c["name"],
            })
            seen.add(tid)
    return out


def run_build(tm_id: int, name: str, log_handle) -> bool:
    """Run build_coach_network.py + generate_dashboard.py for one tm_id."""
    try:
        r1 = subprocess.run(
            ["python3", "execution/build_coach_network.py", "--tm-id", str(tm_id)],
            cwd=BASE, capture_output=True, text=True, timeout=180,
        )
        log_handle.write(f"\n  [{name} {tm_id}] build exit={r1.returncode}\n")
        if r1.returncode != 0:
            log_handle.write(f"    stderr: {r1.stderr[-500:]}\n")
            return False
        net_file = NETS / f"{tm_id}.json"
        if not net_file.exists():
            log_handle.write("    network file missing after build\n")
            return False
        r2 = subprocess.run(
            ["python3", "execution/generate_dashboard.py", "--network", str(net_file)],
            cwd=BASE, capture_output=True, text=True, timeout=60,
        )
        log_handle.write(f"  [{name} {tm_id}] dashboard exit={r2.returncode}\n")
        return r2.returncode == 0
    except subprocess.TimeoutExpired:
        log_handle.write(f"  [{name} {tm_id}] TIMEOUT\n")
        return False
    except Exception as e:
        log_handle.write(f"  [{name} {tm_id}] ERR {e}\n")
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tier", type=int, choices=[1, 2, 3], help="Single tier")
    parser.add_argument("--all", action="store_true", help="All tiers")
    parser.add_argument("--max", type=int, default=0, help="Cap at N (0=unlimited)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--log", type=str, default=None)
    args = parser.parse_args()

    if args.tier:
        roles = TIER_ROLES[args.tier]
        label = f"Tier {args.tier} ({', '.join(sorted(roles))})"
    elif args.all:
        roles = ALL_ROLES
        label = "All tiers"
    else:
        parser.error("Must specify --tier <1|2|3> or --all")

    targets = collect_targets(roles)
    if args.max > 0:
        targets = targets[:args.max]

    print(f"\n=== {label} ===")
    print(f"Targets: {len(targets)} Trainerstab-Members ohne Network")
    from collections import Counter
    cnt = Counter(t["role"] for t in targets)
    for r, n in cnt.most_common():
        print(f"  {r:<22} {n}")

    if args.dry_run:
        print("\n  (dry-run — first 8 targets:)")
        for t in targets[:8]:
            print(f"    {t['name']:<28} ({t['tm_id']}) [{t['role']}] @ {t['club']}")
        return

    log_path = args.log or str(BASE / "logs" / f"trainerstab_{label.replace(' ','_')}.log")
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)

    success = 0
    fail = 0
    start = time.time()
    with open(log_path, "w") as lh:
        lh.write(f"Started {label} with {len(targets)} targets at {time.strftime('%H:%M:%S')}\n")
        for i, t in enumerate(targets, 1):
            elapsed = time.time() - start
            eta_sec = (elapsed / i) * (len(targets) - i) if i > 0 else 0
            print(f"  [{i:3d}/{len(targets)}] {t['name'][:25]:<25} ({t['tm_id']}) {t['role']:<18} @ {t['club'][:20]:<20}  ETA {eta_sec/60:.0f}min", flush=True)
            ok = run_build(t["tm_id"], t["name"], lh)
            if ok:
                success += 1
            else:
                fail += 1

    print(f"\n  ✓ {success} successful, {fail} failed in {(time.time()-start)/60:.1f} min")
    print(f"  Log: {log_path}")


if __name__ == "__main__":
    main()
