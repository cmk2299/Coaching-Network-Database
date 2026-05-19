#!/usr/bin/env python3
"""
Re-match unmatched DFB Lehrgang graduates against the current persons_master.

Background: data/coaching_licenses.json was built 2026-03-27 with 93/203 matched.
persons_master grew from 34k → 81k since. Some graduates (Tedesco, Stilz, Antwerpen…)
have profiles now that didn't exist at original build time.

Usage:
  python3 execution/rematch_lehrgang.py --dry-run
  python3 execution/rematch_lehrgang.py            # actually update the JSON
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


def _normalize(name: str) -> str:
    """Strip diacritics + lowercase for fuzzy compare."""
    if not name:
        return ""
    s = unicodedata.normalize("NFD", name)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.lower().strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="report only, don't write")
    args = parser.parse_args()

    print(f"Loading {PERSONS}…")
    with open(PERSONS) as f:
        persons = json.load(f)["persons"]
    print(f"  {len(persons)} persons loaded")

    # Build TWO indices: exact-name and normalized-name
    exact_idx = defaultdict(list)
    norm_idx = defaultdict(list)
    for tm_id, p in persons.items():
        nm = (p.get("name") or "").strip()
        if not nm:
            continue
        exact_idx[nm].append(tm_id)
        norm_idx[_normalize(nm)].append(tm_id)

    def _disambiguate(matches: list) -> str:
        """When name maps to multiple tm_ids (e.g. player-id + trainer-id of same person),
        prefer the one whose current_club is meaningful (not 'Karriereende' / empty).
        That's the post-career active profile, which is what Lehrgang context needs."""
        if not matches:
            return None
        if len(matches) == 1:
            return matches[0]
        # Score each candidate
        def score(tid):
            p = persons.get(tid, {})
            cc = p.get("current_club") or {}
            cc_name = cc.get("name") if isinstance(cc, dict) else (cc or "")
            cc_name = (cc_name or "").strip()
            if not cc_name or cc_name in ("Karriereende", "Vereinslos", "-"):
                return 0
            return 10
        scored = sorted(matches, key=lambda t: (-score(t), int(t)))
        return scored[0] if score(scored[0]) > 0 else None

    print(f"\nLoading {LIC}…")
    with open(LIC) as f:
        lic = json.load(f)

    cohorts = lic["courses"][0]["cohorts"]

    rematched = 0
    ambiguous = 0
    still_missing = 0
    rematched_names = []

    for cohort_id, c in cohorts.items():
        for g in c["graduates"]:
            if g.get("tm_id"):
                continue
            nm = (g.get("name") or "").strip()
            if not nm:
                still_missing += 1
                continue

            # Try exact match first
            matches = exact_idx.get(nm, [])
            if not matches:
                matches = norm_idx.get(_normalize(nm), [])

            if len(matches) == 1:
                tm_id = matches[0]
                if not args.dry_run:
                    g["tm_id"] = int(tm_id)
                    g["confidence"] = 0.95
                    g["matched_at"] = "rematch_2026-04-30"
                rematched += 1
                rematched_names.append((cohort_id, nm, tm_id, "exact"))
            elif len(matches) > 1:
                # Disambiguate using current_club ('Karriereende' = old player profile)
                tm_id = _disambiguate(matches)
                if tm_id:
                    if not args.dry_run:
                        g["tm_id"] = int(tm_id)
                        g["confidence"] = 0.85  # disambiguated, lower confidence
                        g["matched_at"] = "rematch_2026-04-30 (disambiguated)"
                    rematched += 1
                    rematched_names.append((cohort_id, nm, tm_id, "disambig"))
                else:
                    ambiguous += 1
            else:
                still_missing += 1

    # Update meta + cohort.matched counts — sum across ALL courses, not just course[0]
    if not args.dry_run:
        grand_matched = sum(
            sum(sum(1 for g in c["graduates"] if g.get("tm_id"))
                for c in course.get("cohorts", {}).values())
            for course in lic.get("courses", [])
        )
        grand_total = sum(
            sum(len(c["graduates"]) for c in course.get("cohorts", {}).values())
            for course in lic.get("courses", [])
        )
        lic["meta"]["matched_to_tm"] = grand_matched
        lic["meta"]["total_graduates"] = grand_total
        lic["meta"]["updated_at"] = "2026-04-30"
        for cohort_id, c in cohorts.items():
            c["matched"] = sum(1 for g in c["graduates"] if g.get("tm_id"))

        # Write atomically
        tmp = LIC.with_suffix(".json.tmp")
        with open(tmp, "w") as f:
            json.dump(lic, f, ensure_ascii=False, indent=2)
        tmp.replace(LIC)

    print(f"\n=== Rematch Summary ===")
    print(f"  Rematched: {rematched}")
    print(f"  Ambiguous (skipped): {ambiguous}")
    print(f"  Still missing (not in persons_master): {still_missing}")
    print(f"  New total matched: {lic['meta']['matched_to_tm']} / {lic['meta']['total_graduates']}")
    if rematched_names:
        print(f"\n  Sample (first 15):")
        for cohort_id, nm, tm_id in rematched_names[:15]:
            print(f"    LG {cohort_id}: {nm:<28} → tm_id={tm_id}")

    if args.dry_run:
        print("\n  Dry run — re-run without --dry-run to persist.")


if __name__ == "__main__":
    main()
