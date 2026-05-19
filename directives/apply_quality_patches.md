# Directive: Apply Quality-Patches Q1+Q2+Q3

**Trigger-Phrase für Claude:** "Apply quality patches Q1+Q2+Q3" oder "Implementiere Audit-Patches"

**Bezugnehmend auf:** Live-Audit Polzin/Werner 2026-04-30 (Eta/Fischer/Blessin Stichproben)
**Score-Wirkung:** 95 → ~98/100
**Aufwand:** ~65 Zeilen Code, 1 Rebuild (~30 min), 1 Deploy

---

## Drei Defekte aus Live-Audit

### Q1 — Mitspieler-Kategorie überschreibt Executive-Realität (P0)

**Beispiel Blessin:** Fabio Lapeschi (Geschäftsführer VfL Wolfsburg, ex-Geschäftsführer FC St. Pauli **mit Blessin**, Vorstandsmitglied DFL+DFB) hat Score 21 als "Mitspieler". Sollte Executive ~85.

**Root-Cause:** `cat == "former_teammate"` ist sticky. Code passt `role_score` an, aber Kategorie + pro_status bleiben Mitspieler. Fällt aus Decision-Maker-Filter.

### Q2 — Plain "Geschäftsführer" als Executive (P1)

**Beispiel:** `classify_role("Geschäftsführer")` → `management` (role_weight 8) statt `executive` (30). Aber: Geschäftsführer eines BL-Clubs IST Decision-Maker. Geschäftsführer Marketing/Finanzen/kaufmännisch bleibt management.

### Q3 — DFB-Lehrgang als Sidebar-Station-Chip (P2)

Werner zeigt "DFB-Lehrgang 2019/2020" in linker Sidebar als Station, obwohl Pseudo-Club-Filter es aus dem Score genommen hat. Verwirrt UX.

---

## Implementierung

### Step 1 — Q2 in `execution/lib/normalization.py`

Im `classify_role()` (etwa Line 217), Executive-Block erweitern:

```python
EXECUTIVE_KEYWORDS = [
    "präsident", "vize-präsident", "vize präsident",
    "vorstandsvorsitz", "vorsitzende", "vorstandsmitglied",
    "vorstand sport", "vorstand fußball", "vorstand profifußball",
    "geschäftsführer sport", "geschäftsführer fußball",
    "geschäftsführer profifußball",
    "ceo", "managing director", "executive director",
    "sportlicher leiter", "leiter sport", "leiter lizenz",
    "head of football", "director of football",
    "aufsichtsratsvorsitz",
]
EXEC_NEGATIVE_KEYWORDS = [
    "marketing", "finanzen", "kaufmännisch", "vertrieb",
    "kommunikation", "personal", "merchandising",
]

if any(x in r for x in EXECUTIVE_KEYWORDS):
    return "executive"
# Plain Geschäftsführer/Vorstandsmitglied — executive UNLESS marketing/finance qualifier
if "geschäftsführer" in r and not any(neg in r for neg in EXEC_NEGATIVE_KEYWORDS):
    return "executive"
if "vorstandsmitglied" in r and not any(neg in r for neg in EXEC_NEGATIVE_KEYWORDS):
    return "executive"
```

### Step 2 — Q1 in `execution/build_coach_network.py`

Such nach `if cat == "former_teammate":` (etwa Line 1036). Im `elif teammate_career:` Block category + pro_status promovieren:

```python
elif teammate_career:
    post_role = classify_role(teammate_career[0].get("role", ""))
    role_score = role_weights.get(post_role, 2)
    # Q1 (Live-Audit 2026-04-30): Promote category for ex-teammates with active
    # decision-making careers. Lapeschi-Bug fix.
    if post_role in ("head_coach", "sporting_director", "executive"):
        role_score += 8
        c["category"] = post_role
        c["pro_status"] = {
            "head_coach": "trainer",
            "sporting_director": "sd",
            "executive": "exec",
        }[post_role]
        cat = post_role  # Update local var so league_mod/recency_mod use new cat
    elif post_role == "scouting":
        # Scout-promotion (Minkwitz-Pattern)
        c["category"] = "scouting"
        c["pro_status"] = "scout"
        cat = "scouting"
```

Optional: gleiche Logik in `player_coached`-Block falls Spieler die jetzt Trainer/SD/Exec sind ebenfalls promoted werden sollen. Such nach `elif cat == "player_coached":`.

### Step 3 — Q3 in `blessin_network_v3.html`

Such nach `buildStationChips` oder Station-Chip-Render im linken Sidebar (`sidebar-left`).

```javascript
// Q3 (Live-Audit 2026-04-30): Pseudo-Stations nicht als Sidebar-Chips
const PSEUDO_CHIP_PATTERNS = ['DFB-Lehrgang', 'Mgmt-Lehrgang', 'Trainerausbildung'];
const realStations = stations.filter(
    s => !PSEUDO_CHIP_PATTERNS.some(p => s.includes(p))
);
realStations.forEach(st => { /* render chip */ });
```

Im Detail-Panel — neue Sektion `Lehrgang-Kohorte` einfügen wenn contact `lehrgang_cohort` Feld hat:

```javascript
// In selectContact() detail render:
const lcSection = document.getElementById('d-lehrgang-section');
if (c.lehrgang_cohort && lcSection) {
    document.getElementById('d-lehrgang-cohort').textContent =
        `DFB-Lehrgang ${c.lehrgang_cohort}`;
    lcSection.style.display = 'block';
}
```

(HTML für `d-lehrgang-section` muss separat ergänzt werden falls noch nicht da.)

---

## Smoke-Tests vor Rebuild

```bash
cd "/Users/cmk/Documents/CMK Digital/Football Coaches DB"
python3 -c "
import sys
sys.path.insert(0, 'execution')
from lib.normalization import classify_role
tests = [
    ('Geschäftsführer', 'executive'),
    ('Geschäftsführer Marketing', 'management'),
    ('Geschäftsführer kaufmännisch', 'management'),
    ('Geschäftsführer Sport', 'executive'),
    ('Vorstandsmitglied', 'executive'),
    ('Vorstand Marketing', 'management'),
    ('Vorstand Sport', 'executive'),
    ('Pressesprecher', 'other_staff'),
    ('Cheftrainer', 'head_coach'),
]
ok = 0
for inp, exp in tests:
    got = classify_role(inp)
    mark = 'OK' if got == exp else 'FAIL'
    if got == exp: ok += 1
    print(f'  [{mark}] {inp!r:<32} → {got:<18} (expected {exp})')
print(f'\\nclassify_role: {ok}/{len(tests)} pass')
"
```

Nur weitermachen wenn 9/9 pass.

---

## Rebuild + Deploy

```bash
cd "/Users/cmk/Documents/CMK Digital/Football Coaches DB"

# 1) Networks rebuild (~28-30 min für 59 active coaches)
python3 execution/generate_all_bl_coaches.py \
    --leagues BL1 BL2 BL3 --include-historical \
    2>&1 | tee logs/rebuild_q1q2q3_$(date +%Y%m%d_%H%M).log

# 2) Club-Pages
python3 execution/generate_club_pages.py

# 3) SQLite (executive count sollte hochgehen)
python3 execution/build_sqlite.py

# 4) Deploy
cd output && npx vercel deploy --prod --yes --scope cmk2299s-projects
```

---

## Validierung post-Deploy

```bash
# Lapeschi sollte jetzt category='executive' und Score >= 70 sein in Blessin
curl -s https://coach-network-explorer.vercel.app/dashboards/alexander_blessin_network.html | python3 -c "
import re, json, sys
c = sys.stdin.read()
m = re.search(r'const NETWORK = (\{.*?\});\s*\n', c, re.DOTALL)
net = json.loads(m.group(1))
l = next((co for co in net['contacts'] if co['name']=='Fabio Lapeschi'), None)
if l:
    print(f'Lapeschi: score={l[\"relevance_score\"]}, cat={l[\"category\"]}, pro={l.get(\"pro_status\")}, role={l[\"role\"]}')
print()
# Count Executive contacts in Blessin
ex = [c for c in net['contacts'] if c.get('category')=='executive']
print(f'Executive contacts in Blessin: {len(ex)} (vorher 1)')
for e in ex[:5]:
    print(f'  {e[\"relevance_score\"]:>3} {e[\"name\"]:<28} {e[\"role\"][:50]}')
"

# Werner sollte KEIN DFB-Lehrgang in Sidebar-Stations zeigen (Q3)
curl -s https://coach-network-explorer.vercel.app/dashboards/ole_werner_network.html | grep -o 'class=\"station-chip\"[^>]*>[^<]*DFB-Lehrgang' | wc -l
# Erwartung: 0

# Regression: Fritz/Niemeyer/Baumann sollten Executive bleiben
curl -s https://coach-network-explorer.vercel.app/dashboards/ole_werner_network.html | python3 -c "
import re, json, sys
c = sys.stdin.read()
m = re.search(r'const NETWORK = (\{.*?\});\s*\n', c, re.DOTALL)
net = json.loads(m.group(1))
for nm in ['Clemens Fritz','Peter Niemeyer','Frank Baumann']:
    p = next((co for co in net['contacts'] if co['name']==nm), None)
    if p: print(f'{nm}: score={p[\"relevance_score\"]}, cat={p[\"category\"]}')
"
```

---

## Erwartete Wirkung

| Beispiel | Vorher | Nachher | Begründung |
|---|---:|---:|---|
| Lapeschi (Blessin) | 21 (Mitspieler) | ~85 (Executive) | Q1+Q2 |
| Minkwitz Chefscout (Blessin) | 31 (Mitspieler) | ~70 (Scouting) | Q1 |
| DFB-Lehrgang Sidebar (Werner) | sichtbar | hidden | Q3 |
| Blessin Executive count | 1 (Bornemann only) | 4-6 | Q1+Q2 promotionen |
| Werner Executive count | 8 | 10-15 | Q1 promotionen |

**Score-Estimate:** 95 → ~98/100.

---

## Edge-Cases / Regression-Risiken

1. **Ex-Spieler mit "Geschäftsführer kaufmännisch"** (Lapeschi's St. Pauli-Karriere zeigt das) — bleibt korrekt management ✓
2. **Frank Baumann (Sportvorstand)** ist bereits durch "vorstand sport"-keyword Executive — sollte nicht doppelt promoted werden, Code idempotent
3. **Mitspieler ohne post-career profile** (Michael Kümmerle in Blessin: "Defensives Mittelfeld") — soll Mitspieler bleiben, Code branch checkt `teammate_career` empty → bleibt
4. **DFB-Lehrgang als echte Station bei Lehrgang-Coaches selbst** — die Kohorte-Info muss im Detail-Panel weiterhin erscheinen, nur das Sidebar-Chip raus

---

## Hinweis für Claude (Self-Anneal)

- Vor Code-Edit: lies `audits/SCORE_FIX_LIVE_2026-04-30.md` für Score-Tier-Werte
- Pattern für Override-Anwendung wie Hidden-Gems-Patch (build_coach_network.py Line ~1318) — siehe `_override_applied` flag
- Bei Template-Edit: Lehrgang-Section HTML sicherheitshalber direkt über Stationen-Section
- Nach Rebuild: spot-check **Lapeschi (Blessin)** UND **Kümmerle (Mitspieler ohne post-career)** als Negativ-Beispiel
- Bei Unsicherheit über sidebar-render: `grep -n "buildStationChips\|sidebar-left\|station-chip" blessin_network_v3.html`
