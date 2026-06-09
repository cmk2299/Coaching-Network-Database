#!/usr/bin/env python3
"""End-to-end expansion driver for a coachinside CSV (vereinslos etc.).

For every coach in the CSV, ensure a full coach network exists:
  Phase 1  resolve canonical TRAINER tm_id (existing trainer profile by name, else
           TM Schnellsuche validated by name/age/country) + scrape trainer profile
  Phase 2  scrape gemeinsameSpiele (Mitspieler) for each resolved trainer id
  Phase 3  build network JSON + dashboard for any coach lacking a network

Robust against the TM dual-ID quirk (trainer id != spieler id) and the profile
namespace migration (trainer_<id>.json). Idempotent: skips already-done work.

Usage:
  python3 execution/build_coachinside_batch.py --csv "data/coachinside_csvs/coachinside_vereinslos.csv"
  python3 execution/build_coachinside_batch.py --csv <path> --phase 1   # only resolve+scrape profiles
  python3 execution/build_coachinside_batch.py --csv <path> --dry-run
"""
from __future__ import annotations
import argparse, csv, json, re, subprocess, sys, unicodedata
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data"
PROF = DATA / "person_profiles"
GS = DATA / "gemeinsame_spiele"
NETS = DATA / "networks"
DASH = BASE / "output" / "dashboards"
sys.path.insert(0, str(Path(__file__).parent))
import scrape_coachinside_missing as CIM   # reuse fetch/parse_search/validate
from lib.normalization import slugify


def fold(s):
    s = (s or "").lower()
    for a, b in {"ł": "l", "ø": "o", "æ": "ae", "œ": "oe", "ß": "ss", "đ": "d", "ç": "c"}.items():
        s = s.replace(a, b)
    return re.sub(r"[^a-z]", "", unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode())


def build_trainer_name_index():
    idx = {}
    # existing trainer profiles by name
    for tf in PROF.glob("trainer_*.json"):
        try:
            nm = json.load(open(tf)).get("name", "")
        except Exception:
            continue
        idx.setdefault(fold(nm), tf.stem.replace("trainer_", ""))
    # ALSO index built network centers — catches coaches whose network exists under
    # an id whose profile name folds differently (or has no separate trainer profile)
    for nf in NETS.glob("*.json"):
        if not nf.stem.isdigit():
            continue
        try:
            c = json.load(open(nf)).get("center", "")
        except Exception:
            continue
        idx.setdefault(fold(c), nf.stem)
    return idx


def resolve_trainer_id(full_name, country, age, name_idx):
    """Return (tm_id:str|None, how:str). Prefer existing trainer profile; else TM search."""
    key = fold(full_name)
    if key in name_idx:
        return name_idx[key], "existing-profile"
    # TM Schnellsuche
    try:
        age_i = int(str(age).strip())
    except (ValueError, TypeError):
        age_i = None
    row = {"full_name": full_name, "country": country, "age": age_i, "team": "Ohne aktuelles Team"}
    slug = re.sub(r"[^a-z0-9]+", "-", fold(full_name)) or "x"
    try:
        html = CIM.fetch(f"{CIM.TM_BASE}/schnellsuche/ergebnis/schnellsuche?query={CIM.quote_plus(full_name)}",
                         f"{slug}")
        if not html:
            return None, "no-search-html"
        cands = CIM.parse_search_trainers(html)
        winners = [c for c in cands if CIM.validate(c, row)[0]]
        if len(winners) == 1:
            return str(winners[0].tm_id), "tm-search"
        if len(winners) > 1:
            return None, f"ambiguous({len(winners)})"
        return None, "unmatched"
    except Exception as e:
        return None, f"err:{e!r}"


def scrape_profile(tm_id):
    if (PROF / f"trainer_{tm_id}.json").exists():
        return True
    r = subprocess.run(["python3", str(BASE / "execution/scrape_person_profiles.py"),
                        "--tm-id", str(tm_id), "--type=trainer"],
                       cwd=BASE, capture_output=True, text=True, timeout=120)
    return (PROF / f"trainer_{tm_id}.json").exists()


def scrape_gs(tm_id):
    if (GS / f"{tm_id}.json").exists():
        return True
    r = subprocess.run(["python3", str(BASE / "execution/scrape_gemeinsame_spiele.py"),
                        "--tm-id", str(tm_id)],
                       cwd=BASE, capture_output=True, text=True, timeout=300)
    return (GS / f"{tm_id}.json").exists()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--phase", type=int, default=0, help="0=all, or 1/2/3")
    ap.add_argument("--force", action="store_true", help="rebuild networks even if they exist")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    coaches = []
    with open(args.csv, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            full = ((r.get("firstname") or "").strip() + " " + (r.get("surname") or "").strip()).strip()
            coaches.append({"name": full, "country": (r.get("country") or "").strip(),
                            "age": (r.get("age") or "").strip()})
    print(f"CSV coaches: {len(coaches)}")

    name_idx = build_trainer_name_index()

    # ── Phase 1: resolve + scrape profiles ──
    resolved = {}   # name -> tm_id
    unresolved = []
    print("\n== Phase 1: resolve trainer ids + scrape profiles ==")
    for c in coaches:
        tid, how = resolve_trainer_id(c["name"], c["country"], c["age"], name_idx)
        if not tid:
            unresolved.append((c["name"], how)); print(f"  ? {c['name']:26} {how}"); continue
        resolved[c["name"]] = tid
        if args.dry_run:
            print(f"  • {c['name']:26} trainer/{tid} ({how})"); continue
        ok = scrape_profile(tid)
        print(f"  {'✓' if ok else '✗'} {c['name']:26} trainer/{tid} ({how})")
    print(f"  resolved {len(resolved)}/{len(coaches)}, unresolved {len(unresolved)}")
    if args.phase == 1 or args.dry_run:
        json.dump({"resolved": resolved, "unresolved": unresolved},
                  open(DATA / "coachinside_batch_resolved.json", "w"), ensure_ascii=False, indent=2)
        return

    # ── Phase 2: scrape GS ──
    print("\n== Phase 2: scrape gemeinsameSpiele ==")
    for name, tid in resolved.items():
        ok = scrape_gs(tid)
        print(f"  {'✓' if ok else '·'} {name:26} GS trainer/{tid}")

    # ── Phase 3: build networks + dashboards ──
    print("\n== Phase 3: build networks ==")
    from build_coach_network import (build_network, generate_background_summaries, build_drilldown,
                                     strip_internal_fields, preload_all_profiles, build_profile_index)
    from generate_dashboard import generate_dashboard
    profiles = preload_all_profiles(); idx = build_profile_index(profiles)
    built = skipped = failed = 0
    for name, tid in resolved.items():
        if (NETS / f"{tid}.json").exists() and not args.force:
            skipped += 1; continue
        try:
            net = build_network(int(tid), profiles, idx)
            if not net:
                failed += 1; print(f"  ✗ {name}: no network"); continue
            net = generate_background_summaries(net)
            dd = build_drilldown(net, profiles, idx)
            strip_internal_fields(net)
            json.dump(net, open(NETS / f"{tid}.json", "w"), ensure_ascii=False, indent=2)
            slug = net.get("slug") or slugify(net.get("center", ""))
            generate_dashboard(net, DASH / f"{slug}_network.html", drilldown=dd)
            built += 1
            print(f"  ✓ {name:26} {net.get('total_contacts')} contacts → {slug}_network.html")
        except Exception as e:
            failed += 1; print(f"  ✗ {name}: {e}")
    print(f"\nDone: built {built}, skipped(existing) {skipped}, failed {failed}")
    print(f"Unresolved ({len(unresolved)}): {[u[0] for u in unresolved]}")


if __name__ == "__main__":
    main()
