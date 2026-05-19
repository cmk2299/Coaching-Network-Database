#!/usr/bin/env python3
"""Computes availability_status pro Trainer aus mehreren Quellen.

Sources:
  - persons_master.json (current_club)
  - coach_contracts.json (Vertragsende)
  - coach_mood_signals.json (News-Signale für 'wechselbereit')

Output: data/coach_availability.json
  {
    "_meta": {generated_at, total, by_status},
    "availability": {
      coach_tm_id: {
        name, status, reason, current_club, contract_until,
        days_remaining, last_updated
      }
    }
  }

Status values:
  - vereinslos:           current_club ∈ {Karriereende, Vereinslos, ""}
  - frei_zum_saisonende:  Vertrag < 120 Tage AND season_end (Mai-Jul)
                          OR Vertrag < 60 Tage (any month)
  - wechselbereit:        News-Signal "X bietet sich an" / "X will weg" etc.
  - kontraktiert:         Vertrag > 6 Monate
  - unbekannt:            keine Vertrags- oder Vereins-Daten
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent.parent

WECHSELBEREIT_PATTERNS = [
    r"bietet sich an",
    r"will (verein )?verlassen",
    r"sucht? neue herausforderung",
    r"(steht )?vor (dem )?wechsel",
    r"will weg",
    r"abschied (steht|naht|verkündet)",
]

VEREINSLOS_VALUES = {"Karriereende", "Vereinslos", "-", "", None}


def calc_status(profile, contract, mood):
    """Return (status, reason)."""
    cc = (profile or {}).get("current_club") or {}
    cc_name = cc.get("name") if isinstance(cc, dict) else cc

    # 1. vereinslos
    if cc_name in VEREINSLOS_VALUES:
        return ("vereinslos", "current_club leer/Karriereende")

    # 2. frei zum saisonende
    if contract and contract.get("days_remaining") is not None:
        days = contract["days_remaining"]
        if 0 <= days <= 120 and contract.get("season_end"):
            return ("frei_zum_saisonende",
                    f"Vertrag bis {contract['contract_until']} ({days}d, Saisonende)")
        if 0 <= days <= 60:
            return ("frei_zum_saisonende",
                    f"Vertrag bis {contract['contract_until']} ({days}d)")

    # 3. wechselbereit (Mood-Signal)
    if mood:
        all_signals = " ".join(
            [h.get("title", "") for h in (mood.get("headlines_sample") or [])]
        ).lower()
        for p in WECHSELBEREIT_PATTERNS:
            if re.search(p, all_signals):
                return ("wechselbereit", f"News-Signal: '{p}'")

    # 4. kontraktiert
    if contract and (contract.get("days_remaining") or 0) > 180:
        return ("kontraktiert", f"Vertrag bis {contract.get('contract_until')}")

    # 5. unbekannt
    return ("unbekannt", "keine Vertrags- oder Vereins-Daten")


def main():
    persons = json.load(open(BASE / "data/persons_master.json"))["persons"]

    contracts = {}
    cf = BASE / "data/coach_contracts.json"
    if cf.exists():
        contracts = json.load(open(cf)).get("contracts", {})

    moods = {}
    mf = BASE / "data/coach_mood_signals.json"
    if mf.exists():
        moods = json.load(open(mf)).get("signals", {})
        # Mood signals use int keys — normalize to str
        moods = {str(k): v for k, v in moods.items()}

    out = {}
    for tm_id, p in persons.items():
        # Include trainer-typed AND any person with a contract record
        # (some SDs are type=spieler but still relevant)
        if p.get("type") != "trainer" and tm_id not in contracts:
            continue
        status, reason = calc_status(p, contracts.get(tm_id), moods.get(tm_id))
        cc = p.get("current_club") or {}
        cc_name = cc.get("name") if isinstance(cc, dict) else cc
        contract = contracts.get(tm_id) or {}
        out[tm_id] = {
            "name": p.get("name"),
            "status": status,
            "reason": reason,
            "current_club": cc_name,
            "contract_until": contract.get("contract_until"),
            "days_remaining": contract.get("days_remaining"),
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

    by_status = {}
    for s in ("vereinslos", "frei_zum_saisonende", "wechselbereit",
              "kontraktiert", "unbekannt"):
        by_status[s] = sum(1 for v in out.values() if v["status"] == s)

    out_file = BASE / "data/coach_availability.json"
    json.dump({
        "_meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total": len(out),
            "by_status": by_status,
        },
        "availability": out,
    }, open(out_file, "w"), ensure_ascii=False, indent=2)

    print(f"✓ {len(out)} coaches → {out_file}")
    print("  Status-Breakdown:")
    for s, n in sorted(by_status.items(), key=lambda kv: -kv[1]):
        print(f"    {s:<25} {n}")


if __name__ == "__main__":
    main()
