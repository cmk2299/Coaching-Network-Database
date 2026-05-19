#!/usr/bin/env python3
"""
diff_coachinside_csvs.py

Cross-reference 3 coachinside CSV exports against the existing P5 Football
Coaches Database to find which coaches are MISSING from the platform, which
are MATCHED but have no network built yet, and which are likely matches
(PROBABLE) that need manual confirmation.

Inputs (uploads):
  - Coaches – Trainer.csv         (active head coaches)
  - Coaches – Trainer (1).csv     (vereinslose head coaches)
  - Coaches – Trainer (2).csv     (Trainerstab DACH)

Reference data:
  - data/persons_master.json   (ground truth: scraped persons)
  - data/networks/{tm_id}.json (presence => has-network)

Output:
  - data/coachinside_gap_report.json
  - stdout summary
"""

from __future__ import annotations

import csv
import json
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# ----------------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------------

ROOT = Path(__file__).parent.parent
# CSVs live under data/coachinside_csvs/ on the host (copied there by
# run_coachinside_coverage.sh from the session uploads dir). Sandbox-mode
# fallback (UPLOADS dir under /sessions/*/mnt/) is checked too for
# diff-runs from inside cowork.
_LOCAL_CSV_DIR = ROOT / "data" / "coachinside_csvs"
_SANDBOX_UPLOADS = Path("/sessions/festive-relaxed-planck/mnt/uploads")

if (_LOCAL_CSV_DIR / "coachinside_active.csv").exists():
    CSV_FILES = [
        ("active_headcoaches", _LOCAL_CSV_DIR / "coachinside_active.csv"),
        ("vereinslos",         _LOCAL_CSV_DIR / "coachinside_vereinslos.csv"),
        ("trainerstab_dach",   _LOCAL_CSV_DIR / "coachinside_trainerstab.csv"),
    ]
else:
    CSV_FILES = [
        ("active_headcoaches", _SANDBOX_UPLOADS / "Coaches – Trainer.csv"),
        ("vereinslos",         _SANDBOX_UPLOADS / "Coaches – Trainer (1).csv"),
        ("trainerstab_dach",   _SANDBOX_UPLOADS / "Coaches – Trainer (2).csv"),
    ]

PERSONS_MASTER = ROOT / "data" / "persons_master.json"
NETWORKS_DIR   = ROOT / "data" / "networks"
REPORT_OUT     = ROOT / "data" / "coachinside_gap_report.json"

# ----------------------------------------------------------------------------
# Normalization helpers
# ----------------------------------------------------------------------------

EXTRA_DIACRITIC_MAP = {
    "ß": "ss",
    "Ø": "o", "ø": "o",
    "Æ": "ae", "æ": "ae",
    "Œ": "oe", "œ": "oe",
    "Ð": "d",  "ð": "d",
    "Þ": "th", "þ": "th",
    "Ł": "l",  "ł": "l",
    "Đ": "d",  "đ": "d",
    "İ": "i",  "ı": "i",
}

_WS_RE = re.compile(r"\s+")


def strip_diacritics(s: str) -> str:
    """Strip diacritics + map special characters (ß, ø, ł, etc.)."""
    if not s:
        return ""
    out = []
    for ch in s:
        if ch in EXTRA_DIACRITIC_MAP:
            out.append(EXTRA_DIACRITIC_MAP[ch])
        else:
            out.append(ch)
    s = "".join(out)
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def norm_name(s: str) -> str:
    """Lowercase, ASCII-folded, whitespace-collapsed name."""
    if not s:
        return ""
    s = strip_diacritics(s)
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = _WS_RE.sub(" ", s).strip()
    return s


def initial_lastname(full: str) -> str:
    parts = full.split()
    if len(parts) < 2:
        return ""
    return f"{parts[0][0]}.{parts[-1]}"


def lastname(full: str) -> str:
    parts = full.split()
    return parts[-1] if parts else ""


# ----------------------------------------------------------------------------
# CSV loading
# ----------------------------------------------------------------------------

def load_csv_rows(file_label: str, path: Path) -> list[dict]:
    rows = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            firstname = (raw.get("firstname") or "").strip()
            surname   = (raw.get("surname")   or "").strip()

            if not firstname and " " in surname:
                parts = surname.split(" ", 1)
                firstname, surname = parts[0], parts[1]

            full = f"{firstname} {surname}".strip()

            try:
                age = int(raw.get("age") or 0)
            except (ValueError, TypeError):
                age = 0

            rows.append({
                "_file": file_label,
                "firstname": firstname,
                "surname": surname,
                "full_name": full,
                "norm_full": norm_name(full),
                "norm_last": norm_name(surname),
                "coach_type_name": (raw.get("coach_type_name") or "").strip(),
                "country": (raw.get("country") or "").strip(),
                "age": age,
                "team": (raw.get("team") or "").strip(),
                "league": (raw.get("league") or "").strip(),
            })
    return rows


# ----------------------------------------------------------------------------
# persons_master indexing
# ----------------------------------------------------------------------------

def load_persons_index(path: Path) -> tuple[dict, dict, dict]:
    print(f"[load] reading {path.name} ...", file=sys.stderr)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    persons = data.get("persons", data) if isinstance(data, dict) else {}
    print(f"[load] {len(persons)} persons", file=sys.stderr)

    by_full   = defaultdict(list)
    by_initln = defaultdict(list)
    by_last   = defaultdict(list)

    for tm_id, p in persons.items():
        name = p.get("name") or ""
        if not name:
            continue
        nf = norm_name(name)
        if not nf:
            continue

        dob = p.get("dob") or ""
        birth_year = None
        if isinstance(dob, str) and len(dob) >= 4 and dob[:4].isdigit():
            birth_year = int(dob[:4])

        cc = p.get("current_club")
        if isinstance(cc, dict):
            cc_name = cc.get("name")
        else:
            cc_name = cc

        lite = {
            "tm_id": str(tm_id),
            "name": name,
            "norm_full": nf,
            "birth_year": birth_year,
            "nationality": p.get("nationality"),
            "current_club": cc_name,
        }

        by_full[nf].append(lite)
        il = initial_lastname(nf)
        if il:
            by_initln[il].append(lite)
        ln = lastname(nf)
        if ln:
            by_last[ln].append(lite)

    return by_full, by_initln, by_last


# ----------------------------------------------------------------------------
# Network presence
# ----------------------------------------------------------------------------

def has_network(tm_id: str) -> bool:
    return (NETWORKS_DIR / f"{tm_id}.json").exists()


# ----------------------------------------------------------------------------
# Matching
# ----------------------------------------------------------------------------

def classify_row(row: dict, by_full: dict, by_initln: dict, by_last: dict,
                 current_year: int) -> dict:
    nf = row["norm_full"]
    nl = row["norm_last"]
    age = row["age"]

    candidates = by_full.get(nf, [])
    if len(candidates) == 1:
        return _matched(row, candidates[0], "exact_unique")
    if len(candidates) > 1:
        if age:
            target_year = current_year - age
            tight = [c for c in candidates if c["birth_year"] and abs(c["birth_year"] - target_year) <= 2]
            if len(tight) == 1:
                return _matched(row, tight[0], "exact_age_disambiguated")
        return _matched(row, candidates[0], "exact_ambiguous")

    parts = nf.split()
    if len(parts) >= 2:
        il = initial_lastname(nf)
        ic = by_initln.get(il, [])
        ic = [c for c in ic if lastname(c["norm_full"]) == parts[-1]]
        if age:
            target_year = current_year - age
            tight = [c for c in ic if c["birth_year"] and abs(c["birth_year"] - target_year) <= 2]
            if len(tight) == 1:
                return _matched(row, tight[0], "initial_last_age")
        if len(ic) == 1:
            return _matched(row, ic[0], "initial_last_unique")

    last_cands = by_last.get(nl, [])
    if last_cands and age:
        target_year = current_year - age
        tight = [c for c in last_cands if c["birth_year"] and abs(c["birth_year"] - target_year) <= 2]
        if len(tight) == 1:
            return _matched(row, tight[0], "lastname_age", status="PROBABLE")
        if len(tight) > 1:
            best = tight[0]
            return _matched(row, best, "lastname_age_ambiguous", status="PROBABLE",
                            extra_candidates=[c["tm_id"] for c in tight])
    if last_cands and not age:
        if len(last_cands) == 1:
            return _matched(row, last_cands[0], "lastname_only_unique", status="PROBABLE")

    return {
        "status": "MISSING",
        "match_method": None,
        "tm_id": None,
        "matched_name": None,
        "has_network": False,
        **row,
    }


def _matched(row: dict, person: dict, method: str, status: str = "MATCHED",
             extra_candidates: list | None = None) -> dict:
    out = {
        "status": status,
        "match_method": method,
        "tm_id": person["tm_id"],
        "matched_name": person["name"],
        "matched_birth_year": person.get("birth_year"),
        "matched_nationality": person.get("nationality"),
        "matched_current_club": person.get("current_club"),
        "has_network": has_network(person["tm_id"]),
        **row,
    }
    if extra_candidates:
        out["other_candidates_tm_ids"] = extra_candidates
    return out


# ----------------------------------------------------------------------------
# Report
# ----------------------------------------------------------------------------

def build_report(results: list[dict]) -> dict:
    by_file = defaultdict(list)
    for r in results:
        by_file[r["_file"]].append(r)

    summary = {}
    for fname, rows in by_file.items():
        total = len(rows)
        matched = sum(1 for r in rows if r["status"] == "MATCHED")
        probable = sum(1 for r in rows if r["status"] == "PROBABLE")
        missing  = sum(1 for r in rows if r["status"] == "MISSING")
        matched_no_net = sum(1 for r in rows if r["status"] == "MATCHED" and not r["has_network"])
        summary[fname] = {
            "total": total,
            "matched": matched,
            "probable": probable,
            "missing": missing,
            "matched_no_network": matched_no_net,
        }

    missing_list = sorted(
        [r for r in results if r["status"] == "MISSING"],
        key=lambda r: (r["_file"], r["full_name"]),
    )
    matched_no_net_list = sorted(
        [r for r in results if r["status"] == "MATCHED" and not r["has_network"]],
        key=lambda r: (r["_file"], r["full_name"]),
    )
    probable_list = sorted(
        [r for r in results if r["status"] == "PROBABLE"],
        key=lambda r: (r["_file"], r["full_name"]),
    )

    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "summary_by_file": summary,
        "summary_totals": {
            "total":     sum(s["total"]     for s in summary.values()),
            "matched":   sum(s["matched"]   for s in summary.values()),
            "probable":  sum(s["probable"]  for s in summary.values()),
            "missing":   sum(s["missing"]   for s in summary.values()),
            "matched_no_network": sum(s["matched_no_network"] for s in summary.values()),
        },
        "missing": [
            {
                "file": r["_file"],
                "full_name": r["full_name"],
                "country": r["country"],
                "age": r["age"],
                "team": r["team"],
                "league": r["league"],
                "coach_type": r["coach_type_name"],
            }
            for r in missing_list
        ],
        "matched_no_network": [
            {
                "file": r["_file"],
                "full_name": r["full_name"],
                "matched_name": r["matched_name"],
                "tm_id": r["tm_id"],
                "country": r["country"],
                "team": r["team"],
                "league": r["league"],
                "coach_type": r["coach_type_name"],
                "match_method": r["match_method"],
            }
            for r in matched_no_net_list
        ],
        "probable": [
            {
                "file": r["_file"],
                "full_name": r["full_name"],
                "matched_name": r["matched_name"],
                "tm_id": r["tm_id"],
                "match_method": r["match_method"],
                "country": r["country"],
                "age": r["age"],
                "team": r["team"],
                "has_network": r["has_network"],
            }
            for r in probable_list
        ],
    }


def print_report(report: dict) -> None:
    print()
    print("=" * 78)
    print("COACHINSIDE CSV vs P5 DATABASE — GAP REPORT")
    print("=" * 78)
    print()

    print(f"{'File':<22} {'Total':>6} {'Matched':>8} {'Prob':>6} {'Miss':>6} {'NoNet':>6}")
    print("-" * 60)
    for fname, s in report["summary_by_file"].items():
        print(f"{fname:<22} {s['total']:>6} {s['matched']:>8} {s['probable']:>6} {s['missing']:>6} {s['matched_no_network']:>6}")
    t = report["summary_totals"]
    print("-" * 60)
    print(f"{'TOTAL':<22} {t['total']:>6} {t['matched']:>8} {t['probable']:>6} {t['missing']:>6} {t['matched_no_network']:>6}")

    print()
    print(f"--- MISSING ({len(report['missing'])}) — need to scrape from scratch ---")
    print(f"{'File':<22} {'Name':<32} {'Country':<14} {'Team':<28} {'Age':>4}")
    for r in report["missing"]:
        print(f"{r['file']:<22} {r['full_name'][:31]:<32} {(r['country'] or '')[:13]:<14} {(r['team'] or '')[:27]:<28} {r['age']:>4}")

    print()
    print(f"--- MATCHED-NO-NETWORK ({len(report['matched_no_network'])}) — priority: just run build_coach_network.py ---")
    print(f"{'File':<22} {'Name':<28} {'tm_id':>8}  {'Method':<22} {'Team':<28}")
    for r in report["matched_no_network"]:
        print(f"{r['file']:<22} {r['full_name'][:27]:<28} {r['tm_id']:>8}  {r['match_method']:<22} {(r['team'] or '')[:27]:<28}")

    print()
    print(f"--- PROBABLE ({len(report['probable'])}) — manual confirmation ---")
    print(f"{'File':<22} {'CSV name':<28} {'Matched':<28} {'tm_id':>8} {'Method':<22} {'Net?':>4}")
    for r in report["probable"]:
        print(f"{r['file']:<22} {r['full_name'][:27]:<28} {r['matched_name'][:27]:<28} {r['tm_id']:>8} {r['match_method']:<22} {('Y' if r['has_network'] else 'N'):>4}")
    print()


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------

def main() -> int:
    if not PERSONS_MASTER.exists():
        print(f"[err] {PERSONS_MASTER} not found", file=sys.stderr)
        return 1
    if not NETWORKS_DIR.exists():
        print(f"[err] {NETWORKS_DIR} not found", file=sys.stderr)
        return 1

    by_full, by_initln, by_last = load_persons_index(PERSONS_MASTER)

    current_year = datetime.utcnow().year

    all_results: list[dict] = []
    for label, path in CSV_FILES:
        if not path.exists():
            print(f"[warn] missing {path}", file=sys.stderr)
            continue
        rows = load_csv_rows(label, path)
        print(f"[csv] {label}: {len(rows)} rows", file=sys.stderr)
        for row in rows:
            res = classify_row(row, by_full, by_initln, by_last, current_year)
            all_results.append(res)

    report = build_report(all_results)

    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_OUT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"[out] wrote {REPORT_OUT}", file=sys.stderr)

    print_report(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
