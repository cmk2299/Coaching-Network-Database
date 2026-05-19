#!/usr/bin/env python3
"""
Generate All BL Coaches — Schritt 3 des MVP

Batch-generates network dashboards for all BL1+BL2 head coaches,
plus an index page for coach selection.

Usage:
    python generate_all_bl_coaches.py                          # BL1 + BL2
    python generate_all_bl_coaches.py --leagues BL1            # Only BL1
    python generate_all_bl_coaches.py --skip-networks          # Only rebuild index
    python generate_all_bl_coaches.py --only 26099 5372        # Specific coaches
    python generate_all_bl_coaches.py --include-historical     # Add 150+ historical coaches

Output:
    output/dashboards/{slug}_network.html   — one dashboard per coach
    output/index.html                       — coach selection page
"""

import argparse
import json
import re
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict

import sys
sys.path.insert(0, str(Path(__file__).parent))

from build_coach_network import (
    load_club_registry, get_bl_clubs, load_staff, load_coach_profile,
    build_network, generate_background_summaries, build_drilldown,
    strip_internal_fields,
    preload_all_profiles, build_profile_index,
    OUTPUT_DIR, format_season, PROFILES_DIR, STAFF_DIR,
)
from lib.normalization import normalize_club, filter_nationality, slugify
from generate_dashboard import generate_dashboard

BASE = Path(__file__).parent.parent
DASHBOARD_DIR = BASE / "output" / "dashboards"
INDEX_OUTPUT = BASE / "output" / "index.html"


def load_historical_coaches(include_categories: List[str] = None) -> List[dict]:
    """Load historical coaches from data/historical_coaches_candidates.json."""
    if include_categories is None:
        include_categories = ["A", "C", "D"]  # A=Former, C=Co-Trainer, D=Historical

    hist_path = BASE / "data" / "historical_coaches_candidates.json"
    if not hist_path.exists():
        return []

    try:
        with open(hist_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        coaches = []
        for coach_data in data.get("coaches", []):
            if coach_data.get("category") not in include_categories:
                continue

            # Convert to same format as get_all_head_coaches output
            category = coach_data.get("category", "")
            league_map = {
                "A": "HIST-A",  # Ehemaliger BL-Cheftrainer
                "B": "HIST-B",  # Vereinslos
                "C": "HIST-C",  # Co-Trainer
                "D": "HIST-D",  # Historisch
            }

            coaches.append({
                "tm_id": coach_data.get("tm_id"),
                "name": coach_data.get("name", ""),
                "slug": coach_data.get("slug", slugify(coach_data.get("name", ""))),
                "club": coach_data.get("last_bl_club", ""),
                "club_tm_id": coach_data.get("last_bl_club_tm_id", 0),
                "league": league_map.get(category, "HIST"),
                "tm_url": coach_data.get("tm_url", ""),
                "image_url": coach_data.get("image_url", ""),
                "nationality": filter_nationality(coach_data.get("nationality", "")),
                "has_profile": True,  # They're already in persons_master
                "is_historical": True,
            })

        return coaches
    except Exception as e:
        print(f"  ⚠ Error loading historical coaches: {e}")
        return []


def get_all_head_coaches(club_registry: Dict[int, dict], leagues: List[str],
                         season: int = 2025) -> List[dict]:
    """Get all head coaches for given leagues and season."""
    bl_clubs = get_bl_clubs(club_registry, leagues, season)
    coaches = []

    for club_id, club in sorted(bl_clubs.items(), key=lambda x: x[1].get("name", "")):
        staff = load_staff(club_id)
        if not staff:
            continue

        trainerstab = [s for s in staff.get("staff", []) if s.get("section") == "Trainerstab"]
        if not trainerstab:
            continue

        head = trainerstab[0]
        league_data = club.get("leagues") or club.get("league_history", {})
        # Try "2025/2026" format first, then "2025"
        club_leagues = league_data.get(f"{season}/{season+1}", league_data.get(str(season), []))
        league = "BL1" if "BL1" in club_leagues else ("BL3" if "BL3" in club_leagues else "BL2")

        profile = load_coach_profile(head["tm_id"])

        coaches.append({
            "tm_id": head["tm_id"],
            "name": head["name"],
            "slug": re.sub(r'[^a-z0-9]+', '_', head["name"].lower()).strip('_'),
            "club": normalize_club(club.get("name", staff.get("club_name", "?")), club_id),
            "club_tm_id": club_id,
            "league": league,
            "tm_url": head.get("tm_url", ""),
            "image_url": profile.get("image_url", "") if profile else "",
            "nationality": filter_nationality(profile.get("nationality", "")) if profile else "",
            "has_profile": profile is not None,
        })

    return coaches


def load_all_network_coaches(existing_tm_ids: set) -> List[dict]:
    """Load coach info from ALL network JSONs not already in existing_tm_ids."""
    NETWORKS_DIR = BASE / "data" / "networks"
    PERSONS_MASTER = BASE / "data" / "persons_master.json"

    # Load persons_master for metadata
    pm = {}
    pm_path = PERSONS_MASTER
    if pm_path.exists():
        try:
            raw = json.load(open(pm_path))
            pm = raw.get("persons", {})
        except Exception:
            pass

    extra_coaches = []
    for nf in sorted(NETWORKS_DIR.glob("*.json")):
        tm_id_str = nf.stem
        if not tm_id_str.isdigit():
            continue
        tm_id = int(tm_id_str)
        if tm_id in existing_tm_ids:
            continue

        try:
            net = json.load(open(nf))
        except Exception:
            continue

        name = net.get("center", "?")
        center_info = net.get("center_info", {})
        slug = net.get("slug") or re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')

        # Get nationality from persons_master
        person = pm.get(tm_id_str, {})
        nationality = filter_nationality(person.get("nationality", center_info.get("nationality", "")))
        image_url = person.get("image_url", "")

        # Determine a label from their current role or last station
        stations = net.get("stations", [])
        last_station = stations[0] if stations else ""

        extra_coaches.append({
            "tm_id": tm_id,
            "name": name,
            "slug": slug,
            "club": last_station,
            "club_tm_id": 0,
            "league": "EXTRA",
            "tm_url": center_info.get("tm_url", ""),
            "image_url": image_url,
            "nationality": nationality,
            "has_profile": True,
        })

    return extra_coaches


def generate_index_page(coaches: List[dict], season: int = 2025, include_historical: bool = False,
                         include_decision_makers: bool = False, include_nlz: bool = False):
    """Generate index.html with coach selection cards."""
    bl1 = sorted([c for c in coaches if c["league"] == "BL1"], key=lambda x: x["club"])
    bl2 = sorted([c for c in coaches if c["league"] == "BL2"], key=lambda x: x["club"])
    bl3 = sorted([c for c in coaches if c["league"] == "BL3"], key=lambda x: x["club"])

    # Historical coaches (if included)
    hist_a = sorted([c for c in coaches if c["league"] == "HIST-A"], key=lambda x: x["name"])
    hist_b = sorted([c for c in coaches if c["league"] == "HIST-B"], key=lambda x: x["name"])
    hist_c = sorted([c for c in coaches if c["league"] == "HIST-C"], key=lambda x: x["name"])
    hist_d = sorted([c for c in coaches if c["league"] == "HIST-D"], key=lambda x: x["name"])

    extra = sorted([c for c in coaches if c["league"] == "EXTRA"], key=lambda x: x["name"])
    other = sorted([c for c in coaches if c["league"] not in ("BL1", "BL2", "BL3", "HIST-A", "HIST-B", "HIST-C", "HIST-D", "EXTRA")], key=lambda x: x["club"])

    # Load network stats for contact counts
    network_stats = {}
    for c in coaches:
        net_path = OUTPUT_DIR / f"{c['tm_id']}.json"
        if net_path.exists():
            try:
                n = json.load(open(net_path))
                network_stats[c["tm_id"]] = {
                    "contacts": n.get("total_contacts", 0),
                    "stations": len(n.get("stations", [])),
                }
            except Exception:
                pass

    # Load Hot-Seat-Scores (powered by execution/calc_hot_seat_score.py)
    hot_seat_by_coach = {}
    hot_seat_path = BASE / "data" / "hot_seat_scores.json"
    if hot_seat_path.exists():
        try:
            hs = json.load(open(hot_seat_path))
            for r in hs.get("scores", []):
                hot_seat_by_coach[r["coach_tm_id"]] = r
        except Exception:
            pass

    # Country → ISO-3 code mapping (replaces emoji flags with text badges)
    # Keeps UI emoji-free per brand policy; rendered via .nat-badge CSS class.
    COUNTRY_ISO = {
        "Deutschland": "GER", "Österreich": "AUT", "Schweiz": "SUI",
        "Niederlande": "NED", "Dänemark": "DEN", "Spanien": "ESP",
        "Kroatien": "CRO", "Belgien": "BEL", "Frankreich": "FRA",
        "Italien": "ITA", "England": "ENG", "Schweden": "SWE",
        "Norwegen": "NOR", "Türkei": "TUR", "Polen": "POL",
        "USA": "USA", "Vereinigte Staaten": "USA",
        "Brasilien": "BRA", "Argentinien": "ARG",
        "Portugal": "POR", "Tschechien": "CZE", "Ungarn": "HUN",
        "Bosnien-Herzegowina": "BIH", "Bosnien und Herzegowina": "BIH",
        "Serbien": "SRB", "Jugoslawien (SFR)": "SRB",
        "Nordmazedonien": "MKD", "Rumänien": "ROU", "Griechenland": "GRE",
        "Finnland": "FIN", "Israel": "ISR", "Schottland": "SCO",
        "Irland": "IRL", "Wales": "WAL", "Luxemburg": "LUX",
        "Kosovo": "KOS", "Montenegro": "MNE", "Albanien": "ALB",
        "Slowakei": "SVK", "Slowenien": "SVN", "Bulgarien": "BUL",
        "Ukraine": "UKR", "Japan": "JPN", "Korea, Süd": "KOR",
        "Ghana": "GHA", "Nigeria": "NGA", "Kamerun": "CMR",
        "Senegal": "SEN", "Mali": "MLI", "Marokko": "MAR",
        "Tunesien": "TUN", "Algerien": "ALG", "Côte d'Ivoire": "CIV",
    }

    def make_rows(coach_list: List[dict]) -> str:
        rows = []
        for c in coach_list:
            dashboard_file = f"dashboards/{c['slug']}_network.html"
            img = c.get("image_url", "")
            img_html = f'<img src="{img}" alt="" onerror="this.parentElement.innerHTML=\'&bull;\'">' if img else '<span>&bull;</span>'
            stats = network_stats.get(c["tm_id"], {})
            contacts = stats.get("contacts", 0)
            stations = stats.get("stations", 0)
            nat = filter_nationality(c.get("nationality", ""))
            iso = COUNTRY_ISO.get(nat, "")
            nat_html = f'<span class="nat-badge" title="{nat}">{iso}</span>' if iso else ""

            # Hot-Seat-Score als eigene Spalte (sortable)
            hs = hot_seat_by_coach.get(c["tm_id"])
            hs_score = hs["score"] if hs else 0
            hs_status = hs.get("status", "ruhig") if hs else "ruhig"
            if hs and hs_score > 0:
                tooltip = (
                    f"Hot-Seat {hs_score}/100 ({hs_status}) — "
                    f"PPG {hs['ppg']:.2f}, "
                    f"#{hs['position']} {hs['league']}, "
                    f"winless {hs['winless_streak']}, "
                    f"GD {hs['goal_diff']:+d}"
                )
                # CSS-class mapping: critical/hot-seat/warm/ruhig
                cls_short = {"critical": "critical", "hot-seat": "hot",
                             "warm": "warm", "ruhig": "ruhig"}.get(hs_status, "empty")
                hs_cell = f'<div class="row-hotseat row-hotseat--{cls_short}" title="{tooltip}">{hs_score}</div>'
            else:
                hs_cell = '<div class="row-hotseat row-hotseat--empty" title="Kein Hot-Seat-Score">—</div>'

            rows.append(f"""
        <div class="row-wrap" data-name="{c['name'].lower()}" data-club="{c['club'].lower()}" data-contacts="{contacts}" data-stations="{stations}" data-hotseat="{hs_score}">
          <a href="{dashboard_file}" class="row">
            <div class="row-img">{img_html}</div>
            <div class="row-name">{nat_html}{c['name']}</div>
            <div class="row-club">{c['club']}</div>
            {hs_cell}
            <div class="row-stat">{contacts}</div>
            <div class="row-stat">{stations}</div>
            <div class="row-go">&rsaquo;</div>
          </a>
          <button class="row-refresh" onclick="event.stopPropagation();refreshClub({c['club_tm_id']},this)" title="Staff-Daten aktualisieren">&#x21bb;</button>
        </div>""")
        return "\n".join(rows)

    season_str = format_season(season)
    now = datetime.now().strftime('%d.%m.%Y')
    now_full = datetime.now().strftime('%d.%m.%Y %H:%M')

    total_contacts = sum(s.get("contacts", 0) for s in network_stats.values())

    # Active coaches
    active_coaches = len(bl1) + len(bl2) + len(bl3)

    # Hot-Seat-Counter for Stats-Bar — split critical/hot vs warm
    hot_critical = sum(1 for r in hot_seat_by_coach.values() if r.get("status") == "critical")
    hot_seat_n = sum(1 for r in hot_seat_by_coach.values() if r.get("status") == "hot-seat")
    hot_warm = sum(1 for r in hot_seat_by_coach.values() if r.get("status") == "warm")
    flagged_high = hot_critical + hot_seat_n  # critical + hot-seat (akut)
    flagged_warm = hot_warm                    # nur warm (beobachten)

    hot_seat_stats = ""
    if flagged_high or flagged_warm:
        # Two stat-items: HOT (red) and WARM (amber)
        if flagged_high:
            hot_seat_stats += (
                f'<div class="stat-item">'
                f'<div class="stat-val" style="color:#e74c3c">{flagged_high}</div>'
                f'<div class="stat-lbl" title="Critical (≥80) + Hot-Seat (65-79) — Wechsel realistisch in 2-6 Wochen">'
                f'Hot-Seat</div></div>'
            )
        if flagged_warm:
            hot_seat_stats += (
                f'<div class="stat-item">'
                f'<div class="stat-val" style="color:#f39c12">{flagged_warm}</div>'
                f'<div class="stat-lbl" title="Warm (45-64) — beobachten, Backstory aufbauen">'
                f'Warm</div></div>'
            )

    # SD-Counter: count SDs with their own dashboard
    sd_count = 0
    sd_registry_file = BASE / "data" / "sd_registry.json"
    if sd_registry_file.exists():
        try:
            sd_data = json.load(open(sd_registry_file))
            for sd in sd_data.get("sds", []):
                slug = re.sub(r"[^a-z0-9]+", "_", sd["name"].lower()).strip("_")
                if (DASHBOARD_DIR / f"{slug}_sd_network.html").exists():
                    sd_count += 1
        except Exception:
            pass

    sd_stat = ""
    if sd_count:
        sd_stat = (
            f'<div class="stat-item">'
            f'<div class="stat-val" style="color:#F40009">{sd_count}</div>'
            f'<div class="stat-lbl" title="Sportdirektoren mit eigenem Netzwerk-Dashboard — Hire-Decider">'
            f'Sportdirektoren</div></div>'
        )

    # ── Sprint F+G KPI stats ─────────────────────────────────────────
    # Decision-Maker count (from decision_makers.json — incl. Tier 1/2/3/NLZ)
    dm_count = 0
    dm_tier_text = ""
    dm_registry_path = BASE / "data" / "decision_makers.json"
    if dm_registry_path.exists():
        try:
            dm_data_kpi = json.load(open(dm_registry_path))
            dm_count = dm_data_kpi.get("_meta", {}).get("total_decision_makers", 0)
            tiers = dm_data_kpi.get("tiers", {}) or {}
            dm_tier_text = " · ".join(
                f"T{k}:{v}" if k in ("1", "2", "3") else f"NLZ:{v}"
                for k, v in sorted(tiers.items())
            )
        except Exception:
            pass
    dm_stat = ""
    if dm_count:
        dm_stat = (
            f'<div class="stat-item">'
            f'<div class="stat-val" style="color:#e76e3b">{dm_count}</div>'
            f'<div class="stat-lbl" title="Trainer-Hire-Decision-Maker (Tier 1/2/3/NLZ) — {dm_tier_text}">'
            f'Decision-Maker</div></div>'
        )

    # NLZ-Trainer count (from nlz_trainer_registry.json)
    nlz_count_kpi = 0
    nlz_tier_text = ""
    nlz_registry_path = BASE / "data" / "nlz_trainer_registry.json"
    if nlz_registry_path.exists():
        try:
            nlz_data_kpi = json.load(open(nlz_registry_path))
            nlz_count_kpi = nlz_data_kpi.get("_meta", {}).get("total_trainers", 0)
            tiers = nlz_data_kpi.get("_meta", {}).get("tiers", {}) or {}
            nlz_tier_text = " · ".join(f"{k}:{v}" for k, v in sorted(tiers.items()))
        except Exception:
            pass
    nlz_stat = ""
    if nlz_count_kpi:
        nlz_stat = (
            f'<div class="stat-item">'
            f'<div class="stat-val" style="color:#27ae60">{nlz_count_kpi}</div>'
            f'<div class="stat-lbl" title="NLZ-Trainer (U10-23) — Aufstiegs-Pipeline 2027+ · {nlz_tier_text}">'
            f'NLZ-Trainer</div></div>'
        )

    # Networks count (filesystem-driven)
    networks_dir = BASE / "data" / "networks"
    networks_count = len(list(networks_dir.glob("*.json"))) if networks_dir.exists() else 0
    networks_stat = ""
    if networks_count:
        networks_stat = (
            f'<div class="stat-item">'
            f'<div class="stat-val">{networks_count:,}</div>'
            f'<div class="stat-lbl" title="Trainer- + SD- + NLZ-Networks insgesamt im Datenbestand">'
            f'Networks</div></div>'
        )

    # ── Trainer-Total (Networks minus NLZ minus DMs) ─────────────────
    # Pragmatic count: alle Coach-Networks (Profi + Coachinside + Trainerstab + Historisch)
    # ohne NLZ-Cluster und ohne reine Decision-Maker.
    trainer_total = max(0, networks_count - nlz_count_kpi - dm_count)

    # Hires-Count (from hire_history.json)
    hires_count = 0
    hire_history_path = BASE / "data" / "hire_history.json"
    if hire_history_path.exists():
        try:
            hh_data = json.load(open(hire_history_path))
            hires_count = hh_data.get("_meta", {}).get("total_hires", 0)
        except Exception:
            pass
    hires_stat = ""
    if hires_count:
        hires_stat = (
            f'<div class="stat-item">'
            f'<div class="stat-val" style="color:#e67e22">{hires_count:,}</div>'
            f'<div class="stat-lbl" title="Dokumentierte Trainer-Hire-Events durch Decision-Maker">'
            f'Hires erfasst</div></div>'
        )

    # Build coaches check data for live TM comparison (BL1 + BL2 only)
    coaches_check = {}
    for c in bl1 + bl2:
        club_id = str(c.get("club_tm_id", ""))
        if club_id:
            coaches_check[club_id] = {
                "name": c["name"],
                "club": c["club"],
                "tm_id": c["tm_id"],
                "league": c["league"],
            }
    coaches_check_json = json.dumps(coaches_check, ensure_ascii=False)

    # Build optional BL3 section
    bl3_stat = f'<div class="stat-item"><div class="stat-val">{len(bl3)}</div><div class="stat-lbl">3. Liga</div></div>' if bl3 else ""
    bl3_section = ""
    if bl3:
        bl3_section = f"""<div class="section" id="bl3">
  <div class="section-hdr">
    <h2 class="section-title">3. Liga</h2>
    <span class="section-count">{len(bl3)}</span>
    <span class="section-line"></span>
  </div>
  <div class="table-hdr">
    <span></span><span class="sortable" onclick="sortRows(this,'name')">Trainer</span><span class="sortable" onclick="sortRows(this,'club')">Verein</span><span class="sortable" onclick="sortRows(this,'hotseat')" style="text-align:center" title="Hot-Seat-Score (0-100, Trainer-Wackelkandidat-Risiko)">Hot-Seat</span><span class="sortable" onclick="sortRows(this,'contacts')" style="text-align:right">Kontakte</span><span class="sortable" onclick="sortRows(this,'stations')" style="text-align:right">Stationen</span><span></span>
  </div>
{make_rows(bl3)}
</div>"""

    # Build historical coach sections
    hist_a_stat = f'<div class="stat-item"><div class="stat-val">{len(hist_a)}</div><div class="stat-lbl">Ehemalige</div></div>' if include_historical and hist_a else ""
    hist_a_section = ""
    if include_historical and hist_a:
        hist_a_section = f"""<div class="section" id="hist-a">
  <div class="section-hdr">
    <h2 class="section-title">Ehemalige BL-Cheftrainer</h2>
    <span class="section-count">{len(hist_a)}</span>
    <span class="section-line"></span>
  </div>
  <div class="table-hdr">
    <span></span><span class="sortable" onclick="sortRows(this,'name')">Trainer</span><span class="sortable" onclick="sortRows(this,'club')">Letzte BL-Station</span><span class="sortable" onclick="sortRows(this,'hotseat')" style="text-align:center">Hot-Seat</span><span class="sortable" onclick="sortRows(this,'contacts')" style="text-align:right">Kontakte</span><span class="sortable" onclick="sortRows(this,'stations')" style="text-align:right">Stationen</span><span></span>
  </div>
{make_rows(hist_a)}
</div>"""

    hist_c_section = ""
    if include_historical and hist_c:
        hist_c_section = f"""<div class="section" id="hist-c">
  <div class="section-hdr">
    <h2 class="section-title">Co-Trainer bei BL-Vereinen</h2>
    <span class="section-count">{len(hist_c)}</span>
    <span class="section-line"></span>
  </div>
  <div class="table-hdr">
    <span></span><span class="sortable" onclick="sortRows(this,'name')">Trainer</span><span class="sortable" onclick="sortRows(this,'club')">Letzte BL-Station</span><span class="sortable" onclick="sortRows(this,'hotseat')" style="text-align:center">Hot-Seat</span><span class="sortable" onclick="sortRows(this,'contacts')" style="text-align:right">Kontakte</span><span class="sortable" onclick="sortRows(this,'stations')" style="text-align:right">Stationen</span><span></span>
  </div>
{make_rows(hist_c)}
</div>"""

    hist_d_section = ""
    if include_historical and hist_d:
        hist_d_section = f"""<div class="section" id="hist-d">
  <div class="section-hdr">
    <h2 class="section-title">Historische BL-Trainer</h2>
    <span class="section-count">{len(hist_d)}</span>
    <span class="section-line"></span>
  </div>
  <div class="table-hdr">
    <span></span><span class="sortable" onclick="sortRows(this,'name')">Trainer</span><span class="sortable" onclick="sortRows(this,'club')">Letzte BL-Station</span><span class="sortable" onclick="sortRows(this,'hotseat')" style="text-align:center">Hot-Seat</span><span class="sortable" onclick="sortRows(this,'contacts')" style="text-align:right">Kontakte</span><span class="sortable" onclick="sortRows(this,'stations')" style="text-align:right">Stationen</span><span></span>
  </div>
{make_rows(hist_d)}
</div>"""

    extra_section = ""
    if extra:
        extra_section = f"""<div class="section" id="extra">
  <div class="section-hdr">
    <h2 class="section-title">Weitere Netzwerke</h2>
    <span class="section-count">{len(extra)}</span>
    <span class="section-line"></span>
  </div>
  <div class="table-hdr">
    <span></span><span class="sortable" onclick="sortRows(this,'name')">Trainer</span><span class="sortable" onclick="sortRows(this,'club')">Letzte Station</span><span class="sortable" onclick="sortRows(this,'hotseat')" style="text-align:center">Hot-Seat</span><span class="sortable" onclick="sortRows(this,'contacts')" style="text-align:right">Kontakte</span><span class="sortable" onclick="sortRows(this,'stations')" style="text-align:right">Stationen</span><span></span>
  </div>
{make_rows(extra)}
</div>"""

    # ── SD Section (Sportdirektoren — Hire-Decider) ──
    # D3-Fix (2026-05-11): Wenn DM-Section gerendert wird, dedupliziere SDs, die
    # auch als Decision-Maker erfasst sind (z.B. Krösche). DM-Section hat höhere
    # Daten-Tiefe (Hire-Patterns, Tier) → SD-Eintrag überspringen.
    dm_tm_ids_for_dedup = set()
    if include_decision_makers:
        dm_path_for_dedup = BASE / "data" / "decision_makers.json"
        if dm_path_for_dedup.exists():
            try:
                _dm = json.load(open(dm_path_for_dedup))
                dm_tm_ids_for_dedup = {dm["tm_id"] for dm in _dm.get("decision_makers", []) if dm.get("tm_id")}
            except Exception:
                pass

    sd_registry_file = BASE / "data" / "sd_registry.json"
    sds_with_dashboards = []
    if sd_registry_file.exists():
        sd_data = json.load(open(sd_registry_file))
        for sd in sd_data.get("sds", []):
            # D3: Skip SDs already rendered in DM-Section
            if sd.get("tm_id") in dm_tm_ids_for_dedup:
                continue
            # Use canonical slugify (umlaut transliteration) — naive regex
            # destroyed slugs like "Krösche" → "kr_sche" instead of "kroesche".
            sd_slug = slugify(sd["name"])
            dash = DASHBOARD_DIR / f"{sd_slug}_sd_network.html"
            if not dash.exists():
                continue
            # Lookup network stats — fall back to reading the SD's network JSON
            # directly because network_stats was only populated for head coaches.
            stats = network_stats.get(sd["tm_id"], {})
            if not stats:
                net_path = OUTPUT_DIR / f"{sd['tm_id']}.json"
                if net_path.exists():
                    try:
                        n = json.load(open(net_path))
                        stats = {
                            "contacts": n.get("total_contacts", 0),
                            "stations": len(n.get("stations", [])),
                        }
                    except Exception:
                        stats = {}
            sds_with_dashboards.append({
                **sd,
                "slug": sd_slug,
                "contacts": stats.get("contacts", 0),
                "stations": stats.get("stations", 0),
            })

    def make_sd_rows(sd_list: List[dict]) -> str:
        rows = []
        for s in sd_list:
            dashboard_file = f"dashboards/{s['slug']}_sd_network.html"
            tm_title = s.get("tm_title", "") or s.get("role", "")
            rows.append(f"""
        <div class="row-wrap" data-name="{s['name'].lower()}" data-club="{s['club_name'].lower()}" data-contacts="{s['contacts']}" data-stations="{s['stations']}" data-hotseat="0">
          <a href="{dashboard_file}" class="row">
            <div class="row-img"><span>&bull;</span></div>
            <div class="row-name">{s['name']}<span class="ci-pro" title="Sporting Director" style="color:#F40009;margin-left:6px">SD</span></div>
            <div class="row-club">{s['club_name']}</div>
            <div class="row-hotseat row-hotseat--empty" title="SDs sind nicht im Hot-Seat-Index erfasst (only head coaches)">—</div>
            <div class="row-stat">{s['contacts']}</div>
            <div class="row-stat">{s['stations']}</div>
            <div class="row-go">&rsaquo;</div>
          </a>
        </div>""")
        return "\n".join(rows)

    sd_section = ""
    if sds_with_dashboards:
        sds_with_dashboards.sort(key=lambda s: s["club_name"])
        sd_section = f"""<div class="section" id="sds">
  <div class="section-hdr">
    <h2 class="section-title">Sportdirektoren · Hire-Decider</h2>
    <span class="section-count">{len(sds_with_dashboards)}</span>
    <span class="section-line"></span>
  </div>
  <div class="table-hdr">
    <span></span><span class="sortable" onclick="sortRows(this,'name')">Sportdirektor</span><span class="sortable" onclick="sortRows(this,'club')">Verein</span><span style="text-align:center">—</span><span class="sortable" onclick="sortRows(this,'contacts')" style="text-align:right">Kontakte</span><span class="sortable" onclick="sortRows(this,'stations')" style="text-align:right">Stationen</span><span></span>
  </div>
{make_sd_rows(sds_with_dashboards)}
</div>"""

    # ── Decision-Makers Section (Sprint F — SD/GF Deep Coverage) ──
    dm_section = ""
    if include_decision_makers:
        dm_path = BASE / "data" / "decision_makers.json"
        hh_path = BASE / "data" / "hire_history.json"
        ap_path = BASE / "data" / "sd_agent_patterns.json"
        if dm_path.exists():
            dm_data = json.load(open(dm_path))
            hire_history = {}
            if hh_path.exists():
                hire_history = json.load(open(hh_path)).get("per_dm", {})
            agent_patterns = {}
            if ap_path.exists():
                agent_patterns = json.load(open(ap_path)).get("per_dm", {})

            tier_label = {"1": "Tier 1", "2": "Tier 2", "3": "Tier 3", "nlz": "NLZ"}
            tier_color = {"1": "#F40009", "2": "#e67e22", "3": "#9b59b6", "nlz": "#2ecc40"}

            dm_rows = []
            for dm in dm_data.get("decision_makers", []):
                tm_id = dm["tm_id"]
                tm_id_str = str(tm_id)
                hh = hire_history.get(tm_id_str) or {}
                hires_count = len(hh.get("hires") or [])
                ap = agent_patterns.get(tm_id_str) or {}
                top_agent = ""
                if ap.get("agent_relationships"):
                    a0 = ap["agent_relationships"][0]
                    top_agent = f"{a0['agent']} ({a0['hires']})"
                # Network link if SD-Network exists for this DM
                dm_slug = slugify(dm["name"])
                dash = DASHBOARD_DIR / f"{dm_slug}_sd_network.html"
                net_link = f"dashboards/{dm_slug}_sd_network.html" if dash.exists() else ""
                tier = dm["tier"]
                tier_lbl = tier_label.get(tier, tier)
                tier_clr = tier_color.get(tier, "#999")
                row_a_open = f'<a href="{net_link}" class="row">' if net_link else '<div class="row" style="cursor:default;opacity:0.55">'
                row_a_close = "</a>" if net_link else "</div>"
                go_arrow = '<div class="row-go">&rsaquo;</div>' if net_link else '<div class="row-go" style="opacity:0.3">—</div>'
                dm_rows.append(f"""
        <div class="row-wrap" data-name="{dm['name'].lower()}" data-club="{(dm.get('club_name') or '').lower()}" data-contacts="{hires_count}" data-stations="0" data-hotseat="0" data-tier="{tier}">
          {row_a_open}
            <div class="row-img"><span style="color:{tier_clr}">●</span></div>
            <div class="row-name">{dm['name']}<span class="ci-pro" title="{tier_lbl} — {dm.get('role','')}" style="color:{tier_clr};margin-left:6px;font-weight:600">{tier_lbl}</span></div>
            <div class="row-club">{dm.get('club_name','')}</div>
            <div class="row-stat" title="Dokumentierte Hire-Events">{hires_count}</div>
            <div class="row-stat" title="Top Agent (≥2 Hires)" style="font-size:11px;text-align:right;color:var(--text-dim)">{top_agent or '—'}</div>
            {go_arrow}
          {row_a_close}
        </div>""")

            tier_breakdown = dm_data.get("tiers", {})
            tier_summary = " · ".join(
                f"T{k}:{v}" if k in ("1","2","3") else f"NLZ:{v}"
                for k, v in sorted(tier_breakdown.items())
            )
            dm_section = f"""<div class="section" id="decision-makers">
  <div class="section-hdr">
    <h2 class="section-title">Decision-Makers · Hire-Patterns</h2>
    <span class="section-count">{len(dm_data.get('decision_makers', []))}</span>
    <span style="font-size:11px;color:var(--text-dim);margin-left:12px">{tier_summary}</span>
    <span class="section-line"></span>
  </div>
  <div class="table-hdr">
    <span></span><span class="sortable" onclick="sortRows(this,'name')">Decision-Maker</span><span class="sortable" onclick="sortRows(this,'club')">Verein</span><span class="sortable" onclick="sortRows(this,'contacts')" style="text-align:right">Hires</span><span style="text-align:right">Top-Agent</span><span></span>
  </div>
{''.join(dm_rows)}
</div>"""

    # ── NLZ Talente-Pipeline Section (Sprint G) ──
    nlz_section = ""
    if include_nlz:
        nlz_path = BASE / "data" / "nlz_trainer_registry.json"
        licenses_path = BASE / "data" / "coaching_licenses.json"
        if nlz_path.exists():
            nlz_data = json.load(open(nlz_path))
            # Build cohort lookup for star-badge (Aufstiegs-Indikator)
            lehrgang_lookup = {}
            if licenses_path.exists():
                try:
                    lic = json.load(open(licenses_path))
                    for course in lic.get("courses", []):
                        cid = course.get("id") or course.get("name", "LG")
                        for cohort_id, cohort in (course.get("cohorts") or {}).items():
                            year = cohort.get("year", "?")
                            for grad in cohort.get("graduates", []):
                                tmid = grad.get("tm_id")
                                if tmid:
                                    lehrgang_lookup[int(tmid)] = f"{cid} {year}"
                except Exception:
                    pass

            nlz_trainers = nlz_data.get("trainers", [])
            tier_priority = {"U23": 0, "U19": 1, "U14-17": 2, "U10-13": 3}
            tier_color = {"U23": "#3498db", "U19": "#27ae60", "U14-17": "#f39c12", "U10-13": "#95a5a6"}
            nlz_trainers.sort(key=lambda t: (tier_priority.get(t["tier"], 9),
                                              (t.get("parent_club") or "").lower(),
                                              t["name"].lower()))

            nlz_rows = []
            for t in nlz_trainers:
                tm_id = t["tm_id"]
                slug = slugify(t["name"])
                dash = DASHBOARD_DIR / f"{slug}_nlz_network.html"
                # Fallback: also accept profi-style dashboard if NLZ-specific not yet built
                fallback = DASHBOARD_DIR / f"{slug}_network.html"
                net_link = ""
                if dash.exists():
                    net_link = f"dashboards/{slug}_nlz_network.html"
                elif fallback.exists():
                    net_link = f"dashboards/{slug}_network.html"

                # Lehrgang star (LG 68+ = high-aufstiegs-relevanz)
                lg = lehrgang_lookup.get(tm_id, "")
                star = ""
                if lg:
                    m = re.search(r"\b(6[8-9]|7\d)\b", lg)
                    if m:
                        star = '<span title="DFB-Lehrgang ' + lg + ' — Aufstiegs-Kandidat" style="color:#f1c40f;margin-left:4px">★</span>'
                    else:
                        star = '<span title="DFB-Lehrgang ' + lg + '" style="color:var(--text-dim);margin-left:4px;font-size:10px">●</span>'

                tier = t["tier"]
                tier_clr = tier_color.get(tier, "#999")
                row_a_open = f'<a href="{net_link}" class="row">' if net_link else '<div class="row" style="cursor:default;opacity:0.55">'
                row_a_close = "</a>" if net_link else "</div>"
                go_arrow = '<div class="row-go">&rsaquo;</div>' if net_link else '<div class="row-go" style="opacity:0.3">—</div>'
                nlz_rows.append(f"""
        <div class="row-wrap nlz-row" data-name="{t['name'].lower()}" data-club="{(t.get('parent_club') or '').lower()}" data-tier="{tier}" data-contacts="0" data-stations="0" data-hotseat="0">
          {row_a_open}
            <div class="row-img"><span style="color:{tier_clr};font-weight:600;font-size:13px">{tier}</span></div>
            <div class="row-name">{t['name']}{star}</div>
            <div class="row-club">{t.get('parent_club') or t.get('club_name','')}</div>
            <div class="row-stat" style="text-align:left;color:var(--text-dim);font-size:11px">{t.get('club_name','')}</div>
            <div class="row-stat" style="text-align:right;color:var(--text-dim);font-size:11px">{lg or ''}</div>
            {go_arrow}
          {row_a_close}
        </div>""")

            tier_breakdown = nlz_data.get("_meta", {}).get("tiers", {})
            nlz_summary = " · ".join(f"{k}:{v}" for k, v in sorted(tier_breakdown.items()))
            nlz_section = f"""<div class="section" id="nlz-pipeline">
  <div class="section-hdr">
    <h2 class="section-title">Talente-Pipeline · NLZ-Trainer</h2>
    <span class="section-count">{len(nlz_trainers)}</span>
    <span style="font-size:11px;color:var(--text-dim);margin-left:12px">{nlz_summary}</span>
    <span class="section-line"></span>
  </div>
  <div class="table-hdr">
    <span></span><span class="sortable" onclick="sortRows(this,'name')">Trainer</span><span class="sortable" onclick="sortRows(this,'club')">Mutter-Verein</span><span style="text-align:left">Team</span><span style="text-align:right">Lehrgang</span><span></span>
  </div>
{''.join(nlz_rows)}
</div>"""

    # ── D2-Fix (2026-05-11): Hot-Seat Cross-Liga Top-5 ──
    # Aggregate the 5 highest hot-seat scores across BL1+BL2+BL3 (warm+hot-seat+critical, ≥45)
    # and render a leading block so 3.-Liga-Trainer with score ≥45 (e.g. Schwartz/Münster ~77)
    # are not buried below 1./2.-Liga tables.
    LEAGUE_BADGE = {"BL1": "BL1", "BL2": "BL2", "BL3": "BL3"}
    all_active = bl1 + bl2 + bl3
    hot_seat_ranked = []
    for c in all_active:
        hs = hot_seat_by_coach.get(c["tm_id"])
        if not hs:
            continue
        score = hs.get("score", 0) or 0
        status = hs.get("status", "ruhig")
        if score < 45 or status not in ("warm", "hot-seat", "critical"):
            continue
        hot_seat_ranked.append({
            "name": c["name"],
            "club": c["club"],
            "league": c.get("league", ""),
            "slug": c["slug"],
            "score": score,
            "status": status,
            "ppg": hs.get("ppg", 0.0),
            "winless": hs.get("winless_streak", 0),
            "position": hs.get("position", 0),
        })
    hot_seat_ranked.sort(key=lambda r: r["score"], reverse=True)
    top_hot_seat = hot_seat_ranked[:5]

    hot_seat_block = ""
    if top_hot_seat:
        rows_hs = []
        for r in top_hot_seat:
            cls_short = {"critical": "critical", "hot-seat": "hot", "warm": "warm"}.get(r["status"], "empty")
            badge = LEAGUE_BADGE.get(r["league"], r["league"])
            tooltip = (
                f"Hot-Seat {r['score']}/100 ({r['status']}) — "
                f"PPG {r['ppg']:.2f}, #{r['position']} {r['league']}, "
                f"winless {r['winless']}"
            )
            rows_hs.append(f"""
        <div class="row-wrap" data-name="{r['name'].lower()}" data-club="{r['club'].lower()}" data-hotseat="{r['score']}">
          <a href="dashboards/{r['slug']}_network.html" class="row">
            <div class="row-img"><span>&bull;</span></div>
            <div class="row-name">{r['name']}<span class="league-badge" title="{r['league']}">{badge}</span></div>
            <div class="row-club">{r['club']}</div>
            <div class="row-hotseat row-hotseat--{cls_short}" title="{tooltip}">{r['score']}</div>
            <div class="row-stat">&nbsp;</div>
            <div class="row-stat">&nbsp;</div>
            <div class="row-go">&rsaquo;</div>
          </a>
        </div>""")
        hot_seat_block = f"""<div class="section hot-seat-block" id="hot-seat-cross-liga">
  <div class="section-hdr">
    <h2 class="section-title">Hot-Seat · liga-übergreifend</h2>
    <span class="section-count">{len(top_hot_seat)}</span>
    <span class="section-line"></span>
  </div>
  <div class="table-hdr">
    <span></span><span>Trainer</span><span>Verein</span><span style="text-align:center" title="Hot-Seat-Score (0-100)">Hot-Seat</span><span></span><span></span><span></span>
  </div>
{''.join(rows_hs)}
</div>"""

    html = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Coach Network Explorer — {season_str}</title>
<meta property="og:title" content="Coach Network Explorer — Bundesliga {season_str}">
<meta property="og:description" content="Interaktive Trainer-Netzwerke der Bundesliga — {len(coaches)} Trainer, Kontakte, Karrierewege">
<meta property="og:type" content="website">
<meta property="og:url" content="https://coach-network-explorer.vercel.app">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=IBM+Plex+Sans:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/tokens.css">
<link rel="stylesheet" href="/assets/base.css">
<link rel="stylesheet" href="/assets/buttons.css">
<link rel="stylesheet" href="/assets/haptik.css">
<style>
/* Fallback tokens — also defined in /assets/tokens.css (for direct-open / offline) */
:root{{
  --bg:#0a0a0e;--surface-1:#111318;--surface-2:#1a1d24;
  --surface:var(--surface-1);--surface-h:var(--surface-2);
  --border:rgba(255,255,255,.08);--border-h:rgba(255,255,255,.16);
  --accent:#F40009;--accent-dim:#8b1a2b;--accent-glow:rgba(244,0,9,.12);
  --text:#d4d4d8;--text-2:#8b8d97;--text-3:#7c7e88;
  --radius-sm:3px;--radius-md:6px;--radius-lg:10px;
  --font-sans:'IBM Plex Sans',system-ui,sans-serif;
  --font-display:'Space Grotesk','IBM Plex Sans',sans-serif;
  --font-mono:'JetBrains Mono',ui-monospace,Menlo,monospace;
}}
*{{margin:0;padding:0;box-sizing:border-box}}
html{{font-size:15px}}
body{{background:var(--bg);color:var(--text);font-family:var(--font-sans);-webkit-font-smoothing:antialiased}}

/* ── Header ── */
.hdr{{padding:28px 0;border-bottom:1px solid var(--border);margin:0 40px}}
.hdr-inner{{display:flex;align-items:baseline;justify-content:space-between;gap:24px}}
.hdr h1{{font-family:'Space Grotesk',sans-serif;font-size:17px;font-weight:600;color:#fff;letter-spacing:-.3px}}
.hdr h1 b{{color:var(--accent);font-weight:700}}
.hdr-right{{font-size:12px;color:var(--text-3);text-align:right;line-height:1.5}}

/* ── Stats bar ── */
.stats{{display:flex;gap:32px;padding:24px 40px;border-bottom:1px solid var(--border)}}
.stat-item{{display:flex;flex-direction:column}}
.stat-val{{font-family:'Space Grotesk',sans-serif;font-size:22px;font-weight:700;color:#fff;letter-spacing:-.5px}}
.stat-lbl{{font-size:11px;color:var(--text-3);margin-top:2px;text-transform:uppercase;letter-spacing:.5px}}

/* ── Search ── */
.search-wrap{{padding:20px 40px 0}}
.search{{
  width:100%;max-width:360px;padding:9px 14px;
  background:var(--surface);border:1px solid var(--border);
  color:var(--text);font:inherit;font-size:13px;border-radius:6px;outline:none;
  transition:border-color .15s;
}}
.search:focus{{border-color:var(--accent)}}
.search::placeholder{{color:var(--text-3)}}

/* ── League sections ── */
.section{{padding:28px 40px 0}}
.section-hdr{{
  display:flex;align-items:center;gap:10px;
  margin-bottom:4px;padding-bottom:12px;
}}
.section-title{{
  font-family:'Space Grotesk',sans-serif;font-size:12px;font-weight:600;
  color:var(--accent);text-transform:uppercase;letter-spacing:1.5px;
  margin:0;line-height:inherit;display:inline-block;
}}
.section-count{{font-size:11px;color:var(--text-3)}}
.section-line{{flex:1;height:1px;background:var(--border)}}

/* D2: Hot-Seat Cross-Liga Top-Block (above league tables) */
.hot-seat-block .section-title{{color:#e74c3c}}
.league-badge{{
  display:inline-block;margin-left:8px;padding:1px 6px;
  font-family:'JetBrains Mono',monospace;font-size:9px;font-weight:600;
  color:var(--text-3);border:1px solid var(--border-h);border-radius:3px;
  letter-spacing:.5px;vertical-align:1px;
}}

/* ── Table header ── */
.table-hdr{{
  display:grid;grid-template-columns:44px 1fr 1fr 64px 64px 64px 32px;
  align-items:center;gap:0;
  padding:6px 16px;font-size:10px;color:var(--text-3);
  text-transform:uppercase;letter-spacing:.8px;
}}
/* Hot-Seat (col 4) center; Kontakte (5), Stationen (6) right */
.table-hdr span:nth-child(4){{text-align:center}}
.table-hdr span:nth-child(5),.table-hdr span:nth-child(6){{text-align:right}}
.sortable{{cursor:pointer;user-select:none;transition:color .15s}}
.sortable:hover{{color:var(--accent)}}
.sortable[data-dir="asc"]::after{{content:" \\2191";color:var(--accent)}}
.sortable[data-dir="desc"]::after{{content:" \\2193";color:var(--accent)}}

/* ── Row ── */
.row{{
  display:grid;grid-template-columns:44px 1fr 1fr 64px 64px 64px 32px;
  align-items:center;gap:0;
  padding:10px 16px;
  text-decoration:none;color:var(--text);
  border-bottom:1px solid var(--border);
  transition:background .1s;
}}
/* Hot-Seat cell — color-coded score badge */
.row-hotseat{{text-align:center;font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:600;letter-spacing:.05em}}
.row-hotseat--critical{{color:#e74c3c}}
.row-hotseat--hot{{color:#f39c12}}
.row-hotseat--warm{{color:#f1c40f}}
.row-hotseat--ruhig{{color:var(--text-3);font-weight:400}}
.row-hotseat--empty{{color:var(--text-3);opacity:.4}}
.row:last-child{{border-bottom:none}}
.row:hover{{background:var(--surface-h)}}
.row-img{{
  width:32px;height:32px;border-radius:50%;overflow:hidden;
  background:var(--surface);display:flex;align-items:center;justify-content:center;
  font-size:18px;color:var(--text-3);
}}
.row-img img{{width:100%;height:100%;object-fit:cover}}
.row-name{{font-weight:500;font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
/* Hot-Seat Badge (projectFIVE Trainer-Wackelkandidat-Score) */
.hot-seat-badge{{
  display:inline-block;margin-left:8px;padding:2px 7px;border-radius:3px;
  font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:600;
  letter-spacing:.05em;vertical-align:middle;cursor:help;
}}
.hot-seat-critical{{background:rgba(231,76,60,.18);color:#e74c3c;border:1px solid rgba(231,76,60,.4)}}
.hot-seat-hot-seat{{background:rgba(243,156,18,.18);color:#f39c12;border:1px solid rgba(243,156,18,.4)}}
.hot-seat-warm{{background:rgba(241,196,15,.12);color:#f1c40f;border:1px solid rgba(241,196,15,.3)}}
.row-club{{font-size:13px;color:var(--text-2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.row-stat{{font-family:'Space Grotesk',sans-serif;font-size:13px;color:var(--text-2);text-align:right;font-variant-numeric:tabular-nums}}
.row-go{{font-size:20px;color:var(--text-3);text-align:center;transition:color .15s}}
.row:hover .row-go{{color:var(--accent)}}
.row:hover .row-name{{color:#fff}}
.row-wrap{{position:relative}}
.row-refresh{{
  position:absolute;right:8px;top:50%;transform:translateY(-50%);
  background:none;border:1px solid var(--border);color:var(--text-3);
  width:26px;height:26px;border-radius:3px;cursor:pointer;font-size:14px;
  display:none;align-items:center;justify-content:center;transition:all .15s;z-index:2;
}}
.row-wrap:hover .row-refresh{{display:flex}}
.row-refresh:hover{{border-color:var(--accent);color:var(--accent)}}
.row-refresh.loading{{animation:spin .8s linear infinite;color:var(--accent);border-color:var(--accent)}}
.row-refresh.done{{color:#2ecc40;border-color:#2ecc40}}
.row-refresh.fail{{color:#e74c3c;border-color:#e74c3c}}
@keyframes spin{{to{{transform:translateY(-50%) rotate(360deg)}}}}

/* ── Update banner ── */
.update-banner{{
  margin:24px 40px 0;padding:14px 20px;
  background:var(--surface);border:1px solid var(--border);border-radius:6px;
  display:flex;align-items:center;gap:12px;font-size:12px;color:var(--text-2);
}}
.update-dot{{width:6px;height:6px;border-radius:50%;background:#3b82f6;flex-shrink:0}}
.update-btn{{
  background:none;border:1px solid var(--border);color:var(--text-2);
  padding:6px 14px;border-radius:4px;font-size:11px;cursor:pointer;
  font-family:inherit;white-space:nowrap;transition:all .15s;
}}
.update-btn:hover{{border-color:var(--accent);color:var(--accent)}}
.update-btn.loading{{color:var(--accent);border-color:var(--accent);opacity:.7;pointer-events:none}}

/* ── Coach check results ── */
.check-results{{
  margin:0 40px;padding:16px 20px;
  background:var(--surface);border:1px solid var(--border);border-top:none;
  border-radius:0 0 6px 6px;font-size:13px;color:var(--text-2);
}}
.check-ok{{color:#2ecc40;font-weight:500}}
.check-err{{color:var(--accent)}}
.check-item{{
  padding:10px 0;border-bottom:1px solid var(--border);
  display:flex;gap:16px;align-items:center;flex-wrap:wrap;
}}
.check-item:last-child{{border-bottom:none}}
.check-club{{font-weight:500;color:var(--text);min-width:180px}}
.check-old{{color:var(--accent);text-decoration:line-through;opacity:.7}}
.check-arrow{{color:var(--text-3);font-size:16px}}
.check-new{{color:#2ecc40;font-weight:500}}
.check-tag{{
  font-size:10px;padding:2px 8px;border-radius:3px;
  text-transform:uppercase;letter-spacing:.5px;font-weight:600;
}}
.check-tag.neu{{background:#2ecc4020;color:#2ecc40}}
.check-tag.weg{{background:#F4000920;color:var(--accent)}}
.check-tag.vakant{{background:#f39c1220;color:#f39c12}}
.check-close{{
  margin-top:12px;background:none;border:1px solid var(--border);
  color:var(--text-3);padding:6px 16px;border-radius:4px;font-size:11px;
  cursor:pointer;font-family:inherit;transition:all .15s;
}}
.check-close:hover{{border-color:var(--accent);color:var(--accent)}}

/* ── Footer ── */
.ftr{{padding:20px 40px;margin-top:32px;border-top:1px solid var(--border);font-size:11px;color:var(--text-3);display:flex;justify-content:space-between}}

@media(max-width:768px){{
  .hdr,.stats,.section,.search-wrap,.update-banner,.ftr{{padding-left:16px;padding-right:16px}}
  .hdr{{margin:0 16px}}
  /* Mobile: img | name | hot-seat | go (drop Verein, Kontakte, Stationen) */
  .table-hdr,.row{{grid-template-columns:36px 1fr 56px 32px;font-size:12px}}
  .row-club,.row-stat,.table-hdr span:nth-child(3),.table-hdr span:nth-child(5),.table-hdr span:nth-child(6){{display:none}}
  .stats{{gap:20px;flex-wrap:wrap}}
}}
</style>
</head>
<body>

<div class="hdr">
  <div class="hdr-inner">
    <h1><b>p5</b> Coach Network Explorer</h1>
    <div class="hdr-right"><a href="/clubs.html" class="btn btn--secondary btn--sm" style="margin-bottom:4px">Vereine →</a><br>Saison {season_str} · Stand {now}</div>
  </div>
</div>

<div class="stats">
  <div class="stat-item"><div class="stat-val">{trainer_total:,}</div><div class="stat-lbl" title="Profi-Trainer + Coachinside + Trainerstab + Historische (alle Coach-Networks ohne NLZ und ohne reine SD/Decision-Maker)">Trainer gesamt</div></div>
  <div class="stat-item"><div class="stat-val" style="color:#F40009">{dm_count}</div><div class="stat-lbl" title="Sportdirektoren / Decision-Maker — Tier 1/2/3/NLZ ({dm_tier_text})">Sportdirektoren</div></div>
  <div class="stat-item"><div class="stat-val" style="color:#27ae60">{nlz_count_kpi}</div><div class="stat-lbl" title="NLZ-Trainer (U10-U23) — Aufstiegs-Pipeline 2027+ · {nlz_tier_text}">NLZ-Trainer</div></div>
  <div class="stat-item"><div class="stat-val">{total_contacts:,}</div><div class="stat-lbl" title="Aggregierte Beziehungs-Kontakte über alle Networks">Kontakte gesamt</div></div>
</div>

<div class="search-wrap">
  <input type="text" class="search" placeholder="Trainer oder Verein filtern..." id="q" oninput="filter()">
</div>

<div class="update-banner">
  <div class="update-dot"></div>
  <span>Datenstand: <strong>{datetime.now().strftime('%d.%m.%Y')}</strong></span>
  <button class="update-btn" id="check-btn" onclick="checkCoaches()">Trainerwechsel prüfen</button>
</div>
<div id="check-results" class="check-results" style="display:none"></div>

{hot_seat_block}

<div class="section" id="bl1">
  <div class="section-hdr">
    <h2 class="section-title">1. Bundesliga</h2>
    <span class="section-count">{len(bl1)}</span>
    <span class="section-line"></span>
  </div>
  <div class="table-hdr">
    <span></span><span class="sortable" onclick="sortRows(this,'name')">Trainer</span><span class="sortable" onclick="sortRows(this,'club')">Verein</span><span class="sortable" onclick="sortRows(this,'hotseat')" style="text-align:center" title="Hot-Seat-Score (0-100, Trainer-Wackelkandidat-Risiko)">Hot-Seat</span><span class="sortable" onclick="sortRows(this,'contacts')" style="text-align:right">Kontakte</span><span class="sortable" onclick="sortRows(this,'stations')" style="text-align:right">Stationen</span><span></span>
  </div>
{make_rows(bl1)}
</div>

<div class="section" id="bl2">
  <div class="section-hdr">
    <h2 class="section-title">2. Bundesliga</h2>
    <span class="section-count">{len(bl2)}</span>
    <span class="section-line"></span>
  </div>
  <div class="table-hdr">
    <span></span><span class="sortable" onclick="sortRows(this,'name')">Trainer</span><span class="sortable" onclick="sortRows(this,'club')">Verein</span><span class="sortable" onclick="sortRows(this,'hotseat')" style="text-align:center" title="Hot-Seat-Score (0-100, Trainer-Wackelkandidat-Risiko)">Hot-Seat</span><span class="sortable" onclick="sortRows(this,'contacts')" style="text-align:right">Kontakte</span><span class="sortable" onclick="sortRows(this,'stations')" style="text-align:right">Stationen</span><span></span>
  </div>
{make_rows(bl2)}
</div>

{bl3_section}

{hist_a_section}

{hist_c_section}

{hist_d_section}

{sd_section}

{dm_section}

{nlz_section}

{extra_section}

<div class="ftr">
  <span>projectFIVE &middot; Daten: Transfermarkt</span>
  <span>{now_full}</span>
</div>

<script>
const COACHES={coaches_check_json};

function filter(){{
  const q=document.getElementById('q').value.toLowerCase();
  document.querySelectorAll('.row-wrap').forEach(r=>{{
    const show=r.dataset.name.includes(q)||r.dataset.club.includes(q);
    r.style.display=show?'':'none';
  }});
  document.querySelectorAll('.section').forEach(s=>{{
    const vis=[...s.querySelectorAll('.row-wrap')].filter(r=>r.style.display!=='none');
    s.style.display=vis.length?'':'none';
  }});
}}

function sortRows(el, key){{
  const section=el.closest('.section');
  if(!section) return;
  const rows=[...section.querySelectorAll('.row-wrap')];
  if(!rows.length) return;
  const asc=el.dataset.dir!=='asc';
  el.dataset.dir=asc?'asc':'desc';
  section.querySelectorAll('.sortable').forEach(s=>{{if(s!==el) s.dataset.dir='';}});
  rows.sort((a,b)=>{{
    let va,vb;
    if(key==='name'){{va=a.dataset.name;vb=b.dataset.name;return asc?va.localeCompare(vb):vb.localeCompare(va);}}
    if(key==='club'){{va=a.dataset.club;vb=b.dataset.club;return asc?va.localeCompare(vb):vb.localeCompare(va);}}
    if(key==='contacts'){{va=+a.dataset.contacts;vb=+b.dataset.contacts;return asc?va-vb:vb-va;}}
    if(key==='stations'){{va=+a.dataset.stations;vb=+b.dataset.stations;return asc?va-vb:vb-va;}}
    if(key==='hotseat'){{va=+a.dataset.hotseat||0;vb=+b.dataset.hotseat||0;return asc?va-vb:vb-va;}}
  }});
  const parent=rows[0].parentNode;
  rows.forEach(r=>parent.appendChild(r));
}}

function normalize(s){{ return (s||'').trim().toLowerCase().replace(/\\s+/g,' '); }}
function closeCheck(){{ document.getElementById('check-results').style.display='none'; }}

async function checkCoaches(){{
  const btn=document.getElementById('check-btn');
  const box=document.getElementById('check-results');
  btn.classList.add('loading');
  btn.textContent='Prüfe TM…';
  box.style.display='none';

  try{{
    const r=await fetch('/api/check-coaches');
    if(!r.ok) throw new Error('HTTP '+r.status);
    const data=await r.json();

    if(data.errors && data.errors.length>0 && (data.L1||[]).length===0 && (data.L2||[]).length===0){{
      throw new Error(data.errors.map(e=>e.league+': '+e.message).join(', '));
    }}

    const tmCoaches=[...(data.L1||[]),...(data.L2||[])];
    const changes=[];
    const seenClubIds=new Set();

    for(const tm of tmCoaches){{
      const cid=String(tm.club_tm_id);
      seenClubIds.add(cid);
      const cur=COACHES[cid];
      if(!cur){{
        changes.push({{type:'new',club:tm.club,name:tm.name,tag:'neu'}});
      }} else if(normalize(cur.name)!==normalize(tm.name)){{
        changes.push({{type:'changed',club:tm.club||cur.club,oldName:cur.name,newName:tm.name,tag:'neu'}});
      }}
    }}

    for(const [cid,info] of Object.entries(COACHES)){{
      if(!seenClubIds.has(cid)){{
        changes.push({{type:'missing',club:info.club,name:info.name,tag:'weg'}});
      }}
    }}

    let html='';
    if(changes.length===0){{
      html='<div class="check-ok">Alle '+tmCoaches.length+' Trainer aktuell — keine Wechsel detected.</div>';
    }} else {{
      html='<div style="margin-bottom:8px;color:var(--text)"><strong>'+changes.length+' Änderung'+(changes.length>1?'en':'')+'</strong> gefunden:</div>';
      for(const c of changes){{
        if(c.type==='changed'){{
          html+='<div class="check-item"><span class="check-club">'+c.club+'</span><span class="check-old">'+c.oldName+'</span><span class="check-arrow">&rarr;</span><span class="check-new">'+c.newName+'</span><span class="check-tag neu">'+c.tag+'</span></div>';
        }} else if(c.type==='new'){{
          html+='<div class="check-item"><span class="check-club">'+c.club+'</span><span class="check-new">'+c.name+'</span><span class="check-tag neu">neu</span></div>';
        }} else if(c.type==='missing'){{
          html+='<div class="check-item"><span class="check-club">'+c.club+'</span><span class="check-old">'+c.name+'</span><span class="check-tag weg">nicht gefunden</span></div>';
        }}
      }}
      html+='<div style="margin-top:12px;font-size:11px;color:var(--text-3)">Rebuild: <code>bash run_mvp.sh</code></div>';
    }}
    if(data.errors && data.errors.length>0){{
      html+='<div style="margin-top:8px" class="check-err">Warnungen: '+data.errors.map(e=>e.league+' '+e.message).join(', ')+'</div>';
    }}
    html+='<button class="check-close" onclick="closeCheck()">Schließen</button>';
    box.innerHTML=html;
    box.style.display='block';

  }}catch(e){{
    const _is404=e.message&&e.message.includes('404');
    const _errHtml=_is404
      ?'<div style="color:#f0a500;font-weight:500">TM von Vercel-Servern nicht erreichbar</div><div style="margin-top:4px;font-size:11px;color:var(--text-3)">Serverless-IPs werden von TM blockiert — lokal prüfen: <code>python execution/check_coach_changes.py</code></div>'
      :'<div class="check-err">Fehler: '+e.message+'</div><div style="margin-top:4px;font-size:11px;color:var(--text-3)">Alternativ: <code>python execution/check_coach_changes.py</code></div>';
    box.innerHTML=_errHtml+'<button class="check-close" onclick="closeCheck()">Schließen</button>';
    box.style.display='block';
  }}

  btn.classList.remove('loading');
  btn.textContent='Trainerwechsel prüfen';
}}

const API='http://localhost:8000';
async function refreshClub(clubId,btn){{
  btn.classList.add('loading');
  btn.classList.remove('done','fail');
  try{{
    const r=await fetch(API+'/refresh/'+clubId,{{method:'POST'}});
    const d=await r.json();
    btn.classList.remove('loading');
    if(d.success){{
      btn.classList.add('done');
      btn.innerHTML='&#x2713;';
      setTimeout(()=>{{btn.innerHTML='&#x21bb;';btn.classList.remove('done')}},3000);
    }}else{{
      btn.classList.add('fail');
      btn.title='Fehler: '+JSON.stringify(d.steps);
      setTimeout(()=>{{btn.classList.remove('fail')}},5000);
    }}
  }}catch(e){{
    btn.classList.remove('loading');
    btn.classList.add('fail');
    btn.title='API nicht erreichbar';
    setTimeout(()=>{{btn.classList.remove('fail')}},5000);
  }}
}}
</script>
</body>
</html>"""

    INDEX_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(INDEX_OUTPUT, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n  \u2713 Index: {INDEX_OUTPUT} ({len(bl1)} BL1, {len(bl2)} BL2)")


def main():
    parser = argparse.ArgumentParser(description="Generate all BL coach dashboards")
    parser.add_argument("--leagues", nargs="+", default=["BL1", "BL2"],
                        help="Leagues to include (default: BL1 BL2). Add BL3 for 3. Liga.")
    parser.add_argument("--season", type=int, default=2025)
    parser.add_argument("--skip-networks", action="store_true")
    parser.add_argument("--skip-index", action="store_true")
    parser.add_argument("--only", type=int, nargs="+", help="Only specific tm_ids")
    parser.add_argument("--delta", action="store_true",
                        help="Only rebuild coaches whose staff file is newer than network JSON")
    parser.add_argument("--include-historical", action="store_true",
                        help="Include 150+ historical coaches from data/historical_coaches_candidates.json")
    parser.add_argument("--all-networks", action="store_true",
                        help="Include ALL coaches that have a network JSON (catches unlisted dashboards)")
    parser.add_argument("--include-decision-makers", action="store_true",
                        help="Render Decision-Maker section (Sprint F: SD/GF Deep Coverage)")
    parser.add_argument("--include-nlz", action="store_true",
                        help="Render Talente-Pipeline section (Sprint G: NLZ-Trainer Cluster)")
    args = parser.parse_args()

    print(f"\n{'='*70}")
    print(f"  Coach Network Explorer \u2014 Batch Generator")
    print(f"  Leagues: {', '.join(args.leagues)} | Season: {format_season(args.season)}")
    if args.include_historical:
        print(f"  Include: Historical Coaches ✓")
    print(f"{'='*70}")

    club_registry = load_club_registry()
    coaches = get_all_head_coaches(club_registry, args.leagues, args.season)

    # Add historical coaches if requested
    if args.include_historical:
        historical_coaches = load_historical_coaches(include_categories=["A", "D"])
        print(f"\n  Loaded {len(historical_coaches)} historical coaches")
        coaches.extend(historical_coaches)

    # Add all remaining network coaches
    if args.all_networks:
        existing_ids = {c["tm_id"] for c in coaches}
        extra = load_all_network_coaches(existing_ids)
        print(f"\n  Loaded {len(extra)} additional coaches from network JSONs")
        coaches.extend(extra)

    if args.only:
        coaches = [c for c in coaches if c["tm_id"] in args.only]

    print(f"\n  Found {len(coaches)} total coaches ({len([c for c in coaches if not c.get('is_historical')])} active, {len([c for c in coaches if c.get('is_historical')])} historical)")

    if not args.skip_networks:
        # Preload ALL profiles once (the key optimization)
        profiles = preload_all_profiles()
        profile_index = build_profile_index(profiles)

        success, failed = 0, 0
        t_total = time.time()

        for i, coach in enumerate(coaches, 1):
            print(f"\n  [{i}/{len(coaches)}] {coach['name']} ({coach['club']}, {coach['league']})")

            if not coach["has_profile"]:
                print(f"    \u26a0 No profile \u2014 skipping")
                failed += 1
                continue

            # Delta mode: skip if network JSON is newer than all relevant staff files
            if args.delta:
                network_path = OUTPUT_DIR / f"{coach['tm_id']}.json"
                if network_path.exists():
                    net_mtime = network_path.stat().st_mtime
                    # Check if any staff file for this coach's clubs is newer
                    needs_rebuild = False
                    try:
                        with open(PROFILES_DIR / f"{coach['tm_id']}.json") as pf:
                            profile_data = json.load(pf)
                        for entry in profile_data.get("career_history", []):
                            cid = entry.get("club_tm_id")
                            if cid:
                                staff_path = STAFF_DIR / f"{cid}.json"
                                if staff_path.exists() and staff_path.stat().st_mtime > net_mtime:
                                    needs_rebuild = True
                                    break
                    except Exception:
                        needs_rebuild = True

                    if not needs_rebuild:
                        print(f"    \u2714 Up to date (delta)")
                        success += 1
                        continue

            try:
                network = build_network(coach["tm_id"], profiles, profile_index)
                if not network:
                    failed += 1
                    continue

                network = generate_background_summaries(network)

                # Build drill-down sub-networks
                drilldown = build_drilldown(network, profiles, profile_index)

                # Strip internal fields before serialization
                strip_internal_fields(network)

                # Save network JSON
                OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                network_path = OUTPUT_DIR / f"{coach['tm_id']}.json"
                with open(network_path, "w", encoding="utf-8") as f:
                    json.dump(network, f, ensure_ascii=False, indent=2)

                # Generate dashboard HTML (with drilldown)
                dashboard_path = DASHBOARD_DIR / f"{coach['slug']}_network.html"
                generate_dashboard(network, dashboard_path, drilldown=drilldown)

                success += 1

            except Exception as e:
                print(f"    \u2717 Error: {e}")
                import traceback
                traceback.print_exc()
                failed += 1

        elapsed = time.time() - t_total
        print(f"\n  {'─'*50}")
        print(f"  Results: {success} \u2713  {failed} \u2717  of {len(coaches)} coaches")
        print(f"  Total time: {elapsed:.0f}s ({elapsed/max(1,len(coaches)):.1f}s per coach)")

    if not args.skip_index:
        for c in coaches:
            # Historical coaches don't need a dashboard file (they're placeholders)
            # Existing dashboards are marked as having them
            if c.get("is_historical"):
                c["has_dashboard"] = True  # Always include historical coaches in index
            else:
                c["has_dashboard"] = (DASHBOARD_DIR / f"{c['slug']}_network.html").exists()

        coaches_with_dashboards = [c for c in coaches if c.get("has_dashboard")]
        if not coaches_with_dashboards and not args.skip_networks:
            coaches_with_dashboards = coaches

        generate_index_page(coaches_with_dashboards, args.season,
                            include_historical=args.include_historical,
                            include_decision_makers=args.include_decision_makers,
                            include_nlz=args.include_nlz)

    print(f"\n  Done! Open output/index.html")


if __name__ == "__main__":
    main()
