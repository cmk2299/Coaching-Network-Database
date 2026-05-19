# Directive: Availability-Layer + Replacement-Pool-Filter

**Trigger-Phrase für Claude:** "Build availability layer" oder "/build-availability-layer"

**Bezugnehmend auf:** projectFIVE Strategic-Recommendation #1 (Top-3) — der größte UX-Hebel. Verwandelt Network-Explorer in echten Replacement-Pool-Workflow.

**Mission-Wert:** "Toppmöller wackelt → Krösches Netzwerk → von 200 Kontakten nur die 15 verfügbaren zeigen" wird mit ein Klick. Heute: Filter fehlt komplett.

**Aufwand:** ~6h (Status-Berechnung + UI-Filter + Replacement-Pool-View).

**Voraussetzung:** `/scrape-coach-contracts` muss durch sein (data/coach_contracts.json existiert).

---

## Konzept: 5 Availability-Status-Werte

| Status | Definition | UX-Color |
|---|---|---|
| `vereinslos` | current_club in {Karriereende, Vereinslos, -, ""} | grün (sofort verfügbar) |
| `frei_zum_saisonende` | contract_until in nächsten 90 Tagen UND season_end=true | gelb (Sommer-Hire) |
| `wechselbereit` | News-Signal "X bietet sich an" / "X will Verein verlassen" | gelb |
| `kontraktiert` | Vertrag > 6 Monate | grau |
| `unbekannt` | weder Vertrag noch Verein-Daten klar | grau |

---

## Schritt 1 — Status-Calculator

Neues Skript `execution/calc_availability_status.py`:

```python
#!/usr/bin/env python3
"""Computes availability_status pro Trainer aus mehreren Quellen.

Sources:
  - persons_master (current_club)
  - coach_contracts.json (Vertragsende)
  - coach_mood_signals.json (News-Signale für 'wechselbereit')

Output: data/coach_availability.json
  {tm_id: {status, reason, source, available_from, last_updated}}
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent.parent

WECHSELBEREIT_PATTERNS = [
    r"bietet sich an",
    r"will (verein )?verlassen",
    r"sucht? neue herausforderung",
    r"(steht )?vor (dem )?wechsel",
    r"will weg",
    r"abschied (steht|naht|verkündet)",
]

VEREINSLOS_VALUES = {"Karriereende", "Vereinslos", "-", "", None}


def calc_status(profile, contract, mood):
    """Return (status, reason)."""
    cc = (profile or {}).get("current_club") or {}
    cc_name = cc.get("name") if isinstance(cc, dict) else cc

    # 1. vereinslos
    if cc_name in VEREINSLOS_VALUES:
        return ("vereinslos", "current_club leer/Karriereende")

    # 2. frei zum saisonende
    if contract and contract.get("days_remaining") is not None:
        days = contract["days_remaining"]
        if 0 <= days <= 120 and contract.get("season_end"):
            return ("frei_zum_saisonende", f"Vertrag bis {contract['contract_until']} ({days}d)")
        if 0 <= days <= 60:  # tight contract end (any time of year)
            return ("frei_zum_saisonende", f"Vertrag bis {contract['contract_until']} ({days}d)")

    # 3. wechselbereit (Mood-Signal)
    if mood:
        all_signals = " ".join(
            [h.get("title", "") for h in (mood.get("headlines_sample") or [])]
        ).lower()
        for p in WECHSELBEREIT_PATTERNS:
            if re.search(p, all_signals):
                return ("wechselbereit", f"News-Signal: '{p}'")

    # 4. kontraktiert
    if contract and (contract.get("days_remaining") or 0) > 180:
        return ("kontraktiert", f"Vertrag bis {contract.get('contract_until')}")

    # 5. unbekannt
    return ("unbekannt", "keine Vertrags- oder Vereins-Daten")


def main():
    persons = json.load(open(BASE / "data/persons_master.json"))["persons"]
    contracts = {}
    if (BASE / "data/coach_contracts.json").exists():
        contracts = json.load(open(BASE / "data/coach_contracts.json"))["contracts"]
    moods = {}
    if (BASE / "data/coach_mood_signals.json").exists():
        moods = json.load(open(BASE / "data/coach_mood_signals.json"))["signals"]

    out = {}
    for tm_id, p in persons.items():
        if p.get("type") != "trainer":
            continue
        status, reason = calc_status(p, contracts.get(tm_id), moods.get(tm_id))
        out[tm_id] = {
            "name": p.get("name"),
            "status": status,
            "reason": reason,
            "current_club": (p.get("current_club") or {}).get("name") if isinstance(p.get("current_club"), dict) else p.get("current_club"),
            "contract_until": (contracts.get(tm_id) or {}).get("contract_until"),
            "days_remaining": (contracts.get(tm_id) or {}).get("days_remaining"),
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

    out_file = BASE / "data/coach_availability.json"
    json.dump({
        "_meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total": len(out),
            "by_status": {s: sum(1 for v in out.values() if v["status"] == s)
                         for s in ("vereinslos", "frei_zum_saisonende",
                                   "wechselbereit", "kontraktiert", "unbekannt")},
        },
        "availability": out,
    }, open(out_file, "w"), ensure_ascii=False, indent=2)

    print(f"✓ {len(out)} coaches → {out_file}")
    print("  Status-Breakdown:")
    for s, n in sorted(out_file_meta := json.load(open(out_file))["_meta"]["by_status"].items(),
                        key=lambda kv: -kv[1]):
        print(f"    {s:<25} {n}")

if __name__ == "__main__":
    main()
```

Run:
```bash
python3 execution/calc_availability_status.py
```

Erwartete Verteilung BL-aktive + ex-Trainer:
- vereinslos: 30-50 (ex-coaches mit no current job)
- frei_zum_saisonende: 5-15 (Saisonende-Verträge in 6/26 oder 6/27)
- wechselbereit: 2-8 (News-Signale)
- kontraktiert: 80-120 (active head coaches)
- unbekannt: viele (alle ohne Vertragsdaten)

## Schritt 2 — Filter im Dashboard

Im Template `blessin_network_v3.html` neuer Filter-Button neben "Nur Decision-Maker":

```html
<button class="pro-filter-btn" id="avail-filter-btn"
        title="Nur verfügbare Coaches (vereinslos, freier Vertrag, wechselbereit)">
  Nur Verfügbare
</button>
```

JS:
```javascript
let availFilterActive = false;
const AVAIL_FILTER_STATUS = ["vereinslos", "frei_zum_saisonende", "wechselbereit"];

function toggleAvailFilter() {
    availFilterActive = !availFilterActive;
    document.getElementById('avail-filter-btn').classList.toggle('active', availFilterActive);
    onFilterChange();
}

// In getFilteredContacts():
if (availFilterActive) {
    contacts = contacts.filter(c =>
        AVAIL_FILTER_STATUS.includes(c.availability_status));
}
```

Plus: contact enrichment in `build_coach_network.py` ergänzen um `availability_status`/`availability_reason`:

```python
# Load availability once
avail = {}
if (DATA / "coach_availability.json").exists():
    avail = json.load(open(DATA / "coach_availability.json"))["availability"]

# In contact enrichment:
av = avail.get(str(tm_id))
if av:
    c["availability_status"] = av["status"]
    c["availability_reason"] = av["reason"]
```

## Schritt 3 — Detail-Panel: Verfügbarkeits-Badge

Im Detail-Panel neue Zeile prominent unter Verein:

```html
<dt>Verfügbarkeit</dt>
<dd id="d-avail-value"><span class="avail-badge avail-{status}">{label}</span></dd>
```

CSS:
```css
.avail-vereinslos { background:rgba(46,204,64,.18); color:#2ecc40; border:1px solid rgba(46,204,64,.4); }
.avail-frei_zum_saisonende { background:rgba(243,156,18,.18); color:#f39c12; border:1px solid rgba(243,156,18,.4); }
.avail-wechselbereit { background:rgba(243,156,18,.18); color:#f39c12; border:1px solid rgba(243,156,18,.4); }
.avail-kontraktiert { background:rgba(255,255,255,.05); color:var(--text-2); border:1px solid var(--border); }
.avail-unbekannt { background:transparent; color:var(--text-3); border:1px dashed var(--border); }
```

## Schritt 4 — Replacement-Pool-View (UX-Highlight)

Neue Sektion im SD-Dashboard: "Replacement-Pool" — automatic gefilterte Top-Liste der eigenen Kontakte mit:
- category in (head_coach, executive)
- availability_status in (vereinslos, frei_zum_saisonende, wechselbereit)
- league_match (BL1-Coach für BL1-Replacement)

```javascript
// Im Krösche-Dashboard automatisch sichtbar:
function buildReplacementPool() {
    const candidates = NETWORK.contacts.filter(c =>
        ["head_coach", "executive"].includes(c.category) &&
        ["vereinslos", "frei_zum_saisonende", "wechselbereit"].includes(c.availability_status)
    ).sort((a, b) => b.relevance_score - a.relevance_score);

    return candidates.slice(0, 15).map(c => `
        <div class="replacement-card">
            <span class="replacement-name">${c.name}</span>
            <span class="avail-badge avail-${c.availability_status}">${c.availability_status}</span>
            <span class="replacement-role">${c.role}</span>
            <span class="replacement-score">${c.relevance_score}</span>
        </div>
    `).join('');
}
```

## Schritt 5 — Run + Deploy

```bash
# 1) Calculate availability
python3 execution/calc_availability_status.py

# 2) Re-build active networks with new fields
python3 execution/generate_all_bl_coaches.py --leagues BL1 BL2 BL3 --include-historical

# 3) Re-build SD networks (if Phase /build-sd-networks done)
python3 execution/build_all_sd_networks.py

# 4) Re-generate all dashboards (cross-link refresh)
python3 execution/regenerate_dashboards.py --lazy 500000

# 5) Deploy
cd output && npx vercel deploy --prod --yes --scope cmk2299s-projects
```

## Validierung post-Deploy

```bash
# Vereinslos-Coaches im Status-Index:
python3 -c "
import json
av = json.load(open('data/coach_availability.json'))
verein = [v for v in av['availability'].values() if v['status'] == 'vereinslos']
print(f'{len(verein)} vereinslos:')
for v in verein[:8]:
    print(f\"  {v['name']:<26} ({v['reason']})\")
"

# Live-Test: Krösche's network sollte Filter-Button haben
curl -s https://coach-network-explorer.vercel.app/dashboards/markus_kroesche_sd_network.html | \
  grep -c 'avail-filter-btn'

# Replacement-Pool für Frankfurt: Krösche's verfügbare HC-Kontakte
curl -s https://coach-network-explorer.vercel.app/dashboards/markus_kroesche_sd_network.html | \
  python3 -c "
import re, json, sys
c = sys.stdin.read()
m = re.search(r'const NETWORK = (\\{.*?\\});\\s*\\n', c, re.DOTALL)
net = json.loads(m.group(1))
avail = [co for co in net['contacts']
         if co.get('category') in ('head_coach','executive')
         and co.get('availability_status') in ('vereinslos','frei_zum_saisonende','wechselbereit')]
avail.sort(key=lambda x: -x['relevance_score'])
print(f'Krösche replacement pool: {len(avail)} Kandidaten')
for c in avail[:10]:
    print(f'  {c[\"relevance_score\"]:>3} {c[\"name\"]:<26} [{c[\"availability_status\"]}] {c[\"role\"][:40]}')
"
```

## Erwartete Wirkung

Nach Deploy:
- **Krösche's Dashboard:** Replacement-Pool-Sektion zeigt automatic Top-15 verfügbare HC/Executive aus seinem Netzwerk
- **Filter "Nur Verfügbare"** in jedem Dashboard
- **Detail-Panel** zeigt prominent "vereinslos seit 12/25" / "Vertrag bis 30.06.2026"
- **Berater-Workflow:** wenn Hot-Seat-Coach geflaggt → 1-Klick zu SD → Replacement-Pool

**Score-Wirkung gesamt:** Tool wird vom "Netzwerk-Explorer" zur **vollständigen Trainerberatungs-Pipeline**. Geschätzter Wert-Sprung: 95 → ~99 für den Use-Case.

## Edge-Cases

1. **"vereinslos" aber recently entlassen (1-3 Wochen)**: Berater wartet typisch 2-4 Wochen Schamfrist — könnten als sub-status "freshly_available" markiert werden (created_at < 4 Wochen).
2. **Wechselbereit ohne Vertragsende**: kann ein Trainer der gerade verlängert hat aber unzufrieden ist sein — News-Signal kann über-trigger. Manuelles Override-File analog `data/availability_overrides.json` empfohlen.
3. **Mood-Signal "X bleibt"** als Negativ-Signal: kann später ergänzt werden.
