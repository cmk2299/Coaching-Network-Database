# Directive: SD-Network Phase 1 — alle 56 BL-Sportdirektoren als Center

**Trigger-Phrase für Claude:** "Build SD networks Phase 1" oder "/build-sd-networks"

**Bezugnehmend auf:** projectFIVE Strategic-Recommendation #2 (Top-3) — der größte Multiplikator-Effekt für Replacement-Pool-Logik.

**Mission-Wert:** Ohne SD-Networks bleibt das Replacement-Tool einseitig. Mit ihnen wird "wenn Toppmöller wackelt, schau auf Krösches Netzwerk" zum 1-Klick-Workflow.

**Aufwand:** ~3h (Daten-Extract + Build + Dashboard + Index-Section + Deploy).

---

## Voraussetzungen

POC schon erfolgreich gelaufen (Bornemann tm_id=3223, Krösche tm_id=34524 im persons_master als type=trainer mit voller career_history).

```bash
ls data/networks/3223.json data/networks/34524.json   # beide vorhanden?
ls output/dashboards/andreas_bornemann_sd_network.html   # Bornemann's Dashboard live?
```

Wenn POC noch nicht durch: zuerst `bash run_next_phase.sh` durchziehen (enthält den POC-Build).

---

## Schritt 1 — SD-Liste aus Staff-Daten extrahieren

Pro BL1/BL2/BL3-Club den aktuellen SD finden. Pattern: erste Person in `staff` mit Section in `("Sportdirektor", "Sportvorstand", "Sportgeschäftsführer", "Sportlicher Leiter", "Geschäftsführer Sport", "Technischer Direktor")`.

Neues Skript `execution/extract_sd_registry.py`:

```python
#!/usr/bin/env python3
"""Extract aktiver SDs aus staff/{club_tm_id}.json für BL1/BL2/BL3.

Output: data/sd_registry.json
  {
    "_meta": {extracted_at, season, total_clubs, total_sds, no_sd_clubs},
    "sds": [
      {tm_id, name, club_tm_id, club_name, league, role, since}
    ]
  }
"""
import json
from pathlib import Path
from datetime import datetime, timezone

BASE = Path(__file__).parent.parent
SD_SECTIONS = [
    "Sportdirektor", "Sportvorstand", "Sportgeschäftsführer",
    "Sportlicher Leiter", "Geschäftsführer Sport",
    "Technischer Direktor", "Director of Football",
]

def main():
    registry = json.load(open(BASE / "data/club_registry.json"))["clubs"]
    season = "2025/2026"
    bl_clubs = [c for c in registry if any(
        l in ("BL1", "BL2", "BL3")
        for l in c.get("leagues", {}).get(season, [])
    )]

    sds = []; no_sd = []
    for c in bl_clubs:
        staff_file = BASE / f"data/staff/{c['tm_id']}.json"
        if not staff_file.exists():
            no_sd.append(c["name"])
            continue
        s = json.load(open(staff_file))
        # Find first SD-tier entry
        sd_entry = None
        for entry in s.get("staff", []):
            section = entry.get("section", "")
            if any(sd_kw in section for sd_kw in SD_SECTIONS):
                sd_entry = entry
                break
        if not sd_entry:
            no_sd.append(c["name"])
            continue

        sds.append({
            "tm_id": sd_entry["tm_id"],
            "name": sd_entry["name"],
            "club_tm_id": c["tm_id"],
            "club_name": c["name"],
            "league": next((l for l in c.get("leagues", {}).get(season, [])
                            if l in ("BL1","BL2","BL3")), None),
            "role": sd_entry.get("section", ""),
        })

    out = BASE / "data/sd_registry.json"
    json.dump({
        "_meta": {
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "season": season,
            "total_clubs": len(bl_clubs),
            "total_sds": len(sds),
            "no_sd_clubs": no_sd,
        },
        "sds": sds,
    }, open(out, "w"), ensure_ascii=False, indent=2)
    print(f"✓ {len(sds)} SDs extracted to {out}")
    if no_sd:
        print(f"⚠ {len(no_sd)} clubs ohne SD: {no_sd[:5]}")

if __name__ == "__main__":
    main()
```

Run:
```bash
python3 execution/extract_sd_registry.py
```

## Schritt 2 — Profile-Vollständigkeit prüfen

Für jeden SD: Profile in persons_master verifizieren. Falls type=spieler und current_club="Karriereende", in `data/trainer_profile_overrides.json` ergänzen (wie bei Hidden-Gems-Patch).

```bash
python3 << 'PY'
import json
sds = json.load(open('data/sd_registry.json'))['sds']
persons = json.load(open('data/persons_master.json'))['persons']
ok = 0; stale = 0; missing = 0
for sd in sds:
    p = persons.get(str(sd['tm_id']))
    if not p:
        print(f'  MISSING: {sd["name"]} (tm_id={sd["tm_id"]})')
        missing += 1
    elif p.get('type') == 'spieler' and (p.get('current_club') or {}).get('name') == 'Karriereende':
        print(f'  STALE:   {sd["name"]} (tm_id={sd["tm_id"]}) → trainer_profile_overrides.json ergänzen')
        stale += 1
    else:
        ok += 1
print(f'\n{ok} ok, {stale} stale (need overrides), {missing} missing')
PY
```

Wenn stale > 0: `data/trainer_profile_overrides.json` ergänzen (Pattern wie Hürzeler/Schindzielorz).

## Schritt 3 — SD-Networks bauen

Neues Skript `execution/build_all_sd_networks.py` (parallel zu `generate_all_bl_coaches.py`):

```python
#!/usr/bin/env python3
"""Builds Networks für alle SDs aus sd_registry.json + Dashboards.

Output:
  data/networks/{tm_id}.json (gleiche Struktur wie Coach-Networks)
  output/dashboards/{slug}_sd_network.html (Suffix _sd_network um
                    Coach-/SD-Slug-Kollisionen zu vermeiden)
"""
import json, time, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from build_coach_network import (
    build_network, generate_background_summaries,
    build_drilldown, preload_all_profiles, build_profile_index,
    strip_internal_fields, OUTPUT_DIR,
)
from generate_dashboard import generate_dashboard
from lib.normalization import slugify

BASE = Path(__file__).parent.parent

def main():
    sds = json.load(open(BASE / "data/sd_registry.json"))["sds"]
    print(f"Loading profile index ({len(sds)} SDs to process)...")
    profiles = preload_all_profiles()
    profile_index = build_profile_index(profiles)

    success = 0; failed = 0
    t0 = time.time()
    for i, sd in enumerate(sds, 1):
        tm_id = sd["tm_id"]
        name = sd["name"]
        slug = slugify(name)
        sys.stdout.write(f"  [{i:>2}/{len(sds)}] {name:<26} ({sd['club_name']:<24}) ... ")
        sys.stdout.flush()

        try:
            net = build_network(tm_id, profiles, profile_index)
            if not net:
                print("✗ no profile")
                failed += 1; continue
            net = generate_background_summaries(net)
            drilldown = build_drilldown(net, profiles, profile_index)
            strip_internal_fields(net)

            net_path = OUTPUT_DIR / f"{tm_id}.json"
            json.dump(net, open(net_path, "w"), ensure_ascii=False, indent=2)

            dash_path = BASE / "output/dashboards" / f"{slug}_sd_network.html"
            generate_dashboard(net, dash_path, drilldown=drilldown)
            print(f"✓ {net['total_contacts']} contacts")
            success += 1
        except Exception as e:
            print(f"✗ {e}")
            failed += 1

    print(f"\nDone: {success} ok, {failed} failed ({time.time()-t0:.0f}s)")

if __name__ == "__main__":
    main()
```

Run:
```bash
python3 execution/build_all_sd_networks.py 2>&1 | tee logs/sd_networks_$(date +%Y%m%d_%H%M).log
```

Erwartete Runtime: ~30s × 56 SDs = ~28min (analog Coach-Networks).

## Schritt 4 — SD-Section in Index-Page

In `execution/generate_all_bl_coaches.py` neue Sektion einfügen unter den Trainer-Sektionen:

```python
# In generate_index_page nach hist_d_section:
sd_registry_file = BASE / "data/sd_registry.json"
sds_with_dashboards = []
if sd_registry_file.exists():
    sd_data = json.load(open(sd_registry_file))
    for sd in sd_data["sds"]:
        slug = slugify(sd["name"])
        dash = DASHBOARD_DIR / f"{slug}_sd_network.html"
        if dash.exists():
            sds_with_dashboards.append({
                **sd,
                "slug": slug,
                "image_url": "",  # optional: from profile lookup
            })

sd_section = ""
if sds_with_dashboards:
    bl1_sds = [s for s in sds_with_dashboards if s.get("league") == "BL1"]
    sd_section = f"""<div class="section" id="sds">
  <div class="section-hdr">
    <h2 class="section-title">Sportdirektoren · Hire-Decider</h2>
    <span class="section-count">{len(sds_with_dashboards)}</span>
    <span class="section-line"></span>
  </div>
  <div class="table-hdr">
    <span></span><span>Sportdirektor</span><span>Verein</span>
    <span style="text-align:right">Kontakte</span>
    <span style="text-align:right">Stationen</span><span></span>
  </div>
  {make_sd_rows(sds_with_dashboards)}
</div>"""
```

`make_sd_rows()` ist analog zu `make_rows()` aber linkt auf `dashboards/{slug}_sd_network.html`.

## Schritt 5 — Cross-Link in Coach-Networks

Auto-greift schon: `_dashboard_index` wird aus allen `data/networks/*.json` gebaut (siehe `regenerate_dashboards.build_dashboard_index`). Nach Schritt 3 enthält der Index Bornemanns tm_id=3223 → slug="andreas_bornemann_sd". 

ABER: aktuell linkt er auf `andreas_bornemann_sd_network.html` (slug aus ihrem eigenen Network-Center) — das ist korrekt da das die SD-Dashboard-Datei ist.

**Verifizieren:** nach Coach-Networks Re-Regen sollten Bornemann/Krösche/etc. NET-Badges zeigen.

```bash
python3 execution/regenerate_dashboards.py --lazy 500000  # ~10 min
```

## Schritt 6 — Hot-Seat für SDs (Optional, P2)

Analog zu Coach-Hot-Seat: SDs haben auch Wackel-Patterns (Saison-Performance, Vertragsverlängerung-Diskussionen). Aufwand ~4h, kann als separater Sprint laufen.

## Deploy

```bash
cd output && npx vercel deploy --prod --yes --scope cmk2299s-projects
```

## Validierung post-Deploy

```bash
# Bornemann's Network sollte erreichbar sein:
curl -s -o /dev/null -w "%{http_code}\n" \
  https://coach-network-explorer.vercel.app/dashboards/andreas_bornemann_sd_network.html
# Erwartung: 200

# Frankfurt-Riera-Dashboard sollte Krösche mit NET-Badge zeigen:
curl -s https://coach-network-explorer.vercel.app/dashboards/albert_riera_network.html | \
  grep -o 'data-tm-id="34524"' | wc -l
# Erwartung: ≥1

# SD-Section im Index:
curl -s https://coach-network-explorer.vercel.app/ | grep -c 'sds'
```

## Edge-Cases

1. **Mehrere SDs pro Club** (z.B. Sportvorstand + Sportdirektor): aktuelles Skript nimmt den ersten. Alternative: alle aufnehmen, oder primary aus `staff_section` ranking.
2. **SD ist gleichzeitig Geschäftsführer**: kein Problem, taucht doppelt nicht auf weil per club_tm_id deduplicated.
3. **Junge SDs ohne breite Karriere**: Score-Range eventuell schmaler. Akzeptabel — qualitativ stimmt's.
