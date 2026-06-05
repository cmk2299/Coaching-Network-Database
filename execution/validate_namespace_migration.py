#!/usr/bin/env python3
"""Phase A5: Validate Namespace Migration.

Spot-check known-bad IDs from the directive + random samples to ensure
persons_master now has correct spieler/trainer separation.

Usage:
  python3 execution/validate_namespace_migration.py
  python3 execution/validate_namespace_migration.py --random 50
"""
import argparse
import json
import random
import sys
from pathlib import Path
from typing import Optional

BASE = Path(__file__).parent.parent
MASTER = BASE / "data" / "persons_master.json"

# Known-bad IDs from directive (post-migration: BOTH variants must exist)
KNOWN_SAMPLES = [
    # (tm_id, expected_spieler, expected_trainer)
    (104,    "Fredi Bobic",            "Walter Junghans"),
    (2051,   "Patrick Hagg",           "Michael Piwowarski"),
    (1698,   "Matthias Keller",        "Pako Ayestarán"),
    (82290,  "Maximilian Schwarz",     "Dominik Krüßmann"),
    (40475,  "Fabio Lapeschi",         "Michael Meeske"),
    (122791, "Thomas Tuchel",          "Sam Stevens"),
    # Mark Zimmermann edge case (Bug 3b reference)
    (492,    "Mark Zimmermann",        None),
    (6509,   None,                     "Mark Zimmermann"),
]


def name_match(actual: Optional[str], expected: Optional[str]) -> bool:
    if expected is None:
        return actual is None or actual == ""
    if not actual:
        return False
    # last-name match (TM sometimes shortens to first-initial)
    a_last = actual.strip().split()[-1].lower() if actual else ""
    e_last = expected.strip().split()[-1].lower()
    return a_last == e_last


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--random", type=int, default=20,
                    help="Random ID sample size")
    args = ap.parse_args()

    if not MASTER.exists():
        sys.exit(f"ERR: {MASTER} not found")

    print("Loading master…")
    persons = json.load(open(MASTER))["persons"]
    print(f"  {len(persons):,} keys")

    # ── Known samples ──
    print("\n=== Known-Bad ID Checks ===")
    ok = 0
    fail = 0
    for tm_id, exp_spieler, exp_trainer in KNOWN_SAMPLES:
        for kind, expected in (("spieler", exp_spieler), ("trainer", exp_trainer)):
            key = f"{kind}_{tm_id}"
            entry = persons.get(key) or {}
            actual = entry.get("name")
            ok_flag = name_match(actual, expected)
            mark = "✓" if ok_flag else "✗"
            print(f"  {mark} {key:>14} | expected={expected or '(none)':<25} got={actual or '(none)'}")
            if ok_flag:
                ok += 1
            else:
                fail += 1

    print(f"\n  {ok} ok, {fail} fail")

    # ── Random sample ──
    print(f"\n=== Random {args.random} Numeric-ID Sample (legacy aliases) ===")
    numeric_keys = [k for k in persons if k.isdigit()]
    random.seed(42)
    sample = random.sample(numeric_keys, min(args.random, len(numeric_keys)))
    for k in sample[:8]:
        ent = persons.get(k) or {}
        print(f"  {k:>8}  type={ent.get('type','?'):<8}  name={ent.get('name','?')}")

    # ── Coverage ──
    print("\n=== Coverage ===")
    spieler_keys = [k for k in persons if k.startswith("spieler_")]
    trainer_keys = [k for k in persons if k.startswith("trainer_")]
    numeric_keys = [k for k in persons if k.isdigit()]
    print(f"  spieler_* keys: {len(spieler_keys):,}")
    print(f"  trainer_* keys: {len(trainer_keys):,}")
    print(f"  numeric (legacy alias) keys: {len(numeric_keys):,}")

    sys.exit(0 if fail == 0 else 1)


if __name__ == "__main__":
    main()
