#!/usr/bin/env python3
"""
2026-05-14: Merge coaching_licenses_research_57_60.json into coaching_licenses.json
and run a full match-pass over ALL graduates without tm_id (both files).

Steps:
1. Backup coaching_licenses.json -> .bak.2026-05-14
2. Merge research_57_60: add cohorts 57, 58, 59 as new; cohort 60 replace+keep existing Hoeneß.
3. Fix LG 63 metadata (missing `total` field — has 25 grads, no completeness flag).
4. Build name-index from persons_master.json (exact + diacritics-folded).
5. Match-pass:
   - For each graduate without tm_id, exact-match first, then fold-match.
   - On ambiguity, disambiguate by current_club (skip Karriereende / blanks).
6. Write back atomic. Also rewrite research_57_60.json with tm_ids for traceability.
7. Update meta totals.
"""
import json
import shutil
import unicodedata
from pathlib import Path
from collections import defaultdict
from datetime import datetime

BASE = Path(__file__).parent.parent
LIC = BASE / "data" / "coaching_licenses.json"
RES = BASE / "data" / "coaching_licenses_research_57_60.json"
PERSONS = BASE / "data" / "persons_master.json"
BACKUP = BASE / "data" / "coaching_licenses.json.bak.2026-05-14"


def _normalize(name: str) -> str:
    if not name:
        return ""
    s = unicodedata.normalize("NFD", name)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.lower().strip()


def main():
    # ============ STEP 1: BACKUP ============
    if not BACKUP.exists():
        shutil.copy2(LIC, BACKUP)
        print(f"[1] Backup created: {BACKUP}")
    else:
        print(f"[1] Backup already exists: {BACKUP}")

    # ============ STEP 2: Load files ============
    print("\n[2] Loading files…")
    with open(LIC) as f:
        lic = json.load(f)
    with open(RES) as f:
        res = json.load(f)

    cohorts_main = lic["courses"][0]["cohorts"]
    cohorts_res = res["cohorts"]

    # ============ STEP 3: Merge research data ============
    print("\n[3] Merging cohorts 57-60 from research file…")

    # Build a quick lookup for existing LG 60 entries (Hoeneß)
    existing_60 = {g["name"]: g for g in cohorts_main.get("60", {}).get("graduates", [])}

    for cid in ["57", "58", "59", "60"]:
        if cid not in cohorts_res:
            continue
        src = cohorts_res[cid]
        # New graduate entries (start with tm_id=null, will match in step 5)
        new_grads = []
        for g in src["graduates"]:
            nm = g["name"]
            # If LG 60 already has this name from old file, carry over its tm_id
            if cid == "60" and nm in existing_60 and existing_60[nm].get("tm_id"):
                new_grads.append({
                    "name": nm,
                    "tm_id": existing_60[nm]["tm_id"],
                    "matched_name": existing_60[nm].get("matched_name") or nm,
                    "confidence": existing_60[nm].get("confidence", 1.0),
                    "source": g.get("source"),
                    "note": g.get("note"),
                })
            else:
                entry = {
                    "name": nm,
                    "tm_id": None,
                    "matched_name": None,
                    "confidence": 0.0,
                    "source": g.get("source"),
                }
                if g.get("note"):
                    entry["note"] = g["note"]
                new_grads.append(entry)

        cohorts_main[cid] = {
            "year": src["year"],
            "lehrgangsleiter": src.get("lehrgangsleiter"),
            "graduates": new_grads,
            "total": len(new_grads),
            "matched": 0,  # recompute in step 6
            "source": "research_2026-05-14 — spox.com, dfb.de, kicker.de, fussifreunde.de, reviersport.de",
            "completeness_note": src.get("completeness_note"),
            "added_at": "2026-05-14",
        }
        print(f"  LG {cid} ({src['year']}): {len(new_grads)} graduates merged")

    # ============ STEP 3b: Fix LG 63 metadata ============
    lg63 = cohorts_main.get("63")
    if lg63 and "total" not in lg63:
        lg63["total"] = len(lg63.get("graduates", []))
        if "incomplete" not in lg63:
            lg63["incomplete"] = False
        print(f"  LG 63 metadata fixed: total={lg63['total']}, incomplete=False")

    # ============ STEP 4: Load persons_master and build index ============
    print("\n[4] Loading persons_master.json (large file ~52 MB)…")
    with open(PERSONS) as f:
        persons = json.load(f)["persons"]
    print(f"  {len(persons)} persons indexed")

    exact_idx = defaultdict(list)
    norm_idx = defaultdict(list)
    for tm_id, p in persons.items():
        nm = (p.get("name") or "").strip()
        if not nm:
            continue
        exact_idx[nm].append(tm_id)
        norm_idx[_normalize(nm)].append(tm_id)

    def _score_candidate(tid: str) -> int:
        p = persons.get(tid, {})
        cc = p.get("current_club") or {}
        cc_name = cc.get("name") if isinstance(cc, dict) else (cc or "")
        cc_name = (cc_name or "").strip()
        if not cc_name or cc_name in ("Karriereende", "Vereinslos", "-"):
            # Prefer trainer-type profile with career_history for older Lehrgang grads
            if p.get("type") == "trainer" or p.get("career_history"):
                return 5
            return 0
        return 10

    def _disambiguate(matches: list) -> tuple:
        """Returns (tm_id, reason) or (None, reason)."""
        if not matches:
            return None, "no_match"
        if len(matches) == 1:
            return matches[0], "single"
        scored = sorted(matches, key=lambda t: (-_score_candidate(t), int(t)))
        best = scored[0]
        return (best, "disambig") if _score_candidate(best) > 0 else (None, "ambiguous_low_score")

    # ============ STEP 5: Match-pass over BOTH files ============
    print("\n[5] Running match-pass…")
    rematched = 0
    ambiguous = 0
    still_missing = 0
    multi_match_log = []
    rematched_samples = []

    # 5a: coaching_licenses.json (all courses, all cohorts)
    for course in lic["courses"]:
        for cohort_id, c in course.get("cohorts", {}).items():
            for g in c.get("graduates", []):
                if g.get("tm_id"):
                    continue
                nm = (g.get("name") or "").strip()
                if not nm:
                    still_missing += 1
                    continue
                matches = exact_idx.get(nm) or norm_idx.get(_normalize(nm)) or []
                tid, reason = _disambiguate(matches)
                if tid:
                    g["tm_id"] = int(tid)
                    g["matched_name"] = persons[tid].get("name", nm)
                    g["confidence"] = 0.95 if reason == "single" else 0.85
                    g["matched_at"] = f"merge_match_2026-05-14 ({reason})"
                    rematched += 1
                    rematched_samples.append((cohort_id, nm, tid, reason))
                    if reason == "disambig":
                        multi_match_log.append((cohort_id, nm, len(matches), tid))
                elif reason == "ambiguous_low_score":
                    ambiguous += 1
                    multi_match_log.append((cohort_id, nm, len(matches), None))
                else:
                    still_missing += 1

    # 5b: research_57_60.json — write tm_ids back for traceability
    for cohort_id, c in cohorts_res.items():
        for g in c["graduates"]:
            if g.get("tm_id"):
                continue
            nm = g["name"].strip()
            matches = exact_idx.get(nm) or norm_idx.get(_normalize(nm)) or []
            tid, reason = _disambiguate(matches)
            if tid:
                g["tm_id"] = int(tid)
                g["matched_name"] = persons[tid].get("name", nm)
                g["confidence"] = 0.95 if reason == "single" else 0.85
                g["matched_at"] = f"merge_match_2026-05-14 ({reason})"

    # ============ STEP 6: Recompute meta + cohort.matched counts ============
    print("\n[6] Recomputing meta + cohort.matched…")
    grand_matched = 0
    grand_total = 0
    for course in lic["courses"]:
        course_matched = 0
        course_total = 0
        for c in course.get("cohorts", {}).values():
            cohort_matched = sum(1 for g in c.get("graduates", []) if g.get("tm_id"))
            cohort_total = len(c.get("graduates", []))
            c["matched"] = cohort_matched
            if "total" not in c:
                c["total"] = cohort_total
            course_matched += cohort_matched
            course_total += cohort_total
        course["stats"] = course.get("stats", {})
        course["stats"]["total_cohorts"] = len(course.get("cohorts", {}))
        course["stats"]["total_graduates"] = course_total
        course["stats"]["total_matched"] = course_matched
        course["stats"]["match_rate"] = round(course_matched / course_total, 3) if course_total else 0.0
        grand_matched += course_matched
        grand_total += course_total

    old_total = lic["meta"].get("total_graduates", 0)
    old_matched = lic["meta"].get("matched_to_tm", 0)
    lic["meta"]["total_graduates"] = grand_total
    lic["meta"]["matched_to_tm"] = grand_matched
    lic["meta"]["updated_at"] = "2026-05-14"
    if "research_2026-05-14" not in lic["meta"]["sources"]:
        lic["meta"]["sources"].append("research_2026-05-14_LG_57-60")

    # ============ STEP 7: Write atomically ============
    print("\n[7] Writing files…")
    tmp = LIC.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(lic, f, ensure_ascii=False, indent=2)
    tmp.replace(LIC)

    tmp_res = RES.with_suffix(".json.tmp")
    with open(tmp_res, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    tmp_res.replace(RES)

    # ============ SUMMARY ============
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Before: {old_matched} / {old_total} matched")
    print(f"After:  {grand_matched} / {grand_total} matched (+{grand_matched - old_matched} matched, +{grand_total - old_total} grads)")
    print(f"Match-pass:")
    print(f"  - newly rematched: {rematched}")
    print(f"  - ambiguous (skipped): {ambiguous}")
    print(f"  - still missing: {still_missing}")
    if multi_match_log:
        print(f"\nMulti-match cases ({len(multi_match_log)}):")
        for cid, nm, n_matches, resolved in multi_match_log[:20]:
            status = f"→ {resolved}" if resolved else "(skipped)"
            print(f"  LG {cid}: {nm:<32} ({n_matches} candidates) {status}")
    if rematched_samples:
        print(f"\nFirst 15 new matches:")
        for cid, nm, tid, reason in rematched_samples[:15]:
            print(f"  LG {cid}: {nm:<32} → {tid} ({reason})")


if __name__ == "__main__":
    main()
