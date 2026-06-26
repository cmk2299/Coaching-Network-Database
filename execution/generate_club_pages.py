#!/usr/bin/env python3
"""
Generate Club Pages — Dashboard für alle Clubs und deren Kader/Trainerstab

Generiert:
1. output/clubs.html — Index-Seite mit Clubs gruppiert nach Liga
2. output/clubs/{slug}.html — Einzelseite pro Club mit Trainerstab und Kader

Datenquellen:
- data/club_registry.json — Club-Metadaten und Ligen
- data/staff/{tm_id}.json — Trainerstab und Management
- data/squads/{tm_id}_{season}.json — Kader pro Saison
- data/networks/{tm_id}.json — Existierende Coach-Netzwerk-Dashboards

Usage:
    python generate_club_pages.py                      # BL1 + BL2 + BL3
    python generate_club_pages.py --all                # Alle Clubs inklusive International
    python generate_club_pages.py --skip-index         # Nur Einzelseiten
    python generate_club_pages.py --clubs 2036 631     # Spezifische Clubs

Output:
    output/clubs.html                           — Club-Selektionsseite
    output/clubs/{slug}.html                    — Einzelne Club-Seiten
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Canonical slug rule for dashboard cross-links
sys.path.insert(0, str(Path(__file__).parent))
from lib.normalization import slugify as _dashboard_slugify  # noqa: E402
from datetime import datetime

BASE = Path(__file__).parent.parent
DATA_DIR = BASE / "data"
STAFF_DIR = DATA_DIR / "staff"
SQUADS_DIR = DATA_DIR / "squads"
NETWORKS_DIR = DATA_DIR / "networks"
OUTPUT_DIR = BASE / "output"
CLUBS_OUTPUT_DIR = OUTPUT_DIR / "clubs"

CURRENT_SEASON = 2025
CURRENT_SEASON_DISPLAY = "2025/2026"

# Design tokens (matching coach index)
COLORS = {
    "bg": "#0a0a0e",
    "surface": "#1a1a1e",
    "surface_h": "#252529",
    "border": "#2a2a2e",
    "border_h": "#353539",
    "accent": "#F40009",
    "accent_dim": "#8b1a2b",
    "text": "#e8e8ec",
    "text_dim": "#888",
    "text_3": "#565658",
}

SECTION_ORDER = [
    "Trainerstab",
    "Management",
    "Medizinische Abteilung",
    "Scouting",
    "Analyse",
    "Jugend",
    "Vorstand",
    "Sonstiges",
]

LEAGUE_LABELS = {
    "BL1": "1. Bundesliga",
    "BL2": "2. Bundesliga",
    "BL3": "3. Liga",
}

LEAGUE_ORDER = ["BL1", "BL2", "BL3"]


def load_club_registry() -> Dict[int, dict]:
    """Load club registry and return mapping of tm_id -> club data."""
    registry_path = DATA_DIR / "club_registry.json"
    if not registry_path.exists():
        print("ERROR: club_registry.json not found")
        return {}

    with open(registry_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    clubs = {}
    for club in data.get("clubs", []):
        clubs[club["tm_id"]] = club
    return clubs


def build_dashboard_index() -> Dict[int, str]:
    """Build mapping of tm_id -> network dashboard slug for NET badge linking.

    Suffixes appended downstream:
      - {slug}_network.html (head coaches)
      - {slug}_sd_network.html (SDs / DMs)
      - {slug}_nlz_network.html (NLZ trainers)

    We store the slug WITH suffix (e.g. "andreas_bornemann_sd") when needed,
    so the caller can append "_network.html" uniformly.
    """
    # Load DM tm_ids for type detection
    dm_tm_ids = set()
    dm_path = NETWORKS_DIR.parent / "decision_makers.json"
    if dm_path.exists():
        try:
            dm_data = json.load(open(dm_path))
            dm_tm_ids = {d["tm_id"] for d in dm_data.get("decision_makers", [])}
        except Exception:
            pass

    dashboards_dir = NETWORKS_DIR.parent.parent / "output" / "dashboards"
    index = {}
    if NETWORKS_DIR.exists():
        for nf in NETWORKS_DIR.glob("*.json"):
            try:
                with open(nf, "r", encoding="utf-8") as f:
                    net = json.load(f)
                tm_id = int(nf.stem)
                slug = net.get("slug") or _dashboard_slugify(net.get("center", ""))
                coach_dash = dashboards_dir / f"{slug}_network.html"
                sd_dash = dashboards_dir / f"{slug}_sd_network.html"
                nlz_dash = dashboards_dir / f"{slug}_nlz_network.html"
                if tm_id in dm_tm_ids and sd_dash.exists():
                    index[tm_id] = f"{slug}_sd"
                elif coach_dash.exists():
                    index[tm_id] = slug
                elif sd_dash.exists():
                    index[tm_id] = f"{slug}_sd"
                elif nlz_dash.exists():
                    index[tm_id] = f"{slug}_nlz"
                else:
                    index[tm_id] = slug
            except Exception:
                pass
    return index


def get_german_league_clubs(registry: Dict[int, dict], season: int = CURRENT_SEASON) -> List[Tuple[int, dict]]:
    """Get all clubs in German leagues (BL1, BL2, BL3) for current season."""
    german_leagues = {"BL1", "BL2", "BL3"}
    clubs = []

    for tm_id, club in registry.items():
        season_key = f"{season}/{season + 1}"
        leagues = club.get("leagues", {}).get(season_key, [])

        # Keep only German league clubs
        for league in leagues:
            if league in german_leagues:
                clubs.append((tm_id, club))
                break

    return sorted(clubs, key=lambda x: (
        LEAGUE_ORDER.index(x[1].get("leagues", {}).get(CURRENT_SEASON_DISPLAY, ["BL1"])[0])
        if x[1].get("leagues", {}).get(CURRENT_SEASON_DISPLAY, ["BL1"])[0] in LEAGUE_ORDER else 999,
        x[1].get("name", "")
    ))


def slugify(name: str) -> str:
    """Convert name to URL-friendly slug."""
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    return re.sub(r'-+', '-', slug)


def load_staff(tm_id: int) -> List[dict]:
    """Load staff data for a club, grouped by section."""
    staff_path = STAFF_DIR / f"{tm_id}.json"
    if not staff_path.exists():
        return []

    try:
        with open(staff_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("staff", [])
    except Exception as e:
        print(f"  ⚠ Error loading staff for {tm_id}: {e}")
        return []


def load_squad(tm_id: int, season: int = CURRENT_SEASON) -> List[dict]:
    """Load squad data for a club in a given season."""
    squad_path = SQUADS_DIR / f"{tm_id}_{season}.json"
    if not squad_path.exists():
        return []

    try:
        with open(squad_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("players", [])
    except Exception as e:
        print(f"  ⚠ Error loading squad for {tm_id}/{season}: {e}")
        return []


def group_staff_by_section(staff: List[dict]) -> Dict[str, List[dict]]:
    """Group staff by section, in defined order."""
    grouped = {}
    for person in staff:
        section = person.get("section", "Sonstiges")
        if section not in grouped:
            grouped[section] = []
        grouped[section].append(person)

    # Sort by SECTION_ORDER
    ordered = {}
    for section in SECTION_ORDER:
        if section in grouped:
            ordered[section] = grouped[section]

    # Add any remaining sections not in the predefined order
    for section in grouped:
        if section not in ordered:
            ordered[section] = grouped[section]

    return ordered


def get_league_for_club(club: dict, season: int = CURRENT_SEASON) -> str:
    """Get the primary league for a club in a given season."""
    season_key = f"{season}/{season + 1}"
    leagues = club.get("leagues", {}).get(season_key, [])
    return leagues[0] if leagues else "Unknown"


def escape_html(text: str) -> str:
    """Escape HTML special characters."""
    if not isinstance(text, str):
        return ""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def render_club_index(clubs: List[Tuple[int, dict]]) -> str:
    """Render the clubs.html index page."""
    html_parts = []
    html_parts.append("""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Club Finder — Trainer und Kader</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
/* Fallback tokens — also defined in /assets/tokens.css */
:root{
  --bg:#0a0a0e;--surface-1:#111318;--surface-2:#1a1d24;
  --surface:var(--surface-1);--surface-h:var(--surface-2);
  --border:rgba(255,255,255,.08);--accent:#F40009;--accent-glow:rgba(244,0,9,.12);
  --text:#d4d4d8;--text-2:#8b8d97;--text-3:#7c7e88;
  --radius-sm:3px;--radius-md:6px;
  --font-sans:'IBM Plex Sans',system-ui,sans-serif;
  --font-mono:'JetBrains Mono',ui-monospace,Menlo,monospace;
}
*{margin:0;padding:0;box-sizing:border-box}
html{font-size:15px}
body{background:var(--bg);color:var(--text);font-family:var(--font-sans);-webkit-font-smoothing:antialiased}

.hdr{padding:28px 40px;border-bottom:1px solid var(--border)}
.hdr h1{font-size:20px;font-weight:600;letter-spacing:-.5px}
.hdr p{font-size:13px;color:var(--text-3);margin-top:6px}

.nav{padding:16px 40px;border-bottom:1px solid var(--border);display:flex;gap:16px;align-items:center}
.nav a{font-size:13px;color:var(--accent);text-decoration:none;transition:color .15s;padding:6px 0}
.nav a:hover{color:#fff}

.search-wrap{padding:20px 40px 0}
.search{
  width:100%;max-width:360px;padding:10px 14px;
  background:var(--surface);border:1px solid var(--border);
  color:var(--text);font:inherit;font-size:13px;border-radius:6px;
  outline:none;transition:border-color .15s;
}
.search:focus{border-color:var(--accent)}

.league-section{padding:28px 40px 0}
.league-hdr{
  display:flex;align-items:center;gap:12px;margin-bottom:16px;padding-bottom:12px;
}
.league-title{font-size:13px;font-weight:600;color:var(--accent);text-transform:uppercase;letter-spacing:1px}
.league-count{font-size:12px;color:var(--text-3)}
.league-line{flex:1;height:1px;background:var(--border)}

.clubs-table{width:100%}
.club-row{
  display:grid;grid-template-columns:1fr 120px 100px 1fr 40px;
  align-items:center;gap:16px;
  padding:14px;border-bottom:1px solid var(--border);
  text-decoration:none;color:var(--text);
  transition:background .1s;
}
.club-row:hover{background:var(--surface-h)}
.club-name{font-weight:500;font-size:14px}
.club-league{
  font-size:11px;padding:4px 8px;border-radius:3px;
  background:var(--surface);color:var(--text-3);
  text-transform:uppercase;letter-spacing:.5px;white-space:nowrap;
}
.club-stat{font-size:12px;color:var(--text-2);text-align:right}
.club-go{font-size:16px;color:var(--text-3);text-align:center;transition:color .15s}
.club-row:hover .club-go{color:var(--accent)}

.ftr{padding:20px 40px;margin-top:32px;border-top:1px solid var(--border);font-size:11px;color:var(--text-3)}

@media(max-width:768px){
  .hdr,.nav,.search-wrap,.league-section,.ftr{padding-left:16px;padding-right:16px}
  .club-row{grid-template-columns:1fr 40px;gap:8px}
  .club-league,.club-stat{display:none}
}
</style>
</head>
<body>

<div class="hdr">
  <h1>Club Finder</h1>
  <p>Trainer, Trainerstab und Kader der deutschen Bundesliga</p>
</div>

<div class="nav">
  <a href="/">← Trainer-Netzwerke</a>
</div>

<div class="search-wrap">
  <input type="text" class="search" placeholder="Club oder Trainer suchen..." id="q" oninput="filter()">
</div>

""")

    # Group clubs by league
    clubs_by_league = {}
    for tm_id, club in clubs:
        league = get_league_for_club(club)
        if league not in clubs_by_league:
            clubs_by_league[league] = []
        clubs_by_league[league].append((tm_id, club))

    # Render sections in order
    for league in LEAGUE_ORDER:
        if league not in clubs_by_league:
            continue

        league_clubs = clubs_by_league[league]
        league_label = LEAGUE_LABELS.get(league, league)

        html_parts.append(f"""<div class="league-section">
  <div class="league-hdr">
    <div class="league-title">{escape_html(league_label)}</div>
    <div class="league-count">{len(league_clubs)} Clubs</div>
    <div class="league-line"></div>
  </div>
  <table class="clubs-table">
""")

        for tm_id, club in sorted(league_clubs, key=lambda x: x[1].get("name", "")):
            club_name = club.get("name", "Unknown")
            club_slug = club.get("slug", slugify(club_name))
            staff = load_staff(tm_id)
            staff_count = len(staff)

            # Find head coach in staff
            head_coach = None
            for person in staff:
                if person.get("role") == "head_coach":
                    head_coach = person.get("name")
                    break

            # Only show trainer label when matched — no "Kein Trainer" ghost text.
            head_coach_text = f"Trainer: {escape_html(head_coach)}" if head_coach else ""

            html_parts.append(f"""    <tr class="club-row" onclick="window.location='clubs/{club_slug}.html'">
      <td class="club-name">{escape_html(club_name)}</td>
      <td class="club-league">{league}</td>
      <td class="club-stat">{staff_count} Stab</td>
      <td class="club-stat">{head_coach_text}</td>
      <td class="club-go">→</td>
    </tr>
""")

        html_parts.append("""  </table>
</div>

""")

    html_parts.append("""<div class="ftr">
  <div>Coach Network Explorer — Club Pages</div>
  <div>Aktualisiert: """ + datetime.now().strftime("%d.%m.%Y") + """</div>
</div>

<script>
function filter() {
  const q = document.getElementById('q').value.toLowerCase();
  const rows = document.querySelectorAll('.club-row');
  rows.forEach(row => {
    const text = row.textContent.toLowerCase();
    row.style.display = text.includes(q) ? '' : 'none';
  });
}
</script>

</body>
</html>
""")

    return "".join(html_parts)


def render_club_page(club: dict, staff: List[dict], squad: List[dict],
                     dashboard_index: Dict[int, str]) -> str:
    """Render a single club page (clubs/{slug}.html)."""
    club_name = club.get("name", "Unknown")
    club_slug = club.get("slug", "unknown")
    tm_id = club.get("tm_id", 0)
    league = get_league_for_club(club)
    league_label = LEAGUE_LABELS.get(league, league)

    grouped_staff = group_staff_by_section(staff)

    html_parts = []
    html_parts.append(f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{escape_html(club_name)} — Club Profil</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
/* Fallback tokens */
:root{{
  --bg:#0a0a0e;--surface-1:#111318;--surface-2:#1a1d24;
  --surface:var(--surface-1);--surface-h:var(--surface-2);
  --border:rgba(255,255,255,.08);--accent:#F40009;--accent-glow:rgba(244,0,9,.12);
  --text:#d4d4d8;--text-2:#8b8d97;--text-3:#7c7e88;
  --radius-sm:3px;--radius-md:6px;
  --font-sans:'IBM Plex Sans',system-ui,sans-serif;
  --font-mono:'JetBrains Mono',ui-monospace,Menlo,monospace;
}}
*{{margin:0;padding:0;box-sizing:border-box}}
html{{font-size:15px}}
body{{background:var(--bg);color:var(--text);font-family:var(--font-sans);-webkit-font-smoothing:antialiased}}

.hdr{{padding:28px 40px;border-bottom:1px solid var(--border)}}
.hdr-inner{{display:flex;align-items:baseline;justify-content:space-between;gap:24px}}
.hdr h1{{font-size:24px;font-weight:600;letter-spacing:-.5px}}
.hdr-meta{{display:flex;gap:16px;align-items:center;font-size:13px;color:var(--text-3)}}
.league-badge{{
  font-size:11px;padding:6px 10px;border-radius:3px;
  background:var(--surface);color:var(--text-3);
  text-transform:uppercase;letter-spacing:.5px;
}}

.nav{{padding:16px 40px;border-bottom:1px solid var(--border);display:flex;gap:16px}}
.nav a{{font-size:13px;color:var(--accent);text-decoration:none;transition:color .15s}}
.nav a:hover{{color:#fff}}

.content{{padding:28px 40px}}

.section{{margin-bottom:48px}}
.section-title{{
  font-size:14px;font-weight:600;color:var(--accent);
  text-transform:uppercase;letter-spacing:1px;
  margin-bottom:20px;padding-bottom:10px;border-bottom:1px solid var(--border);
}}

.subsection{{margin-bottom:24px}}
.subsection-title{{
  font-size:12px;font-weight:500;color:var(--text-2);
  text-transform:uppercase;letter-spacing:.8px;
  margin-bottom:12px;padding:8px 12px;background:var(--surface);border-radius:4px;
}}

.staff-table, .squad-table{{width:100%;border-collapse:collapse}}
.staff-table th, .squad-table th{{
  font-size:11px;font-weight:500;color:var(--text-3);
  text-transform:uppercase;letter-spacing:.6px;
  text-align:left;padding:10px 12px;border-bottom:1px solid var(--border);
  background:var(--surface);
}}
.staff-table td, .squad-table td{{
  padding:12px;border-bottom:1px solid var(--border);
  font-size:13px;
}}
.staff-table tr:hover, .squad-table tr:hover{{background:var(--surface-h)}}

.person-name{{font-weight:500}}
.person-role{{color:var(--text-2);font-size:12px}}
.person-nat{{color:var(--text-3);font-size:12px}}

.badges{{display:flex;gap:6px;align-items:center}}
.badge{{
  font-size:10px;padding:3px 7px;border-radius:2px;
  background:var(--surface);color:var(--accent);
  font-family:'JetBrains Mono',monospace;font-weight:500;
  text-transform:uppercase;letter-spacing:.4px;cursor:pointer;
  transition:all .15s;
}}
.badge:hover{{background:var(--accent);color:var(--bg)}}
.badge.net{{background:var(--accent);color:var(--bg)}}

.tm-link{{
  color:var(--accent);text-decoration:none;
  font-size:12px;transition:color .15s;
}}
.tm-link:hover{{color:#fff}}

.empty-message{{color:var(--text-3);font-size:13px;padding:20px;text-align:center;background:var(--surface);border-radius:4px}}

.ftr{{padding:20px 40px;margin-top:48px;border-top:1px solid var(--border);font-size:11px;color:var(--text-3)}}

@media(max-width:768px){{
  .hdr,.nav,.content,.ftr{{padding-left:16px;padding-right:16px}}
  .hdr-inner{{flex-direction:column;align-items:flex-start}}
  .staff-table th, .squad-table th{{font-size:10px}}
  .staff-table td, .squad-table td{{padding:8px;font-size:12px}}
}}
</style>
</head>
<body>

<div class="hdr">
  <div class="hdr-inner">
    <h1>{escape_html(club_name)}</h1>
    <div class="hdr-meta">
      <div class="league-badge">{league}</div>
      <div>{CURRENT_SEASON_DISPLAY}</div>
    </div>
  </div>
</div>

<div class="nav">
  <a href="../clubs.html">← Zurück zum Club-Index</a>
  <a href="../">← Trainer-Netzwerke</a>
</div>

<div class="content">
""")

    # Trainerstab section
    if grouped_staff:
        html_parts.append("""
<div class="section">
  <div class="section-title">Trainerstab & Management</div>
""")

        for section in SECTION_ORDER:
            if section not in grouped_staff:
                continue

            section_staff = grouped_staff[section]
            html_parts.append(f"""
  <div class="subsection">
    <div class="subsection-title">{escape_html(section)}</div>
    <table class="staff-table">
      <thead>
        <tr>
          <th style="width:30%">Name</th>
          <th style="width:25%">Funktion</th>
          <th style="width:25%">Nationalität</th>
          <th style="width:20%">Profile</th>
        </tr>
      </thead>
      <tbody>
""")

            for person in sorted(section_staff, key=lambda x: x.get("name", "")):
                name = person.get("name", "")
                role = person.get("role", "")
                tm_url = person.get("tm_url", "")
                person_tm_id = person.get("tm_id", 0)

                # Format role display
                role_display = role.replace("_", " ").title() if role else "—"

                # Get nationality (not available in staff data, so use placeholder)
                nat = "—"

                # Check if this person has a network dashboard
                has_network = person_tm_id in dashboard_index

                badges_html = ""
                if tm_url:
                    badges_html += f'<a href="{tm_url}" class="tm-link" target="_blank">TM</a>'
                if has_network:
                    dashboard_slug = dashboard_index[person_tm_id]
                    badges_html += f'<a href="../dashboards/{dashboard_slug}_network.html" class="badge net">NET</a>'

                if badges_html:
                    badges_html = f'<div class="badges">{badges_html}</div>'
                else:
                    badges_html = "<div>—</div>"

                html_parts.append(f"""
        <tr>
          <td><div class="person-name">{escape_html(name)}</div></td>
          <td><div class="person-role">{escape_html(role_display)}</div></td>
          <td><div class="person-nat">{escape_html(nat)}</div></td>
          <td>{badges_html}</td>
        </tr>
""")

            html_parts.append("""
      </tbody>
    </table>
  </div>
""")

        html_parts.append("""
</div>
""")
    else:
        html_parts.append("""
<div class="section">
  <div class="section-title">Trainerstab & Management</div>
  <div class="empty-message">Keine Trainerstab-Daten verfügbar</div>
</div>
""")

    # Squad section
    if squad:
        html_parts.append(f"""
<div class="section">
  <div class="section-title">Kader {CURRENT_SEASON_DISPLAY}</div>
  <table class="squad-table">
    <thead>
      <tr>
        <th style="width:5%">#</th>
        <th style="width:30%">Name</th>
        <th style="width:15%">Position</th>
        <th style="width:10%">Alter</th>
        <th style="width:25%">Nationalität</th>
        <th style="width:15%">Profil</th>
      </tr>
    </thead>
    <tbody>
""")

        for player in sorted(squad, key=lambda x: x.get("shirt_number") or 999):
            shirt_no = player.get("shirt_number") or "—"
            name = player.get("name", "")
            position = player.get("position", "—")
            age = player.get("age") or "—"
            nationality = player.get("nationality", "—")
            tm_url = player.get("tm_url", "")

            tm_link = f'<a href="{tm_url}" class="tm-link" target="_blank">TM</a>' if tm_url else "—"

            html_parts.append(f"""
      <tr>
        <td><div class="person-name" style="font-family:'JetBrains Mono',monospace">{shirt_no}</div></td>
        <td><div class="person-name">{escape_html(name)}</div></td>
        <td><div class="person-role">{escape_html(position)}</div></td>
        <td><div class="person-role">{escape_html(str(age))}</div></td>
        <td><div class="person-nat">{escape_html(nationality)}</div></td>
        <td>{tm_link}</td>
      </tr>
""")

        html_parts.append("""
    </tbody>
  </table>
</div>
""")
    else:
        html_parts.append(f"""
<div class="section">
  <div class="section-title">Kader {CURRENT_SEASON_DISPLAY}</div>
  <div class="empty-message">Keine Kader-Daten verfügbar</div>
</div>
""")

    html_parts.append(f"""
</div>

<div class="ftr">
  <div>Club Profil — Coach Network Explorer</div>
  <div>Aktualisiert: {datetime.now().strftime("%d.%m.%Y")}</div>
</div>

</body>
</html>
""")

    return "".join(html_parts)


def main():
    parser = argparse.ArgumentParser(description="Generate club index and individual club pages")
    parser.add_argument("--all", action="store_true",
                        help="Include international clubs (default: German leagues only)")
    parser.add_argument("--skip-index", action="store_true",
                        help="Skip generating index.html (only generate club pages)")
    parser.add_argument("--clubs", type=int, nargs="+",
                        help="Generate specific club pages by tm_id")
    args = parser.parse_args()

    print("[Club Pages Generator]")

    # Load data
    print("  Loading club registry...")
    registry = load_club_registry()
    if not registry:
        print("ERROR: No clubs loaded")
        return

    print("  Building dashboard index...")
    dashboard_index = build_dashboard_index()

    # Determine clubs to process
    if args.clubs:
        print(f"  Processing {len(args.clubs)} specific clubs...")
        clubs_to_process = [(tm_id, registry[tm_id]) for tm_id in args.clubs if tm_id in registry]
    else:
        print("  Getting German league clubs...")
        clubs_to_process = get_german_league_clubs(registry, CURRENT_SEASON)

    if not clubs_to_process:
        print("WARNING: No clubs to process")
        return

    print(f"  Found {len(clubs_to_process)} clubs")

    # Create output directory
    CLUBS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Generate club pages
    print("  Generating individual club pages...")
    for tm_id, club in clubs_to_process:
        club_name = club.get("name", "Unknown")
        club_slug = club.get("slug", slugify(club_name))

        staff = load_staff(tm_id)
        squad = load_squad(tm_id, CURRENT_SEASON)

        html = render_club_page(club, staff, squad, dashboard_index)
        output_path = CLUBS_OUTPUT_DIR / f"{club_slug}.html"
        output_path.write_text(html, encoding="utf-8")
        print(f"    ✓ {club_name}")

    # Generate index page
    if not args.skip_index:
        print("  Generating club index...")
        index_html = render_club_index(clubs_to_process)
        index_output = OUTPUT_DIR / "clubs.html"
        index_output.write_text(index_html, encoding="utf-8")
        print(f"    ✓ clubs.html ({len(clubs_to_process)} clubs)")

    print("  Done!")


if __name__ == "__main__":
    main()
