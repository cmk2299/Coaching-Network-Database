# Directive: SD/GF Deep Coverage — Demand-Side Expansion (Sprint F)

**Trigger-Phrase für Claude Code:** "Build SD deep coverage" oder "/sd-deep-coverage"

**Bezugnehmend auf:**
- `directives/build_sd_networks.md` (Phase 1, abgeschlossen — 45 SD-Networks live)
- USP #4 *Berater-Workflow* (CRM-light) — funktioniert nur mit tiefer Demand-Side
- Stakeholder-Brief 2026-05-04: "Masse erweitern" — coachinside-Coverage ist Angebotsseite, dies ist Pendant Nachfrageseite

**Mission-Wert:** Berater verkaufen Trainer und müssen wissen *wer entscheidet*, *welche Türen* offen sind, *welche Patterns* der Decision-Maker zeigt. Phase 1 hat geklärt *wer* SD ist; Phase 2 klärt *wie* sie entscheiden.

**Aufwand:** ~6-8h (3-4 Sessions oder 1 Overnight-Run).

**Risiko:** Niedrig — alle Daten-Quellen vorhanden, additive Erweiterungen, kein Breaking-Change.

---

## Voraussetzungen

```bash
# Prüfen, dass Phase 1 live ist
ls data/sd_registry.json data/sd_coach_overlaps.json
python3 -c "import json; r=json.load(open('data/sd_registry.json')); print(f'{r[\"_meta\"][\"total_sds\"]} SDs in registry')"
ls output/dashboards/*_sd_network.html | wc -l   # erwartet: 40-50
```

Wenn nicht erfüllt: erst `directives/build_sd_networks.md` durchziehen.

---

## Status Quo (Phase 1)

| Komponente | Stand |
|------------|-------|
| `sd_registry.json` | nur "Sportdirektor"-Top-Level pro BL1/BL2/BL3-Club |
| `sd_coach_overlaps.json` | nur BL1, Saison 24/25, 18 SDs × 18 Trainer, 33 relationships |
| SD-Networks live | ~45 (Krösche, Bornemann, Schicker, Fritz, etc.) |
| Hire-History pro SD | nicht aggregiert (existiert nur als Overlap-Score, nicht als Decision-Event) |
| Decision-Maker neben SD | fehlen (Vorstand Sport, CEO, Aufsichtsrat, NLZ-Leiter, Director of Football) |
| Berater-zu-SD-Mapping | fehlt (Daten in `agent`-Feld vorhanden, aber nicht aggregiert) |
| Vertragslaufzeit SD | fehlt (TM-Feld `contract_until` existiert für Trainer, sollte für SDs analog gehen) |

---

## Sprint-Phasen

### Phase 1 — Decision-Maker Registry erweitern

**Ziel:** Pro Club nicht nur den primären SD, sondern alle Trainer-Hire-relevanten Personen.

**Pattern (aus staff/{club_tm_id}.json):**
```
"Verein"-Sektion enthält:
  - Vorstand Sport / Sportvorstand → primär
  - Geschäftsführer Sport / Sportgeschäftsführer → primär
  - Sportdirektor / Sportlicher Leiter → primär (Phase 1)
  - Technischer Direktor / Director of Football → primär
  - Sportkoordinator → sekundär
  - Aufsichtsrat (sportlich) → sekundär (eV-Vereine)
  - CEO / Vorstandsvorsitzender → tertiär (bei Watzke-Pattern)

"Jugend"/"NLZ"-Sektion enthält:
  - NLZ-Leiter → eigene Liga (Talente-Pipeline)
  - Sportkoordinator NLZ → Sub-Decision-Maker
```

**Neues Skript:** `execution/extract_decision_makers.py`

```python
#!/usr/bin/env python3
"""Extract alle Trainer-Hire-Decision-Maker pro Club.

Erweitert sd_registry.json zu decision_makers.json mit Tier-Klassifikation:
  Tier 1 (primary): direkter Trainer-Hire-Power
  Tier 2 (secondary): Mitsprache / Veto
  Tier 3 (tertiary): formal überstimmend (Vorstand bei eV / KGaA)
  Tier nlz: eigenes NLZ-Hiring

Output: data/decision_makers.json
  {
    "_meta": {extracted_at, season, total_clubs, total_decision_makers},
    "tiers": {1: count, 2: count, 3: count, "nlz": count},
    "decision_makers": [
      {
        tm_id, name, club_tm_id, club_name, league, role, section,
        tier, since_text, contract_until_text  // beide aus staff entry
      }
    ]
  }
"""
import json
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

BASE = Path(__file__).parent.parent

TIER_1_KEYWORDS = [  # primary hire-power
    "sportdirektor", "sportvorstand", "geschäftsführer sport",
    "sportgeschäftsführer", "sportlicher leiter", "technischer direktor",
    "director of football", "head of football", "head of sport",
]
TIER_2_KEYWORDS = [  # secondary
    "sportkoordinator", "leiter sport", "sportlicher koordinator",
    "kaderplaner", "head of scouting", "leiter scouting",
    "leiter lizenzbereich", "leiter lizenzspielerabteilung",
]
TIER_3_KEYWORDS = [  # tertiary (governance)
    "vorstandsvorsitzender", "vorsitzender des vorstands",
    "präsident", "vorstand", "geschäftsführer",
    "ceo", "aufsichtsratsvorsitzender",
]
NLZ_KEYWORDS = [
    "nlz-leiter", "nachwuchsleistungszentrum",
    "leiter nlz", "leiter nachwuchs", "sportkoordinator nlz",
    "leiter jugendabteilung", "head of academy", "akademiedirektor",
]

def classify_tier(role: str, section: str) -> str | None:
    rt = (role + " " + section).lower()
    if any(k in rt for k in NLZ_KEYWORDS):
        return "nlz"
    if any(k in rt for k in TIER_1_KEYWORDS):
        return "1"
    if any(k in rt for k in TIER_2_KEYWORDS):
        return "2"
    if any(k in rt for k in TIER_3_KEYWORDS):
        return "3"
    return None

def main():
    registry = json.load(open(BASE / "data/club_registry.json"))["clubs"]
    season = "2025/2026"
    bl_clubs = [c for c in registry if any(
        l in ("BL1", "BL2", "BL3")
        for l in c.get("leagues", {}).get(season, [])
    )]

    dms = []
    for c in bl_clubs:
        staff_file = BASE / f"data/staff/{c['tm_id']}.json"
        if not staff_file.exists():
            continue
        s = json.load(open(staff_file))
        seen_tm_ids = set()
        for entry in s.get("staff", []):
            tm_id = entry.get("tm_id")
            if not tm_id or tm_id in seen_tm_ids:
                continue
            tier = classify_tier(entry.get("role", ""), entry.get("section", ""))
            if not tier:
                continue
            seen_tm_ids.add(tm_id)
            dms.append({
                "tm_id": tm_id,
                "name": entry.get("name", ""),
                "club_tm_id": c["tm_id"],
                "club_name": c["name"],
                "league": next((l for l in c.get("leagues", {}).get(season, [])
                                if l in ("BL1","BL2","BL3")), None),
                "role": entry.get("role", ""),
                "section": entry.get("section", ""),
                "tier": tier,
                "since_text": entry.get("since_text") or entry.get("appointed", ""),
                "contract_until_text": entry.get("contract_until_text") or "",
            })

    tier_counts = defaultdict(int)
    for d in dms:
        tier_counts[d["tier"]] += 1

    out = BASE / "data/decision_makers.json"
    json.dump({
        "_meta": {
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "season": season,
            "total_clubs": len(bl_clubs),
            "total_decision_makers": len(dms),
        },
        "tiers": dict(tier_counts),
        "decision_makers": dms,
    }, open(out, "w"), ensure_ascii=False, indent=2)
    print(f"✓ {len(dms)} Decision-Makers extracted ({dict(tier_counts)})")

if __name__ == "__main__":
    main()
```

**Acceptance:**
- ≥150 Decision-Maker insgesamt für 56 BL-Clubs (Ø 2.5-3 pro Club)
- Tier 1 ≥ 50, Tier 2 ≥ 30, Tier 3 ≥ 40, NLZ ≥ 30
- Krösche, Bornemann, Schicker, Fritz weiter Tier 1
- Watzke (Dortmund), Heidel-Nachfolger Mainz erscheinen Tier 3
- NLZ-Leiter aller BL1-Clubs Tier "nlz"

**Run:**
```bash
python3 execution/extract_decision_makers.py
```

---

### Phase 2 — Hire-History pro Decision-Maker

**Ziel:** Pro Tier-1-DM aggregieren: welche Cheftrainer-Wechsel fanden während seiner Amtszeit am aktuellen + früheren Clubs statt? Das ist der **eigentliche Demand-Insight**, den coachinsider nicht hat.

**Datenquelle:**
- `data/staff/{club_tm_id}.json` historisch (TM-Mitarbeiter-Seite hat "ehemalige Mitarbeiter") — derzeit scrapen wir nur aktuelle. Für Phase 2 erweitern.
- `data/persons_master.json` `career_history` für SDs (existiert dank Phase 1)
- `data/persons_master.json` `career_history` für Trainer
- Zeitraum-Overlap: SD@Club-Stationen × Trainer@Club-Stationen → Hire-Kandidat

**Logik:** Wenn Trainer X bei Club Y angefangen hat während SD Z bei Club Y war, ist Z als wahrscheinlicher Hirer markiert. Ehemalige Trainer-Karrieren auswerten = Hire-Track-Record.

**Erweiterung von:** `execution/build_sd_coach_overlaps.py` (existiert) → aktuell nur BL1 24/25. Skalieren auf BL1+BL2+BL3 + alle Saisons in `career_history`.

**Neues Skript:** `execution/build_hire_history.py`

```python
#!/usr/bin/env python3
"""Build Hire-History pro SD/GF aus career_history-Overlaps.

Output: data/hire_history.json
  {
    "_meta": {built_at, total_dms, total_hires, multi_club_dms},
    "per_dm": {
      "<dm_tm_id>": {
        "name": "Markus Krösche",
        "tier": "1",
        "career": [{"club": "Eintracht Frankfurt", "role": "Sportvorstand",
                    "from": 2021, "to": 2026}, ...],
        "hires": [
          {
            "coach_tm_id": 12345,
            "coach_name": "Oliver Glasner",
            "club": "Eintracht Frankfurt",
            "year": 2021,
            "confidence": "high",  // start year matches DM tenure start ±1y
            "tenure_years": 3,
            "outcome": "regular_end" | "fired" | "active"
          }, ...
        ],
        "patterns": {
          "preferred_age_at_hire_avg": 42.5,
          "preferred_nationality": ["Deutschland", "Österreich"],
          "preferred_license": ["DFB-Pro", "ÖFB-Profitrainer"],
          "lehrgang_overrepresented": ["LG 67", "LG 70"],
          "avg_tenure_years": 2.3,
          "international_share": 0.4
        }
      }
    }
  }
"""
import json
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone

BASE = Path(__file__).parent.parent

# Pseudo-code skeleton — full implementation at run-time:
def main():
    dms = json.load(open(BASE / "data/decision_makers.json"))["decision_makers"]
    persons = json.load(open(BASE / "data/persons_master.json"))["persons"]
    licenses = json.load(open(BASE / "data/coaching_licenses.json"))

    per_dm = {}
    for dm in dms:
        if dm["tier"] not in ("1", "2"):
            continue
        # 1) Get DM career
        p = persons.get(str(dm["tm_id"]), {})
        career = p.get("career_history", []) or []
        # 2) For each (club, period) in DM career, find coaches who started at that club in that window
        hires = []
        for cs in career:
            if not cs.get("from") or not cs.get("club"):
                continue
            club_name = cs["club"]
            from_y = int(str(cs["from"])[:4]) if cs.get("from") else None
            to_y = int(str(cs["to"])[:4]) if cs.get("to") else 9999
            if not from_y:
                continue
            # Find all coaches whose career_history has this club within DM window
            for coach_tm_id, coach in persons.items():
                if coach.get("type") != "trainer":
                    continue
                for cc in (coach.get("career_history") or []):
                    if cc.get("club", "").lower() != club_name.lower():
                        continue
                    coach_from = int(str(cc.get("from", ""))[:4]) if cc.get("from") else None
                    if not coach_from:
                        continue
                    if from_y - 1 <= coach_from <= to_y:
                        # Hire candidate
                        coach_to = int(str(cc.get("to", ""))[:4]) if cc.get("to") else 9999
                        hires.append({
                            "coach_tm_id": int(coach_tm_id),
                            "coach_name": coach.get("name"),
                            "club": club_name,
                            "year": coach_from,
                            "confidence": "high" if abs(coach_from - from_y) <= 1 else "medium",
                            "tenure_years": min(coach_to, 2026) - coach_from,
                        })
        # 3) Pattern analysis
        ages = []; nationalities = []; lehrgaenge = []
        for h in hires:
            cp = persons.get(str(h["coach_tm_id"]), {})
            if cp.get("dob"):
                # age at hire
                try:
                    dob_y = int(cp["dob"][-4:])
                    ages.append(h["year"] - dob_y)
                except Exception:
                    pass
            if cp.get("nationality"):
                nat = cp["nationality"]
                if isinstance(nat, list):
                    nat = nat[0] if nat else None
                if nat:
                    nationalities.append(nat)
            # license/lehrgang lookup via coaching_licenses
            for course in licenses.get("courses", []):
                for cohort in course.get("cohorts", []):
                    for grad in cohort.get("graduates", []):
                        if grad.get("tm_id") == h["coach_tm_id"]:
                            lehrgaenge.append(f"{course.get('id','LG')} {cohort.get('year','?')}")
        nat_counter = Counter(nationalities)
        lg_counter = Counter(lehrgaenge)
        per_dm[str(dm["tm_id"])] = {
            "name": dm["name"],
            "tier": dm["tier"],
            "career": career,
            "hires": hires,
            "patterns": {
                "preferred_age_at_hire_avg": round(sum(ages)/len(ages),1) if ages else None,
                "preferred_nationality": [n for n,_ in nat_counter.most_common(3)],
                "lehrgang_overrepresented": [lg for lg,c in lg_counter.most_common() if c >= 2],
                "avg_tenure_years": round(sum(h["tenure_years"] for h in hires)/len(hires),1) if hires else None,
                "international_share": round(sum(1 for n in nationalities if n != "Deutschland")/max(1,len(nationalities)),2),
            }
        }

    out = BASE / "data/hire_history.json"
    json.dump({
        "_meta": {
            "built_at": datetime.now(timezone.utc).isoformat(),
            "total_dms": len(per_dm),
            "total_hires": sum(len(d["hires"]) for d in per_dm.values()),
            "multi_club_dms": sum(1 for d in per_dm.values() if len({h["club"] for h in d["hires"]}) > 1),
        },
        "per_dm": per_dm,
    }, open(out, "w"), ensure_ascii=False, indent=2)
    print(f"✓ Hire history built — {len(per_dm)} DMs, {sum(len(d['hires']) for d in per_dm.values())} hires")

if __name__ == "__main__":
    main()
```

**Acceptance:**
- Krösche zeigt mindestens: Glasner@Frankfurt (2021), Toppmöller@Frankfurt (2023)
- Bornemann zeigt mindestens: Streich-Nachfolger@Freiburg / vorherige Stationen
- ≥150 DMs mit ≥1 Hire
- ≥30 DMs mit Multi-Club-Karriere → erkennbares Pattern
- `lehrgang_overrepresented` zeigt für ≥10 DMs einen klaren Lehrgang-Bias

**Run:**
```bash
python3 execution/build_hire_history.py
```

**Self-anneal-Hinweise:**
- TM-Career-History für SDs ist oft unvollständig (Junior-Rollen fehlen). Falls Hire-Count <2 für >30% der DMs → manuell SD-career_history-Quellen ergänzen (LinkedIn-Scrape oder TM-Profil-Refresh erzwingen).
- Stationen-Overlap-Window: aktuell ±1y vor Trainer-Start. Falls False-Positives auftauchen, auf 0y verengen.

---

### Phase 3 — Berater-zu-SD-Mapping

**Ziel:** Welche Berater-Firma hat *welcher SD* mehrfach genutzt? Das ist die direkteste Türen-Information für projectFIVE.

**Datenquelle:** `hire_history.json` × `persons_master.json` (Feld `agent` pro Trainer).

**Logik:** Aggregiere pro SD die Berater seiner gehirten Trainer. Wenn ein Berater ≥2 Hires hat → Türen-Pattern.

**Neues Skript:** `execution/build_sd_agent_patterns.py`

```python
#!/usr/bin/env python3
"""Aggregiere Berater-Patterns pro SD.

Output: data/sd_agent_patterns.json
  {
    "per_dm": {
      "<dm_tm_id>": {
        "name": "...",
        "agent_relationships": [
          {"agent": "Lian Sports", "hires": 3, "coaches": ["Glasner", "Toppmöller", "Topal"]},
          ...
        ]
      }
    }
  }
"""
import json
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).parent.parent
AGENT_BLACKLIST = {"ohne berater", "familienangehörige", "eltern",
                   "keine angabe", "-", "n/a", "unbekannt", ""}

def main():
    hh = json.load(open(BASE / "data/hire_history.json"))["per_dm"]
    persons = json.load(open(BASE / "data/persons_master.json"))["persons"]

    out = {}
    for dm_id, dm in hh.items():
        agents = defaultdict(list)
        for h in dm["hires"]:
            cp = persons.get(str(h["coach_tm_id"]), {})
            agent = (cp.get("agent") or "").strip()
            if agent.lower() in AGENT_BLACKLIST:
                continue
            agents[agent].append(h["coach_name"])
        rels = [
            {"agent": a, "hires": len(coaches), "coaches": coaches}
            for a, coaches in sorted(agents.items(), key=lambda x: -len(x[1]))
            if len(coaches) >= 2  # nur Patterns mit ≥2 Hires
        ]
        if rels:
            out[dm_id] = {"name": dm["name"], "agent_relationships": rels}

    json.dump({"per_dm": out}, open(BASE / "data/sd_agent_patterns.json", "w"),
              ensure_ascii=False, indent=2)
    print(f"✓ {len(out)} DMs mit Agent-Patterns (≥2 Hires/Agent)")

if __name__ == "__main__":
    main()
```

**Acceptance:**
- ≥20 DMs mit Agent-Patterns
- Top-Agent pro Bundesliga-SD identifizierbar (z.B. CAA Stellar, ROGON, SportsTotal)
- Doppelte Pflege ROGON × Krösche → falls vorhanden, sichtbar

**Run:**
```bash
python3 execution/build_sd_agent_patterns.py
```

---

### Phase 4 — coachinsider SD/GF-CSV-Diff (analog Trainer)

**Ziel:** Falls coachinsider auch SDs/GFs listet → analoger Diff wie für Trainer (`execution/diff_coachinside_csvs.py` Pattern).

**Voraussetzung:** Nutzer fragen, ob er coachinsider-CSVs für SDs/GFs hat. Wenn ja → in `data/coachinside_csvs/` ablegen mit Filename `coachinside_sds.csv` / `coachinside_gfs.csv`.

**Wenn CSVs vorhanden:**

Neues Skript: `execution/diff_coachinside_sds.py` (Copy von `diff_coachinside_csvs.py`):
- Lädt CSVs
- Cross-Reference gegen `decision_makers.json` (nicht `persons_master.json`, weil DM-Scope wichtiger)
- Output: `data/coachinside_sd_gap_report.json`
  - matched
  - matched-no-network (haben TM-ID, aber kein SD-Network → priorisierter Build-Target)
  - missing (nicht im DM-Registry → entweder neu in TM scrapen oder Tier neu klassifizieren)

**Wenn CSVs fehlen:** Tasks anlegen mit Hinweis "Nutzer um Export bitten" → Phase 4 skip → Phase 5 weiter.

---

### Phase 5 — Vertragslaufzeiten (SD-Hot-Seat)

**Ziel:** TM-Profile haben für SDs/Manager `Vertrag bis`-Feld. Extrahieren analog zu Trainer-Vertragsdaten (`scrape_coach_contracts.md`).

**Erweiterung von:** `execution/scrape_coach_contracts.py` → Subjekt-Klasse erweitern auf SDs.

```bash
python3 execution/scrape_coach_contracts.py --subject sd --refresh-all
```

(Falls das Skript noch nicht SD-fähig ist: `--subject`-Flag einbauen + auf TM-Trainer-Profil-Pfad analog zu SD-Profil-Pfad mappen — beide nutzen `/profil/trainer/{id}` und `/profil/spieler/{id}`-Mischung.)

**Output:** `data/sd_contracts.json` mit pro DM: `contract_until`, `joined`, `extension_history`.

**Hot-Seat-SD-Score:** Optional in Phase 6/7. Hier nur Daten extrahieren.

---

### Phase 6 — DM-Networks erweitern

**Ziel:** Bestehende SD-Networks mit Hire-History + Agent-Patterns + Tier-2/Tier-3-Personen anreichern.

**Erweiterung:** `execution/build_coach_network.py` Step 6 (neu)

In Step 6 für DMs:
1. Lade `hire_history.json` + `sd_agent_patterns.json` für aktuellen DM (wenn `network.center.tier` in 1/2/3/nlz).
2. Füge `hires` als neue Kategorie `coach_hired` mit Badge "H" hinzu (Farbe: orange `#e67e22`).
3. Füge Top-3-Agent-Patterns als Detail-Panel-Block "Agent-Beziehungen" hinzu.
4. Tier-2/Tier-3-DMs am gleichen Club als Kategorie `co_decision_maker` mit Badge "D".

**Acceptance:**
- Krösche-Dashboard zeigt Glasner + Toppmöller als "H"-Kontakte
- Detail-Panel zeigt "Agent-Beziehungen: ROGON (3 Hires: ...), CAA Stellar (2 Hires: ...)"
- Kontaktzahl Krösche +5-10 (Hires + Co-DMs)

**Run:**
```bash
# Re-Build alle SD-Networks
python3 execution/build_all_sd_networks.py 2>&1 | tee logs/sd_phase2_$(date +%Y%m%d_%H%M).log
# ~30s × ~150 DMs = ~75 min
```

---

### Phase 7 — Index-Section "Decision-Makers"

**Ziel:** Eigene Sektion auf Index-Page neben Trainer-Sektionen.

**Erweiterung:** `execution/generate_all_bl_coaches.py` (oder neuer Path: `execution/generate_decision_maker_section.py` und Inject als sub-section).

**Layout:**
```
Decision-Makers · Hire-Patterns
─────────────────────────────────
| Tier | Name           | Verein            | Hires | Top-Agent       | Vertrag bis | NET |
|------|----------------|-------------------|------:|-----------------|-------------|-----|
|  1   | Markus Krösche | Eintracht Frankfurt|  4   | ROGON (3)       | 2027        | →   |
|  1   | Andreas Bornem.| SC Freiburg       |  2   | SportsTotal (2) | 2028        | →   |
| ...
```

Filter:
- Tier (1/2/3/NLZ)
- Liga (BL1/BL2/BL3)
- Verein
- min. Hires (≥0/1/3/5)

**Acceptance:**
- Sektion `<div id="decision-makers">` rendert auf Index
- Mindestens 100 DMs sichtbar
- Klick auf Zeile → öffnet `{slug}_sd_network.html`
- "Tier 1 only" als Default-Filter (Power-User können erweitern)

---

### Phase 8 — Coachinsider-Wettbewerbs-Vergleich (Stakeholder-Output)

**Ziel:** Eine Statistik-Tabelle für den Stakeholder-Pitch.

**Output:** `output/stakeholder_demand.html` (oder Erweiterung von `output/stakeholder.html`).

| Dimension | coachinsider | projectFIVE Tool |
|-----------|--------------|------------------|
| SDs aktiv DACH | (User-Input) | {tier_1_count} |
| GFs / Vorstand Sport | (?) | {tier_3_count} |
| NLZ-Leiter | (?) | {nlz_count} |
| Hire-History pro SD | nicht öffentlich | Ø {avg_hires} pro DM |
| Agent-Patterns | nicht öffentlich | {agent_pattern_count} DMs mit ≥2-Hire-Agents |
| Vertragslaufzeit | nicht öffentlich | {contract_count} DMs mit `contract_until` |

**Acceptance:**
- HTML-Sektion ergänzt an `output/stakeholder.html` als 5. Pillar "Demand-Side"
- Zahlen aus `decision_makers.json` + `hire_history.json` + `sd_agent_patterns.json` programmatisch generiert (kein Hardcoding)

---

## Master-Wrapper

`run_sd_deep_coverage.sh`:

```bash
#!/usr/bin/env bash
# Sprint F · SD/GF Deep Coverage
# Empfehlung: nach run_overnight.sh ausführen, damit Staff-Daten frisch sind.
set -uo pipefail
cd "$(dirname "$0")"

START_TS=$(date +%s)
RUN_ID="sd_deep_$(date +%Y%m%d_%H%M)"
LOG_DIR="logs/$RUN_ID"
mkdir -p "$LOG_DIR"
NTFY_TOPIC="${NTFY_TOPIC:-cmk-coachdb}"
ntfy() { curl -s -d "$1" "https://ntfy.sh/${NTFY_TOPIC}" >/dev/null 2>&1 || true; }
note() {
  echo ""
  echo "═══ $1 @ $(date '+%H:%M:%S') ═══"
}

ntfy "SD Deep Coverage gestartet"

note "[1/8] Decision-Maker Registry"
python3 execution/extract_decision_makers.py > "$LOG_DIR/01_dm_registry.log" 2>&1 || true
tail -3 "$LOG_DIR/01_dm_registry.log"

note "[2/8] Hire-History"
python3 execution/build_hire_history.py > "$LOG_DIR/02_hire_history.log" 2>&1 || true
tail -3 "$LOG_DIR/02_hire_history.log"

note "[3/8] Agent-Patterns"
python3 execution/build_sd_agent_patterns.py > "$LOG_DIR/03_agent_patterns.log" 2>&1 || true
tail -3 "$LOG_DIR/03_agent_patterns.log"

note "[4/8] Coachinsider SD-Diff (skip wenn keine CSVs)"
[ -f data/coachinside_csvs/coachinside_sds.csv ] && \
  python3 execution/diff_coachinside_sds.py > "$LOG_DIR/04_csv_diff.log" 2>&1 || \
  echo "  (skipped — keine SD-CSV vorhanden)"

note "[5/8] SD-Vertragslaufzeiten"
python3 execution/scrape_coach_contracts.py --subject sd --refresh-all \
  > "$LOG_DIR/05_contracts.log" 2>&1 || true

note "[6/8] DM-Networks (re)build"
python3 execution/build_all_sd_networks.py --include-tier-2 --include-nlz \
  > "$LOG_DIR/06_networks.log" 2>&1 || true

note "[7/8] Index-Page mit DM-Section"
python3 execution/generate_all_bl_coaches.py --include-historical --include-decision-makers \
  > "$LOG_DIR/07_index.log" 2>&1 || true
python3 execution/generate_club_pages.py > "$LOG_DIR/07b_clubs.log" 2>&1 || true

note "[8/8] Vercel Deploy"
cd output
DEPLOY_URL=$(npx vercel deploy --prod --yes --scope cmk2299s-projects 2>&1 \
  | tee "../$LOG_DIR/08_deploy.log" | grep -oE 'https://[^ ]+vercel\.app' | tail -1)
cd ..

END_TS=$(date +%s)
DURATION_MIN=$(( (END_TS - START_TS) / 60 ))
DM_COUNT=$(python3 -c "import json; print(json.load(open('data/decision_makers.json'))['_meta']['total_decision_makers'])" 2>/dev/null || echo "?")
HIRES=$(python3 -c "import json; print(json.load(open('data/hire_history.json'))['_meta']['total_hires'])" 2>/dev/null || echo "?")

note "✓ DONE — $DURATION_MIN min"
echo "  Decision-Makers: $DM_COUNT"
echo "  Hires erfasst:   $HIRES"
echo "  Logs:            $LOG_DIR/"
echo "  Deploy:          ${DEPLOY_URL:-(see 08_deploy.log)}"

ntfy "✓ SD Deep DONE — $DURATION_MIN min · $DM_COUNT DMs · $HIRES Hires · ${DEPLOY_URL:-deploy.log}"
```

**Run:**
```bash
chmod +x run_sd_deep_coverage.sh
bash run_sd_deep_coverage.sh
```

---

## Stakeholder-Argumentation

**Vor Sprint F:** "Wir haben SDs als Center" (Phase 1) — *Listing*.
**Nach Sprint F:** "Wir wissen pro SD, *welche Trainer er holt*, *durch welche Berater*, *mit welchen Patterns*, *wie lange sein Vertrag läuft*" — *Decision-Layer*.

Coachinsider listet Personen. projectFIVE-Tool zeigt **Patterns pro Person**. Das ist der Berater-Workflow-USP, den der Stakeholder gefordert hat.

---

## Edge-Cases

1. **Mehrere DMs gleicher Tier am Club** (z.B. Sportvorstand + Sportdirektor): beide in Registry, beide eigene Networks. Cross-Link über `co_decision_maker`-Kategorie.
2. **DM ohne TM-Profil** (z.B. Aufsichtsrats-Mitglieder): in `decision_makers.json` mit `tm_id: null` aufnehmen, Network überspringen, nur als String-Referenz im Coach-Dashboard zeigen.
3. **Hire-History bei jungen DMs** (<2 Jahre Amtszeit): Patterns leer, `patterns: null` setzen — UI zeigt "Datenlage zu jung".
4. **Vereins-Wechsel des SD mid-Saison** (z.B. Eberl Bayern → Inter Mailand): aktueller Eintrag in Registry, alte Stationen in `career_history`. Hire-History deckt beides ab.
5. **DM ist Ex-Trainer** (z.B. Ole Werner irgendwann SD): persons_master `type` ist `trainer`, aber DM-Tier-Klassifikation greift trotzdem über `staff`-Section. Doppel-Listing möglich (als Trainer und DM) — Decision: ja, das ist akzeptabel und sogar wertvoll (zeigt Karriere-Übergang).

---

## Validierung post-Deploy

```bash
# DM-Section auf Index erreichbar?
curl -s https://coach-network-explorer.vercel.app/ | grep -c 'decision-makers'
# Erwartung: ≥1

# Krösche-Dashboard zeigt Glasner als "H"-Kategorie?
curl -s https://coach-network-explorer.vercel.app/dashboards/markus_kroesche_sd_network.html \
  | grep -c '"category":"coach_hired"'
# Erwartung: ≥2

# Stakeholder-Page hat Demand-Pillar?
curl -s https://coach-network-explorer.vercel.app/stakeholder.html | grep -c 'Demand-Side'
# Erwartung: 1
```

---

## Open Questions für Nutzer (vor Sprint-Start klären)

1. **Coachinsider SD-Export:** hast du Excel/CSV-Listen mit SDs/GFs vom coachinsider, analog zu den Trainer-CSVs? Wenn ja → Phase 4 wird durchgeführt; wenn nein → Phase 4 skippen oder durch manuelles Cross-Check ersetzen.
2. **NLZ-Tier-Inklusion:** sollen NLZ-Leiter direkt in der Decision-Maker-Section sichtbar sein, oder als eigene "Talente-Pipeline"-Section parallel? (Empfehlung: eigene Section, Sprint G.)
3. **Vorstand/CEO-Tier:** sollen Vorstandsvorsitzende (Watzke-Pattern, Heidel-Nachfolger) in Tier 3 oder als eigene Tier "governance" laufen? (Empfehlung: Tier 3 — sind Trainer-Hire-relevant via Veto-Power, aber nicht primär.)
4. **International:** sollen ausländische SDs (z.B. PSV, Brighton, FCB) hier auch rein, oder nur DACH+BL3? (Empfehlung: DACH+BL3 für Sprint F, international als Sprint G.)

---

## Erwartetes Stakeholder-Outcome

Nach Sprint F:
- **150-200 Decision-Makers** in der Plattform (vorher ~45 SDs)
- **400-600 dokumentierte Hire-Events** mit Patterns (vorher ~33 BL1-Overlaps)
- **Agent-Patterns für 20-40 DMs** (vorher 0)
- **Vertragslaufzeiten für ~50 DMs** (vorher 0)
- **Stakeholder-Page**: 5. Pillar "Demand-Side" mit konkreten Zahlen vs. coachinsider

Damit hat projectFIVE-Berater zum ersten Mal nicht nur "wer ist mit wem verbunden", sondern "**wer entscheidet wie, mit welchen Türen, wann verfügbar**" — der Daily-Driver-USP greift.

---

## Sprint-Reihenfolge

```
✅ Sprint A    LG 70/71 + Lehrgang-Tiefe (DONE)
✅ Sprint B    NLZ Variant-2 Discovery (DONE)
✅ Sprint C    Trainerstab Tier 1+2 Mass-Coverage (DONE)
✅ coachinsider Trainer-Diff (Pipeline läuft)
↓
→  Sprint F    SD/GF Deep Coverage (DIESE Directive)
   Sprint G    NLZ-Trainer eigenes Network-Cluster
   Sprint H    Spielstil-Tags + Formationen + Sprachen
   Sprint I    Berater-Workflow CRM-light (Pipeline-Stages)
```

Sprint F ist Voraussetzung für Sprint I (CRM-Workflow braucht Demand-Side-Tiefe um Pipeline-Stages zu modellieren).
