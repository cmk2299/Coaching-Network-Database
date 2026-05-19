# Directive: Sprint G — NLZ-Trainer eigenes Cluster (Talente-Pipeline)

**Trigger-Phrase für Claude Code:** "Build NLZ trainer cluster" oder "/nlz-cluster"

**Bezugnehmend auf:**
- USP #2 *Nachwuchs-Pipeline* — NLZ-Trainer als Aufstiegs-Kandidaten 2027+
- Sprint B: Variant-2 NLZ-Sub-Verein-Discovery (✅ DONE) — ~150-200 Sub-Vereine in `club_registry.json`
- Stakeholder-Brief 2026-05-04: "Coachinside listet ähnlich, wir zeigen Bindungs-Tiefe + Aufstiegs-Story"

**Mission-Wert:** projectFIVE-Berater suchen **kommende Trainer**, nicht nur etablierte. Die Trainer, die 2027/28/29 in der BL ankommen, trainieren heute U17/U19. Coachinsider listet sie nicht systematisch — wir bauen die **Pipeline-Sicht**.

**Aufwand:** ~4-6h (Registry-Extract + Profile-Scrape + reduced Networks + Index-Section + Cross-Drilldown + Deploy).

**Risiko:** Mittel — viele NLZ-Trainer haben dünne TM-Profile, Karriere-Daten oft Fragmenten. Reduce-Scope-Strategie nötig.

---

## Voraussetzungen

```bash
# Sprint B-Output prüfen
python3 -c "
import json
reg = json.load(open('data/club_registry.json'))['clubs']
nlz_clubs = [c for c in reg if c.get('parent_tm_id') or c.get('is_nlz')]
print(f'{len(nlz_clubs)} NLZ-Sub-Vereine im Registry')
"
# Erwartung: ≥150
ls data/staff/*.json | wc -l   # erwartet: ≥850 inkl. NLZ-Sub-Clubs
```

Wenn nicht erfüllt: erst Sprint B durchziehen (Variant-2-Discovery + Staff-Scrape).

---

## Status Quo

| Komponente | Stand |
|------------|-------|
| NLZ-Sub-Vereine im Registry | ~150-200 (Sprint B) |
| Staff-Files für NLZ-Clubs | gemischt — manche scraped, manche nicht |
| NLZ-Trainer-Profile in persons_master | unbekannt (vermutet ~600-1000) |
| NLZ-Trainer-Networks | 0 (kein systematischer Build) |
| Index-Section "Talente-Pipeline" | fehlt |
| Cross-Drilldown NLZ-Trainer ↔ Profi-Trainer | fehlt |

---

## Sprint-Phasen

### Phase 1 — NLZ-Trainer Registry extrahieren

**Ziel:** Aus allen NLZ-Sub-Vereinen die Trainer pro Altersklasse listen.

**Pattern (aus staff/{nlz_club_tm_id}.json):**
```
"Trainerstab"-Sektion enthält:
  - Cheftrainer → primär (head_coach pro Team)
  - Co-Trainer → sekundär
  - Torwart-Trainer → sekundär
  
Team-Klassifikation aus Verein-Name:
  - Endung "U10" / "U11" / "U12" / "U13" → Tier "U10-13"
  - Endung "U14" / "U15" / "U16" / "U17" → Tier "U14-17"
  - Endung "U18" / "U19" → Tier "U19"
  - Endung "U20" / "U21" / "U23" / "II" / "Reserve" → Tier "U23"
```

**Neues Skript:** `execution/extract_nlz_trainer_registry.py`

```python
#!/usr/bin/env python3
"""Extract aller NLZ-Trainer pro Tier aus Sub-Verein-Staff.

Output: data/nlz_trainer_registry.json
  {
    "_meta": {extracted_at, season, total_nlz_clubs, total_trainers,
              tiers: {U10-13: n, U14-17: n, U19: n, U23: n}},
    "trainers": [
      {tm_id, name, club_tm_id, club_name, parent_club, tier,
       role, section, age_group_label}
    ]
  }
"""
import json
import re
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

BASE = Path(__file__).parent.parent
SEASON = "2025/2026"

TIER_PATTERNS = [
    ("U10-13", re.compile(r"\bU\s?(10|11|12|13)\b", re.I)),
    ("U14-17", re.compile(r"\bU\s?(14|15|16|17)\b", re.I)),
    ("U19",    re.compile(r"\bU\s?(18|19)\b", re.I)),
    ("U23",    re.compile(r"\b(U\s?(20|21|23)|II|Reserve|Amateure?|2\.\s*Mannschaft)\b", re.I)),
]
ROLE_KEEP = {"head_coach", "assistant_coach", "goalkeeper_coach", "co_trainer"}

def detect_tier(club_name: str) -> str | None:
    for tier, pat in TIER_PATTERNS:
        if pat.search(club_name):
            return tier
    return None

def main():
    reg = json.load(open(BASE / "data/club_registry.json"))["clubs"]
    nlz_clubs = [c for c in reg if c.get("parent_tm_id") or c.get("is_nlz")]
    print(f"Loaded {len(nlz_clubs)} NLZ sub-clubs from registry")

    trainers = []
    seen = set()
    tier_counter = defaultdict(int)
    for c in nlz_clubs:
        tier = detect_tier(c["name"])
        if not tier:
            continue
        path = BASE / f"data/staff/{c['tm_id']}.json"
        if not path.exists():
            continue
        try:
            sd = json.load(open(path))
        except Exception:
            continue
        for entry in sd.get("staff", []):
            tm_id = entry.get("tm_id")
            if not tm_id or tm_id in seen:
                continue
            section = (entry.get("section") or "").strip()
            role = (entry.get("role") or "").strip().lower()
            if section != "Trainerstab":
                continue
            if role not in ROLE_KEEP and "cheftrainer" not in (entry.get("role_text") or "").lower():
                continue
            seen.add(tm_id)
            trainers.append({
                "tm_id": int(tm_id),
                "name": entry.get("name", ""),
                "club_tm_id": c["tm_id"],
                "club_name": c["name"],
                "parent_club": c.get("parent_club") or c.get("parent_name") or "",
                "tier": tier,
                "role": role,
                "section": section,
                "age_group_label": tier.replace("-", "–"),
            })
            tier_counter[tier] += 1

    out = BASE / "data/nlz_trainer_registry.json"
    json.dump({
        "_meta": {
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "season": SEASON,
            "total_nlz_clubs": len(nlz_clubs),
            "total_trainers": len(trainers),
            "tiers": dict(tier_counter),
        },
        "trainers": trainers,
    }, open(out, "w"), ensure_ascii=False, indent=2)
    print(f"✓ {len(trainers)} NLZ-Trainers extracted ({dict(tier_counter)})")

if __name__ == "__main__":
    main()
```

**Acceptance:**
- ≥600 NLZ-Trainer insgesamt (über alle Tiers)
- U19-Tier ≥150 (BL-NLZ + 2. Bundesliga-NLZ + 3. Liga-NLZ)
- U14-17-Tier ≥250
- mindestens 50 BL1-Vereine haben ≥3 NLZ-Trainer in der Liste
- Top-15-NLZ-Vereine (Bayern, Dortmund, Leipzig, Schalke, Hoffenheim, Stuttgart, Frankfurt, Mainz, Leverkusen, Wolfsburg, Bremen, Köln, Hertha, M'gladbach, HSV) komplett abgedeckt

**Run:**
```bash
python3 execution/extract_nlz_trainer_registry.py
```

---

### Phase 2 — Profile-Coverage-Check + Scrape Missing

**Ziel:** Sicherstellen, dass jeder NLZ-Trainer in `persons_master.json` ein Profil hat.

```bash
python3 << 'PY'
import json
from pathlib import Path
BASE = Path(".")
reg = json.load(open(BASE / "data/nlz_trainer_registry.json"))["trainers"]
persons = json.load(open(BASE / "data/persons_master.json"))["persons"]
missing = []
stale = []
for t in reg:
    p = persons.get(str(t["tm_id"]))
    if not p:
        missing.append(t)
    elif not p.get("career_history"):
        stale.append(t)
print(f"{len(reg)} trainers, {len(missing)} missing, {len(stale)} ohne career_history")
if missing[:5]:
    print("First missing:", [(t["tm_id"], t["name"]) for t in missing[:5]])
PY
```

Falls `missing > 50`: Batch-Scrape via existierendem `scrape_person_profiles.py`.

```bash
python3 execution/scrape_person_profiles.py --tm-ids-from-file data/nlz_trainer_registry.json \
  --type trainer --max-age-days=180
```

(Falls das Flag `--tm-ids-from-file` noch nicht existiert: kleines Helper-Skript schreiben das die `tm_id`-Liste extrahiert und subprocess-loop fährt.)

**Acceptance:**
- ≥95% der NLZ-Trainer in persons_master mit Mindest-Coverage (name, dob, nationality)
- Restliche <5% in `data/nlz_trainer_unmatched.json` für Manual-Review

---

### Phase 3 — Reduced-Scope Networks

**Ziel:** NLZ-Trainer haben anderes Netzwerk-Profil als Profi-Trainer:
- weniger Stationen (oft 1-3 vs. 8+ bei Profis)
- mehr Cohort-Connections (Lehrgang ist wichtiger als Karriere)
- Mitspieler weniger relevant (viele waren keine Profi-Spieler)
- Spielerstab des aktuellen NLZ-Teams = primärer Kontakt-Pool

**Strategie:** `build_coach_network.py` nutzen, aber mit **NLZ-Mode-Flag** der die Tiefe reduziert:
- `max_depth=2` (statt unbegrenzt)
- `skip_former_teammates=True` (reduziert Noise)
- `keep_lehrgang=True`
- `keep_age_group_peers=True` (alle U19-Trainer derselben Region als Cohort)

**Erweiterung von:** `execution/build_coach_network.py` um `--mode nlz` Flag.

**Neues Skript:** `execution/build_all_nlz_networks.py`

```python
#!/usr/bin/env python3
"""Builds reduced-scope Networks für alle NLZ-Trainer.

Output:
  data/networks/{tm_id}.json (reduced flag im _meta)
  output/dashboards/{slug}_nlz_network.html (Suffix _nlz_network)
"""
import json, time, sys, subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from lib.normalization import slugify

BASE = Path(__file__).parent.parent
NETS = BASE / "data" / "networks"
OUT_DASH = BASE / "output" / "dashboards"

def run_build(tm_id: int, name: str, log_handle) -> bool:
    try:
        r1 = subprocess.run(
            ["python3", "execution/build_coach_network.py",
             "--tm-id", str(tm_id), "--mode", "nlz"],
            cwd=BASE, capture_output=True, text=True, timeout=120,
        )
        if r1.returncode != 0:
            log_handle.write(f"  [{name} {tm_id}] build failed: {r1.stderr[-300:]}\n")
            return False
        net_file = NETS / f"{tm_id}.json"
        if not net_file.exists():
            return False
        slug = slugify(name)
        dash = OUT_DASH / f"{slug}_nlz_network.html"
        r2 = subprocess.run(
            ["python3", "execution/generate_dashboard.py",
             "--network", str(net_file), "--output", str(dash)],
            cwd=BASE, capture_output=True, text=True, timeout=60,
        )
        return r2.returncode == 0
    except Exception as e:
        log_handle.write(f"  [{name} {tm_id}] ERR {e}\n")
        return False

def main():
    reg = json.load(open(BASE / "data/nlz_trainer_registry.json"))["trainers"]
    print(f"Building {len(reg)} NLZ-Networks...")
    success = 0; failed = 0
    t0 = time.time()
    log_path = BASE / f"logs/nlz_networks_{time.strftime('%Y%m%d_%H%M')}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w") as lh:
        for i, t in enumerate(reg, 1):
            elapsed = time.time() - t0
            eta = (elapsed / i) * (len(reg) - i) if i > 0 else 0
            print(f"  [{i:>4}/{len(reg)}] {t['name'][:24]:<24} ({t['tier']:<7}) "
                  f"@ {t['parent_club'][:18]:<18} ETA {eta/60:.0f}min", flush=True)
            ok = run_build(t["tm_id"], t["name"], lh)
            if ok: success += 1
            else: failed += 1
    print(f"\nDone: {success} ok, {failed} failed ({(time.time()-t0)/60:.0f} min)")

if __name__ == "__main__":
    main()
```

**Acceptance:**
- ≥80% der NLZ-Trainer mit Network gebaut
- Median Kontakte pro NLZ-Network: 30-80 (nicht 200-300 wie Profi)
- Lehrgang-Connections, falls vorhanden, sichtbar
- Build-Time pro Network: ~15s (schneller als Profi-Build wegen reduced scope)

**Run:**
```bash
python3 execution/build_all_nlz_networks.py 2>&1 | tee logs/nlz_phase3_$(date +%Y%m%d_%H%M).log
```

Erwartete Runtime: ~15s × 600 = ~150 min (~2.5h).

---

### Phase 4 — Index-Section "Talente-Pipeline"

**Ziel:** Eigene Sektion auf Index-Page mit Tier-Filter + Aufstiegs-Story.

**Erweiterung:** `execution/generate_all_bl_coaches.py` neue Sektion `<div id="nlz-pipeline">`.

**Layout:**
```
Talente-Pipeline · NLZ-Trainer
─────────────────────────────────
[Tier-Filter: U10-13 | U14-17 | U19 | U23]   [Verein-Filter: Bayern, Dortmund, ...]

| Tier | Trainer        | Verein           | Stationen | Lehrgang | NET |
|------|----------------|------------------|----------:|----------|-----|
| U19  | Patrick Glöckner| Borussia Dortmund |     3     | LG 68    |  →  |
| U17  | ...            | ...              |     2     | A-Lizenz |  →  |
| ...
```

**UX-Hinweis:**
- Tier-Reihenfolge `U23 > U19 > U14-17 > U10-13` (Aufstiegs-Wahrscheinlichkeit absteigend)
- Default-Filter: U19 + U23 (Berater-Use-Case = nahbare Aufstiegs-Kandidaten)
- "Aufstiegs-Indikator": wenn Trainer Lehrgang LG 68+ hat, gelbes Sterne-Badge

**Acceptance:**
- Sektion `<div id="nlz-pipeline">` rendert
- Tier-Filter funktioniert (CSS `.hidden` Toggle)
- Mindestens 200 NLZ-Trainer sichtbar
- Klick auf Zeile → öffnet `{slug}_nlz_network.html`
- Aufstiegs-Indikator-Badge auf ~30-50 Trainern

---

### Phase 5 — Cross-Drilldown NLZ ↔ Profi

**Ziel:** Wenn ein NLZ-Trainer später Profi-Trainer wird, müssen beide Networks verlinkt sein.

**Pattern erkennen:**
- NLZ-Trainer-Profil hat `career_history` mit späteren Profi-Stationen
- Profi-Trainer hat oft NLZ-Stationen in seiner Karriere (z.B. Hoeneß VfB-U19 vor Profi)

**Logik:** In `build_coach_network.py` Step 7 (neu):
- Wenn `mode="nlz"` und Trainer hat Profi-Network gleichzeitig → Cross-Link beide Dashboards
- Wenn `mode="profi"` und Trainer hat NLZ-Stationen → Cross-Link unten als "Vorherige NLZ-Tätigkeit"

**Acceptance:**
- Min. 50 Cross-Links existieren (NLZ ↔ Profi für gleiche Person)
- Sebastian Hoeneß-Dashboard zeigt seine VfB-U19-Vorgeschichte (falls Daten vorhanden)
- Bei Klick auf NLZ-Station im Profi-Dashboard → öffnet NLZ-Dashboard wenn vorhanden

---

### Phase 6 — Stakeholder-Pillar #2 mit Zahlen

**Ziel:** USP #2 *Nachwuchs-Pipeline* von Pitch-Behauptung → konkrete Zahlen.

**Erweiterung:** `output/stakeholder.html` Pillar #2 ergänzen:

```html
<div class="pillar pillar-talente">
  <div class="pillar-num">02</div>
  <h3>Nachwuchs-Pipeline · Aufstiegs-Kandidaten 2027+</h3>
  <p class="pillar-claim">Coachinsider listet Profi-Trainer. Wir zeigen die <strong>{nlz_count} NLZ-Trainer</strong>, 
  die heute U17/U19 trainieren — und 2027/28 in der BL ankommen.</p>
  <ul class="pillar-stats">
    <li>{nlz_count} NLZ-Trainer aktiv</li>
    <li>{u19_count} davon U19 oder U23 — direkt-Profi-relevant</li>
    <li>{cohort_match_count} bereits in DFB-Cohorten</li>
    <li>{cross_link_count} Cross-Links zu Profi-Karrieren</li>
  </ul>
  <a href="/index.html#nlz-pipeline" class="btn-pillar">→ Talente-Pipeline öffnen</a>
</div>
```

Zahlen werden zur Build-Zeit aus `nlz_trainer_registry.json` + `coaching_licenses.json` injiziert.

**Acceptance:**
- Pillar zeigt 4 dynamische Zahlen
- Link auf `#nlz-pipeline` funktioniert (Anchor + Filter pre-applied)

---

## Master-Wrapper

`run_nlz_cluster.sh`:

```bash
#!/usr/bin/env bash
# Sprint G · NLZ-Trainer Talente-Pipeline
# Voraussetzung: Sprint B (Variant-2 Discovery) durch
set -uo pipefail
cd "$(dirname "$0")"

START_TS=$(date +%s)
RUN_ID="nlz_$(date +%Y%m%d_%H%M)"
LOG_DIR="logs/$RUN_ID"
mkdir -p "$LOG_DIR"
NTFY_TOPIC="${NTFY_TOPIC:-cmk-coachdb}"
ntfy() { curl -s -d "$1" "https://ntfy.sh/${NTFY_TOPIC}" >/dev/null 2>&1 || true; }
note() {
  echo ""
  echo "═══ $1 @ $(date '+%H:%M:%S') ═══"
}

ntfy "NLZ Cluster gestartet"

note "[1/6] NLZ-Trainer Registry"
python3 execution/extract_nlz_trainer_registry.py > "$LOG_DIR/01_registry.log" 2>&1 || true
tail -3 "$LOG_DIR/01_registry.log"

note "[2/6] Profile-Coverage-Check + Missing-Scrape"
python3 execution/scrape_nlz_trainer_profiles.py > "$LOG_DIR/02_profiles.log" 2>&1 || true

note "[3/6] NLZ-Networks bauen"
python3 execution/build_all_nlz_networks.py > "$LOG_DIR/03_networks.log" 2>&1 || true

note "[4/6] Index-Section Talente-Pipeline"
python3 execution/generate_all_bl_coaches.py --include-historical --include-nlz \
  > "$LOG_DIR/04_index.log" 2>&1 || true

note "[5/6] Cross-Drilldown NLZ ↔ Profi (Re-build betroffener Profi-Networks)"
python3 execution/regenerate_dashboards.py --lazy 500000 \
  > "$LOG_DIR/05_drilldown.log" 2>&1 || true

note "[6/6] Vercel Deploy"
cd output
DEPLOY_URL=$(npx vercel deploy --prod --yes --scope cmk2299s-projects 2>&1 \
  | tee "../$LOG_DIR/06_deploy.log" | grep -oE 'https://[^ ]+vercel\.app' | tail -1)
cd ..

END_TS=$(date +%s)
DURATION_MIN=$(( (END_TS - START_TS) / 60 ))
NLZ_COUNT=$(python3 -c "import json; print(json.load(open('data/nlz_trainer_registry.json'))['_meta']['total_trainers'])" 2>/dev/null || echo "?")
NLZ_NETS=$(ls data/networks/*.json 2>/dev/null | wc -l)

note "✓ NLZ DONE — $DURATION_MIN min"
echo "  NLZ-Trainer:  $NLZ_COUNT"
echo "  Networks:     $NLZ_NETS"
echo "  Logs:         $LOG_DIR/"
echo "  Deploy:       ${DEPLOY_URL:-(see 06_deploy.log)}"

ntfy "✓ NLZ DONE — $DURATION_MIN min · $NLZ_COUNT NLZ-Trainer · ${DEPLOY_URL:-deploy.log}"
```

**Run:**
```bash
chmod +x run_nlz_cluster.sh
bash run_nlz_cluster.sh
```

---

## Edge-Cases

1. **NLZ-Trainer mit nur U-Mannschaft als Karriere** → reduced-scope-network ist klein (10-30 Kontakte). UI-Hinweis: „Profil im Aufbau" wenn Kontakt-Anzahl <15.
2. **Doppel-Funktion U17 + U19** → Eintrag in beide Tiers. Deduplication per `tm_id` in der Top-Level-Liste, aber Tier-Tags multi-value.
3. **NLZ-Trainer ohne TM-Profil** (klein/Amateur-Betrieb) → in `data/nlz_trainer_unmatched.json` mit Hinweis. Manuell ergänzbar via `data/trainer_profile_overrides.json`.
4. **Frauenfußball-NLZ** (z.B. Bayern Frauen U17): in eigenes Tier-Tag „W-U17/U19" → optional als Phase G2 separater Filter.
5. **Karriere-Sprung U19→Profi vor 2024** (z.B. Polzin HSV-U19→Profi): Cross-Link historisch nicht immer in TM dokumentiert — nutze `coachinside_csvs` als Validation-Hilfe.

---

## Validierung post-Deploy

```bash
# NLZ-Section auf Index?
curl -s https://coach-network-explorer.vercel.app/ | grep -c 'nlz-pipeline'   # ≥1

# Beispiel-NLZ-Network erreichbar?
curl -s -o /dev/null -w "%{http_code}\n" \
  https://coach-network-explorer.vercel.app/dashboards/patrick_gloeckner_nlz_network.html
# Erwartung: 200 (oder ähnlicher BVB-NLZ-Trainer)

# Stakeholder-Pillar #2 mit Zahlen?
curl -s https://coach-network-explorer.vercel.app/stakeholder.html | grep -c 'NLZ-Trainer aktiv'   # 1
```

---

## Open Questions für Nutzer

1. **Frauenfußball-NLZ separat?** — eigenes Tier oder integriert? (Default: integriert, eigenes Tag-Filter.)
2. **U23 oder Reserve-Mannschaft als Profi-äquivalent?** — manche Vereine (BVB II, RB Leipzig II) sind 3.-Liga-Teams mit eigenen Profi-Strukturen. Default: U23 als eigenes Tier behandeln, aber Aufstiegs-Indikator-Badge schon ab U19+.
3. **DFB-Stützpunkt-Trainer / Honorartrainer** — gehören die rein? Vermutung: nein, zu volatile/teilzeit. Default: nur fest angestellte NLZ-Trainer.

---

## Erwartetes Stakeholder-Outcome

Nach Sprint G:
- **600-800 NLZ-Trainer** in der Plattform (vorher 0 systematisch)
- **~150 U19-Trainer** als direkte Aufstiegs-Kandidaten 2027+
- **~30-50 Cross-Links** NLZ↔Profi-Karriere
- **Stakeholder-Pillar #2** wird von Behauptung zu konkreter Zahl

Damit hat projectFIVE nicht nur den Profi-Markt von heute, sondern den Profi-Markt von morgen kartiert. Das ist die direkte Differenzierung zu coachinsider.

---

## Sprint-Reihenfolge

```
✅ Sprint A   LG 70/71 + Lehrgang-Tiefe
✅ Sprint B   NLZ Variant-2 Discovery
✅ Sprint C   Trainerstab Tier 1+2
✅ Sprint coachinsider-Diff (Trainer)
↓
   Sprint F   SD/GF Deep Coverage    (Demand-Side)
↓
→  Sprint G   NLZ-Trainer Cluster    (DIESE Directive — Talente-Pipeline)
   Sprint H   (gestrichen — SkillCorner-Alternativen on-demand)
   Sprint I   Berater-CRM-Workflow   (Daily-Driver, USP #4)
```

Sprint G nach Sprint F, weil die Decision-Maker-Tiefe das Cross-Linking SD-NLZ-Leiter ↔ NLZ-Trainer ermöglicht (nächste Aufstiegs-Stufe!).
