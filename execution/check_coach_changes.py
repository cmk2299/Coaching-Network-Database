#!/usr/bin/env python3
"""
Build current head-coach snapshot from LOCAL staff data.

Background: TM hat den alten Trainer-Overview-Endpunkt
(/{liga}/trainer/wettbewerb/{Lx}) im April 2026 entfernt → 404. Vorheriger
Workaround (lokaler Fetch des Endpunkts) funktioniert daher nicht mehr.

Lösung: Wir lesen die aktuelle Staff-Snapshot-Dateien (data/staff/{club_tm_id}.json),
die `run_mvp.sh` täglich refreshed, und extrahieren den Head-Coach pro BL1/BL2/BL3-Club.
Output: output/api/check-coaches.json — vom Frontend "Trainerwechsel prüfen"-Button gelesen.

Datenfrische: hängt am --max-age-days Lauf von scrape_squads.py --staff-only in run_mvp.sh
(typisch 1 Tag), nicht an einem TM-Live-Aufruf.

Usage:
  python3 execution/check_coach_changes.py
  python3 execution/check_coach_changes.py --leagues L1 L2
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "execution"))
from lib.normalization import normalize_club  # noqa: E402

OUT = BASE / "output" / "api" / "check-coaches.json"
REGISTRY = BASE / "data" / "club_registry.json"
STAFF_DIR = BASE / "data" / "staff"
SEASON = "2025/2026"

LEAGUE_LABELS = {
    "L1": ("BL1", "1. Bundesliga"),
    "L2": ("BL2", "2. Bundesliga"),
    "L3": ("BL3", "3. Liga"),
}


def collect_clubs(league_codes: list[str]) -> dict[str, list[dict]]:
    """Pick clubs from registry that played in given leagues this season."""
    reg = json.loads(REGISTRY.read_text())
    by_league = {key: [] for key in league_codes}
    for c in reg["clubs"]:
        leagues = c.get("leagues", {}).get(SEASON, [])
        for key in league_codes:
            registry_code, _ = LEAGUE_LABELS[key]
            if registry_code in leagues:
                by_league[key].append(c)
    return by_league


def head_coach_for_club(club_tm_id: int) -> dict | None:
    """Read head_coach from staff/{tm_id}.json. Returns None if missing."""
    path = STAFF_DIR / f"{club_tm_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    candidates = []
    for entry in data.get("staff", []):
        section = (entry.get("section") or "").strip()
        role = (entry.get("role") or "").strip().lower()
        role_text = (entry.get("role_text") or "").strip().lower()
        is_trainerstab = section in ("Trainerstab", "Cheftrainer", "Trainer")
        if not is_trainerstab:
            continue
        if role == "head_coach" or "cheftrainer" in role_text or role_text == "trainer":
            candidates.append(entry)
    if not candidates:
        return None
    # Prefer explicit head_coach role, then first in list
    candidates.sort(key=lambda e: 0 if (e.get("role") or "").lower() == "head_coach" else 1)
    pick = candidates[0]
    tm_id = pick.get("tm_id")
    name = (pick.get("name") or "").strip()
    if not name or not tm_id:
        return None
    return {"name": name, "tm_id": int(tm_id)}


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--leagues",
        nargs="+",
        default=["L1", "L2", "L3"],
        choices=list(LEAGUE_LABELS.keys()),
    )
    args = parser.parse_args()

    OUT.parent.mkdir(parents=True, exist_ok=True)

    by_league = collect_clubs(args.leagues)
    results: dict[str, list[dict]] = {}
    summary_counts: list[str] = []

    for key in args.leagues:
        _, label = LEAGUE_LABELS[key]
        clubs = by_league[key]
        coaches = []
        missing = 0
        for club in clubs:
            tm_id = club["tm_id"]
            club_name = normalize_club(club["name"])
            hc = head_coach_for_club(tm_id)
            if hc is None:
                missing += 1
                continue
            coaches.append({
                "name": hc["name"],
                "tm_id": hc["tm_id"],
                "club": club_name,
                "club_tm_id": tm_id,
            })
        results[key] = coaches
        summary_counts.append(f"{label}: {len(coaches)} coaches ({missing} missing)")

    out = {
        **results,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "source": "local snapshot via execution/check_coach_changes.py (data/staff/*.json)",
        "season": SEASON,
    }

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    total = sum(len(v) for v in results.values())
    print("\n  ".join(["✓ Snapshot generated:"] + summary_counts))
    print(f"  → {OUT.relative_to(BASE)} ({total} coaches total)")


if __name__ == "__main__":
    main()
