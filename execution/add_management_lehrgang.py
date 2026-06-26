#!/usr/bin/env python3
"""
Add the DFB/DFL "Management im Profifußball" course as a second course to
coaching_licenses.json, and match graduates to tm_ids in persons_master.

This Lehrgang is the equivalent of UEFA Pro Lizenz for *managers* (sporting
directors, team managers, head of scouting, etc.). It's a critical bridge in
the projectFIVE network — Robin Trost, Niko Bungert, Sebastian Freis etc. all
went through this program.

Sources:
  - DFL: https://www.dfl.de/de/aktuelles/...
  - DFB: https://www.dfb-akademie.de/management-im-profifussball/...
  - kicker.de, sport1.de cohort articles

Usage:
  python3 execution/add_management_lehrgang.py --dry-run
  python3 execution/add_management_lehrgang.py
"""
import argparse
import json
import unicodedata
from pathlib import Path
from collections import defaultdict

BASE = Path(__file__).parent.parent
LIC = BASE / "data" / "coaching_licenses.json"
PERSONS = BASE / "data" / "persons_master.json"


# ─ Cohort data (curated from DFB/DFL/kicker articles, updated 2026-04-30) ─
MANAGEMENT_COURSE = {
    "course_id": "dfb_dfl_management",
    "name": "Management im Profifußball",
    "provider": "DFB-Akademie / DFL",
    "location": "Frankfurt am Main, Herzogenaurach",
    "license_level": "Zertifikat",
    "cohorts": {
        "1": {
            "year": "2019/2020",
            "label": "Pilotjahrgang",
            "source": "kicker.de, dfl.de",
            "total": 14,
            "graduates": [
                {"name": "Christian Gentner",     "club_at_time": "FC Luzern"},
                {"name": "Timmo Hardung",         "club_at_time": "Eintracht Frankfurt"},
                {"name": "Christofer Heimeroth",  "club_at_time": "Borussia M'gladbach"},
                {"name": "Johannes Holzmüller",   "club_at_time": "FIFA"},
                {"name": "Thomas Kessler",        "club_at_time": "1.FC Köln"},
                {"name": "Stefan Kießling",       "club_at_time": "Bayer 04 Leverkusen"},
                {"name": "Florian Meier",         "club_at_time": "1.FC Nürnberg"},
                {"name": "Julius Ohnesorge",      "club_at_time": "VfL Osnabrück"},
                {"name": "Sascha Riether",        "club_at_time": "—"},
                {"name": "Marcel Schäfer",        "club_at_time": "VfL Wolfsburg"},
                {"name": "Tobias Schätzle",       "club_at_time": "SC Freiburg"},
                {"name": "Maximilian Vollmar",    "club_at_time": "TSG Hoffenheim"},
                {"name": "Benjamin Weber",        "club_at_time": "—"},
                {"name": "Sebastian Zelichowski", "club_at_time": "Hertha BSC"},
            ],
        },
        "2": {
            "year": "2021/2022",
            "label": "Zweiter Jahrgang",
            "source": "dfl.de, kicker.de",
            "total": 16,
            "graduates": [
                {"name": "Claus Costa",           "club_at_time": "Hamburger SV"},
                {"name": "Philipp Gründler",      "club_at_time": "SV Wehen Wiesbaden"},
                {"name": "Jonas Hecking",         "club_at_time": "DSC Arminia Bielefeld"},
                {"name": "Katharina Kiel",        "club_at_time": "talentZONE"},
                {"name": "Thomas Krücken",        "club_at_time": "VfB Stuttgart"},
                {"name": "Kathleen Krüger",       "club_at_time": "FC Bayern München"},
                {"name": "Fabio Morena",          "club_at_time": "Hannover 96"},
                {"name": "Michael Parensen",      "club_at_time": "1.FC Union Berlin"},
                {"name": "Martin Pieckenhagen",   "club_at_time": "FC Hansa Rostock"},
                {"name": "Carsten Rothenbach",    "club_at_time": "FC St. Pauli"},
                {"name": "Svenja Schlenker",      "club_at_time": "Borussia Dortmund"},
                # Additional 5 names not surfaced in initial article — flagged incomplete
            ],
            "incomplete": True,
            "note": "11 of 16 graduates surfaced; 5 names pending recovery from DFL release",
        },
        "3": {
            "year": "2023/2024",
            "label": "Dritter Jahrgang",
            "source": "dfl.de",
            "total": 16,
            "graduates": [
                {"name": "Gerald Asamoah",        "club_at_time": "FC Schalke 04"},
                {"name": "Lukas Berg",            "club_at_time": "—"},
                {"name": "Matthias Borst",        "club_at_time": "—"},
                {"name": "Niko Bungert",          "club_at_time": "1.FSV Mainz 05"},
                {"name": "Daniela Danzeisen",     "club_at_time": "—"},
                {"name": "Sebastian Freis",       "club_at_time": "Karlsruher SC"},
                {"name": "Nadja Kischkat",        "club_at_time": "—"},
                {"name": "Tim Kister",            "club_at_time": "—"},
                {"name": "Kai Krüger",            "club_at_time": "—"},
                {"name": "Peter Niemeyer",        "club_at_time": "Preußen Münster"},
                {"name": "Boris Notzon",          "club_at_time": "1.FC Köln"},
                {"name": "Christina Pohlers-Saß", "club_at_time": "—"},
                {"name": "Nils Schmadtke",        "club_at_time": "—"},
                {"name": "Chris Schmoldt",        "club_at_time": "—"},
                {"name": "Robin Trost",           "club_at_time": "Hertha BSC"},
                {"name": "Roman Weidenfeller",    "club_at_time": "Borussia Dortmund"},
            ],
        },
        "4": {
            "year": "2024/2025",
            "label": "Vierter Jahrgang",
            "source": "dfl.de, dfb.de",
            "total": 18,
            "graduates": [
                {"name": "Ronald Becht",          "club_at_time": "—"},
                {"name": "Daniel Beiderbeck",     "club_at_time": "Borussia Dortmund"},
                {"name": "Gonzalo Castro",        "club_at_time": "—"},
                {"name": "Matthieu Delpierre",    "club_at_time": "VfB Stuttgart"},
                {"name": "Marco Engelhardt",      "club_at_time": "SV Werder Bremen"},
                {"name": "Kevin Izzadeen",        "club_at_time": "1.FC Köln"},
                {"name": "Nicole Kalemba",        "club_at_time": "FC Ingolstadt 04"},
                {"name": "Vincent Keller",        "club_at_time": "SC Freiburg"},
                {"name": "Benjamin Kessel",       "club_at_time": "Eintracht Braunschweig"},
                {"name": "Felix Krüger",          "club_at_time": "RB Leipzig"},
                {"name": "Kevin Meinhardt",       "club_at_time": "FC Hansa Rostock"},
                {"name": "Christoph Preuß",       "club_at_time": "Eintracht Frankfurt"},
                {"name": "Michael Rensing",       "club_at_time": "Fortuna Düsseldorf"},
                {"name": "Rachel Rinast",         "club_at_time": "—"},
                # 4 more names not surfaced — flagged incomplete
            ],
            "incomplete": True,
            "note": "14 of 18 graduates surfaced; 4 names pending",
        },
    },
}


def _normalize(name: str) -> str:
    if not name:
        return ""
    s = unicodedata.normalize("NFD", name)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.lower().strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="don't write")
    args = parser.parse_args()

    print(f"Loading {PERSONS}…")
    with open(PERSONS) as f:
        persons = json.load(f)["persons"]
    print(f"  {len(persons)} persons")

    exact_idx = defaultdict(list)
    norm_idx = defaultdict(list)
    for tm_id, p in persons.items():
        nm = (p.get("name") or "").strip()
        if not nm:
            continue
        exact_idx[nm].append(tm_id)
        norm_idx[_normalize(nm)].append(tm_id)

    def _disambiguate(matches):
        if not matches: return None
        if len(matches) == 1: return matches[0]
        def score(tid):
            p = persons.get(tid, {})
            cc = p.get("current_club") or {}
            cc_name = cc.get("name") if isinstance(cc, dict) else (cc or "")
            cc_name = (cc_name or "").strip()
            return 0 if not cc_name or cc_name in ("Karriereende", "Vereinslos", "-") else 10
        scored = sorted(matches, key=lambda t: (-score(t), int(t)))
        return scored[0] if score(scored[0]) > 0 else None

    print(f"\nLoading {LIC}…")
    with open(LIC) as f:
        lic = json.load(f)

    # Inject Management course
    course = json.loads(json.dumps(MANAGEMENT_COURSE))  # deep copy

    total_grads = 0
    matched = 0
    samples = []
    for cohort_id, c in course["cohorts"].items():
        for g in c["graduates"]:
            total_grads += 1
            nm = g["name"].strip()
            hits = exact_idx.get(nm, []) or norm_idx.get(_normalize(nm), [])
            if len(hits) == 1:
                g["tm_id"] = int(hits[0])
                g["confidence"] = 0.95
                g["matched_at"] = "add_2026-04-30"
                matched += 1
                samples.append((cohort_id, nm, hits[0], "exact"))
            elif len(hits) > 1:
                tid = _disambiguate(hits)
                if tid:
                    g["tm_id"] = int(tid)
                    g["confidence"] = 0.85
                    g["matched_at"] = "add_2026-04-30 (disambig)"
                    matched += 1
                    samples.append((cohort_id, nm, tid, "disambig"))
                else:
                    g["tm_id"] = None
                    g["confidence"] = 0.0
                    g["match_note"] = f"ambiguous, {len(hits)} candidates"
            else:
                g["tm_id"] = None
                g["confidence"] = 0.0
        c["matched"] = sum(1 for g in c["graduates"] if g.get("tm_id"))

    course["stats"] = {"total": total_grads, "matched": matched}

    # Add as second course (don't overwrite the existing one)
    existing_ids = {c["course_id"] for c in lic["courses"]}
    if course["course_id"] not in existing_ids:
        lic["courses"].append(course)
        action = "added"
    else:
        # Replace existing entry
        for i, c in enumerate(lic["courses"]):
            if c["course_id"] == course["course_id"]:
                lic["courses"][i] = course
                break
        action = "replaced"

    # Update meta totals
    grand_total = sum(
        sum(len(c["graduates"]) for c in cs["cohorts"].values())
        for cs in lic["courses"]
    )
    grand_matched = sum(
        sum(sum(1 for g in c["graduates"] if g.get("tm_id"))
            for c in cs["cohorts"].values())
        for cs in lic["courses"]
    )
    lic["meta"]["total_graduates"] = grand_total
    lic["meta"]["matched_to_tm"] = grand_matched
    lic["meta"]["updated_at"] = "2026-04-30"
    lic["meta"]["sources"] = list(set(
        lic["meta"].get("sources", []) + ["dfb.de", "dfl.de", "kicker.de"]
    ))

    print("\n=== Management Course Stats ===")
    print(f"  Total grads: {total_grads}")
    print(f"  Matched: {matched}")
    if samples:
        print("  Samples:")
        for s in samples[:18]:
            cid, nm, tid = s[0], s[1], s[2]
            mode = s[3] if len(s) > 3 else ""
            print(f"    LG {cid}: {nm:<30} → tm_id={tid} ({mode})")

    print("\n=== Grand Totals (across all courses) ===")
    print(f"  {grand_total} graduates total, {grand_matched} matched ({100*grand_matched/grand_total:.0f}%)")

    if not args.dry_run:
        tmp = LIC.with_suffix(".json.tmp")
        with open(tmp, "w") as f:
            json.dump(lic, f, ensure_ascii=False, indent=2)
        tmp.replace(LIC)
        print(f"\n  ✓ {action} 'Management im Profifußball' in {LIC}")


if __name__ == "__main__":
    main()
