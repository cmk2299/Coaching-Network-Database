#!/usr/bin/env python3
"""
generate_daily_digest.py — Sprint I (Berater-CRM-Workflow)

Generates output/daily.html. The page is a static shell that pulls all
data from window.localStorage on DOMContentLoaded. Optionally embeds
Hot-Seat-Alerts seed data from data/hot_seat_scores.json so the
"Hot-Seat-Alerts in deiner Pipeline" section can show live scores
without an extra fetch.

Idempotent: just rewrites output/daily.html each run.

Routing: handled by output/vercel.json (rewrite /daily → /daily.html)
"""

from datetime import datetime
from pathlib import Path
import json

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "output" / "daily.html"
HOT_SEAT_PATH = BASE / "data" / "hot_seat_scores.json"


def load_hot_seat_seed() -> dict:
    """Return {tm_id: {name, club, score, tier}} for fast client-side lookup."""
    if not HOT_SEAT_PATH.exists():
        return {}
    try:
        data = json.loads(HOT_SEAT_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    out = {}
    for s in data.get("scores", []):
        tm = s.get("coach_tm_id")
        if not tm:
            continue
        out[str(tm)] = {
            "name": s.get("coach_name", ""),
            "club": s.get("club_name", ""),
            "score": s.get("score", 0),
            "tier": s.get("tier", ""),
        }
    return out


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Daily-Digest · projectFIVE Berater-Workflow</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=IBM+Plex+Sans:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/tokens.css">
<link rel="stylesheet" href="/assets/base.css">
<link rel="stylesheet" href="/assets/buttons.css">
<link rel="stylesheet" href="/assets/haptik.css">
<link rel="stylesheet" href="/assets/workflow.css">
<style>
  body {{ background: var(--bg); color: var(--text); font-family: var(--font-sans); margin: 0; }}
  a {{ color: var(--accent); text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .topbar {{
    display: flex; gap: 16px; align-items: center;
    padding: 16px 40px; border-bottom: 1px solid var(--border);
  }}
  .topbar a.brand {{ font-family: var(--font-display); font-weight: 600; color: var(--text); }}
  .topbar a.brand b {{ color: var(--accent); }}
  .topbar nav {{ display: flex; gap: 12px; margin-left: auto; font-size: 13px; }}
  .filter-toggle {{
    margin-left: auto; font-size: 12px; color: var(--text-2);
  }}
  .filter-toggle select {{
    background: var(--surface-2); color: var(--text);
    border: 1px solid var(--border); border-radius: var(--radius-sm);
    padding: 4px 8px; font: inherit; font-size: 12px;
  }}
</style>
</head>
<body>

<div class="topbar">
  <a class="brand" href="/index.html"><b>p5</b> Network Explorer</a>
  <nav>
    <a href="/index.html">Trainer</a>
    <a href="/clubs.html">Vereine</a>
    <a href="/daily.html" aria-current="page" style="color:var(--accent)">Daily-Digest</a>
  </nav>
</div>

<main class="daily-wrap">
  <header class="daily-hdr">
    <h1>Daily-Digest</h1>
    <span class="daily-date" id="daily-date"></span>
  </header>

  <section class="daily-section">
    <h2 id="pinned-h">Angepinnt</h2>
    <ul class="daily-list" id="pinned-list"></ul>
  </section>

  <section class="daily-section">
    <h2 id="reminders-h">Fällige Reminder</h2>
    <ul class="daily-list" id="reminders-list"></ul>
  </section>

  <section class="daily-section">
    <h2 id="activity-h">Pipeline-Aktivität (7 Tage)</h2>
    <ul class="daily-list" id="activity-list"></ul>
  </section>

  <section class="daily-section">
    <h2 id="hotseat-h">Hot-Seat-Alerts (Pipeline)</h2>
    <ul class="daily-list" id="hotseat-list"></ul>
  </section>

  <section class="daily-section">
    <h2>Pipeline-Stats</h2>
    <div class="daily-stats" id="pipeline-stats"></div>
  </section>

  <div class="workflow-export">
    <button id="export-workflow" type="button">Daten exportieren</button>
    <input type="file" id="import-workflow-file" accept=".json" hidden />
    <button id="import-workflow" type="button">Daten importieren</button>
    <span style="margin-left:auto;font-size:11px;color:var(--text-3);font-family:var(--font-mono)">
      localStorage · privat · nicht synchronisiert
    </span>
  </div>
</main>

<script src="/assets/workflow.js" defer></script>
<script>
// Hot-Seat seed (server-side embedded). May be empty if data file missing.
const HOT_SEAT_SEED = __HOT_SEAT_PLACEHOLDER__;

function fmtDate(iso) {{ return new Date(iso).toLocaleString('de-DE'); }}
function fmtDay(iso)  {{ return new Date(iso).toLocaleDateString('de-DE'); }}
function ago(iso) {{
  const d = (Date.now() - new Date(iso).getTime()) / 86400000;
  if (d < 1) return 'heute';
  if (d < 2) return 'gestern';
  return `vor ${{Math.floor(d)}} Tagen`;
}}

function dashLink(tmId) {{
  // No reliable slug→tm_id reverse — fall back to /index.html with hash.
  // Index page wires up clicks via tm_id when available.
  return `/index.html#tm${{tmId}}`;
}}

function render() {{
  if (!window.PF_WORKFLOW) {{
    setTimeout(render, 80);
    return;
  }}
  const s = window.PF_WORKFLOW.loadStore();

  document.getElementById('daily-date').textContent =
    new Date().toLocaleDateString('de-DE', {{ weekday: 'long', day: '2-digit', month: '2-digit', year: 'numeric' }});

  // Pinned
  const pinned = Object.entries(s.pipeline).filter(([_, e]) => e.pinned);
  const pinnedList = document.getElementById('pinned-list');
  document.getElementById('pinned-h').textContent = `Angepinnt (${{pinned.length}})`;
  if (pinned.length === 0) {{
    pinnedList.innerHTML = '<li class="daily-empty">Keine angepinnten Kontakte. Auf einem Dashboard via Pin-Toggle hinzufügen.</li>';
  }} else {{
    pinnedList.innerHTML = pinned.map(([tmId, e]) => {{
      const lastNote = (s.notes[tmId] || []).slice(-1)[0];
      const stage = (window.PF_WORKFLOW.STAGES.find(x => x.id === e.stage) || {{}}).label || '—';
      return `<li>
        <span><a href="${{dashLink(tmId)}}">tm:${{tmId}}</a> · ${{stage}}</span>
        <span class="meta">${{lastNote ? 'Notiz ' + ago(lastNote.at) : 'keine Notizen'}}</span>
        <span class="meta">${{e.stage_changed_at ? 'Stage ' + ago(e.stage_changed_at) : ''}}</span>
      </li>`;
    }}).join('');
  }}

  // Due reminders
  const due = window.PF_WORKFLOW.getDueReminders();
  document.getElementById('reminders-h').textContent = `Fällige Reminder (${{due.length}})`;
  const remList = document.getElementById('reminders-list');
  if (due.length === 0) {{
    remList.innerHTML = '<li class="daily-empty">Keine fälligen Reminder.</li>';
  }} else {{
    remList.innerHTML = due.map(r => `<li>
      <span><a href="${{dashLink(r.tm_id)}}">tm:${{r.tm_id}}</a> · ${{r.text.replace(/[<>]/g, '')}}</span>
      <span class="meta">${{fmtDay(r.at)}}</span>
      <span><button class="reminder-done" data-id="${{r.id}}" title="erledigt">erledigt</button></span>
    </li>`).join('');
  }}

  // 7-day activity
  const cutoff = Date.now() - 7 * 86400000;
  const recent = Object.entries(s.pipeline)
    .filter(([_, e]) => e.stage_changed_at && new Date(e.stage_changed_at).getTime() >= cutoff)
    .sort((a, b) => new Date(b[1].stage_changed_at) - new Date(a[1].stage_changed_at));
  const actList = document.getElementById('activity-list');
  document.getElementById('activity-h').textContent = `Pipeline-Aktivität (${{recent.length}}, 7 Tage)`;
  if (recent.length === 0) {{
    actList.innerHTML = '<li class="daily-empty">Keine Stage-Änderungen in den letzten 7 Tagen.</li>';
  }} else {{
    actList.innerHTML = recent.map(([tmId, e]) => {{
      const stage = (window.PF_WORKFLOW.STAGES.find(x => x.id === e.stage) || {{}}).label || '—';
      return `<li>
        <span><a href="${{dashLink(tmId)}}">tm:${{tmId}}</a> &rarr; ${{stage}}</span>
        <span class="meta">${{ago(e.stage_changed_at)}}</span>
        <span class="meta">${{fmtDate(e.stage_changed_at)}}</span>
      </li>`;
    }}).join('');
  }}

  // Hot-Seat-Alerts on pipeline contacts (score > 70)
  const hotList = document.getElementById('hotseat-list');
  const inPipeline = Object.keys(s.pipeline);
  const hotPick = inPipeline
    .map(tmId => ({{ tmId, hs: HOT_SEAT_SEED[String(tmId)] }}))
    .filter(x => x.hs && x.hs.score >= 70)
    .sort((a, b) => b.hs.score - a.hs.score);
  document.getElementById('hotseat-h').textContent = `Hot-Seat-Alerts (${{hotPick.length}})`;
  if (hotPick.length === 0) {{
    hotList.innerHTML = '<li class="daily-empty">Keine Hot-Seat-Alerts in deiner Pipeline (Score >= 70).</li>';
  }} else {{
    hotList.innerHTML = hotPick.map(({{ tmId, hs }}) => `<li>
      <span><a href="${{dashLink(tmId)}}">${{hs.name}}</a></span>
      <span class="meta">${{hs.club}}</span>
      <span class="meta">Score ${{hs.score}} (${{hs.tier}})</span>
    </li>`).join('');
  }}

  // Stats grid
  const counts = {{ watching: 0, contacted: 0, in_talks: 0, mandate: 0, placed: 0, passed: 0 }};
  Object.values(s.pipeline).forEach(e => {{ if (counts.hasOwnProperty(e.stage)) counts[e.stage]++; }});
  const labels = {{ watching: 'BEO', contacted: 'KON', in_talks: 'GES', mandate: 'MAN', placed: 'PLA', passed: 'ARC' }};
  const stats = document.getElementById('pipeline-stats');
  stats.innerHTML = Object.keys(counts).map(k => `<div class="daily-stat stage-${{k}}">
    <div class="v">${{counts[k]}}</div><div class="k">${{labels[k]}}</div>
  </div>`).join('');
}}

document.addEventListener('DOMContentLoaded', () => {{
  render();
  // Re-render on store change
  window.addEventListener('pf-workflow-changed', render);
  window.addEventListener('storage', render);

  // Reminder done — handled globally by workflow.js, plus local re-render
  document.addEventListener('click', (e) => {{
    if (e.target.classList && e.target.classList.contains('reminder-done')) {{
      // workflow.js completes the reminder; we re-render here
      setTimeout(render, 50);
    }}
  }});

  document.getElementById('export-workflow').addEventListener('click', () => window.PF_WORKFLOW.exportData());
  document.getElementById('import-workflow').addEventListener('click', () => document.getElementById('import-workflow-file').click());
  document.getElementById('import-workflow-file').addEventListener('change', (e) => {{
    const file = e.target.files && e.target.files[0];
    if (file) window.PF_WORKFLOW.importData(file);
  }});
}});
</script>
</body>
</html>
"""


def main() -> int:
    seed = load_hot_seat_seed()
    seed_json = json.dumps(seed, ensure_ascii=False, separators=(",", ":"))
    # HTML_TEMPLATE uses doubled braces ({{ }}) as escape syntax — collapse to
    # single braces so the emitted JS/CSS is valid. The collapse pass MUST
    # happen BEFORE placeholder substitution so it never touches `}}` inside
    # seed_json (which legitimately ends with `}}` when the outer object's
    # final entry is itself an object: ..."tier":null}} ).
    html = HTML_TEMPLATE.replace("{{", "{").replace("}}", "}")
    html = html.replace("__HOT_SEAT_PLACEHOLDER__", seed_json)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"  ✓ Wrote {OUT.relative_to(BASE)}  ({len(html):,} bytes)")
    print(f"    Hot-Seat seed entries: {len(seed)}")
    print(f"    Generated: {datetime.now().isoformat(timespec='seconds')}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
