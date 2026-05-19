# Directive: Sprint I — Berater-CRM-Workflow (Daily-Driver)

**Trigger-Phrase für Claude Code:** "Build berater CRM" oder "/crm-workflow"

**Bezugnehmend auf:**
- USP #4 *Berater-Workflow* (Stakeholder-Pivot 2026-05-04: "CRM-light, Pipeline-Stages, Daily-Driver statt read-only")
- Sprint F: SD/GF Deep Coverage (Voraussetzung — Pipeline-Stages brauchen Demand-Side-Tiefe)
- Sprint G: NLZ-Cluster (optional — Watchlist nutzbar für Aufstiegs-Kandidaten)

**Mission-Wert:** Bisheriges Tool ist *read-only Reference*. Berater nutzen es, schließen es, nutzen woanders ihr CRM. Ziel: Tool wird **erste App, die der Berater morgens öffnet**, weil persönliche Daten + Aufgaben + Notes + Reminders integriert sind. Erst dann zahlen Stakeholder die 20k EUR/Jahr für *uns*, nicht für coachinsider.

**Aufwand:** ~8-12h (MVP localStorage + Pipeline-Stages + Notes + Reminders + Daily-Digest + Export). Cloud-Sync später als Sprint J.

**Risiko:** Mittel — UX-kritisch (Daily-Driver-Anspruch), aber technisch stra­ight­for­ward (kein Backend für MVP).

---

## Voraussetzungen

```bash
# Sprint F muss durch sein, damit Decision-Maker als Pipeline-Targets verfügbar sind
ls data/decision_makers.json data/hire_history.json
# Persons-Master + Networks Standard-Dataset
ls data/persons_master.json
```

---

## Architekturentscheidung: localStorage statt Backend (MVP)

**Pro localStorage-MVP:**
- Sofortige Implementierung (kein Auth, kein Hosting, kein DB)
- 100% privat — Berater-Notizen verlassen ihren Browser nie
- Keine Datenschutz-/DSGVO-Komplikationen für Beta-Phase
- Stakeholder kann sofort testen ohne Account-Setup

**Contra:**
- Nicht Multi-Device (Berater nutzt Laptop + iPad → Daten getrennt)
- Bei Browser-Cache-Clear: alles weg
- Kein Team-Sharing innerhalb projectFIVE-Beraterteam

**Entscheidung:** localStorage als MVP, Cloud-Sync als Sprint J nach Stakeholder-Validation. Export/Import als JSON ist im MVP enthalten — Berater kann manuell zwischen Devices syncen.

**Storage-Schema:** `localStorage["pf_workflow_v1"] = JSON.stringify({...})`

```js
// Daten-Modell
{
  version: 1,
  user: { name: "", initials: "" },        // optional, zur Eigen-Identifikation
  pipeline: {
    "<tm_id>": {
      stage: "watching" | "contacted" | "in_talks" | "mandate" | "placed" | "passed",
      added_at: "2026-05-09T10:00:00Z",
      stage_changed_at: "...",
      pinned: false
    }
  },
  notes: {
    "<tm_id>": [
      { id: "n1", at: "...", text: "Markdown content", tags: ["call","2027"] }
    ]
  },
  reminders: [
    { id: "r1", tm_id: "12345", at: "2026-06-15T09:00:00Z", text: "Folge-Anruf", done: false }
  ],
  watchlist_filters: {  // gespeicherte Filter-Kombinationen
    "<filter_id>": { name: "U19 Aufsteiger 2027", query: { tier: "U19", lehrgang_min: "LG 68" } }
  }
}
```

---

## Sprint-Phasen

### Phase 1 — Pipeline-Stage-System

**Ziel:** Pro Trainer/SD/NLZ-Trainer Stage-Tag setzen. Sichtbar im Index + Detail-Panel.

**Stages:**

| Stage | Label | Farbe | Beschreibung |
|-------|-------|-------|--------------|
| `watching` | Beobachtung | Grau | Auf Radar, kein Kontakt |
| `contacted` | Kontaktiert | Blau | Erste Mail/Anruf raus |
| `in_talks` | Im Gespräch | Gelb | Aktive Gespräche, Mandat in Vorbereitung |
| `mandate` | Mandat | Orange | Mandatsvertrag unterschrieben |
| `placed` | Vermittelt | Grün | Trainer/SD wurde vermittelt (Erfolg) |
| `passed` | Abgeschlossen | Dunkelgrau | Nicht mehr aktiv (z.B. anderswo unterschrieben, archiviert) |

**Neue UI-Komponente:** Stage-Picker im Detail-Panel jedes Dashboards.

```html
<!-- Im Detail-Panel zwischen Meta und Background-Summary -->
<div class="workflow-pipeline">
  <label>Pipeline-Status</label>
  <select class="pipeline-stage" data-tm-id="12345">
    <option value="">— nicht in Pipeline —</option>
    <option value="watching">Beobachtung</option>
    <option value="contacted">Kontaktiert</option>
    <option value="in_talks">Im Gespräch</option>
    <option value="mandate">Mandat</option>
    <option value="placed">Vermittelt</option>
    <option value="passed">Abgeschlossen</option>
  </select>
  <label class="pin-toggle">
    <input type="checkbox" class="pipeline-pin" data-tm-id="12345"> 
    📌 Anpinnen (zeigt im Daily-Digest)
  </label>
</div>
```

**JavaScript (in `output/assets/workflow.js`, neu):**

```js
const STORE_KEY = "pf_workflow_v1";

function loadStore() {
  try { return JSON.parse(localStorage.getItem(STORE_KEY)) || defaultStore(); }
  catch { return defaultStore(); }
}
function saveStore(s) { localStorage.setItem(STORE_KEY, JSON.stringify(s)); }
function defaultStore() {
  return { version: 1, user: {}, pipeline: {}, notes: {}, reminders: [], watchlist_filters: {} };
}

function setStage(tmId, stage) {
  const s = loadStore();
  if (!stage) { delete s.pipeline[tmId]; }
  else {
    s.pipeline[tmId] = s.pipeline[tmId] || { added_at: new Date().toISOString(), pinned: false };
    s.pipeline[tmId].stage = stage;
    s.pipeline[tmId].stage_changed_at = new Date().toISOString();
  }
  saveStore(s);
  refreshPipelineUI();
}

function togglePin(tmId) {
  const s = loadStore();
  if (!s.pipeline[tmId]) return;
  s.pipeline[tmId].pinned = !s.pipeline[tmId].pinned;
  saveStore(s);
  refreshPipelineUI();
}

document.addEventListener("change", (e) => {
  if (e.target.classList.contains("pipeline-stage")) {
    setStage(e.target.dataset.tmId, e.target.value);
  }
  if (e.target.classList.contains("pipeline-pin")) {
    togglePin(e.target.dataset.tmId);
  }
});

function refreshPipelineUI() {
  const s = loadStore();
  document.querySelectorAll(".pipeline-stage").forEach(sel => {
    const e = s.pipeline[sel.dataset.tmId];
    sel.value = e?.stage || "";
  });
  document.querySelectorAll(".pipeline-pin").forEach(cb => {
    const e = s.pipeline[cb.dataset.tmId];
    cb.checked = !!(e?.pinned);
  });
}
window.addEventListener("DOMContentLoaded", refreshPipelineUI);
```

**Index-Page Erweiterung:** Neue Spalte „Status" mit Stage-Badge (CSS-color per Stage).

```html
<!-- Pro Index-Row -->
<span class="row-stage" data-tm-id="12345"></span>
```

```js
// In existing index-rendering JS:
function renderStageBadge(tmId) {
  const s = loadStore();
  const e = s.pipeline[tmId];
  if (!e) return "";
  const labels = { watching: "BEO", contacted: "KON", in_talks: "GES",
                   mandate: "MAN", placed: "PLA", passed: "ARC" };
  const pin = e.pinned ? "📌 " : "";
  return `<span class="stage-badge stage-${e.stage}">${pin}${labels[e.stage]}</span>`;
}
```

**Acceptance:**
- Auf Trainer-Dashboard kann Stage gesetzt werden, persistiert nach Reload
- Index-Page zeigt Stage-Badge in eigener Spalte
- Pin-Toggle funktioniert, sichtbar im Daily-Digest (Phase 4)

---

### Phase 2 — Notes-System

**Ziel:** Pro Person freie Markdown-Notes mit Tags + Datum.

**UI im Detail-Panel:**

```html
<div class="workflow-notes">
  <label>Notizen</label>
  <ul class="notes-list" data-tm-id="12345"></ul>
  <textarea class="note-input" placeholder="Neue Notiz (Markdown ok). Tags via #call #2027"></textarea>
  <button class="note-save">Speichern</button>
</div>
```

**JS:**

```js
function addNote(tmId, text) {
  const s = loadStore();
  s.notes[tmId] = s.notes[tmId] || [];
  const tags = (text.match(/#\w+/g) || []).map(t => t.slice(1));
  s.notes[tmId].push({
    id: "n" + Date.now(),
    at: new Date().toISOString(),
    text: text.replace(/#\w+/g, "").trim(),
    tags
  });
  saveStore(s);
  renderNotes(tmId);
}

function renderNotes(tmId) {
  const s = loadStore();
  const list = document.querySelector(`.notes-list[data-tm-id="${tmId}"]`);
  if (!list) return;
  const notes = (s.notes[tmId] || []).slice().reverse();
  list.innerHTML = notes.map(n => `
    <li class="note-item">
      <div class="note-meta">${new Date(n.at).toLocaleString('de-DE')}
        ${n.tags.map(t=>`<span class="note-tag">#${t}</span>`).join("")}
      </div>
      <div class="note-text">${markdownToHTML(n.text)}</div>
      <button class="note-delete" data-id="${n.id}">×</button>
    </li>
  `).join("");
}
```

**Acceptance:**
- Notes lassen sich pro Person hinzufügen, anzeigen, löschen
- Tags via `#tag-name` werden als Chips gerendert
- Notes persistieren nach Reload

---

### Phase 3 — Reminders / Follow-Ups

**Ziel:** Pro Person Datum-basierte Reminder. Tagesfälliger Reminder im Daily-Digest sichtbar.

**UI:**

```html
<div class="workflow-reminder">
  <label>Reminder</label>
  <input type="date" class="reminder-date" />
  <input type="text" class="reminder-text" placeholder="z.B. Anruf zur Vertragsverlängerung" />
  <button class="reminder-add">+</button>
  <ul class="reminders-list" data-tm-id="12345"></ul>
</div>
```

**JS:**

```js
function addReminder(tmId, dateStr, text) {
  const s = loadStore();
  s.reminders.push({
    id: "r" + Date.now(),
    tm_id: tmId,
    at: new Date(dateStr + "T09:00:00").toISOString(),
    text,
    done: false
  });
  saveStore(s);
}

function getDueReminders() {
  const s = loadStore();
  const now = new Date();
  return s.reminders
    .filter(r => !r.done && new Date(r.at) <= now)
    .sort((a, b) => new Date(a.at) - new Date(b.at));
}
```

**Browser-Notification (optional):** beim Page-Load prüfen, ob fällige Reminder existieren → `Notification`-API.

**Acceptance:**
- Reminder lassen sich anlegen + abhaken (`done: true`)
- Fällige Reminder erscheinen im Daily-Digest hervorgehoben
- Notification-Permission wird beim ersten fälligen Reminder angefragt

---

### Phase 4 — Daily-Digest-View

**Ziel:** Eine Seite `/daily.html`, die der Berater morgens als erstes öffnet — fasst alles zusammen.

**Layout:**

```
Daily-Digest · 09.05.2026                                            [Filter: alles | nur Pipeline]
═══════════════════════════════════════════════════════════════════════════════════════════

📌 ANGEPINNT (3)
  Markus Krösche      | Mandat | letzte Note vor 2 Tagen     | nächster Reminder: 12.05.
  Eugen Polański      | Im Gespräch | letzte Note gestern    | —
  Patrick Glöckner    | Beobachtung | NLZ U19 Dortmund       | nächster Reminder: 15.05.

🔔 FÄLLIGE REMINDER (2)
  Heute, 09:00       Hansi Flick: Erstkontakt nach Saisonende  → [öffnen] [erledigt]
  Heute, 09:00       Adi Hütter: Vertragsverhandlung nachfragen → [öffnen] [erledigt]

📰 PIPELINE-AKTIVITÄT (letzte 7 Tage)
  Krösche → Mandat (vor 2 Tagen)
  Polański → Im Gespräch (vor 4 Tagen)
  Hürzeler → Kontaktiert (vor 6 Tagen)

🚀 HOT-SEAT-ALERTS (Trainer mit Score >70 in deiner Pipeline)
  Eugen Polański (Score 78) — siehe News-Sentiment

📊 PIPELINE-STATS
  Beobachtung: 12 | Kontaktiert: 5 | Im Gespräch: 3 | Mandat: 1 | Vermittelt: 2 | Archiv: 8
```

**Neues File:** `output/daily.html`

Routing (in `vercel.json`):
```json
{ "src": "/daily", "dest": "/daily.html" }
```

Verlinkung im Header `<header>` aller Pages: „Daily-Digest" als Primär-Link links.

**Acceptance:**
- `/daily` zeigt alle 5 Sektionen (Angepinnt, Reminder, Aktivität, Hot-Seat-Alerts, Stats)
- Klick auf Person öffnet Network-Dashboard
- "erledigt"-Button setzt Reminder auf done: true und entfernt aus Liste
- Update bei jedem Page-Load aus localStorage

---

### Phase 5 — Watchlist-Filters speichern

**Ziel:** Berater filtert Index („alle U19-Trainer mit LG 68+, in BL-NLZ-Vereinen"), klickt „Filter speichern", gibt Namen ein → bleibt in Sidebar als Quick-Link.

**UI auf Index-Page:**

```html
<aside class="saved-filters">
  <h4>Meine Filter</h4>
  <ul id="saved-filters-list">
    <li>U19 Aufsteiger 2027 (24 Trainer) <button>×</button></li>
    <li>Vereinslose Top-Tier (8) <button>×</button></li>
  </ul>
  <button id="save-current-filter">Aktuellen Filter speichern</button>
</aside>
```

**JS:**

```js
function saveCurrentFilter(name, query) {
  const s = loadStore();
  const id = "f" + Date.now();
  s.watchlist_filters[id] = { name, query, saved_at: new Date().toISOString() };
  saveStore(s);
  renderSavedFilters();
}

function applyFilter(id) {
  const s = loadStore();
  const f = s.watchlist_filters[id];
  if (!f) return;
  // Apply f.query to current Index filter state
  Object.entries(f.query).forEach(([k, v]) => {
    document.querySelector(`[data-filter="${k}"]`).value = v;
  });
  document.dispatchEvent(new Event("filter-changed"));
}
```

**Acceptance:**
- Filter speicherbar mit Namen
- Klick auf gespeicherten Filter wendet ihn auf Index an
- Löschbar via × Button

---

### Phase 6 — Export / Import

**Ziel:** Berater kann seinen Workflow-State als JSON-File exportieren, auf anderem Device importieren.

**UI auf `/daily.html`:**

```html
<div class="workflow-export">
  <button id="export-workflow">📥 Daten exportieren</button>
  <input type="file" id="import-workflow" accept=".json" hidden />
  <button onclick="document.getElementById('import-workflow').click()">📤 Daten importieren</button>
</div>
```

**JS:**

```js
document.getElementById("export-workflow").onclick = () => {
  const blob = new Blob([JSON.stringify(loadStore(), null, 2)], 
                        { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `pf_workflow_${new Date().toISOString().slice(0,10)}.json`;
  a.click();
};

document.getElementById("import-workflow").onchange = (e) => {
  const file = e.target.files[0];
  if (!file) return;
  if (!confirm("Aktuelle Daten werden überschrieben. Fortfahren?")) return;
  const reader = new FileReader();
  reader.onload = (e) => {
    try {
      saveStore(JSON.parse(e.target.result));
      location.reload();
    } catch (err) { alert("Import fehlgeschlagen: " + err.message); }
  };
  reader.readAsText(file);
};
```

**Acceptance:**
- Export erzeugt JSON-File mit Datum im Namen
- Import lädt JSON, zeigt Confirm-Dialog, überschreibt localStorage
- Page-Reload nach Import zeigt importierte Daten

---

### Phase 7 — Stakeholder-Pillar #4 mit Live-Demo

**Ziel:** USP #4 *Berater-Workflow* von Pitch-Behauptung → konkrete Live-Demo.

**Erweiterung:** `output/stakeholder.html` Pillar #4:

```html
<div class="pillar pillar-workflow">
  <div class="pillar-num">04</div>
  <h3>Berater-Workflow · Daily-Driver</h3>
  <p class="pillar-claim">Coachinsider ist read-only. Wir sind <strong>der Tab, den du morgens öffnest</strong>.</p>
  <ul class="pillar-stats">
    <li>6-Stufen-Pipeline (Beobachtung → Vermittelt)</li>
    <li>Notes mit Markdown + Tags pro Person</li>
    <li>Reminder mit Browser-Notifications</li>
    <li>Daily-Digest mit Hot-Seat-Alerts</li>
    <li>Gespeicherte Filter ("U19 Aufsteiger 2027" 1-Klick)</li>
    <li>Export/Import zwischen Devices</li>
  </ul>
  <a href="/daily" class="btn-pillar">→ Daily-Digest öffnen (Demo)</a>
</div>
```

**Acceptance:**
- Pillar #4 zeigt 6 Workflow-Features
- Demo-Link zu `/daily` funktioniert (auch wenn leer für neue Besucher)

---

## Master-Wrapper

`run_crm_workflow.sh`:

```bash
#!/usr/bin/env bash
# Sprint I · Berater-CRM-Workflow MVP
# Voraussetzung: Sprint F (Decision-Maker) durch
set -uo pipefail
cd "$(dirname "$0")"

START_TS=$(date +%s)
RUN_ID="crm_$(date +%Y%m%d_%H%M)"
LOG_DIR="logs/$RUN_ID"
mkdir -p "$LOG_DIR"
NTFY_TOPIC="${NTFY_TOPIC:-cmk-coachdb}"
ntfy() { curl -s -d "$1" "https://ntfy.sh/${NTFY_TOPIC}" >/dev/null 2>&1 || true; }
note() {
  echo ""
  echo "═══ $1 @ $(date '+%H:%M:%S') ═══"
}

ntfy "CRM-Workflow MVP gestartet"

note "[1/5] Workflow-JS + CSS erstellen"
# Schreibt output/assets/workflow.js und output/assets/workflow.css
python3 execution/scaffold_workflow_assets.py > "$LOG_DIR/01_assets.log" 2>&1 || true

note "[2/5] Dashboards-Template erweitern (Pipeline-Stage + Notes + Reminder)"
python3 execution/extend_dashboard_template_with_workflow.py > "$LOG_DIR/02_template.log" 2>&1 || true

note "[3/5] Index-Page Stage-Spalte + Saved-Filters Sidebar"
python3 execution/extend_index_with_workflow.py > "$LOG_DIR/03_index.log" 2>&1 || true

note "[4/5] /daily.html generieren"
python3 execution/generate_daily_digest.py > "$LOG_DIR/04_daily.log" 2>&1 || true

note "[5/5] Re-Build + Deploy"
python3 execution/regenerate_dashboards.py --lazy 500000 > "$LOG_DIR/05_regen.log" 2>&1 || true
python3 execution/generate_all_bl_coaches.py --include-historical --include-decision-makers \
  > "$LOG_DIR/05b_index.log" 2>&1 || true
python3 execution/generate_club_pages.py > "$LOG_DIR/05c_clubs.log" 2>&1 || true
cd output
DEPLOY_URL=$(npx vercel deploy --prod --yes --scope cmk2299s-projects 2>&1 \
  | tee "../$LOG_DIR/05d_deploy.log" | grep -oE 'https://[^ ]+vercel\.app' | tail -1)
cd ..

END_TS=$(date +%s)
DURATION_MIN=$(( (END_TS - START_TS) / 60 ))

note "✓ CRM DONE — $DURATION_MIN min"
echo "  Daily-Digest:  ${DEPLOY_URL}/daily"
echo "  Logs:          $LOG_DIR/"

ntfy "✓ CRM-Workflow live — $DURATION_MIN min · ${DEPLOY_URL:-deploy.log}/daily"
```

---

## Edge-Cases

1. **Daten-Migration nach Schema-Änderung** (z.B. neue Stage hinzu): `version: 1` im Store → bei Page-Load Migrations-Fn die alte Versionen auf neue Felder mapped.
2. **localStorage-Limit (5-10 MB)** → bei ~10.000 Notes erreichen wir das. Watch: bei >5 MB Warning anzeigen, „Backup empfohlen".
3. **Multi-Tab-Konflikt**: 2 offene Tabs schreiben parallel → letzter gewinnt. `storage`-Event nutzen für Cross-Tab-Sync (best effort).
4. **Privacy**: Notes sind im Browser, aber bei geteilten Geräten (Berater-Team-Laptop) sichtbar. Klare Hint im UI: "Nur in deinem Browser, nicht synchronisiert".
5. **Stakeholder-Demo-Account**: Default-Datensatz für Stakeholder-Demo? Empfehlung: `output/daily_demo.html` mit hardcoded Beispiel-State, separater Pfad. Nicht im MVP, aber für Pitch.

---

## Validierung post-Deploy

```bash
# Daily-Digest erreichbar?
curl -s -o /dev/null -w "%{http_code}\n" https://coach-network-explorer.vercel.app/daily
# Erwartung: 200

# workflow.js geladen auf Dashboard?
curl -s https://coach-network-explorer.vercel.app/dashboards/markus_kroesche_sd_network.html | \
  grep -c 'workflow.js'
# Erwartung: ≥1

# Stage-Picker im Detail-Panel sichtbar?
curl -s https://coach-network-explorer.vercel.app/dashboards/markus_kroesche_sd_network.html | \
  grep -c 'pipeline-stage'
# Erwartung: ≥1
```

---

## Open Questions für Nutzer

1. **Stages anpassen?** — sind die 6 Stages („Beobachtung → Kontaktiert → Im Gespräch → Mandat → Vermittelt → Abgeschlossen") für projectFIVE-Beraterkontext richtig? Oder anderes Mapping?
2. **Reminder-Zeit** — Default 9:00 Uhr lokal? Konfigurierbar im Daily-Digest?
3. **Cloud-Sync später**: bevorzugte Backend-Architektur? Empfehlung Supabase (gleicher Stack wie DepotPilot) oder Firebase. Für MVP nicht relevant, aber Sprint J planbar.
4. **Multi-User-Team** (mehrere projectFIVE-Berater): wollen sie *gemeinsame* Pipeline (geteilt) oder *eigene* (privat)? Default-Empfehlung MVP: privat (lokal). Cloud-Sync hat optional Team-Workspace.
5. **Hot-Seat-Alerts im Daily-Digest**: nur für Pipeline-Trainer, oder auch für nicht-tracked Trainer in deinen Watchlist-Filtern?

---

## Erwartetes Stakeholder-Outcome

Nach Sprint I:
- **Daily-Driver-Demo**: Stakeholder kann Pipeline live durchspielen
- **Pillar #4 ist real** — nicht „wir haben CRM-Pläne" sondern „klick hier, probier es"
- **Argument**: „Coachinsider liefert dir die Daten. Wir liefern dir die *Arbeitsweise*. Beides zusammen → ein Tool weniger im Stack."
- **Daily-Driver-Loop entsteht**: Berater öffnet morgens `/daily`, sieht 3 Reminder + 2 Hot-Seat-Alerts → klickt rein, macht Notiz, ändert Stage → nutzt das Tool 4-6×/Tag statt 0×.

Erst dann zahlt projectFIVE die 20k EUR/Jahr **für uns**, nicht für coachinsider.

---

## Sprint-Reihenfolge

```
✅ Sprint A   LG 70/71
✅ Sprint B   NLZ Variant-2
✅ Sprint C   Trainerstab Tier 1+2
✅ coachinsider-Diff
↓
   Sprint F   SD/GF Deep Coverage    (Demand-Tiefe — Voraussetzung für Pipeline)
   Sprint G   NLZ-Trainer Cluster    (Talente-Pipeline)
↓
→  Sprint I   Berater-CRM-Workflow   (DIESE Directive — Daily-Driver, USP #4)
   Sprint J   Cloud-Sync             (Multi-Device, Team-Workspace, Auth)
```

Sprint I ist **der**Critical-Path-Sprint für den Daily-Driver-USP. Sprint J nur wenn Stakeholder-Validation positiv.

---

## Kosten-Modell für Sprint J (Cloud-Sync, später)

Für Stakeholder-Klarheit:

| Tier | Stack | Kosten/Monat (10 Berater) | Aufwand |
|------|-------|---------------------------|---------|
| MVP localStorage | static HTML+JS | 0 EUR | 0 (im MVP enthalten) |
| Sprint J Tier 1 | Supabase Free + Auth | 0 EUR (bis 50k MAU) | ~6h |
| Sprint J Tier 2 | Supabase Pro + RLS | 25 EUR/Monat | ~10h (RLS + Team-Workspaces) |
| Sprint J Tier 3 | Eigenes Backend (FastAPI/Postgres/Railway) | 20-40 EUR/Monat | ~3 Tage |

Empfehlung: **Sprint J Tier 1** (Supabase Free) für 1-10 Berater. Wenn projectFIVE-Beraterteam wächst → Tier 2.
