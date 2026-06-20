#!/usr/bin/env python3
"""Scoring audit — validates the relevance-score / strength / ordering invariants of
data/networks/*.json. Complements logic_audit.py (relationship correctness) and
audit_all_networks.py (role classification).

Scoring model (see build_coach_network.py):
  relevance_score = relationship + role + league + recency + gs_bonus, capped at 100
  strength        = clamp((seasons_together + 1) // 2, 1, 5)   # relationship DURATION
  sort order      = (-relevance_score, cat_order, name.lower, tm_id)   # canonical

Checks:
  SC1 score-range      relevance_score missing / non-int / outside [0,100]
  SC2 strength-range   strength missing / non-int / outside [1,5]
  SC3 strength-formula strength != clamp((seasons_together+1)//2,1,5) when seasons known
  SC4 sort-order       relevance_score not non-increasing across contacts (a more
                       relevant contact buried below a less relevant one)
  SC5 degenerate       >=8 contacts but all share one relevance_score (no differentiation)

Usage:
  python3 execution/scoring_audit.py                 # full, exit 0 clean else 1
  python3 execution/scoring_audit.py --sample 200    # random sample of N networks
  python3 execution/scoring_audit.py --seed 42       # reproducible sample
  python3 execution/scoring_audit.py --json FILE     # machine-readable report
  python3 execution/scoring_audit.py --limit N       # only first N (sorted) networks
  python3 execution/scoring_audit.py --check SC1,SC4 # only named checks
"""
import argparse
import glob
import json
import os
import random
import sys
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NET_DIR = os.path.join(BASE, "data", "networks")

CAT_ORDER = {"head_coach": 0, "sporting_director": 1, "executive": 2,
             "executive_governance": 3, "coaching_staff": 4, "lehrgang": 5,
             "scouting": 6, "management": 7, "executive_secondary": 8,
             "academy": 9, "player_coached": 10, "former_teammate": 11,
             "analyst": 12, "other_staff": 13, "medical": 14}

ALL_CHECKS = ["SC1", "SC2", "SC3", "SC4", "SC5"]


def _safe_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def expected_strength(seasons_together):
    return min(5, max(1, (seasons_together + 1) // 2))


def sort_key(c):
    return (-(c.get("relevance_score") or 0),
            CAT_ORDER.get(c.get("category", ""), 99),
            (c.get("name") or "").lower(),
            _safe_int(c.get("tm_id") or c.get("_tm_id")))


def audit_network(path, checks):
    """Return list of (check, message) findings for one network file."""
    out = []
    try:
        d = json.load(open(path))
    except Exception as e:
        return [("SC0", f"unreadable: {e}")]
    center = d.get("center", os.path.basename(path))
    contacts = d.get("contacts", [])
    on = lambda k: k in checks

    for c in contacts:
        name = c.get("name", "?")
        sc = c.get("relevance_score")
        if on("SC1"):
            if sc is None or not isinstance(sc, (int, float)) or isinstance(sc, bool) \
               or sc != sc or sc < 0 or sc > 100:
                out.append(("SC1", f"{center}/{name}: relevance_score={sc!r}"))
        st = c.get("strength")
        if on("SC2"):
            if st is None or not isinstance(st, int) or isinstance(st, bool) \
               or st < 1 or st > 5:
                out.append(("SC2", f"{center}/{name}: strength={st!r}"))
        if on("SC3"):
            seas = c.get("seasons_together")
            if isinstance(seas, int) and not isinstance(seas, bool) and isinstance(st, int):
                exp = expected_strength(seas)
                if st != exp:
                    out.append(("SC3", f"{center}/{name}: strength={st} but "
                                       f"seasons_together={seas} → expected {exp}"))

    if on("SC4") and len(contacts) > 1:
        # The one ordering guarantee that matters for UX: relevance_score must be
        # non-increasing (most relevant first). Tie-order among equal scores is
        # cosmetic and not flagged.
        for i in range(len(contacts) - 1):
            a = contacts[i].get("relevance_score")
            b = contacts[i + 1].get("relevance_score")
            if isinstance(a, (int, float)) and isinstance(b, (int, float)) and b > a:
                out.append(("SC4", f"{center}: contact #{i} '{contacts[i].get('name')}' "
                                   f"score {a} < #{i+1} '{contacts[i+1].get('name')}' "
                                   f"score {b} (out of order)"))
                break

    if on("SC5") and len(contacts) >= 8:
        scores = {c.get("relevance_score") for c in contacts}
        if len(scores) == 1:
            out.append(("SC5", f"{center}: all {len(contacts)} contacts share "
                               f"relevance_score={next(iter(scores))} (no differentiation)"))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", metavar="FILE")
    ap.add_argument("--sample", type=int, help="random sample of N networks")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--limit", type=int, help="first N networks (sorted by filename)")
    ap.add_argument("--check", help="comma list, e.g. SC1,SC4")
    args = ap.parse_args()

    checks = set(ALL_CHECKS)
    if args.check:
        checks = {c.strip().upper() for c in args.check.split(",")}

    files = sorted(glob.glob(os.path.join(NET_DIR, "*.json")))
    if args.limit:
        files = files[:args.limit]
    if args.sample and args.sample < len(files):
        rng = random.Random(args.seed)
        files = rng.sample(files, args.sample)

    findings = []
    by_check = defaultdict(int)
    nets_with = set()
    for i, f in enumerate(files, 1):
        for chk, msg in audit_network(f, checks):
            findings.append({"check": chk, "msg": msg, "file": os.path.basename(f)})
            by_check[chk] += 1
            nets_with.add(f)
        if i % 500 == 0:
            print(f"    …{i}/{len(files)}", file=sys.stderr)

    print("\n  ── SCORING AUDIT RESULTS ──")
    for chk in (["SC0"] if by_check.get("SC0") else []) + ALL_CHECKS:
        if chk not in checks and chk != "SC0":
            continue
        n = by_check.get(chk, 0)
        mark = "✓" if n == 0 else "✗"
        print(f"  [{mark}] {chk}: {n}" + (" finding(s)" if n else ""))
        if n:
            for fi in [x for x in findings if x["check"] == chk][:8]:
                print(f"        {fi['msg']}")
            if n > 8:
                print(f"        … +{n-8} more")

    print(f"\n  SCORING AUDIT: {len(findings)} finding(s) across "
          f"{len(nets_with)} network(s) of {len(files)}")

    if args.json:
        json.dump({"total": len(findings), "by_check": dict(by_check),
                   "networks_with_findings": len(nets_with),
                   "networks_scanned": len(files), "findings": findings},
                  open(args.json, "w"), ensure_ascii=False, indent=2)
        print(f"  → {args.json}")

    sys.exit(1 if findings else 0)


if __name__ == "__main__":
    main()
