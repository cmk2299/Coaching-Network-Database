# Directive: GemeinsameSpiele Scrapen (Punkt 4 aus Henryk-Brief)

## Ziel

Henryk's Anforderung #4: **"What other coaches & sporting directors has he played together with?"** — basierend auf der TM-Seite `/gemeinsameSpiele/spieler/{player_id}`.

Aktuell nutzen wir Squad-Overlap als Approximation (wer war im selben Kader?). Das ist ungenau — gemeinsamer Kader ≠ gemeinsam auf dem Platz gestanden. TM hat die echten Daten: **Gemeinsame Spiele, Minuten, Tore** zwischen zwei Spielern. Das ist die Wahrheit.

---

## Ist-Zustand

| Was | Stand |
|-----|-------|
| Script | `execution/scrape_teammates.py` existiert, parst `/gemeinsameSpiele/spieler/{id}`, pagination, caching |
| Coaches mit player_tm_id | **33 von 461** Netzwerk-Coaches haben `player_tm_id` in person_profiles |
| Squad-Overlap Mitspieler | 35/461 Netzwerke haben `former_teammate`-Kontakte (aus Kader-Überlappung) |
| GemeinsameSpiele-Daten | **0** — noch nie gescrapt |
| Daten-Format | `{name, position, url, shared_matches, teams_together, total_minutes}` |

### Die 33 Coaches mit player_tm_id

| Coach | Trainer-ID | Spieler-ID | Erwarteter Impact |
|-------|-----------|------------|-------------------|
| Miroslav Klose | 49850 | 10 | Sehr hoch (BL-Legende, 672 Bundesliga-Spiele) |
| Vincent Kompany | 69681 | 9594 | Sehr hoch (Man City 2008-19) |
| Steffen Baumgart | 9622 | 231 | Hoch (BL-Spieler 1998-2011) |
| Niko Kovac | — | — | Hoch (HSV, Bayern, Salzburg) |
| Urs Fischer | 5965 | 4938 | Mittel (Schweizer Liga) |
| Merlin Polzin | 37595 | 151161 | Niedrig (kurze Spielerkarriere) |
| Alexander Ende | 30051 | 1972 | Mittel |
| Uwe Rösler | 1766 | 1440 | Hoch (BL + England) |
| Miron Muslic | 55100 | 17008 | Niedrig |
| Thomas Stamm | 18550 | 19689 | Niedrig |
| ... + 23 weitere | | | |

---

## Architektur

### Was NICHT tun

- **Nicht** den bestehenden `scrape_teammates.py` direkt in die Pipeline einbauen — der ist für Einzelabfragen gedacht
- **Nicht** alle 33 Coaches parallel scrapen — TM blockt bei zu vielen Requests
- **Nicht** die Squad-Overlap-Mitspieler ersetzen — GemeinsameSpiele ergänzt, ersetzt nicht

### Was tun

Neues Batch-Script das:
1. Alle 33 Coaches mit `player_tm_id` identifiziert
2. Für jeden die `/gemeinsameSpiele/spieler/{player_id}` Seiten scrapt (alle Pagination-Pages)
3. Ergebnisse als JSON pro Coach speichert: `data/gemeinsame_spiele/{trainer_tm_id}.json`
4. Rate-Limiting: 3-5s zwischen Requests, Session-Pause alle 50 Requests

---

## Implementierung

### Script: `execution/scrape_gemeinsame_spiele.py`

```bash
# Alle 33 Coaches scrapen
python execution/scrape_gemeinsame_spiele.py --all

# Einzelner Coach
python execution/scrape_gemeinsame_spiele.py --tm-id 49850

# Dry-Run: Nur zeigen wer gescrapt werden würde
python execution/scrape_gemeinsame_spiele.py --dry-run

# Mit Minimum-Schwelle (nur Spieler mit 5+ gemeinsamen Spielen)
python execution/scrape_gemeinsame_spiele.py --all --min-matches 5

# Resume nach Abbruch (überspringt bereits gescrappte)
python execution/scrape_gemeinsame_spiele.py --all --skip-existing
```

### Logik

```
1. Lade person_profiles für alle 461 Netzwerk-Coaches
2. Filtere auf die mit player_tm_id (→ 33 Coaches)
3. Für jeden Coach:
   a. player_id = profile["player_tm_id"]
   b. Slug ermitteln: aus profile["tm_url"] oder generisch "x"
   c. Seite 1 fetchen: /slug/gemeinsameSpiele/spieler/{player_id}
   d. Total Pages ermitteln (Pagination)
   e. Alle Seiten fetchen + parsen
   f. Pro Teammate extrahieren:
      - name, position, tm_url, tm_id (aus URL parsen)
      - shared_matches, teams_together, total_minutes
   g. Speichern: data/gemeinsame_spiele/{trainer_tm_id}.json
4. Summary ausgeben: X Coaches, Y Teammates gesamt, Z mit 10+ Spielen
```

### Output-Format: `data/gemeinsame_spiele/{trainer_tm_id}.json`

```json
{
  "coach_tm_id": 49850,
  "coach_name": "Miroslav Klose",
  "player_tm_id": 10,
  "scraped_at": "2026-04-09T15:00:00",
  "total_teammates": 523,
  "pages_scraped": 11,
  "teammates": [
    {
      "name": "Thomas Müller",
      "tm_id": 58358,
      "tm_url": "/thomas-muller/profil/spieler/58358",
      "position": "Offensives Mittelfeld",
      "shared_matches": 287,
      "teams_together": 1,
      "total_minutes": 18420,
      "clubs_together": ["FC Bayern München", "Deutschland"]
    },
    ...
  ]
}
```

### Caching-Strategie

- HTML-Cache: `tmp/cache/gemeinsame_spiele/{player_id}_page{n}.html` (30 Tage TTL)
- JSON-Ergebnis: `data/gemeinsame_spiele/{trainer_tm_id}.json` (persistent)
- `--skip-existing` überspringt Coaches deren JSON < 7 Tage alt ist

---

## Integration in build_coach_network.py

### Neuer Step nach Mitspieler (Step 2c)

```python
# ── 2c) GemeinsameSpiele-Daten laden (echte Spieldaten statt Squad-Overlap) ──
gs_path = DATA_DIR / "gemeinsame_spiele" / f"{coach_tm_id}.json"
if gs_path.exists():
    gs_data = json.load(open(gs_path))
    gs_teammates = gs_data.get("teammates", [])
    
    for tm in gs_teammates:
        pid = tm.get("tm_id")
        if not pid or pid == coach_tm_id:
            continue
        
        if pid in contacts_map:
            # Bestehenden Kontakt anreichern mit echten Spieldaten
            existing = contacts_map[pid]
            existing["shared_matches"] = tm["shared_matches"]
            existing["shared_minutes"] = tm["total_minutes"]
            existing["teams_together_count"] = tm["teams_together"]
            # Upgrade relationship confidence
            if existing.get("category") == "former_teammate":
                existing["_gs_verified"] = True  # Durch echte Spieldaten bestätigt
        else:
            # Neuer Kontakt NUR aus GemeinsameSpiele (war nicht im Squad-Overlap)
            # Nur hinzufügen wenn signifikant: 10+ Spiele
            if tm["shared_matches"] >= 10:
                contacts_map[pid] = {
                    "name": tm["name"],
                    "stations": [],  # Werden später via Profile-Lookup gefüllt
                    "category": "former_teammate",
                    "role": f"Mitspieler ({tm.get('position', '')})",
                    "tm_url": tm.get("tm_url", ""),
                    "tm_id": pid,
                    "shared_matches": tm["shared_matches"],
                    "shared_minutes": tm["total_minutes"],
                    "seasons_together": max(1, tm["teams_together"]),
                    "relationship_type": "playing",
                    "_gs_verified": True,
                }
```

### Dashboard-Template: GemeinsameSpiele-Daten anzeigen

Im Detail-Panel, wenn `c.shared_matches` vorhanden:

```javascript
// Nach der Karriere-Tabelle, vor Connections
if (c.shared_matches) {
    const gsDiv = document.createElement('div');
    gsDiv.className = 'detail-gs-stats';
    gsDiv.innerHTML = `
        <span class="gs-stat">${c.shared_matches} Spiele</span>
        ${c.shared_minutes ? `<span class="gs-stat">${Math.round(c.shared_minutes/60)}h gemeinsam` : ''}
    `;
    // In passende Section einfügen
}
```

### Relevance Score Boost

In der Scoring-Logik: GemeinsameSpiele-verifizierte Mitspieler bekommen einen Bonus:

```python
if c.get("_gs_verified"):
    score += 5  # Bonus für echte Spieldaten
if c.get("shared_matches", 0) >= 50:
    score += 5  # Bonus für langjährige Mitspieler
if c.get("shared_matches", 0) >= 100:
    score += 5  # Bonus für enge Spielpartner
```

---

## Aufwand-Schätzung

| Phase | Requests | Zeit | Ergebnis |
|-------|----------|------|----------|
| Scraping (33 Coaches) | ~200-400 Requests (je nach Pagination) | ~20-40 Min (3s Delay) | 33 JSON-Files |
| Integration (build_coach_network.py) | 0 | 30 Min Code | Step 2c + Scoring |
| Template Update | 0 | 15 Min | GS-Stats im Detail-Panel |
| Rebuild 461 Netzwerke | 0 | ~100 Min | Aktualisierte Dashboards |
| **Gesamt** | **~400** | **~3h** | **Punkt 4 des Briefs abgehakt** |

---

## Request-Budget & Rate-Limiting

- **33 Coaches × ~6-12 Seiten im Schnitt = ~200-400 Requests**
- Klose/Kompany haben vermutlich 15-20+ Seiten (500+ Teammates)
- **Delay: 3s zwischen Requests** (konservativ, TM toleriert das)
- **Session-Pause: 30s alle 50 Requests** (Anti-Block)
- **Retry: 1× bei 429, dann 60s Pause + Retry**
- **User-Agent: Rotation** aus 3-4 Browser-Strings

---

## Ausführungsreihenfolge

```
1. Script schreiben: execution/scrape_gemeinsame_spiele.py
   - Basis: bestehende Funktionen aus scrape_teammates.py wiederverwenden
   - Batch-Modus, --all, --skip-existing, --dry-run
   - Output: data/gemeinsame_spiele/{trainer_tm_id}.json

2. Dry-Run: python execution/scrape_gemeinsame_spiele.py --dry-run
   → Zeigt 33 Coaches, geschätzte Requests

3. Scrapen: python execution/scrape_gemeinsame_spiele.py --all --min-matches 5
   → ~20-40 Min, ~200-400 Requests
   → Zwischenstand prüfen nach 5 Coaches

4. Validierung: Klose-Datei checken
   - Erwartet: 400-600 Teammates
   - Thomas Müller, Manuel Neuer, etc. sollten ganz oben stehen
   - shared_matches > 200 für langjährige Bayern-Mitspieler

5. Integration: build_coach_network.py Step 2c einbauen
   - GemeinsameSpiele-JSON laden
   - Bestehende Kontakte anreichern (shared_matches, shared_minutes)
   - Neue Kontakte nur bei 10+ Spielen

6. Template: Detail-Panel GS-Stats
   - "X gemeinsame Spiele, Yh auf dem Platz"

7. Rebuild + Deploy
   - python execution/generate_all_bl_coaches.py --all-networks --include-historical
   - cd output && npx vercel deploy --prod
```

---

## Edge Cases

### Coach hat player_tm_id aber GemeinsameSpiele-Seite ist leer
- Manche Ex-Spieler haben auf TM keine gemeinsame-Spiele-Daten (Amateur, Jugend)
- Script: Leeres JSON speichern mit `"total_teammates": 0`
- Nicht als Fehler werten

### TM-ID Kollision (Spieler-ID ≠ Trainer-ID)
- Bei 33 Coaches ist das bereits gelöst: `player_tm_id` im Profil ist die korrekte Spieler-ID
- Die `/gemeinsameSpiele/spieler/{player_tm_id}` URL nutzt die Spieler-ID, nicht die Trainer-ID

### Teammate ist bereits im Netzwerk (als Trainer-Kollege)
- `contacts_map` Dedup greift automatisch
- Bestehenden Kontakt anreichern statt duplizieren
- `_gs_verified: True` Flag setzen

### Pagination endet unerwartet
- TM zeigt manchmal weniger Seiten als erwartet
- Script: Pagination robust parsen, bei leerer Seite aufhören
- Nicht crashen bei fehlender Pagination

### Sehr große Ergebnisse (Klose: 600+ Teammates)
- Alle speichern in JSON (kein Limit beim Scraping)
- Filter (`--min-matches 5`) erst bei Integration anwenden
- Dashboard: Mitspieler mit < 10 gemeinsamen Spielen nicht als Kontakt aufnehmen

---

## Learnings Log
_(Claude Code updatet diesen Abschnitt während der Ausführung)_

- [ ] Wie viele Seiten hat Klose (erwartet: 15-20)?
- [ ] Rate-Limiting-Verhalten von TM bei /gemeinsameSpiele
- [ ] Parsing-Quirks der Tabelle (Spaltenreihenfolge, fehlende Daten)
- [ ] Wie viele neue Kontakte kommen pro Coach dazu (vs. Squad-Overlap)?
- [ ] Performance-Impact auf Dashboard (Klose mit 600+ Mitspieler-Nodes)
