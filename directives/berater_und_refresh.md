# Directive: Berater-Integration & Daten-Refresh-Strategie

## Teil 1: Berater (Agents) im Dashboard

### Ziel

Henryks Anforderung: **"Who manages the coach?"** — Berater/Agent-Daten im Detail-Panel anzeigen und als Filter nutzbar machen.

### Ist-Zustand

| Was | Stand |
|-----|-------|
| Agent-Feld in person_profiles | ~38.5% Coverage (6.835/~18.000 Spieler) |
| Feld-Name | `agent` (String) |
| Unique Agenturen | ~1.515 |
| Top Agenturen | CAA Stellar (71), The.Team (66), Unique Sports Group (53), SEG (43) |
| Sonderwert | `"ohne Berater"` = kein Agent |
| Trainer-Profile | Haben kein `agent`-Feld auf TM (nur Spieler) |
| Dashboard-Integration | ❌ Nicht vorhanden |

### Implementierung

#### Phase 1: Agent-Daten in Network-Kontakte übernehmen

In `build_coach_network.py`, im Enrichment-Block (nach career_history):

```python
# Enrich with agent data from person_profiles
agent = p.get("agent", "")
if agent and agent != "ohne Berater":
    c["agent"] = agent
```

Das reicht — der Kontakt bekommt ein `agent`-Feld wenn vorhanden.

#### Phase 2: Dashboard-Template — Detail-Panel

Im Detail-Panel, nach der Karriere-Tabelle:

```javascript
// Agent/Berater
if (c.agent) {
    const agentDiv = document.createElement('div');
    agentDiv.className = 'detail-agent';
    agentDiv.innerHTML = `<span class="detail-label">Berater</span><span class="detail-value">${c.agent}</span>`;
    // Einfügen nach career-section
}
```

CSS:
```css
.detail-agent { margin: 8px 0; font-size: 12px; }
.detail-agent .detail-label { color: var(--text-dim); margin-right: 8px; }
.detail-agent .detail-value { color: var(--text); font-weight: 500; }
```

#### Phase 3: Berater als Filter (Optional, Phase 2)

Sidebar-Filter: "Berater" Dropdown mit den Top-20 Agenturen.

```javascript
// In buildFilters() — neuer Berater-Filter
const agents = {};
NETWORK.contacts.forEach(c => {
    if (c.agent) agents[c.agent] = (agents[c.agent] || 0) + 1;
});
const topAgents = Object.entries(agents)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 20);
// Dropdown oder Chips rendern
```

Das ist Phase 2 — erstmal nur im Detail-Panel anzeigen.

### Aufwand

| Phase | Aufwand | Was |
|-------|---------|-----|
| 1: Agent-Feld in Netzwerk | 5 Min | 2 Zeilen in build_coach_network.py |
| 2: Detail-Panel | 15 Min | Template-Update |
| 3: Filter (optional) | 30 Min | Sidebar-Erweiterung |
| Rebuild + Deploy | ~100 Min | Automatisch |

---

## Teil 2: Daten-Refresh-Strategie

### Problem

Fußball-Daten ändern sich. Die wichtigsten Trigger:

| Periode | Was ändert sich | Frequenz |
|---------|-----------------|----------|
| **Sommer-Transferfenster** (1. Jul – 31. Aug) | Spieler-Transfers, Trainer-Wechsel, Staff-Änderungen | Täglich |
| **Winter-Transferfenster** (1. Jan – 31. Jan) | Spieler-Transfers, Trainer-Wechsel | Täglich |
| **Saison-Start** (Aug/Sep) | Neue Kader, neue Trainer | Einmalig |
| **Laufende Saison** (Sep – Mai) | Trainer-Entlassungen, Interimscoaches | Unregelmäßig (1-3x/Monat) |
| **Off-Season** (Jun) | Vertragsverlängerungen, Jugendaufstiege | Gelegentlich |

### Daten-Typen und ihre Volatilität

| Datentyp | Quelle | Änderungs-Frequenz | Aktuelle Refresh-Rate | Soll |
|----------|--------|--------------------|-----------------------|------|
| **Staff** (wer arbeitet wo) | TM Mitarbeiter-Seiten | Hoch (Transferfenster), Niedrig (Saison) | Täglich (Cron) | ✅ Passt |
| **Squads** (Kader) | TM Squad-Seiten | Hoch (Transferfenster) | ❌ Nie (nur initial) | Transferfenster: wöchentlich |
| **Berater** | TM Spieler-Profile | Niedrig (1-2x/Jahr) | ❌ Nie | Monatlich |
| **Person-Profile** (Name, DOB, Nationalität) | TM Profil-Seiten | Sehr niedrig | ❌ Nie | Quartalsweise |
| **GemeinsameSpiele** | TM GS-Seiten | Laufende Saison: wöchentlich | ❌ Nie | Saisonende |
| **Spielerkarriere** | TM Leistungsdaten | Laufende Saison: wöchentlich | ❌ Nie | Saisonende |
| **Coaching Licenses** | DFB-Quellen | Jährlich (neuer Lehrgang) | ❌ Manuell | Jährlich |

### Architektur: 3-Tier-Refresh

#### Tier 1: Hot Data (Staff + Squads)

Ändern sich im Transferfenster täglich. Müssen zeitnah aktualisiert werden.

**Aktuell:** `run_mvp.sh` scrapt Staff täglich um 7:22. Squads werden nie refresht.

**Soll:**

```bash
# run_mvp.sh (bestehend, erweitert)
#!/bin/bash

SEASON="25/26"
MODE=$(date +%m | awk '{
    if ($1 == "01") print "winter_window"
    else if ($1 >= "07" && $1 <= "08") print "summer_window"
    else print "regular"
}')

echo "Mode: $MODE"

# Staff immer refreshen (schnell, ~5 Min)
python3 execution/scrape_squads.py --staff-only --season "$SEASON"

# Squads: nur in Transferfenstern
if [ "$MODE" != "regular" ]; then
    echo "Transfer window — refreshing squads..."
    python3 execution/scrape_squads.py --squads-only --season "$SEASON" --leagues BL1,BL2
fi

# Networks bauen + Dashboards + Deploy
python3 execution/generate_all_bl_coaches.py --all-networks --include-historical
cd output && npx vercel deploy --prod --yes --scope cmk2299s-projects
```

#### Tier 2: Warm Data (Berater, Profiles)

Ändern sich selten, aber regelmäßig.

**Soll:** Monatlicher Batch-Refresh, getriggert als separater Cron (z.B. 1. des Monats):

```bash
# monthly_refresh.sh (NEU)
#!/bin/bash

echo "=== Monthly Profile Refresh ==="

# Berater-Update: Nur Spieler in aktuellen BL1/BL2-Kadern
python3 execution/scrape_person_profiles.py --refresh-agents --leagues BL1,BL2

# Profile-Update: Nur Personen die in aktiven Netzwerken vorkommen
python3 execution/scrape_person_profiles.py --refresh-active --max-age 30

echo "=== Done ==="
```

**Neues Flag in `scrape_person_profiles.py`:**
- `--refresh-agents`: Nur das `agent`-Feld refreshen (schnell, ~1 Request/Spieler)
- `--refresh-active`: Vollständiger Re-Scrape für Personen deren Cache > 30 Tage alt ist
- `--max-age N`: Nur Profiles refreshen die älter als N Tage sind

#### Tier 3: Cold Data (GemeinsameSpiele, Spielerkarriere, Coaching Licenses)

Historische Daten die sich kaum ändern. Einmal pro Saison refreshen reicht.

**Soll:** Manueller Trigger am Saisonende (Mai/Juni):

```bash
# end_of_season_refresh.sh (NEU)
#!/bin/bash

echo "=== End-of-Season Data Refresh ==="

# GemeinsameSpiele: Nur für Coaches die diese Saison aktiv waren
python3 execution/scrape_gemeinsame_spiele.py --all --skip-existing --max-age 180

# Spielerkarrieren: Neue Saison-Einträge
python3 execution/scrape_coach_playing_careers.py --all

# Coaching Licenses: Manuell checken ob neuer Lehrgang
echo "REMINDER: Check DFB.de for new Fußball-Lehrer cohort"

echo "=== Done ==="
```

### Staleness-Tracking

Jeder Datenpunkt braucht einen `last_updated` Timestamp damit klar ist wie aktuell die Daten sind.

#### Im Network JSON:

```json
{
  "coach": "Alexander Blessin",
  "generated_at": "2026-04-10T00:30:00",
  "data_freshness": {
    "staff": "2026-04-10",
    "squads": "2026-03-27",
    "profiles": "2026-03-26",
    "gemeinsame_spiele": "2026-04-09",
    "playing_careers": "2026-04-07"
  },
  "contacts": [...]
}
```

#### Im Dashboard:

Footer oder Header-Badge: **"Daten-Stand: 10.04.2026"** (= `generated_at`)

Bei veralteten Daten (> 30 Tage): Gelber Hinweis "Daten älter als 30 Tage — Refresh empfohlen"

### Implementierungs-Reihenfolge

```
Phase 1 (Jetzt — 30 Min):
  1. Agent-Feld in build_coach_network.py einbauen (2 Zeilen)
  2. Template: Agent im Detail-Panel anzeigen
  3. Rebuild + Deploy (läuft sowieso gerade)

Phase 2 (Nächste Session — 1h):
  1. run_mvp.sh erweitern: Transfer-Window-Modus
  2. monthly_refresh.sh erstellen
  3. scrape_person_profiles.py: --refresh-agents Flag
  4. Staleness-Tracking in Network-JSON

Phase 3 (Saisonende — 30 Min):
  1. end_of_season_refresh.sh erstellen
  2. Coaching Licenses LG 70 recherchieren + einpflegen
  3. GemeinsameSpiele für neue Saison refreshen
```

### Transfer-Window-Detection

```python
from datetime import date

def get_refresh_mode():
    """Determine data refresh aggressiveness based on football calendar."""
    today = date.today()
    month = today.month
    day = today.day
    
    # Winter window: Jan 1 - Jan 31 (+ Feb 1-7 for late deals)
    if month == 1 or (month == 2 and day <= 7):
        return "winter_window"
    
    # Summer window: Jul 1 - Aug 31 (+ Sep 1-7 for late deals)
    if month in (7, 8) or (month == 9 and day <= 7):
        return "summer_window"
    
    # Pre-season: Jun (lots of announcements)
    if month == 6:
        return "pre_season"
    
    return "regular"
```

### Request-Budget pro Refresh-Typ

| Refresh | Requests | Zeit | Frequenz |
|---------|----------|------|----------|
| Staff (36 BL-Clubs) | ~36 | ~3 Min | Täglich |
| Squads (BL1+BL2, 1 Saison) | ~36 | ~3 Min | Wöchentlich (nur Transferfenster) |
| Agent-Update (BL-Kader) | ~800 | ~40 Min | Monatlich |
| Full Profile Refresh | ~5.000 | ~4h | Quartalsweise |
| GemeinsameSpiele (300 Coaches) | ~400 | ~30 Min | Saisonende |

**Gesamt-Budget pro Monat:**
- Regular: ~1.100 Requests (Staff daily)
- Transferfenster: ~2.200 Requests (Staff + Squads weekly)
- Mit Agent-Refresh: +800/Monat

---

## Edge Cases

### Trainer-Entlassung Mitte Saison
- Staff-Files werden täglich refresht → neuer Trainer taucht am nächsten Tag auf
- Alter Trainer bleibt in Historical-Index
- Dashboard zeigt "Ehemaliger Trainer" mit letztem bekanntem Stand

### Berater-Wechsel
- Monatlicher Refresh fängt die meisten ab
- Im Transferfenster: Agent-Data kann 1-2 Wochen veraltet sein (akzeptabel)
- Workaround: User kann TM-Link im Dashboard klicken für aktuelle Daten

### Saison-Wechsel (Aug→Sep)
- SEASON-Variable in run_mvp.sh manuell umstellen: `SEASON="26/27"`
- Oder: Auto-Detection basierend auf Datum (Jul-Dez = aktuelle Saison, Jan-Jun = Vorjahr +1)
- Club Registry: Neue Auf-/Absteiger einpflegen (manuell oder via `scrape_club_registry.py --refresh`)

### TM-Blocking bei zu vielen Requests
- Bestehende Rate-Limiting-Logik (3-5s Delay) bleibt
- Monatlicher Agent-Refresh: Session-Pause alle 100 Requests
- Bei 429: Exponential Backoff (30s → 60s → 120s → Abbruch)

---

## Learnings Log
_(Claude Code updatet diesen Abschnitt während der Ausführung)_

- [ ] Wie lange dauert ein Agent-Refresh für alle BL-Kader?
- [ ] Gibt es TM-Rate-Limiting-Änderungen bei häufigem Profile-Refresh?
- [ ] Wie viele Berater-Wechsel gibt es pro Transferfenster?
- [ ] Performance-Impact von Staleness-Tracking auf Network-JSON-Größe?
