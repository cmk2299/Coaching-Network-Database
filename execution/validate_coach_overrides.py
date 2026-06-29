#!/usr/bin/env python3
"""Validate data/coach_overrides.json — catch typos before they ship.

Checks every entry's:
  • required fields present
  • tm_id integer + > 0
  • club_tm_id integer + > 0
  • appointed.replaces_tm_id (if non-null) is integer + > 0
  • appointed entries don't conflict (no two appointed for same club_tm_id)
  • sd entries don't conflict (no two sd for same club_tm_id)

Run:
  python3 execution/validate_coach_overrides.py
  → exit 0 if clean, 1 with a list of issues otherwise.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
OVERRIDES = BASE / "data" / "coach_overrides.json"


def _is_pos_int(v):
    return isinstance(v, int) and not isinstance(v, bool) and v > 0


def validate(data: dict) -> list[str]:
    issues: list[str] = []
    sacked = data.get("sacked", [])
    appointed = data.get("appointed", [])
    sd = data.get("sd", [])

    for label, lst, required, optional_int in (
        ("sacked", sacked, ("club_tm_id", "club", "tm_id", "name"), ()),
        ("appointed", appointed, ("club_tm_id", "club", "tm_id", "name"),
         ("replaces_tm_id",)),
        ("sd", sd, ("club_tm_id", "club", "tm_id", "name"), ()),
    ):
        for i, e in enumerate(lst):
            tag = f"{label}[{i}] ({e.get('name', '?')})"
            for k in required:
                if k not in e:
                    issues.append(f"{tag}: missing required '{k}'")
            for k in ("club_tm_id", "tm_id"):
                if k in e and not _is_pos_int(e[k]):
                    issues.append(f"{tag}: {k}={e[k]!r} must be int > 0")
            for k in optional_int:
                if k in e and e[k] is not None and not _is_pos_int(e[k]):
                    issues.append(f"{tag}: optional {k}={e[k]!r} must be int>0 or null")

    for label, lst in (("appointed", appointed), ("sd", sd)):
        clubs = Counter(e["club_tm_id"] for e in lst if "club_tm_id" in e)
        for cid, n in clubs.items():
            if n > 1:
                names = [e.get("name", "?") for e in lst if e.get("club_tm_id") == cid]
                issues.append(f"{label}: club_tm_id={cid} has {n} entries — "
                              f"only one allowed: {names}")

    return issues


def main():
    if not OVERRIDES.exists():
        print(f"⚠ {OVERRIDES} not found — nothing to validate")
        return 0
    try:
        data = json.load(open(OVERRIDES))
    except json.JSONDecodeError as e:
        print(f"✗ INVALID JSON in {OVERRIDES}: {e}")
        return 1

    issues = validate(data)
    if issues:
        print(f"✗ {OVERRIDES.name}: {len(issues)} issue(s)")
        for i in issues:
            print(f"    {i}")
        return 1
    counts = " · ".join(f"{k}={len(v)}" for k, v in data.items()
                        if isinstance(v, list))
    print(f"✓ {OVERRIDES.name} valid ({counts})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
