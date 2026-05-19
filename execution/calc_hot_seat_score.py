#!/usr/bin/env python3
"""
Hot-Seat-Score Calculator — projectFIVE Trainerberatung.

Combines openligadb match results (data/match_results/club_form_2025.json)
with our staff data (data/staff/{club_tm_id}.json) to score every active
BL1/BL2/BL3 head coach by replacement-risk.

Score 0-100:
  0-39   ruhig (no replacement risk)
  40-69  warm (form wackelig, beobachten)
  70-84  hot-seat (Trainerwechsel realistisch in 2-6 Wochen)
  85-100 critical (Wechsel praktisch zwingend)

Usage:
  python3 execution/calc_hot_seat_score.py
  python3 execution/calc_hot_seat_score.py --season 2025

Output: data/hot_seat_scores.json
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent.parent
DATA = BASE / "data"
MATCH_DIR = DATA / "match_results"
STAFF_DIR = DATA / "staff"
EXPECTATIONS = DATA / "club_expectations.json"
MOOD_SIGNALS = DATA / "coach_mood_signals.json"
COACH_CONTRACTS = DATA / "coach_contracts.json"
HOT_SEAT_OVERRIDES = DATA / "hot_seat_overrides.json"


def load_expectations() -> dict:
    if not EXPECTATIONS.exists():
        return {}
    try:
        return json.load(open(EXPECTATIONS))
    except Exception:
        return {}


def load_mood_signals() -> dict:
    """Load coach_mood_signals.json (Mood-Layer A).
    Returns: {coach_tm_id: {mood_score, kiss_of_death_signals, ...}}.
    """
    if not MOOD_SIGNALS.exists():
        return {}
    try:
        d = json.load(open(MOOD_SIGNALS))
        return {int(k): v for k, v in d.get("signals", {}).items()}
    except Exception:
        return {}


def load_coach_contracts() -> dict:
    """Load coach_contracts.json.
    Returns: {coach_tm_id: {contract_until, parsed_date, days_remaining, ...}}.
    """
    if not COACH_CONTRACTS.exists():
        return {}
    try:
        d = json.load(open(COACH_CONTRACTS))
        return {int(k): v for k, v in d.get("contracts", {}).items()}
    except Exception:
        return {}


def load_hot_seat_overrides() -> dict:
    """Load hot_seat_overrides.json — manual score caps for vote-of-confidence cases.

    Returns: {coach_tm_id (int): override_dict} where override has
      action, until_date (ISO), score_cap, status_override, source.
    Only returns overrides whose until_date is still in the future.
    """
    if not HOT_SEAT_OVERRIDES.exists():
        return {}
    try:
        raw = json.load(open(HOT_SEAT_OVERRIDES))
    except Exception:
        return {}
    from datetime import date
    today = date.today()
    out = {}
    for tm_id, ov in raw.get("overrides", {}).items():
        ud = ov.get("until_date")
        if ud:
            try:
                y, m, d = ud.split("-")
                if date(int(y), int(m), int(d)) < today:
                    continue  # expired override — ignore
            except Exception:
                pass
        try:
            out[int(tm_id)] = ov
        except (ValueError, TypeError):
            pass
    return out

# Manual overrides for openligadb-name → TM-name mismatch
NAME_OVERRIDES = {
    "TSG Hoffenheim": "TSG 1899 Hoffenheim",
}


def normalize_for_match(n: str) -> str:
    n = n.lower()
    n = n.replace("1.", "").replace("fc ", "").replace("sv ", "").replace("vfb ", "")
    n = n.replace(" ", "").replace("-", "").replace(".", "").replace("'", "")
    n = n.replace("ü", "u").replace("ö", "o").replace("ä", "a").replace("ß", "ss")
    return n


def build_name_map(registry: list, season_key: str = "2025/2026") -> dict:
    """Map normalized openligadb name → TM tm_id."""
    out = {}
    for c in registry:
        leagues = c.get("leagues", {}).get(season_key, [])
        if any(l in ("BL1", "BL2", "BL3") for l in leagues):
            out[normalize_for_match(c["name"])] = c["tm_id"]
    return out


def find_head_coach(club_tm_id: int) -> dict:
    """First 'Trainerstab' entry per club is consistently the head coach."""
    p = STAFF_DIR / f"{club_tm_id}.json"
    if not p.exists():
        return {}
    try:
        s = json.load(open(p))
    except Exception:
        return {}
    first = next(
        (x for x in s.get("staff", []) if x.get("section") == "Trainerstab"),
        None,
    )
    if not first:
        return {}
    return {
        "tm_id": first.get("tm_id"),
        "name": first.get("name"),
        "tm_url": first.get("tm_url"),
    }


def calc_score(form: dict, league: str, expectation: dict = None,
               mood: dict = None, contract: dict = None) -> dict:
    """8-component hot-seat score (0-100). Captures form + position +
    expectation-gap + winless + days + goal-diff + mood + contract-expiry.

    Mood-Layer (Phase 2, 2026-05-04) catches the secondary Riera-Pattern:
    headlines reveal internal pressure even with okay form. Mood max 15 pts.

    Contract-Layer (Phase 2, 2026-05-XX): "Vertrag läuft aus < 3 Mo" is the
    second-strongest activation trigger after wackel-form. Max 8 pts.
    """
    components = {}
    score = 0

    # 1. Recent form: last-5 PPG (30 pts)
    ppg = form.get("last5_ppg", 0.0)
    if ppg < 0.4:
        c = 30
    elif ppg < 0.8:
        c = 22
    elif ppg < 1.2:
        c = 13
    elif ppg < 1.5:
        c = 5
    else:
        c = 0
    components["form"] = c
    score += c

    # 2. Tabellen-Position absolut (Relegation/Abstieg) — 20 pts
    pos = form.get("position")
    table_size = form.get("table_size") or {"BL1": 18, "BL2": 18, "BL3": 20}.get(league, 18)
    rel_zone_start = {"BL1": 16, "BL2": 16, "BL3": 18}.get(league, 16)
    if pos is None:
        c = 0
    elif pos >= table_size - 1:
        c = 20  # Last 2 → critical
    elif pos >= rel_zone_start:
        c = 14  # Relegation zone
    elif pos >= int(table_size * 0.7):
        c = 6   # Lower third
    else:
        c = 0
    components["position"] = c
    score += c

    # 3. Expectation-Gap (NEU 2026-05-04, Riera-Pattern, 20 pts)
    # Big-tier club (CL/EL ambition) at lower-half = HUGE pressure even with
    # mid PPG. Small-tier club at relegation zone is only flagged via #2 above.
    exp_gap_pts = 0
    if expectation and pos is not None:
        expected_max = expectation.get("expected_max_pos")
        tier = expectation.get("tier", "C")
        if expected_max:
            gap = pos - expected_max
            # Tier-A (CL): every position below CL line = 4 pts (Bayern out of top 1 alone)
            # Tier-B (EL): every position below EL line = 3 pts (Frankfurt out of top 6)
            # Tier-C: 1 pt per position below (light pressure)
            # Tier-D: 0 (no expectation pressure, just survival)
            if gap > 0 and tier in ("S", "A"):
                exp_gap_pts = min(20, gap * 4)
            elif gap > 0 and tier == "B":
                exp_gap_pts = min(18, gap * 3)
            elif gap > 0 and tier == "C":
                exp_gap_pts = min(10, gap * 1)
            elif gap > 0 and tier == "D":
                exp_gap_pts = 0
    components["expectation_gap"] = exp_gap_pts
    score += exp_gap_pts

    # 4. Winless streak (15 pts)
    streak = form.get("winless_streak", 0)
    if streak >= 8:
        c = 15
    elif streak >= 5:
        c = 11
    elif streak >= 3:
        c = 6
    else:
        c = 0
    components["winless_streak"] = c
    score += c

    # 5. Days since last win (5 pts)
    days = form.get("days_since_win")
    if days is None or days > 60:
        c = 5
    elif days > 30:
        c = 3
    elif days > 21:
        c = 1
    else:
        c = 0
    components["days_since_win"] = c
    score += c

    # 6. Goal differential last 5 (10 pts)
    gd = form.get("last5_goal_diff", 0)
    if gd <= -7:
        c = 10
    elif gd <= -4:
        c = 6
    elif gd <= -2:
        c = 3
    else:
        c = 0
    components["goal_diff"] = c
    score += c

    # 7. Mood / News-Sentiment (Phase 2 — catches Riera-Pattern, max 15 pts)
    mood_pts = 0
    mood_score = 0
    if mood:
        mood_score = mood.get("mood_score", 0)  # 0-20 from scrape_coach_mood.py
        mood_pts = min(15, int(round(mood_score * 0.75)))  # 20 → 15
    components["mood"] = mood_pts
    score += mood_pts

    # 8. Contract-Expiry-Pressure (Aktivierungs-Trigger, max 8 pts)
    # < 90 Tage = 8 (HOT trigger), < 180 = 5 (warm), < 365 = 2 (light), else 0.
    # Already-expired = 0 (neutral; coach is technically frei but still in club).
    contract_pts = 0
    contract_days = None
    if contract:
        contract_days = contract.get("days_remaining")
        if contract_days is not None and contract_days >= 0:
            if contract_days < 90:
                contract_pts = 8
            elif contract_days < 180:
                contract_pts = 5
            elif contract_days < 365:
                contract_pts = 2
    components["contract_expiry"] = contract_pts
    score += contract_pts

    return {
        "score": min(score, 100),
        "components": components,
        "ppg": ppg,
        "position": pos,
        "winless_streak": streak,
        "days_since_win": days,
        "goal_diff": gd,
        "expected_max_pos": (expectation or {}).get("expected_max_pos"),
        "tier": (expectation or {}).get("tier"),
        "ambition": (expectation or {}).get("ambition"),
        "mood_score": mood_score,
        "mood_signals": {
            "kiss_of_death": (mood or {}).get("kiss_of_death_signals", []),
            "wackel": (mood or {}).get("wackel_signals", []),
            "criticism": (mood or {}).get("criticism_signals", []),
            "articles_n": (mood or {}).get("articles_n", 0),
        } if mood else None,
        "contract_until": (contract or {}).get("contract_until"),
        "contract_days_remaining": contract_days,
    }


def status_label(score: int) -> str:
    """Thresholds tuned for projectFIVE Trainerberatungs-Praxis:
      80+ critical: Wechsel realistisch innerhalb 2-6 Wochen
      65+ hot-seat: Beratung sollte angestoßen werden
      45+ warm:    beobachten, Backstory aufbauen
      <45  ruhig:  keine Aktion nötig
    """
    if score >= 80:
        return "critical"
    if score >= 65:
        return "hot-seat"
    if score >= 45:
        return "warm"
    return "ruhig"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, default=2025)
    args = parser.parse_args()

    form_file = MATCH_DIR / f"club_form_{args.season}.json"
    if not form_file.exists():
        print(f"✗ {form_file} not found. Run scrape_match_results.py first.")
        sys.exit(1)

    form_data = json.load(open(form_file))
    clubs_form = form_data["clubs"]

    registry = json.load(open(DATA / "club_registry.json"))["clubs"]
    name_to_tm = build_name_map(registry, f"{args.season}/{args.season+1}")
    expectations = load_expectations()
    mood_signals = load_mood_signals()
    contracts = load_coach_contracts()
    hot_seat_overrides = load_hot_seat_overrides()

    results = []
    matched = 0
    no_coach = 0

    for old_id, c in clubs_form.items():
        # Resolve openligadb name → TM tm_id
        oligadb_name = c["name"]
        canonical = NAME_OVERRIDES.get(oligadb_name, oligadb_name)
        nn = normalize_for_match(canonical)
        tm_club_id = name_to_tm.get(nn)
        if not tm_club_id:
            # Try substring fallback
            cands = [v for k, v in name_to_tm.items() if nn in k or k in nn]
            tm_club_id = cands[0] if len(cands) == 1 else None
        if not tm_club_id:
            print(f"  ⚠ No TM-id for {oligadb_name}")
            continue
        matched += 1

        coach = find_head_coach(tm_club_id)
        if not coach.get("tm_id"):
            no_coach += 1
            continue

        # Resolve expectation: try canonical name first, then a few normalised variants
        league_exp = expectations.get(c["league"], {})
        exp_entry = league_exp.get(canonical) or league_exp.get(oligadb_name) or {}
        if not exp_entry:
            # Try fuzzy by normalize
            for k, v in league_exp.items():
                if isinstance(v, dict) and normalize_for_match(k) == normalize_for_match(canonical):
                    exp_entry = v
                    break

        mood_entry = mood_signals.get(coach["tm_id"])
        contract_entry = contracts.get(coach["tm_id"])
        score_data = calc_score(c, c["league"],
                                expectation=exp_entry or None,
                                mood=mood_entry,
                                contract=contract_entry)
        # Apply manual vote-of-confidence override if active (caps score + status)
        ov = hot_seat_overrides.get(coach["tm_id"])
        if ov:
            cap = ov.get("score_cap", 35)
            if score_data["score"] > cap:
                score_data["_override_applied"] = {
                    "action": ov.get("action"),
                    "score_was": score_data["score"],
                    "score_cap": cap,
                    "source": ov.get("source"),
                    "until_date": ov.get("until_date"),
                }
                score_data["score"] = cap
            status = ov.get("status_override") or status_label(score_data["score"])
        else:
            status = status_label(score_data["score"])
        results.append({
            "coach_tm_id": coach["tm_id"],
            "coach_name": coach["name"],
            "club_tm_id": tm_club_id,
            "club_name": canonical,
            "league": c["league"],
            **score_data,
            "status": status,
        })

    # Sort by score DESC
    results.sort(key=lambda x: -x["score"])

    out = {
        "_meta": {
            "calculated_at": datetime.now(timezone.utc).isoformat(),
            "season": args.season,
            "matched_clubs": matched,
            "missing_coach": no_coach,
            "thresholds": {
                "critical": 80,
                "hot_seat": 65,
                "warm": 45,
                "ruhig": 0,
            },
        },
        "scores": results,
    }
    with open(DATA / "hot_seat_scores.json", "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # Print summary
    by_status = {}
    for r in results:
        by_status.setdefault(r["status"], []).append(r)

    print(f"\n=== Hot-Seat-Score Summary (Saison {args.season}/{args.season+1}) ===")
    print(f"  Clubs analyzed: {matched}")
    print(f"  No head-coach in staff: {no_coach}")
    print(f"  Status:")
    for status in ("critical", "hot-seat", "warm", "ruhig"):
        n = len(by_status.get(status, []))
        print(f"    {status:<10} {n}")

    print(f"\n=== Top 12 Hot-Seats ===")
    for r in results[:12]:
        print(f"  {r['score']:>3}  {r['status']:<10} {r['league']:<3} #{(r['position'] or '?'):<2} "
              f"{r['coach_name']:<22} ({r['club_name']:<24}) "
              f"PPG={r['ppg']:.2f} winless={r['winless_streak']} GD={r['goal_diff']:+d}")

    print(f"\n  → data/hot_seat_scores.json")


if __name__ == "__main__":
    main()
