#!/usr/bin/env python3
"""Build Hire-History pro DM aus career_history-Overlaps.

Performance-optimiert: baut zuerst einen Index aller Trainer × ihrer Stationen
nach normalisiertem Club-Name. Dann iteriert pro DM nur über O(career_stations)
statt O(81k_persons * career_stations).

Reads:  data/decision_makers.json + data/persons_master.json + data/coaching_licenses.json
Output: data/hire_history.json
"""
import json
import re
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime, timezone

BASE = Path(__file__).parent.parent


def normalize_club(name: str) -> str:
    if not name:
        return ""
    n = name.lower().strip()
    n = re.sub(r"[^a-z0-9äöü]+", "", n)
    return n


def parse_year(val) -> int:
    """Extract 4-digit year from various formats: '2021', '2021-07-01', '01.07.2021'."""
    if val is None:
        return None
    s = str(val)
    # ISO date: 2021-07-01
    m = re.search(r"\b(19\d{2}|20\d{2})\b", s)
    if m:
        return int(m.group(1))
    return None


def main():
    print("Loading data...")
    dms = json.load(open(BASE / "data/decision_makers.json"))["decision_makers"]
    persons = json.load(open(BASE / "data/persons_master.json"))["persons"]
    licenses_raw = {}
    lic_path = BASE / "data/coaching_licenses.json"
    if lic_path.exists():
        try:
            licenses_raw = json.load(open(lic_path))
        except Exception:
            pass

    # Build lehrgang lookup: tm_id → "<course> <year>"
    print("Building lehrgang lookup...")
    lehrgang_by_tm = defaultdict(list)
    for course in licenses_raw.get("courses", []):
        course_id = course.get("id") or course.get("name", "LG")
        cohorts = course.get("cohorts", {})
        # cohorts is a dict {cohort_id: {year, graduates}}
        if isinstance(cohorts, dict):
            cohort_iter = cohorts.items()
        elif isinstance(cohorts, list):
            cohort_iter = [(c.get("id", "?"), c) for c in cohorts]
        else:
            cohort_iter = []
        for cid, cohort in cohort_iter:
            year = cohort.get("year", "?")
            for grad in cohort.get("graduates", []):
                tmid = grad.get("tm_id")
                if tmid:
                    lehrgang_by_tm[int(tmid)].append(f"{course_id} {year}")

    # Build trainer-station-index: normalized_club → [(tm_id, from_year, to_year), ...]
    print("Building trainer-station-index...")
    trainer_stations = defaultdict(list)
    trainer_count = 0
    for tm_id_str, p in persons.items():
        if p.get("type") != "trainer":
            continue
        trainer_count += 1
        for cs in (p.get("career_history") or []):
            # career_history entries use 'club_name' (with fallback to 'club')
            club = cs.get("club_name") or cs.get("club") or ""
            role = (cs.get("role") or "").lower()
            # Only true coaching/decision roles
            if not any(k in role for k in ["trainer", "coach", "manager", "cheftrainer"]):
                continue
            # Skip co-trainer/Athletik/etc.
            if any(k in role for k in ["co-", "co ", "fitness", "athletik", "torwart", "analyst", "physio"]):
                continue
            from_y = parse_year(cs.get("date_from") or cs.get("from"))
            to_y = parse_year(cs.get("date_to") or cs.get("to")) or 9999
            if not from_y:
                continue
            trainer_stations[normalize_club(club)].append({
                "tm_id": int(tm_id_str),
                "name": p.get("name"),
                "from": from_y,
                "to": to_y,
                "club_orig": club,
                "role": cs.get("role"),
            })

    print(f"  Indexed {trainer_count} trainers across {len(trainer_stations)} normalized clubs")

    # For each DM, find hires
    print(f"Computing hires for {len(dms)} DMs...")
    per_dm = {}
    for dm in dms:
        if dm["tier"] not in ("1", "2"):
            continue
        p = persons.get(str(dm["tm_id"]), {})
        career = p.get("career_history", []) or []
        hires = []
        seen_hires = set()
        for cs in career:
            club_name = cs.get("club_name") or cs.get("club") or ""
            if not club_name:
                continue
            from_y = parse_year(cs.get("date_from") or cs.get("from"))
            to_y = parse_year(cs.get("date_to") or cs.get("to")) or 9999
            if not from_y:
                continue
            # Find all coaches who started at this club within the DM's tenure
            for ts in trainer_stations.get(normalize_club(club_name), []):
                if dm["tm_id"] == ts["tm_id"]:
                    continue
                if from_y - 1 <= ts["from"] <= to_y:
                    key = (ts["tm_id"], club_name, ts["from"])
                    if key in seen_hires:
                        continue
                    seen_hires.add(key)
                    # Coach-Start innerhalb SD-Tenure ±1y = high
                    # SD-Tenure am Club: from_y bis to_y; Coach-Start = ts["from"]
                    sd_from = from_y
                    sd_to = to_y if to_y != 9999 else 9999
                    confidence = "high" if (sd_from - 1) <= ts["from"] <= (sd_to + 1) else "medium"
                    coach_to = min(ts["to"], 2026)
                    hires.append({
                        "coach_tm_id": ts["tm_id"],
                        "coach_name": ts["name"],
                        "club": club_name,
                        "year": ts["from"],
                        "confidence": confidence,
                        "tenure_years": coach_to - ts["from"],
                    })

        # Pattern analysis
        ages = []
        nationalities = []
        lehrgaenge = []
        for h in hires:
            cp = persons.get(str(h["coach_tm_id"]), {})
            dob = cp.get("dob")
            if dob:
                m = re.search(r"(19\d{2}|20\d{2})", str(dob))
                if m:
                    ages.append(h["year"] - int(m.group(1)))
            nat = cp.get("nationality")
            if isinstance(nat, list) and nat:
                nat = nat[0]
            if nat:
                nationalities.append(nat)
            lehrgaenge.extend(lehrgang_by_tm.get(h["coach_tm_id"], []))

        nat_counter = Counter(nationalities)
        lg_counter = Counter(lehrgaenge)
        per_dm[str(dm["tm_id"])] = {
            "name": dm["name"],
            "tier": dm["tier"],
            "club": dm.get("club_name"),
            "league": dm.get("league"),
            "career": career,
            "hires": hires,
            "patterns": {
                "preferred_age_at_hire_avg": round(sum(ages) / len(ages), 1) if ages else None,
                "preferred_nationality": [n for n, _ in nat_counter.most_common(3)],
                "lehrgang_overrepresented": [lg for lg, c in lg_counter.most_common() if c >= 2],
                "avg_tenure_years": round(sum(h["tenure_years"] for h in hires) / len(hires), 1) if hires else None,
                "international_share": (round(sum(1 for n in nationalities if n != "Deutschland") / max(1, len(nationalities)), 2)
                                        if nationalities else 0),
            }
        }

    out = BASE / "data/hire_history.json"
    json.dump({
        "_meta": {
            "built_at": datetime.now(timezone.utc).isoformat(),
            "total_dms": len(per_dm),
            "total_hires": sum(len(d["hires"]) for d in per_dm.values()),
            "multi_club_dms": sum(1 for d in per_dm.values() if len({h["club"] for h in d["hires"]}) > 1),
        },
        "per_dm": per_dm,
    }, open(out, "w"), ensure_ascii=False, indent=2)

    print(f"✓ Hire history built — {len(per_dm)} DMs, {sum(len(d['hires']) for d in per_dm.values())} hires")
    print("  Top-DMs by hire-count:")
    top = sorted(per_dm.items(), key=lambda kv: -len(kv[1]["hires"]))[:10]
    for tm_id, d in top:
        print(f"    {d['name']:<28} {len(d['hires'])} hires (tier {d['tier']})")


if __name__ == "__main__":
    main()
