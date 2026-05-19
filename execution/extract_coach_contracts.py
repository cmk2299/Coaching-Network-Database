#!/usr/bin/env python3
"""Liest contract_until aus existing person_profiles + persons_master.

Output: data/coach_contracts.json
  {
    "_meta": {generated_at, total, with_date, expiring_in_6mo, expiring_in_3mo},
    "contracts": {
      coach_tm_id: {
        contract_until: "30.06.2026" | "unbekannt" | null,
        parsed_date: "2026-06-30" | null,
        days_remaining: int | null,
        season_end: bool,
        verified_at: iso str,
        source: "persons_master"
      }
    }
  }

Usage:
  python3 execution/extract_coach_contracts.py
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent.parent
TODAY = datetime.now(timezone.utc).date()


def parse_contract(s):
    """Parse 'vsl. 30.06.2026' / '30.06.2026' / 'unbekannt' → date or None."""
    if not s:
        return None
    s = s.strip()
    if s.lower() in ("unbekannt", "-", "n/a", ""):
        return None
    # Strip "vsl." prefix and unicode whitespace
    s = s.replace("vsl.", "").replace("\xa0", " ").strip()
    m = re.match(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)
    if not m:
        return None
    d, mn, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return datetime(y, mn, d).date()
    except ValueError:
        return None


def main():
    persons = json.load(open(BASE / "data/persons_master.json"))["persons"]
    out = {}

    # Both trainer-typed AND spieler-typed (some SDs may be type=spieler)
    for tm_id, p in persons.items():
        cu = p.get("contract_until")
        # Skip persons with no contract data at all
        if cu is None and "contract_until" not in p:
            continue

        parsed = parse_contract(cu) if cu else None
        days = (parsed - TODAY).days if parsed else None
        out[tm_id] = {
            "contract_until": cu,
            "parsed_date": parsed.isoformat() if parsed else None,
            "days_remaining": days,
            "season_end": parsed.month in (5, 6, 7) if parsed else False,
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "source": "persons_master",
        }

    out_file = BASE / "data/coach_contracts.json"
    with_date = sum(1 for v in out.values() if v["parsed_date"])
    expiring_6mo = sum(1 for v in out.values()
                       if v["days_remaining"] is not None and 0 <= v["days_remaining"] <= 180)
    expiring_3mo = sum(1 for v in out.values()
                       if v["days_remaining"] is not None and 0 <= v["days_remaining"] <= 90)

    json.dump({
        "_meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total": len(out),
            "with_date": with_date,
            "expiring_in_6mo": expiring_6mo,
            "expiring_in_3mo": expiring_3mo,
        },
        "contracts": out,
    }, open(out_file, "w"), ensure_ascii=False, indent=2)

    print(f"✓ {len(out)} contracts → {out_file}")
    print(f"  with parsed date:    {with_date}")
    print(f"  expiring in 6 mo:    {expiring_6mo}")
    print(f"  expiring in 3 mo:    {expiring_3mo}")


if __name__ == "__main__":
    main()
