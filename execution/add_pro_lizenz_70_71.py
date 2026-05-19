#!/usr/bin/env python3
"""
Sprint A — Step 1: LG 70 + LG 71 zur DFB Fußball-Lehrer/Pro-Lizenz-Reihe ergänzen.

Hintergrund: Die DFB hat das Fußball-Lehrer-Lehrgang-Format 2022 in "Pro Lizenz"
umbenannt. Vorhandene coaching_licenses.json deckt LG 61-69 (2014-2024) ab.
LG 70 (2024/25, abgeschlossen 28.01.2025) und LG 71 (2025/26, abgeschlossen
28.01.2026) sind frisch publik und werden als zwei neue Cohorten in den
bestehenden course_id="dfb_fussball_lehrer" angehängt.

Quellen:
  - LG 70: https://www.dfb.de/news/dfb-beglueckwuenscht-17-neue-inhaber-der-pro-lizenz (28.01.2025)
  - LG 71: https://www.dfb.de/news/dfb-zeichnet-17-neue-pro-lizenz-inhaberinnen-aus (28.01.2026)

Usage:
  python3 execution/add_pro_lizenz_70_71.py --dry-run
  python3 execution/add_pro_lizenz_70_71.py
"""
import argparse
import json
import sys
import unicodedata
from pathlib import Path
from collections import defaultdict

BASE = Path(__file__).parent.parent
LIC = BASE / "data" / "coaching_licenses.json"
PERSONS = BASE / "data" / "persons_master.json"


COHORT_70 = {
    "year": "2024/2025",
    "label": "70. DFB Pro Lizenz-Lehrgang",
    "source": "dfb.de/news/dfb-beglueckwuenscht-17-neue-inhaber-der-pro-lizenz",
    "graduation_date": "2025-01-28",
    "graduates": [
        {"name": "Heiner Backhaus",        "club_at_time": "Alemannia Aachen"},
        {"name": "Silvio Bankert",          "club_at_time": "1.FC Magdeburg"},
        {"name": "Lars Barlemann",          "club_at_time": "Hannover 96"},
        {"name": "Pascal Bieler",           "club_at_time": "TSV Steinbach"},
        {"name": "Daniel Brinkmann",        "club_at_time": "Hansa Rostock"},
        {"name": "Mads Buttgereit",         "club_at_time": "DFB-Männer"},
        {"name": "Loïc Favé",               "club_at_time": "Hamburger SV"},
        {"name": "Jan Fießer",              "club_at_time": "Eintracht Frankfurt"},
        {"name": "Kristjan Glibo",          "club_at_time": "Eintracht Frankfurt"},
        {"name": "Tim Görner",              "club_at_time": "FSV Frankfurt"},
        {"name": "Stefan Kleineheismann",   "club_at_time": "SpVgg Greuther Fürth"},
        {"name": "Andreas Patz",            "club_at_time": "Jahn Regensburg"},
        {"name": "Marc Pfitzner",           "club_at_time": "Eintracht Braunschweig"},
        {"name": "Merlin Polzin",           "club_at_time": "Hamburger SV"},
        {"name": "Orest Shala",             "club_at_time": "FC St. Gallen"},
        {"name": "Marc Unterberger",        "club_at_time": "SpVgg Unterhaching"},
        {"name": "Marian Wilhelm",          "club_at_time": "Viktoria Köln"},
    ],
}

COHORT_71 = {
    "year": "2025/2026",
    "label": "71. DFB Pro Lizenz-Lehrgang",
    "source": "dfb.de/news/dfb-zeichnet-17-neue-pro-lizenz-inhaberinnen-aus",
    "graduation_date": "2026-01-28",
    "graduates": [
        {"name": "Niko Arnautis",           "club_at_time": "Eintracht Frankfurt"},
        {"name": "Theodoros Dedes",         "club_at_time": "TSG Hoffenheim"},
        {"name": "Markus Fiedler",          "club_at_time": "1.FC Magdeburg"},
        {"name": "Alexander Hahn",          "club_at_time": "Holstein Kiel"},
        {"name": "Roberto Hilbert",         "club_at_time": "SpVgg Greuther Fürth"},
        {"name": "Florian Kästner",         "club_at_time": "FC Carl Zeiss Jena"},
        {"name": "Ralf Kettemann",          "club_at_time": "SC Paderborn"},
        {"name": "Lars Kornetka",           "club_at_time": "ÖFB-Männer"},
        {"name": "David Krecidlo",          "club_at_time": "VfB Stuttgart"},
        {"name": "Dennis Schmitt",          "club_at_time": "Eintracht Frankfurt"},
        {"name": "Christian Tiffert",       "club_at_time": "FC Hansa Rostock"},
        {"name": "Saban Uzun",              "club_at_time": "1.FC Magdeburg"},
        {"name": "Eva-Maria Virsinger",     "club_at_time": "TSG Hoffenheim"},
        {"name": "Sandro Wagner",           "club_at_time": "FC Augsburg"},
        {"name": "Vincent Wagner",          "club_at_time": "SV Elversberg"},
        {"name": "Heiko Westermann",        "club_at_time": "FC Barcelona"},
        {"name": "Sabrina Wittmann",        "club_at_time": "FC Ingolstadt"},
    ],
}


def _normalize(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return s.lower().strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
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
        # prefer persons with active current_club (non-trivial value)
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

    # find dfb_fussball_lehrer course
    fl_course = None
    for c in lic["courses"]:
        if c["course_id"] == "dfb_fussball_lehrer":
            fl_course = c
            break
    if fl_course is None:
        print("  ✗ course_id=dfb_fussball_lehrer not found in coaching_licenses.json")
        sys.exit(1)

    # Inject LG 70 and LG 71 (or replace if already exist)
    matched_total = 0
    grads_total = 0
    samples = []
    for cohort_id, cohort_data in [("70", COHORT_70), ("71", COHORT_71)]:
        # deep copy
        cohort = json.loads(json.dumps(cohort_data))
        for g in cohort["graduates"]:
            grads_total += 1
            nm = g["name"].strip()
            hits = exact_idx.get(nm, []) or norm_idx.get(_normalize(nm), [])
            if len(hits) == 1:
                g["tm_id"] = int(hits[0])
                g["confidence"] = 0.95
                g["matched_at"] = "add_pro_lizenz_70_71_2026-05-04"
                matched_total += 1
                samples.append((cohort_id, nm, hits[0], "exact"))
            elif len(hits) > 1:
                tid = _disambiguate(hits)
                if tid:
                    g["tm_id"] = int(tid)
                    g["confidence"] = 0.85
                    g["matched_at"] = "add_pro_lizenz_70_71_2026-05-04 (disambig)"
                    matched_total += 1
                    samples.append((cohort_id, nm, tid, "disambig"))
                else:
                    g["tm_id"] = None
                    g["confidence"] = 0.0
                    g["match_note"] = f"ambiguous, {len(hits)} candidates"
            else:
                g["tm_id"] = None
                g["confidence"] = 0.0
        cohort["matched"] = sum(1 for g in cohort["graduates"] if g.get("tm_id"))
        fl_course["cohorts"][cohort_id] = cohort

    print(f"\n=== LG 70 + LG 71 stats ===")
    print(f"  Graduates added: {grads_total}")
    print(f"  Matched to tm_id: {matched_total} ({100*matched_total/grads_total:.0f}%)")
    if samples:
        print("  Sample matches:")
        for s in samples[:24]:
            cid, nm, tid = s[0], s[1], s[2]
            mode = s[3] if len(s) > 3 else ""
            print(f"    LG {cid}: {nm:<32} → tm_id={tid} ({mode})")

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
    lic["meta"]["updated_at"] = "2026-05-04"
    sources = set(lic["meta"].get("sources", []))
    sources.update([COHORT_70["source"], COHORT_71["source"]])
    lic["meta"]["sources"] = sorted(sources)

    print(f"\n=== Grand totals across all courses ===")
    print(f"  {grand_total} graduates, {grand_matched} matched ({100*grand_matched/grand_total:.0f}%)")

    if not args.dry_run:
        tmp = LIC.with_suffix(".json.tmp")
        with open(tmp, "w") as f:
            json.dump(lic, f, ensure_ascii=False, indent=2)
        tmp.replace(LIC)
        print(f"\n  ✓ LG 70 + LG 71 added to {LIC}")


if __name__ == "__main__":
    main()
