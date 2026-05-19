# Directive: Coach-Vertragsdaten Scrape — Aktivierungs-Trigger #5

**Trigger-Phrase für Claude:** "Scrape coach contracts" oder "/scrape-coach-contracts"

**Bezugnehmend auf:** projectFIVE Strategic-Recommendation #5 (Top-3) — "Vertrag läuft aus 30.06.2026" ist der wichtigste Berater-Trigger nach Hot-Seat.

**Mission-Wert:** Beratungs-Aktivierung passiert nicht nur bei Wackel-Coaches sondern auch bei vertraglich auslaufenden — der Coach kann frei wechseln, der Berater muss sich positionieren. Datenfundament für `/build-availability-layer`.

**Aufwand:** ~4h (Scrape + Re-calc + Display).

---

## Daten-Quelle: TM-Profile-Block "Vertrag bis"

Beispiel TM Trainer-Profil-HTML (https://www.transfermarkt.de/x/profil/trainer/{tm_id}):
```html
<span class="info-table__content info-table__content--bold">vsl. 30.06.2026</span>
```
oder
```html
<span class="info-table__content info-table__content--bold">unbekannt</span>
```

Bereits gescrapte Profile (`data/person_profiles/{tm_id}.json`) haben teilweise das Feld `contract_until` — verifizieren:

```bash
python3 -c "
import json, glob
hits = misses = 0
for f in list(glob.glob('data/person_profiles/*.json'))[:200]:
    p = json.load(open(f))
    if p.get('type') == 'trainer':
        if p.get('contract_until'): hits += 1
        else: misses += 1
print(f'Trainer-Profile: {hits} mit contract_until, {misses} ohne')
"
```

Wenn Quote < 50%: separate Re-Scrape benötigt. Wenn > 80%: nur Lückenschluss.

---

## Schritt 1 — Bestehende Daten konsolidieren

Neues Skript `execution/extract_coach_contracts.py`:

```python
#!/usr/bin/env python3
"""Liest contract_until aus existing person_profiles + sd_registry.

Output: data/coach_contracts.json
  {
    coach_tm_id: {
      contract_until: "30.06.2026" | "unbekannt" | null,
      parsed_date: "2026-06-30" | null,
      days_remaining: int | null,
      season_end: bool,        # true wenn 30.06 oder 31.07
      verified_at: iso str,
      source: "persons_master" | "scrape" | "manual_override"
    }
  }
"""
import json, re
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent.parent
TODAY = datetime.now(timezone.utc).date()

def parse_contract(s: str):
    if not s or s.lower() in ("unbekannt", "-", "n/a"): return None
    s = s.strip().replace("vsl.", "").replace("\xa0", " ").strip()
    m = re.match(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)
    if not m: return None
    d, mn, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return datetime(y, mn, d).date()
    except ValueError:
        return None

def main():
    persons = json.load(open(BASE / "data/persons_master.json"))["persons"]
    out = {}

    # All trainer-typed profiles
    for tm_id, p in persons.items():
        if p.get("type") != "trainer": continue
        cu = p.get("contract_until")
        parsed = parse_contract(cu) if cu else None
        days = (parsed - TODAY).days if parsed else None
        out[tm_id] = {
            "contract_until": cu,
            "parsed_date": parsed.isoformat() if parsed else None,
            "days_remaining": days,
            "season_end": parsed.month in (5, 6, 7) if parsed else False,
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "source": "persons_master",
        }

    out_file = BASE / "data/coach_contracts.json"
    json.dump({
        "_meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total": len(out),
            "with_date": sum(1 for v in out.values() if v["parsed_date"]),
            "expiring_in_6mo": sum(1 for v in out.values()
                if v["days_remaining"] and 0 <= v["days_remaining"] <= 180),
        },
        "contracts": out,
    }, open(out_file, "w"), ensure_ascii=False, indent=2)
    print(f"✓ {len(out)} contracts → {out_file}")

if __name__ == "__main__":
    main()
```

Run:
```bash
python3 execution/extract_coach_contracts.py
```

## Schritt 2 — Lücken-Re-Scrape (falls nötig)

Wenn Coverage < 50%: re-run `scrape_person_profiles.py` mit Filter auf trainer-types ohne contract_until. Erweitern um TM-HTML-Selector wenn nicht schon in scrape-Logic enthalten:

```python
# In scrape_person_profiles.py — HTML-Block "Vertrag bis":
contract_match = re.search(
    r'Vertrag bis:.*?<span[^>]*>([^<]+)</span>',
    html, re.DOTALL
)
if contract_match:
    profile["contract_until"] = contract_match.group(1).strip()
```

## Schritt 3 — Hot-Seat-Komponente: Vertragsende-Aktivierungs-Druck

In `execution/calc_hot_seat_score.py` neue (8.) Komponente:

```python
def calc_score(form, league, expectation=None, mood=None, contract=None):
    # ... existing 7 components ...

    # 8. Contract-Expiry-Pressure (Aktivierungs-Trigger, max 8 pts)
    contract_pts = 0
    if contract and contract.get("days_remaining") is not None:
        days = contract["days_remaining"]
        if days < 0:
            contract_pts = 0  # already expired
        elif days < 90:    # < 3 Monate: kritisch (HOT trigger)
            contract_pts = 8
        elif days < 180:   # 3-6 Monate: warm
            contract_pts = 5
        elif days < 365:   # 6-12 Monate: leicht erhöht
            contract_pts = 2
    components["contract_expiry"] = contract_pts
    score += contract_pts
```

→ Reduziere mood-max von 15 auf 12 (oder days_since_win 5 auf 3) um neuen 8 Pts Platz zu machen, oder den hard cap bei 100 lassen — Komponenten-Summe darf ≥100 sein, `min(score, 100)` regelt.

## Schritt 4 — Display-Layer im Dashboard

Im Detail-Panel (template `blessin_network_v3.html`) neue Zeile zwischen "Lizenz" und "Gemeinsame Spiele":

```javascript
// In selectContact() detail render:
const contractRow = document.getElementById('d-contract-row');
if (contractRow) {
    if (c.contract_until && c.contract_days_remaining !== null) {
        const days = c.contract_days_remaining;
        const cls = days < 90 ? 'gs-stat' : '';  // rot wenn kritisch
        document.getElementById('d-contract-value').innerHTML =
            `<span class="${cls}">${c.contract_until} (${days} Tage)</span>`;
        contractRow.style.display = '';
    } else {
        contractRow.style.display = 'none';
    }
}
```

Plus contract-Felder im build_coach_network.py contact-enrichment einfügen:

```python
# Im contact enrichment:
ct = contracts.get(str(tm_id))
if ct:
    c["contract_until"] = ct.get("contract_until")
    c["contract_days_remaining"] = ct.get("days_remaining")
```

## Schritt 5 — Run + Re-Build + Deploy

```bash
# 1) Extract contracts
python3 execution/extract_coach_contracts.py

# 2) Re-calc Hot-Seat with contract component
python3 execution/calc_hot_seat_score.py

# 3) Re-build active networks (für die 56 active coaches)
#    (alternativ via run_mvp.sh)
python3 execution/generate_all_bl_coaches.py --leagues BL1 BL2 BL3 --include-historical

# 4) Deploy
cd output && npx vercel deploy --prod --yes --scope cmk2299s-projects
```

## Validierung post-Deploy

```bash
# Wieviele Coaches haben Vertragsende < 90 Tage?
python3 -c "
import json
c = json.load(open('data/coach_contracts.json'))
n = sum(1 for v in c['contracts'].values()
        if v.get('days_remaining') and 0 <= v['days_remaining'] < 90)
print(f'{n} Coaches mit Vertragsende in nächsten 90 Tagen')
"

# Live spot-check: Eta sollte Vertragsende sehen falls vorhanden
curl -s https://coach-network-explorer.vercel.app/dashboards/marie_louise_eta_network.html | \
  grep -o 'contract_days_remaining":[0-9-]*' | head -3
```

## Edge-Cases

1. **"vsl. 30.06.2026"** — TM-Format mit "vsl." prefix; parser strippt automatisch
2. **"unbekannt"** — viele Trainer-Profile haben das; bleibt null in days_remaining
3. **Bereits abgelaufen** — Coach ist vertraglich frei, aber im Verein → unklar, Score-Auswirkung 0 (neutral)
4. **Saisonende-Vertrag (30.06)** vs. **Mid-Season-Vertrag (z.B. 31.12)** — beide gleich behandelt, aber `season_end: bool` Flag erlaubt späteren Filter
