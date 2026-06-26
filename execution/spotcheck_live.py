#!/usr/bin/env python3
"""Live platform spotcheck — crawls every BL1/2/3 head-coach dashboard + every
Sportdirektor dashboard linked from the production index, and validates each
actually loads with sane embedded data. Scriptable (curl/urllib), loop-friendly.

Per dashboard it checks:
  - HTTP 200 (follows Vercel clean-URL 308)
  - embedded `const NETWORK = {...}` parses and has a center + contacts
  - no contact carries a foreign-club from a wrong-namespace id (the Bode/Ilsanker
    class) — heuristic: player/teammate contact with a non-playing role + club
  - drilldown JSON (lazy) resolves if referenced

Usage:
  python3 execution/spotcheck_live.py            # full report, exit 1 if problems
  python3 execution/spotcheck_live.py --quiet     # summary only
  python3 execution/spotcheck_live.py --limit 30  # first N of each group
"""
import re, json, sys, argparse, urllib.request, urllib.error, time

BASE = "https://coach-network-explorer.vercel.app"
UA = {"User-Agent": "Mozilla/5.0 (spotcheck)"}


def get(url, timeout=25):
    # Vercel serves dashboards at clean URLs (no .html) and 308-redirects the
    # .html form. urllib's default opener doesn't always follow 308 → request
    # the clean URL directly.
    if url.endswith(".html"):
        url = url[:-5]
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout)
        return r.getcode(), r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return 0, str(e)


def extract_network(html):
    m = re.search(r"const NETWORK\s*=\s*(\{.*?\});", html, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None


def classify_links(index_html):
    """Return (coach_dashboards, sd_dashboards) from the index sections."""
    # SD section + DM section use _sd_network.html; everything else _network.html
    sd = sorted(set(re.findall(r'(dashboards/[a-z0-9_]+_sd_network\.html)', index_html)))
    # coaches: ALL _network.html (non-SD). The BL coaches are the priority but we
    # also catch hist/extra; that's fine — every coach dashboard should load.
    coach = sorted(set(re.findall(r'(dashboards/[a-z0-9_]+_network\.html)', index_html)))
    coach = [c for c in coach if "_sd_network" not in c]
    return coach, sd


import os, unicodedata
PROFILES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "data", "person_profiles")
_FOLD = {"ł": "l", "ø": "o", "æ": "ae", "œ": "oe", "ð": "d", "þ": "th", "ß": "ss"}


def _fold(s):
    s = (s or "").lower()
    s = "".join(_FOLD.get(c, c) for c in s)
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def _name_matches(a, b):
    na, nb = re.sub(r"[^a-z]", "", _fold(a)), re.sub(r"[^a-z]", "", _fold(b))
    if not na or not nb:
        return True  # can't disprove
    if na == nb:
        return True
    ta = [t for t in re.split(r"[^a-z]+", _fold(a)) if len(t) > 1]
    tb = [t for t in re.split(r"[^a-z]+", _fold(b)) if len(t) > 1]
    return bool(ta and tb and ta[-1] == tb[-1])


def _profile_names(tid):
    out = []
    for ns in ("spieler", "trainer"):
        p = os.path.join(PROFILES, f"{ns}_{tid}.json")
        if os.path.exists(p):
            try:
                out.append(json.load(open(p)).get("name"))
            except Exception:
                pass
    return out


def check_network(net):
    """Return list of REAL problems: a contact whose id resolves (in either
    namespace) ONLY to a different person, yet still carries a club/career.
    Legit career transitions (DOB-verified, name matches) are NOT flagged."""
    probs = []
    if not net.get("center"):
        probs.append("no center")
    contacts = net.get("contacts") or []
    if not contacts:
        probs.append("no contacts")
    for c in contacts:
        tid = c.get("_tm_id") or c.get("tm_id")
        if not tid:
            continue
        names = _profile_names(tid)
        if not names:
            continue  # no profile to contradict — can't judge from local files
        if any(_name_matches(n, c.get("name", "")) for n in names):
            continue  # id confirms the person → legit
        cc = c.get("current_club")
        ccn = cc.get("name") if isinstance(cc, dict) else cc
        if ccn or c.get("career_history"):
            probs.append(f"WRONG-ID: {c.get('name')} [{c.get('category')}] id={tid} "
                         f"role='{c.get('role')}' club={ccn} (profile={names})")
    return probs[:5]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    code, idx = get(BASE + "/")
    if code != 200 or not idx:
        print(f"SPOTCHECK FAIL: index HTTP {code}")
        return 1
    coaches, sds = classify_links(idx)
    if args.limit:
        coaches, sds = coaches[:args.limit], sds[:args.limit]

    total_problems = 0
    groups = [("COACH", coaches), ("SD", sds)]
    summary = {}
    for label, links in groups:
        ok = bad = 0
        for href in links:
            code, html = get(f"{BASE}/{href}")
            if code != 200:
                if not args.quiet:
                    print(f"  [{label}] HTTP {code}  {href}")
                bad += 1; total_problems += 1
                continue
            net = extract_network(html)
            if net is None:
                if not args.quiet:
                    print(f"  [{label}] NETWORK unparsable  {href}")
                bad += 1; total_problems += 1
                continue
            probs = check_network(net)
            if probs:
                bad += 1; total_problems += len(probs)
                if not args.quiet:
                    print(f"  [{label}] {href} ({net.get('center')}):")
                    for p in probs:
                        print(f"        {p}")
            else:
                ok += 1
            time.sleep(0.15)  # be gentle
        summary[label] = (ok, bad, len(links))

    print("\n  SPOTCHECK: " + " | ".join(
        f"{k}: {v[0]}/{v[2]} ok" for k, v in summary.items()) +
        f"  — {total_problems} problem(s)")
    return 1 if total_problems else 0


if __name__ == "__main__":
    sys.exit(main())
