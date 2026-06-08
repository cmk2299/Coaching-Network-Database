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


def _latest_season() -> str:
    """Derive the latest season label present in the registry's leagues maps so
    this snapshot never goes stale on a hardcoded constant (was "2025/2026")."""
    try:
        import json as _json
        reg = _json.load(open(REGISTRY))
        clubs = reg.get("clubs", reg) if isinstance(reg, dict) else reg
        seasons = set()
        for c in (clubs.values() if isinstance(clubs, dict) else clubs):
            seasons.update((c.get("leagues") or {}).keys())
        # season labels sort lexicographically by start year ("2026/2027" > "2025/2026")
        return max(seasons) if seasons else "2025/2026"
    except Exception:
        return "2025/2026"


SEASON = _latest_season()

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


def _appointed_overrides() -> "dict[int, dict]":
    """Map club_tm_id -> appointed-coach override. Covers TM-lag where a newly
    hired Cheftrainer isn't on TM's staff page yet (e.g. Strobl@Wolfsburg,
    Lustrinelli@Union). Without this, such clubs falsely report 'missing'."""
    try:
        ov = json.loads((BASE / "data" / "coach_overrides.json").read_text())
    except (json.JSONDecodeError, OSError):
        return {}
    out = {}
    for e in ov.get("appointed", []):
        cid = e.get("club_tm_id")
        if cid and e.get("name") and e.get("tm_id"):
            out[int(cid)] = {"name": e["name"].strip(), "tm_id": int(e["tm_id"]),
                             "source": "override"}
    return out


def head_coach_for_club(club_tm_id: int) -> "dict | None":
    """Return the club's head coach. An appointed-override ALWAYS wins — it is a
    manually-confirmed statement "this club's HC is X now" and must take
    precedence over the scraped staff page, which lags reality (still lists the
    outgoing HC, e.g. Hjulmand@Leverkusen until TM updates)."""
    override = _appointed_overrides().get(int(club_tm_id))
    if override:
        return override
    path = STAFF_DIR / f"{club_tm_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return override
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
        return override
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
