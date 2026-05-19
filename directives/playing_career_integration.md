# Directive: Spielerkarriere-Integration (Mitspieler / Former Teammates)

## Problem

Der Network Builder kennt nur die **Trainer-Karriere** jedes Coaches. Aber viele BL-Trainer waren vorher Profispieler:

| Trainer | Spielerkarriere | Fehlende Kontakte |
|---------|----------------|-------------------|
| Alexander Blessin | VfB Stuttgart, Stuttg. Kickers, Braunschweig | ~60-100 Mitspieler |
| Niko Kovac | Hertha, Leverkusen, HSV, Bayern, Salzburg | ~100-200 Mitspieler |
| Bo Svensson | Mainz 05 (10 Jahre) | ~80-120 Mitspieler |
| Sebastian Hoeneß | Bayern II, Hoffenheim Jugend | ~30-50 Mitspieler |
| Vincent Kompany | Man City, Anderlecht, HSV | ~150-250 Mitspieler |

Diese Mitspieler-Netzwerke sind für projectFIVE extrem wertvoll — persönliche Beziehungen aus gemeinsamer Spielerzeit wiegen mehr als zufällige Trainer-Stationen.

### Root Cause

TM trennt Spieler- und Trainer-Profile strikt:
- `/trainer/profil/trainer/26099` → Zeigt nur Trainer-Karriere (unser aktueller Scraper)
- `/alexander-blessin/profil/spieler/26099` → Zeigt Spieler-Karriere + Leistungsdaten

Unsere Pipeline scrapt nur die Trainer-Seite. Die Spieler-Seite wird ignoriert, selbst wenn die Person als `type: "trainer"` und über `career_transitions` als Ex-Spieler bekannt ist.

---

## Lösungskonzept

### Architektur-Entscheidung: Squad-First (nicht Scraping-First)

Es gibt zwei Wege an Mitspieler-Daten:

**Option A: Spielerkarriere scrapen → Squads laden**
- Pro: Präzise Karrieredaten mit Datumsbereichen
- Contra: Braucht 2. Scrape pro Coach (Spieler-Seite), dann Squad-Files die wir evtl. nicht haben
- Contra: Viele Spieler-Stationen sind vor 2010 → keine Squad-Daten vorhanden

**Option B: Spielerkarriere scrapen → Profile-Index nutzen** ✅
- Spielerkarriere scrapen für die 36 BL-Coaches (nur ~36 extra Requests)
- `career_history` um Spieler-Einträge erweitern
- Profile-Index (`(club_tm_id, season) → [tm_ids]`) findet automatisch alle Personen die gleichzeitig dort waren
- Funktioniert mit bestehendem Code in `build_network()` Step 2 ("Shared career stations")

**→ Option B ist der klare Gewinner.** Der Network Builder macht das Heavy Lifting bereits — wir müssen nur die Karriere-Daten vervollständigen.

---

## Implementierung

### Phase 1: Spielerkarriere scrapen (36 Requests)

#### Neues Script: `execution/scrape_playing_careers.py`

```bash
python execution/scrape_playing_careers.py                    # Alle BL-Coaches
python execution/scrape_playing_careers.py --tm-id 26099      # Einzelner Coach
python execution/scrape_playing_careers.py --dry-run           # Nur zeigen wer Spieler war
```

**Logik:**
1. Lade alle 36 BL-Head-Coaches aus Staff-Files
2. Für jeden Coach: prüfe ob TM eine Spieler-Seite hat
   - URL: `https://www.transfermarkt.de/{slug}/profil/spieler/{tm_id}`
   - Wenn 200 → Spielerkarriere existiert
   - Wenn 404 oder Redirect → War kein Profi-Spieler
3. Parse Spielerkarriere mit `parse_career_history(soup, is_coach=False)` (existiert bereits!)
4. Merge in bestehendes Profil:

```python
# In person_profiles/{tm_id}.json
{
  "tm_id": 26099,
  "name": "Alexander Blessin",
  "type": "trainer",
  "career_history": [
    # Bestehende Trainer-Karriere (unverändert)
    {"club_name": "FC St. Pauli", "role": "Trainer", ...},
    {"club_name": "Union SG", "role": "Trainer", ...},
    ...
  ],
  "playing_career": [                          # ← NEU
    {"club_tm_id": 79, "club_name": "VfB Stuttgart", "role": "Spieler", "date_from": "96/97", "date_to": "99/00", ...},
    {"club_tm_id": 78, "club_name": "Stuttgarter Kickers", "role": "Spieler", ...},
    {"club_tm_id": 73, "club_name": "Eintracht Braunschweig", "role": "Spieler", ...},
  ],
  "was_player": true,                         # ← NEU
  "player_positions": ["Rechtes Mittelfeld"],  # ← NEU (aus TM Spielerprofil)
  ...
}
```

**Wichtig:** `playing_career` als separates Feld, NICHT in `career_history` mischen. Grund:
- `career_history` wird vom Profile-Index für Trainer-Überlappungen genutzt
- Spieler-Stationen brauchen eigene Behandlung im Network Builder
- Bestehende Logik bleibt unberührt

### Phase 2: Profile-Index erweitern

In `build_coach_network.py` → `build_profile_index()`:

```python
def build_profile_index(profiles, include_playing=True):
    """Build inverted index: (club_tm_id, season) → [tm_id, ...]"""
    index = defaultdict(list)

    for tm_id, profile in profiles.items():
        # Bestehend: Trainer/Karriere-History
        for entry in profile.get("career_history", []):
            # ... (unverändert)

        # NEU: Spielerkarriere
        if include_playing:
            for entry in profile.get("playing_career", []):
                club_id = entry.get("club_tm_id")
                if not club_id:
                    continue
                seasons = get_season_range(entry.get("date_from", ""), entry.get("date_to", ""))
                for s in seasons:
                    index[(club_id, s)].append(tm_id)

    return dict(index)
```

### Phase 3: Network Builder erweitern

In `build_network()`, nach Step 2 ("Shared career stations"), neuer Step:

```python
# ── 2b) Mitspieler aus Spielerkarriere ──
playing_career = profile.get("playing_career", [])
if playing_career:
    playing_stations = defaultdict(lambda: {"name": "", "seasons": set()})
    for entry in playing_career:
        club_id = entry.get("club_tm_id")
        if not club_id:
            continue
        seasons = get_season_range(entry.get("date_from", ""), entry.get("date_to", ""))
        name = normalize_club(entry.get("club_name", ""), club_id)
        playing_stations[club_id]["name"] = name
        playing_stations[club_id]["seasons"].update(seasons)

    # Finde alle Personen die gleichzeitig beim selben Club waren
    for club_id, info in playing_stations.items():
        for season in info["seasons"]:
            # Aus Squad-Files (Spieler)
            squad = load_squad(club_id, season)
            if squad:
                for player in squad.get("players", []):
                    pid = player["tm_id"]
                    if pid == coach_tm_id:
                        continue
                    if pid not in contacts_map:
                        contacts_map[pid] = {
                            "name": player.get("name", ""),
                            "stations": [info["name"]],
                            "category": "former_teammate",       # ← Neue Kategorie
                            "role": f"Mitspieler ({player.get('position', '')})",
                            "tm_url": player.get("tm_url", ""),
                            "tm_id": pid,
                            "seasons_together": 1,
                            "relationship_type": "playing",      # ← Neu: Beziehungstyp
                        }
                    else:
                        existing = contacts_map[pid]
                        if info["name"] not in existing["stations"]:
                            existing["stations"].append(info["name"])
                        existing["seasons_together"] = existing.get("seasons_together", 0) + 1
                        # Upgrade: wenn jemand Mitspieler UND späterer Kollege ist
                        if existing.get("relationship_type") != "playing":
                            existing["relationship_type"] = "both"

            # Aus Profile-Index (Trainer/Staff die gleichzeitig dort waren)
            for other_id in profile_index.get((club_id, season), []):
                if other_id == coach_tm_id or other_id in contacts_map:
                    continue
                # ... (analog zu bestehendem Step 2)
```

### Phase 4: Dashboard-Template erweitern

Neue Kategorie im Template:

```javascript
// Kategorie-Config erweitern
const CATEGORIES = {
    head_coach: { label: "Trainer", badge: "T", color: "#c8102e" },
    sporting_director: { label: "Sportdirektor", badge: "SD", color: "#1e88e5" },
    coaching_staff: { label: "Trainerstab", color: "#66bb6a" },
    scouting: { label: "Scouting", color: "#ffa726" },
    medical: { label: "Medizin", color: "#ab47bc" },
    management: { label: "Management", color: "#78909c" },
    player: { label: "Spieler (betreut)", color: "#29b6f6" },
    former_teammate: { label: "Mitspieler", badge: "M", color: "#ef5350" },  // ← NEU
    // ...
};
```

Im Detail-Panel: Beziehungstyp anzeigen:
- `"relationship_type": "playing"` → "Mitspieler bei VfB Stuttgart (96/97–99/00)"
- `"relationship_type": "coaching"` → "(bestehend)"
- `"relationship_type": "both"` → "Mitspieler + späterer Kollege" ← wertvollste Verbindungen

### Phase 5: Spezialfall "Doppel-Beziehungen" hervorheben

Kontakte die sowohl Mitspieler als auch spätere Kollegen sind, sind die stärksten Beziehungen im Netzwerk. Beispiel: Jemand der mit Blessin bei Stuttgart gespielt hat und jetzt Co-Trainer bei St. Pauli ist.

Im Dashboard:
- Dickere Edge-Linie im Graph
- Badge "M+T" oder "M+SD"
- Eigene Sortierung im Detail-Panel: "Stärkste Verbindungen" zuerst

---

## Daten-Verfügbarkeit

### Was haben wir bereits?

| Datenquelle | Abdeckung | Mitspieler-Potential |
|-------------|-----------|---------------------|
| Squad-Files BL1/BL2/BL3 (DE) | 2010–2025 | Stark für Coaches die ab 2010 gespielt haben |
| Squad-Files Top-5-Ligen | 2010–2025 | Stark für Kompany (Man City), Kovac (Monaco) |
| Squad-Files NLZ | Lückenhaft | Schwach |
| Squad-Files vor 2010 | ❌ Nicht vorhanden | Blind für ältere Karrieren |

### Abdeckungslücken

**Blessin-Beispiel:**
- VfB Stuttgart 1996–2000 → ❌ Keine Squad-Files (vor 2010)
- Stuttgarter Kickers 2000–2004 → ❌ Keine Squad-Files (vor 2010)
- Eintracht Braunschweig 2004–2010 → ❌/⚠️ Teilweise (ab 2010/11 wenn BL2/BL3)

**Kompany-Beispiel:**
- Man City 2008–2019 → ✅ Ab 2010 in PL Squad-Files
- Hamburg 2006–2008 → ❌ Vor 2010

**Lösung:** Für Stationen vor 2010 könnten wir gezielt historische Squads scrapen. Aber das ist Phase 2 — erstmal das nutzen was wir haben.

### Erwarteter Impact (Phase 1: nur bestehende Squad-Files)

| Coach | Spieler ab 2010? | Erwartete neue Mitspieler |
|-------|-----------------|--------------------------|
| Kompany | Ja (Man City 2010-2019) | ~100-150 |
| Kovac | Ja (Salzburg 2010-12) | ~30-40 |
| Bo Svensson | Ja (Mainz 2010-14) | ~40-60 |
| Blessin | Nein (Karriereende ~2010) | ~10-20 (nur Braunschweig ab 2010) |
| Hoeneß | Ja (Bayern II 2010-14) | ~30-40 |
| Christian Ilzer | Ja (WAC, Hartberg 2010+) | ~40-60 |

**Gesamt-Schätzung:** ~30-80 neue Mitspieler pro Coach im Schnitt, bei Coaches mit langer Post-2010-Spielerkarriere deutlich mehr.

---

## Ausführungsreihenfolge

```
1. scrape_playing_careers.py schreiben + testen (Blessin als Testfall)
2. 36 Spielerkarrieren scrapen (~36 Requests, ~2 Min)
3. Profile-JSON-Files updaten (playing_career Feld hinzufügen)
4. build_coach_network.py erweitern (Step 2b + neue Kategorie)
5. Dashboard-Template: former_teammate Kategorie + M-Badge
6. Netzwerke regenerieren + Deploy
7. Validierung: Blessin vor/nach Vergleich
```

**Abhängigkeit:** Unabhängig von League Expansion (Sprint 10). Kann parallel oder danach laufen.
**Aufwand:** ~2-3 Stunden (Script + Builder + Template + Test)

---

## Edge Cases

### Coach war nie Profi-Spieler
- TM Spieler-Seite existiert nicht → Skip
- `was_player: false` im Profil
- Kein Mitspieler-Block im Dashboard

### Spieler-TM-ID ≠ Trainer-TM-ID
- Bei den meisten Coach-Spieler-Karrieren ist die TM-ID identisch
- Prüfung: `career_transitions` Tabelle hat 382 Einträge mit Spieler→Trainer-Wechsel
- Wenn TM-IDs unterschiedlich sind, muss der Scraper beide URLs versuchen

### Spieler-Seite hat keine Leistungsdaten
- Manche Ex-Profis haben auf TM nur rudimentäre Spieler-Seiten
- Fallback: career_history aus der Spieler-Seite extrahieren, auch ohne detaillierte Stats

### Mitspieler sind bereits als Kontakt vorhanden
- z.B. jemand der mit Kovac bei Salzburg gespielt hat UND jetzt Trainer in BL2 ist
- Der `contacts_map` Dedup-Mechanismus handled das bereits
- Neue Logik: `relationship_type: "both"` setzen

### Sehr große Mitspieler-Netzwerke
- Kompany (Man City 2010-2019): ~25 Spieler/Saison × 10 Saisons = ~150-250 Mitspieler
- Dashboard könnte überladen wirken
- Lösung: Mitspieler-Filter im Dashboard (Checkbox ein/aus), default OFF für > 100 Mitspieler
- Oder: Nur Mitspieler mit 2+ gemeinsamen Saisons zeigen

---

## Slug-Discovery für Spieler-URL

TM Spieler-URLs folgen dem Schema:
```
/alexander-blessin/profil/spieler/26099
```

Der Slug (hier `alexander-blessin`) ist im Profil nicht gespeichert. Lösungen:
1. **Aus persons_index:** Viele Einträge haben `tm_url` mit dem vollen Pfad
2. **Aus Trainer-Profil-HTML:** TM verlinkt oft zur Spieler-Seite wenn beides existiert
3. **Generischer Slug:** TM akzeptiert auch `/x/profil/spieler/{tm_id}` als Wildcard (wie unser Scraper bereits nutzt — Zeile 509 in `scrape_person_profiles.py`)

→ **Lösung: `/x/profil/spieler/{tm_id}`** — funktioniert immer, TM redirected zur kanonischen URL.

---

## Learnings Log
_(Update as you discover issues)_

- [pending] Wie viele der 36 BL-Coaches haben eine TM-Spielerseite?
- [pending] Welche Spieler-Stationen liegen vor 2010 (= keine Squad-Files)?
- [pending] Verhalten bei TM-Redirect (Spieler-Seite → Trainer-Seite wenn kein Spielerprofil)
- [pending] Performance-Impact: Wie viele Mitspieler kommen pro Coach dazu?
- [pending] Dashboard-Usability mit 200+ Mitspieler-Nodes (Kompany-Test)
