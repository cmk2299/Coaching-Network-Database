#!/usr/bin/env python3
"""Backfill current football roles for retired ex-player contacts.

For each candidate spieler tm_id: fetch their TM spieler page, extract a linked
/profil/trainer/{id} (TM's dual-ID cross-link), scrape that trainer profile ONLY
if its DOB matches the spieler's DOB (collision guard — TM reuses ids across
namespaces AND links relatives/namesakes). Writes data/person_profiles/trainer_{id}.json.

The existing build_coach_network post-career logic + sanitizer then surface the
role automatically on rebuild.

Usage:
  python3 execution/backfill_retiree_roles.py --ids-file /tmp/retiree_candidates.txt --limit 30
  python3 execution/backfill_retiree_roles.py --ids-file /tmp/retiree_candidates.txt   # all
  python3 execution/backfill_retiree_roles.py --ids 3851 63022                          # specific
"""
import sys, re, json, time, argparse, unicodedata
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
PROFILES = BASE / "data" / "person_profiles"
sys.path.insert(0, str(Path(__file__).parent))
import scrape_person_profiles as SPP  # reuse its fetch + parse

_FOLD = {"ł": "l", "ø": "o", "æ": "ae", "œ": "oe", "ð": "d", "þ": "th", "ß": "ss"}
def _fold(s):
    s = (s or "").lower(); s = "".join(_FOLD.get(c, c) for c in s)
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
def name_match(a, b):
    na, nb = re.sub(r"[^a-z]", "", _fold(a)), re.sub(r"[^a-z]", "", _fold(b))
    if not na or not nb: return False
    if na == nb: return True
    ta = [t for t in re.split(r"[^a-z]+", _fold(a)) if len(t) > 1]
    tb = [t for t in re.split(r"[^a-z]+", _fold(b)) if len(t) > 1]
    return bool(ta and tb and ta[-1] == tb[-1])

def load_spieler(tid):
    f = PROFILES / f"spieler_{tid}.json"
    if f.exists():
        try: return json.load(open(f))
        except Exception: return None
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids-file"); ap.add_argument("--ids", type=int, nargs="+")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--report", default=None)
    args = ap.parse_args()

    ids = args.ids or []
    if args.ids_file:
        ids += [int(x) for x in open(args.ids_file).read().split()]
    if args.limit: ids = ids[:args.limit]

    stats = {"checked": 0, "no_spieler": 0, "no_trainer_link": 0,
             "dob_reject": 0, "scraped_with_role": 0, "scraped_no_role": 0, "errors": 0}
    found = []
    for i, sid in enumerate(ids, 1):
        sp = load_spieler(sid)
        if not sp:
            stats["no_spieler"] += 1; continue
        stats["checked"] += 1
        sp_dob = (sp.get("dob") or "").strip()
        sp_name = sp.get("name") or ""
        url = sp.get("tm_url") or f"https://www.transfermarkt.de/x/profil/spieler/{sid}"
        try:
            html = SPP.fetch_page(url, f"spieler_{sid}")
        except Exception:
            stats["errors"] += 1; continue
        if not html:
            stats["errors"] += 1; continue
        trainer_ids = sorted(set(int(x) for x in re.findall(r"/profil/trainer/(\d+)", html)))
        if not trainer_ids:
            stats["no_trainer_link"] += 1; continue
        # scrape each linked trainer profile; accept only DOB+name match
        matched = None
        for tid in trainer_ids:
            t_url = f"{SPP.TM_BASE}/x/profil/trainer/{tid}"
            try:
                t_html = SPP.fetch_page(t_url, f"trainer_{tid}")
                prof = SPP.parse_profile(t_html, tid, "trainer") if t_html else None
            except Exception:
                prof = None
            if not prof:
                continue
            t_dob = (prof.get("dob") or "").strip()
            if sp_dob and t_dob and t_dob == sp_dob and name_match(prof.get("name"), sp_name):
                # persist the verified trainer profile
                try:
                    p = SPP.get_profile_path(tid, "trainer")
                    json.dump(prof, open(p, "w"), ensure_ascii=False, indent=2)
                except Exception:
                    pass
                matched = (tid, prof); break
            else:
                stats["dob_reject"] += 1
        if matched:
            tid, prof = matched
            ch = prof.get("career_history") or []
            cur = ch[0] if ch else {}
            role = (cur.get("role") or "").strip()
            if role:
                stats["scraped_with_role"] += 1
                found.append({"spieler": sid, "trainer": tid, "name": sp_name,
                              "role": role, "club": cur.get("club_name")})
            else:
                stats["scraped_no_role"] += 1
        if i % 10 == 0:
            print(f"  [{i}/{len(ids)}] with_role={stats['scraped_with_role']} "
                  f"no_link={stats['no_trainer_link']} dob_reject={stats['dob_reject']}", flush=True)

    print("\nBACKFILL RESULT:", json.dumps(stats))
    print(f"YIELD: {stats['scraped_with_role']}/{stats['checked']} checked have a real current role")
    for f in found[:30]:
        print(f"  + {f['name']}: {f['role']} ({f['club']})  [spieler {f['spieler']} → trainer {f['trainer']}]")
    if args.report:
        json.dump({"stats": stats, "found": found}, open(args.report, "w"), ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
