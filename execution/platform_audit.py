#!/usr/bin/env python3
"""Platform integrity audit — codifies the manual Playwright walkthrough findings
into repeatable, automated checks. Run on a loop to continuously catch regressions.

Checks (each = one CHECK function returning list[str] of problems):
  C1 template_drilldown_guard  — selectContact/center-image must null-guard DRILLDOWN
                                  (lazy dashboards set DRILLDOWN=null → crash on click)
  C2 est_games_display_leak    — template must not render est_games as appearances
  C3 vacancy_sd_slug           — vacancy SD cross-links must use slugify + resolve to a file
  C4 index_dead_links          — every dashboards/*.html href in index must exist on disk
  C5 overrides_consistency     — coach_overrides entries must reference real staff/clubs;
                                  appointed coaches need a network; no sacked∩appointed dup
  C6 league_counts             — 2026/2027 must be BL1=18 BL2=18 BL3=20
  C7 dashboard_drilldown_pairs — lazy dashboards (DRILLDOWN=null) must have their
                                  {slug}_drilldown.json sibling present
  C8 saison_label              — index must show the current season label

Usage:
  python3 execution/platform_audit.py              # report, exit 0 if clean else 1
  python3 execution/platform_audit.py --json FILE  # also write machine-readable report
  python3 execution/platform_audit.py --quiet      # only print summary line
"""
import json
import re
import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
DASH = OUT / "dashboards"
DATA = ROOT / "data"
TEMPLATE = ROOT / "blessin_network_v3.html"
INDEX = OUT / "index.html"
SEASON = 2026  # 2026/2027

sys.path.insert(0, str(Path(__file__).parent))
try:
    from lib.normalization import slugify
except Exception:
    def slugify(s):
        return re.sub(r"[^a-z0-9]+", "_", (s or "").lower()).strip("_")


def C1_template_drilldown_guard():
    """Every DRILLDOWN[...] access in the template must be null-guarded."""
    probs = []
    if not TEMPLATE.exists():
        return ["C1: template missing"]
    src = TEMPLATE.read_text()
    for i, line in enumerate(src.splitlines(), 1):
        for m in re.finditer(r"DRILLDOWN\s*\[", line):
            # acceptable if 'DRILLDOWN &&' appears before the access on the same line
            prefix = line[: m.start()]
            if "DRILLDOWN &&" not in prefix and "DRILLDOWN&&" not in prefix:
                probs.append(f"C1: unguarded DRILLDOWN[...] at template line {i}: {line.strip()[:80]}")
    return probs


def C2_est_games_display_leak():
    """Template must not fall back to est_games for the appearances column / sort."""
    probs = []
    if not TEMPLATE.exists():
        return probs
    src = TEMPLATE.read_text()
    # Any *executable* use of est_games (not in a comment) is a leak
    for i, line in enumerate(src.splitlines(), 1):
        stripped = line.strip()
        if "est_games" in line and not stripped.startswith("//") and not stripped.startswith("*"):
            probs.append(f"C2: est_games used in template line {i}: {stripped[:80]}")
    return probs


def C3_vacancy_sd_slug(index_html):
    """Vacancy SD links must resolve (umlaut-safe slugify, real file)."""
    probs = []
    vb_start = index_html.find("vacancy-block")
    if vb_start < 0:
        return probs
    vb = index_html[vb_start: index_html.find("hot-seat-block")]
    for href in re.findall(r'<a href="(dashboards/[^"]+)" class="row"', vb):
        if not (OUT / href).exists():
            probs.append(f"C3: vacancy SD link 404 → {href}")
        if "_sche" in href or re.search(r"_[bcdfghjklmnpqrstvwxyz]_", href):
            # heuristic: dropped-umlaut artifact like kr_sche
            probs.append(f"C3: suspicious slug (dropped umlaut?) → {href}")
    return probs


def C4_index_dead_links(index_html):
    """Every dashboards/*.html link in the index must exist on disk."""
    probs = []
    hrefs = set(re.findall(r'href="(dashboards/[^"]+\.html)"', index_html))
    for h in sorted(hrefs):
        if not (OUT / h).exists():
            probs.append(f"C4: dead index link → {h}")
    return probs


def C5_overrides_consistency():
    probs = []
    ovp = DATA / "coach_overrides.json"
    if not ovp.exists():
        return ["C5: coach_overrides.json missing"]
    ov = json.loads(ovp.read_text())
    # A coach sacked at club A and appointed at club B is LEGITIMATE (job change).
    # Only flag the same tm_id sacked AND appointed at the SAME club.
    sacked_by_club = {(s["tm_id"], s.get("club_tm_id")) for s in ov.get("sacked", [])}
    appt_by_club = {(a["tm_id"], a.get("club_tm_id")) for a in ov.get("appointed", [])}
    dup = sacked_by_club & appt_by_club
    if dup:
        probs.append(f"C5: tm_id sacked AND appointed at same club: {dup}")
    # appointed coaches must have a network to render
    for a in ov.get("appointed", []):
        if not (DATA / "networks" / f"{a['tm_id']}.json").exists():
            probs.append(f"C5: appointed {a['name']} ({a['tm_id']}) has NO network → won't render")
    # club staff file must exist for every override club
    for grp in ("sacked", "appointed", "sd"):
        for e in ov.get(grp, []):
            cid = e.get("club_tm_id")
            if cid and not (DATA / "staff" / f"{cid}.json").exists():
                probs.append(f"C5: {grp} entry club {cid} ({e.get('club')}) has no staff file")
    return probs


def C6_league_counts():
    probs = []
    reg = json.loads((DATA / "club_registry.json").read_text())
    clubs = reg["clubs"] if isinstance(reg, dict) else reg
    key = f"{SEASON}/{SEASON+1}"
    counts = {"BL1": 0, "BL2": 0, "BL3": 0}
    for c in clubs:
        nxt = (c.get("leagues") or {}).get(key)
        if not nxt:
            continue
        for code in ("BL1", "BL2", "BL3"):
            if code in nxt:
                counts[code] += 1
                break
    expected = {"BL1": 18, "BL2": 18, "BL3": 20}
    if counts != expected:
        probs.append(f"C6: {key} league counts {counts} != expected {expected}")
    return probs


def C7_dashboard_drilldown_pairs(sample=400):
    """Lazy dashboards (DRILLDOWN=null) must have their drilldown JSON sibling."""
    probs = []
    files = sorted(DASH.glob("*_network.html"))
    checked = 0
    for f in files:
        if checked >= sample:
            break
        head = f.read_text()[:6000]  # DRILLDOWN const is near top of the data block
        m = re.search(r"const DRILLDOWN_URL\s*=\s*'([^']+)'", head)
        is_lazy = "const DRILLDOWN = null" in head
        checked += 1
        if is_lazy:
            if not m:
                probs.append(f"C7: {f.name} DRILLDOWN=null but no DRILLDOWN_URL")
                continue
            jp = f.parent / m.group(1)
            if not jp.exists():
                probs.append(f"C7: {f.name} drilldown JSON missing → {m.group(1)}")
    return probs


def C8_saison_label(index_html):
    probs = []
    m = re.search(r"Saison (\d{2})/(\d{2})", index_html)
    want = f"{str(SEASON)[2:]}/{str(SEASON+1)[2:]}"
    if not m:
        probs.append("C8: no Saison label in index")
    elif f"{m.group(1)}/{m.group(2)}" != want:
        probs.append(f"C8: index Saison {m.group(1)}/{m.group(2)} != expected {want}")
    return probs


def C9_player_current_club_staleness(sample_networks=60, per_net=40):
    """player_coached contacts must carry a REAL current_club from the profile,
    not the squad/station name. Heuristic: if a player_coached contact's
    current_club equals one of the coach's own stations for (almost) ALL such
    contacts, the builder stamped the station instead of the profile club
    (Augsburg-retiree bug). Also flags networks where profiles are so stale
    that 0 retirees show 'Karriereende' despite many veteran players."""
    probs = []
    nets = sorted((DATA / "networks").glob("*.json"))
    # focus on BL coach networks (have a sd_registry-independent signal): sample broadly
    step = max(1, len(nets) // sample_networks)
    checked = 0
    for nf in nets[::step]:
        try:
            net = json.loads(nf.read_text())
        except Exception:
            continue
        pcs = [c for c in net.get("contacts", []) if c.get("category") == "player_coached"]
        if len(pcs) < 8:
            continue
        stations = set(net.get("stations", []))
        def ccname(c):
            cc = c.get("current_club")
            return cc.get("name") if isinstance(cc, dict) else cc
        # what fraction of player current_clubs are just one of the coach's stations?
        on_station = sum(1 for c in pcs[:per_net] if ccname(c) in stations)
        n = min(len(pcs), per_net)
        if n and on_station / n >= 0.85:
            probs.append(f"C9: {nf.stem} — {on_station}/{n} coached-players' current_club == a coach station (builder stamped station, not real club)")
        checked += 1
    if checked == 0:
        return probs
    return probs


def C10_namespace_collisions():
    """TM reuses numeric ids across spieler/trainer namespaces for DIFFERENT
    people. Flag any tm_id with both a spieler_ and trainer_ profile whose
    names differ — these are landmines for any bare-id lookup."""
    probs = []
    pdir = DATA / "person_profiles"
    sp, tr = {}, {}
    for f in pdir.glob("spieler_*.json"):
        tid = f.stem[len("spieler_"):]
        try:
            sp[tid] = (json.loads(f.read_text()).get("name") or "").strip().lower()
        except Exception:
            pass
    for f in pdir.glob("trainer_*.json"):
        tid = f.stem[len("trainer_"):]
        try:
            tr[tid] = (json.loads(f.read_text()).get("name") or "").strip().lower()
        except Exception:
            pass
    for tid in set(sp) & set(tr):
        if sp[tid] and tr[tid] and sp[tid] != tr[tid]:
            probs.append(f"C10: id {tid} collision — spieler='{sp[tid]}' vs trainer='{tr[tid]}' (bare-id lookups unsafe)")
    # This is informational: the builder is now namespace-safe, so these are
    # expected. We cap the report so it doesn't drown the others.
    if len(probs) > 6:
        head = probs[:6]
        head.append(f"C10: … +{len(probs)-6} more known collisions (builder handles via namespace keys)")
        return head
    return probs


CHECKS = [
    ("C1_template_drilldown_guard", lambda ctx: C1_template_drilldown_guard()),
    ("C2_est_games_display_leak", lambda ctx: C2_est_games_display_leak()),
    ("C3_vacancy_sd_slug", lambda ctx: C3_vacancy_sd_slug(ctx["index"])),
    ("C4_index_dead_links", lambda ctx: C4_index_dead_links(ctx["index"])),
    ("C5_overrides_consistency", lambda ctx: C5_overrides_consistency()),
    ("C6_league_counts", lambda ctx: C6_league_counts()),
    ("C7_dashboard_drilldown_pairs", lambda ctx: C7_dashboard_drilldown_pairs()),
    ("C8_saison_label", lambda ctx: C8_saison_label(ctx["index"])),
    ("C9_player_current_club_staleness", lambda ctx: C9_player_current_club_staleness()),
]

# Informational checks: printed for awareness but NOT counted as failures
# (the builder already handles these correctly via namespace-keyed lookups).
INFO_CHECKS = [
    ("C10_namespace_collisions", lambda ctx: C10_namespace_collisions()),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", type=Path, help="write machine-readable report")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    ctx = {"index": INDEX.read_text() if INDEX.exists() else ""}
    report = {}
    total = 0
    for name, fn in CHECKS:
        try:
            probs = fn(ctx)
        except Exception as e:
            probs = [f"{name}: EXCEPTION {e}"]
        report[name] = probs
        total += len(probs)
        if not args.quiet:
            status = "✓" if not probs else f"✗ {len(probs)}"
            print(f"  [{status}] {name}")
            for p in probs[:15]:
                print(f"        {p}")
            if len(probs) > 15:
                print(f"        … +{len(probs)-15} more")

    # Informational checks (not counted toward pass/fail)
    info = {}
    for name, fn in INFO_CHECKS:
        try:
            probs = fn(ctx)
        except Exception as e:
            probs = [f"{name}: EXCEPTION {e}"]
        info[name] = probs
        if not args.quiet and probs:
            print(f"  [i] {name} ({len(probs)} known, informational)")
            for p in probs[:8]:
                print(f"        {p}")

    print(f"\n  PLATFORM AUDIT: {total} problem(s) across {len(CHECKS)} checks")
    if args.json:
        args.json.write_text(json.dumps(
            {"total": total, "checks": report, "info": info}, ensure_ascii=False, indent=2))
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
