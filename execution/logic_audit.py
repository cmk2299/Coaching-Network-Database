#!/usr/bin/env python3
"""Relationship-logic audit — bulletproofs coaches, SDs, players-coached and their
connections in data/networks/*.json against the authoritative person profiles.

Unlike platform_audit.py (template/structure) and audit_all_networks.py (generic-role
Schuhen-pattern), this validates the *logical correctness of relationships*:

  COACHES (head_coach / coaching_staff / academy / nlz_coach)
    LC1 active-player-as-coach   profile is a pure player (type=spieler, playing
                                 position, no coach career) but categorized as a coach
  SPORTING DIRECTORS (sporting_director / executive*)
    LS1 sd-without-mgmt-role     SD/executive contact whose profile has no management/SD
                                 keyword anywhere in career_history (false-positive SD)
  PLAYERS COACHED (player_coached)
    LP1 station-not-coached      a coached-at station that the coach never coached at
    LP2 stats-insane             negative / impossible appearances·goals·assists·minutes
    LP3 current-club-stamped     current_club == a coach station but the player's own
                                 profile says otherwise (C9 stale-stamp, cross-network)
  CONNECTIONS (all categories)
    LX1 self-loop                the center appears as one of its own contacts
    LX2 duplicate-contact        same tm_id appears twice in one network
    LX3 namespace-frankenstein   contact name ≠ the profile name for its tm_url namespace
                                 (surname mismatch → wrong-namespace career bleed)
    LX4 teammate-no-evidence     former_teammate with 0 shared matches AND 0 shared
                                 stations (no basis for the "Mitspieler" link)
    LX5 connection-empty-shared  coaches/sds_worked_with entry with empty shared[]
    LX6 current-club-bad-shape   current_club is neither str nor {name:...} dict

Usage:
  python3 execution/logic_audit.py                 # report, exit 0 clean else 1
  python3 execution/logic_audit.py --json FILE      # machine-readable report
  python3 execution/logic_audit.py --limit N        # only first N networks (debug)
  python3 execution/logic_audit.py --check LP1,LX3  # only run named checks
"""
import argparse
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NETWORKS = ROOT / "data" / "networks"
MASTER = ROOT / "data" / "persons_master.json"

sys.path.insert(0, str(Path(__file__).parent))
try:
    from lib.normalization import classify_role
except Exception:
    def classify_role(s):
        return ""
try:
    from lib.normalization import normalize_club
except Exception:
    def normalize_club(name, tm_id=None):
        return name or ""

MGMT_KEYWORDS = (
    "sportdirektor", "sportvorstand", "sportlich", "geschäftsführer", "direktor",
    "manager", "vorstand", "kaderplan", "technical director", "sporting director",
    "leiter", "aufsichtsrat", "präsident", "vizepräsident", "generalsekretär",
    "präsidium", "geschäftsführung", "ceo", "kaufmänn", "scout",
)
PLAYING_POSITIONS = (
    "torwart", "abwehr", "verteidig", "innenverteidig", "aussenverteidig",
    "mittelfeld", "sturm", "stürmer", "flügel", "angriff", "spielmacher",
    "rechtsaußen", "linksaußen", "hängende spitze", "defensives mittelfeld",
    "zentrales mittelfeld", "offensives mittelfeld", "libero",
)


# TM slugs are lossy ASCII folds: ß→ss, ü→u, ı→i, ø→o, etc. Map the chars that
# NFKD does NOT decompose, then strip remaining combining marks.
_TRANSLIT = str.maketrans({
    "ß": "ss", "ı": "i", "ø": "o", "æ": "ae", "œ": "oe", "ð": "d", "þ": "th",
    "ł": "l", "đ": "d", "ŋ": "n", "ħ": "h",
})


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s or "")
                   if not unicodedata.combining(c))


def fold(s):
    """ASCII-fold a name the way TM builds slugs (so display↔slug compare cleanly)."""
    return strip_accents((s or "").lower().translate(_TRANSLIT))


def name_tokens(s):
    """Set of alnum tokens from a display name (splits space AND hyphen)."""
    return {t for t in re.split(r"[^a-z0-9]+", fold(s)) if len(t) > 1}


def slug_tokens(tm_url):
    """Set of alnum tokens from the TM url slug — authoritative link target."""
    m = re.search(r"transfermarkt\.[a-z]+/([^/]+)/profil/", tm_url or "")
    if not m:
        return set()
    return {t for t in re.split(r"[^a-z0-9]+", fold(m.group(1))) if len(t) > 1}


def surname(name):
    toks = strip_accents(name or "").lower().replace(".", " ").split()
    return toks[-1] if toks else ""


COACH_ROLE_KW = ("trainer", "coach", "co-trainer", "cheftrainer", "torwarttrainer")


def tm_namespace(tm_url):
    """Return ('spieler'|'trainer', id) from a TM url, else (None, None)."""
    m = re.search(r"/profil/(spieler|trainer)/(\d+)", tm_url or "")
    if m:
        return m.group(1), m.group(2)
    return None, None


def slug_surname(tm_url):
    """Surname from the TM url slug — the authoritative target name for that link.
    Collision-immune: does not depend on persons_master keys. e.g.
    '/sascha-molders/profil/spieler/17689' -> 'molders'."""
    m = re.search(r"transfermarkt\.[a-z]+/([^/]+)/profil/", tm_url or "")
    if not m:
        return ""
    toks = m.group(1).replace("-", " ").split()
    return strip_accents(toks[-1]).lower() if toks else ""


def cc_name(cc):
    """current_club can be str, dict{name}, or None — normalize to a name string."""
    if isinstance(cc, dict):
        return (cc.get("name") or "").strip()
    if isinstance(cc, str):
        return cc.strip()
    return ""


def load_master():
    raw = json.loads(MASTER.read_text())
    persons = raw.get("persons", raw)
    return persons


def profile_strict(persons, ns_type, tm_id):
    """STRICT namespaced lookup only — NO bare-id fallback.

    Bare-id keys are collision-prone (679 dual-namespace ids: the last-scraped
    namespace overwrote the first). Returning a bare-id profile produces false
    Frankenstein/role flags. Identity checks must use the namespaced key or skip.
    Returns None when the namespaced profile is absent (coverage gap, not a bug)."""
    if ns_type and tm_id:
        return persons.get(f"{ns_type}_{tm_id}")
    return None


def career_text(profile):
    out = []
    for e in (profile or {}).get("career_history", []) or []:
        if isinstance(e, dict):
            out.append((e.get("role") or "") + " " + (e.get("club") or ""))
        elif isinstance(e, str):
            out.append(e)
    return " | ".join(out).lower()


COACH_CATS = {"head_coach", "coaching_staff", "academy", "nlz_coach"}
SD_CATS = {"sporting_director", "executive", "executive_governance",
           "executive_secondary", "management"}


def audit_network(path, persons, enabled):
    """Return list of (check, network_id, contact_name, detail)."""
    nid = path.stem
    try:
        d = json.loads(path.read_text())
    except Exception as e:
        return [("LOAD", nid, "", f"unreadable: {e}")]
    out = []
    center = d.get("center")
    center_name = center if isinstance(center, str) else (center or {}).get("name", "")
    coach_stations = set(d.get("stations") or [])
    contacts = d.get("contacts") or []

    seen_ids = {}
    cn_sur = surname(center_name)

    def on(c):
        return c in enabled

    for c in contacts:
        name = c.get("name", "")
        cat = c.get("category", "")
        tmid = c.get("_tm_id")
        ns_type, ns_id = tm_namespace(c.get("tm_url"))
        # STRICT: namespaced profile only — never bare-id (collision-prone).
        prof = profile_strict(persons, ns_type, ns_id)
        url_sur = slug_surname(c.get("tm_url"))

        # LX1 self-loop
        if on("LX1") and name and surname(name) == cn_sur and cn_sur:
            if (ns_id and center and isinstance(center, dict)
                    and str(center.get("tm_id")) == str(ns_id)):
                out.append(("LX1", nid, name, "center appears as own contact"))

        # LX2 duplicate
        if on("LX2"):
            key = (ns_type, ns_id) if ns_id else ("_tm", tmid)
            if key != (None, None) and key in seen_ids:
                out.append(("LX2", nid, name, f"duplicate of {seen_ids[key]} ({key})"))
            else:
                seen_ids[key] = name

        # LX6 current_club shape
        cc = c.get("current_club", "")
        if on("LX6") and cc is not None and not isinstance(cc, (str, dict)):
            out.append(("LX6", nid, name, f"current_club bad type {type(cc).__name__}"))

        # LX3 namespace frankenstein — contact name vs its OWN url slug tokens
        # (the authoritative target). Collision-immune. A real frankenstein has
        # ZERO shared tokens between the embedded name and the link slug;
        # transliteration/word-order diffs still share ≥1 token and pass.
        if on("LX3"):
            nt, st = name_tokens(name), slug_tokens(c.get("tm_url"))
            # prefix match handles single-name TM slugs (Raí→'raitm', Edú→'edutm')
            def _rel(a, b):
                # substring containment handles single-name TM slugs that append
                # to the name (Raí→'raitm', Edú→'edutm', Jô→'jotm')
                return a == b or (len(a) >= 2 and len(b) >= 2 and
                                  (a in b or b in a))
            shared = any(_rel(a, b) for a in nt for b in st)
            if nt and st and not shared:
                out.append(("LX3", nid, name,
                            f"name tokens {sorted(nt)} share nothing with slug {sorted(st)}"))

        # LX5 empty shared in connections
        if on("LX5"):
            for field in ("coaches_worked_with", "sds_worked_with"):
                for e in c.get(field) or []:
                    if isinstance(e, dict) and not (e.get("shared") or []):
                        out.append(("LX5", nid, name,
                                    f"{field} -> {e.get('name')} empty shared[]"))
                        break

        # COACHES — LC1: coach-category contact whose TM link is a /spieler/ profile
        # that is a pure player (playing position, no coaching career). The link
        # pointing at a player profile is the misclassification signal.
        role_l = (c.get("role") or "").lower()
        if on("LC1") and cat in COACH_CATS and ns_type == "spieler" and prof \
                and not any(k in role_l for k in COACH_ROLE_KW):
            pos = (prof.get("position") or "").lower()
            ct = career_text(prof)
            has_coach_career = any(k in ct for k in COACH_ROLE_KW)
            playing = any(p in pos for p in PLAYING_POSITIONS)
            if playing and not has_coach_career:
                out.append(("LC1", nid, name,
                            f"cat={cat} role='{c.get('role')}' links to /spieler/ pure player (pos={pos})"))

        # SPORTING DIRECTORS — LS1: SD-category contact linking to a /spieler/
        # profile that is a pure player with no management role anywhere. This is
        # the false-positive-SD pattern (player miscast as Sportdirektor), NOT a
        # legitimate governance figure (Generalsekretär/Präsident keep a /trainer/
        # mgmt profile and are skipped).
        if on("LS1") and cat in SD_CATS and ns_type == "spieler" and prof \
                and not any(k in role_l for k in COACH_ROLE_KW):
            pos = (prof.get("position") or "").lower()
            ct = career_text(prof)
            role = role_l
            playing = any(p in pos for p in PLAYING_POSITIONS)
            has_mgmt = any(k in ct for k in MGMT_KEYWORDS) or \
                any(k in role for k in MGMT_KEYWORDS)
            if playing and not has_mgmt:
                out.append(("LS1", nid, name,
                            f"cat={cat} links to /spieler/ pure player (pos={pos}) role='{c.get('role')}'"))

        # PLAYERS COACHED
        if cat == "player_coached":
            # LP1 station not coached
            if on("LP1") and coach_stations:
                bad = [s for s in (c.get("stations") or []) if s not in coach_stations]
                if bad:
                    out.append(("LP1", nid, name,
                                f"coached-at {bad} not in coach stations"))
            # LP2 stats insanity
            if on("LP2"):
                app = c.get("appearances")
                g = c.get("goals")
                a = c.get("assists")
                mn = c.get("minutes")
                nums = {"appearances": app, "goals": g, "assists": a, "minutes": mn}
                for k, v in nums.items():
                    if isinstance(v, (int, float)) and v < 0:
                        out.append(("LP2", nid, name, f"{k}={v} negative"))
                if isinstance(app, (int, float)) and app >= 0:
                    if isinstance(g, (int, float)) and g > app:
                        out.append(("LP2", nid, name, f"goals {g} > appearances {app}"))
                    if isinstance(a, (int, float)) and a > app:
                        out.append(("LP2", nid, name, f"assists {a} > appearances {app}"))
                    if isinstance(mn, (int, float)) and mn > app * 130:
                        out.append(("LP2", nid, name,
                                    f"minutes {mn} > appearances {app}*130"))
            # LP3 current_club stamped from coach station (profile-authoritative)
            # Normalize BOTH sides via normalize_club() before comparing: the contact
            # value is already normalized at build time ("TSG Hoffenheim") while the
            # profile value is raw ("TSG 1899 Hoffenheim") — a naive string compare
            # produced ~1600 false positives for active players still at the club.
            # Skip post-career contacts: their current_club is intentionally their
            # REAL current employer (e.g. retired player now coaching at the same
            # club the coach passed through) — not a stale coach-station stamp.
            if on("LP3") and prof and not c.get("post_career_role"):
                disp = cc_name(c.get("current_club"))
                truth = cc_name(prof.get("current_club"))
                disp_n = normalize_club(disp, None) if disp else ""
                truth_n = normalize_club(truth, None) if truth else ""
                if disp and disp in coach_stations and truth and \
                   strip_accents(disp_n).lower() != strip_accents(truth_n).lower():
                    out.append(("LP3", nid, name,
                                f"shows current_club='{disp}' (coach station) but profile='{truth}'"))

        # CONNECTIONS — LX4 teammate without evidence
        if on("LX4") and cat == "former_teammate":
            sm = c.get("shared_matches")
            ss = c.get("shared_station_count", 0)
            if (not sm or sm == 0) and (not ss or ss == 0) and \
               not c.get("teams_together_count"):
                out.append(("LX4", nid, name,
                            "former_teammate, 0 shared matches & 0 shared stations"))

    return out


ALL_CHECKS = ["LC1", "LS1", "LP1", "LP2", "LP3",
              "LX1", "LX2", "LX3", "LX4", "LX5", "LX6"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", type=Path)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--check", help="comma list, e.g. LP1,LX3")
    ap.add_argument("--examples", type=int, default=8)
    args = ap.parse_args()

    enabled = set(args.check.split(",")) if args.check else set(ALL_CHECKS)

    print("  Loading persons_master…", flush=True)
    persons = load_master()
    files = sorted(NETWORKS.glob("*.json"))
    if args.limit:
        files = files[: args.limit]
    print(f"  Auditing {len(files)} networks, checks={sorted(enabled)}\n", flush=True)

    findings = []
    nets_with = set()
    for i, f in enumerate(files):
        res = audit_network(f, persons, enabled)
        if res:
            nets_with.add(f.stem)
        findings.extend(res)
        if (i + 1) % 200 == 0:
            print(f"    …{i + 1}/{len(files)}", flush=True)

    by_check = defaultdict(list)
    for chk, nid, name, detail in findings:
        by_check[chk].append({"network": nid, "contact": name, "detail": detail})

    print("\n  ── LOGIC AUDIT RESULTS ──")
    total = 0
    for chk in ["LOAD"] + ALL_CHECKS:
        items = by_check.get(chk, [])
        if not items:
            if chk in enabled:
                print(f"  [✓] {chk}: 0")
            continue
        total += len(items)
        nnets = len({it["network"] for it in items})
        print(f"  [✗] {chk}: {len(items)} finding(s) in {nnets} network(s)")
        for it in items[: args.examples]:
            print(f"        {it['network']}/{it['contact']}: {it['detail']}")
        if len(items) > args.examples:
            print(f"        … +{len(items) - args.examples} more")

    print(f"\n  LOGIC AUDIT: {total} finding(s) across "
          f"{len(nets_with)} network(s) of {len(files)}")

    if args.json:
        args.json.write_text(json.dumps({
            "total": total,
            "networks_audited": len(files),
            "networks_with_findings": len(nets_with),
            "by_check": {k: by_check.get(k, []) for k in ALL_CHECKS},
            "counts": {k: len(by_check.get(k, [])) for k in ALL_CHECKS},
        }, ensure_ascii=False, indent=2))
        print(f"  → {args.json}")

    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
