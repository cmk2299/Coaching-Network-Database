# Directive: Historical Coaches Expansion

## Ziel
Die 56 aktiven BL1/BL2/BL3-Dashboards um **historische Trainer** erweitern — ehemalige BL-Cheftrainer, aktuell vereinslose Trainer, und aufsteigende Co-Trainer. Zielgröße: 150-200 Dashboards.

## Kontext
Im SQLite/persons_master existieren **424 Trainer mit BL-Erfahrung**, die aktuell kein Dashboard haben. Diese sind hochrelevant für projectFIVE: vereinslose Trainer suchen Jobs, ehemalige BL-Trainer haben extensive Netzwerke, Co-Trainer werden zu Cheftrainern.

## Kategorien

### Kategorie A: Ehemalige BL1/BL2 Cheftrainer (letzte 5 Saisons)
- **Kriterium:** War Head Coach in BL1/BL2 seit 2020/21, aktuell nicht bei einem BL1/2/3-Verein
- **Beispiele:** Peter Bosz, Adi Hütter, Bo Svensson, Markus Weinzierl, Steffen Baumgart
- **Relevanz:** Höchste — diese Trainer werden regelmäßig für BL-Positionen gehandelt
- **Geschätzte Anzahl:** 40-60

### Kategorie B: Aktuell vereinslose BL-Trainer
- **Kriterium:** `current_club` = leer/ohne Verein, hat BL-Karriere-Einträge
- **Relevanz:** Hoch — aktive Kandidaten für offene Positionen
- **Geschätzte Anzahl:** 30-50

### Kategorie C: Co-Trainer / Assistenten mit Potenzial
- **Kriterium:** Aktuell Co-Trainer bei BL1/BL2-Verein, hat eigene Karriere als Spieler oder Trainer
- **Relevanz:** Mittel — werden oft zum Interimstrainer befördert
- **Geschätzte Anzahl:** 50-80

### Kategorie D: Historisch relevante BL-Trainer (vor 2020)
- **Kriterium:** War Head Coach in BL1/BL2, mindestens 2 Saisons, aber vor 2020/21
- **Beispiele:** Thomas Tuchel, Jürgen Klopp (sofern nicht international aktiv)
- **Relevanz:** Mittel bis hoch — bei Rückkehr nach Deutschland sofort relevant
- **Geschätzte Anzahl:** 80-120

## Implementierung

### Phase 1: Identifikation & Filterung
**Script:** `execution/identify_historical_coaches.py` (neu)

```
Inputs:
  - data/persons_master.json (34,513 Personen)
  - data/staff/*.json (657 Staff-Files)
  - data/squads/*.json (3,273 Squad-Files)

Logic:
  1. Alle Personen mit type=trainer aus persons_master laden
  2. Karriere-Einträge filtern: wer war je Head Coach in BL1/BL2/BL3?
  3. Aktive BL-Trainer (56 current dashboards) ausschließen
  4. Kategorisieren (A/B/C/D) basierend auf:
     - Letzte BL-Station (wann?)
     - Aktueller Status (vereinslos vs. Ausland vs. Co-Trainer)
     - Gesamtdauer BL-Erfahrung
  5. Priorisierte Liste als JSON ausgeben

Output: data/historical_coaches_candidates.json
  - tm_id, name, category (A/B/C/D), last_bl_club, last_bl_season, current_status
  - Sortiert nach Kategorie, dann nach letzter BL-Saison (neueste zuerst)
```

### Phase 2: Netzwerk-Generierung
**Script:** Bestehend `execution/build_coach_network.py` (keine Änderung nötig)

```
- Für jeden Kandidaten: build_network(tm_id) aufrufen
- Speichern in data/networks/{tm_id}.json
- Batch-Mode: alle Kategorie-A zuerst, dann B, C, D
- Erwartete Laufzeit: ~2-5 Min pro Coach (je nach Karrierelänge)
```

### Phase 3: Dashboard-Generierung erweitern
**Script:** `execution/generate_all_bl_coaches.py` (anpassen)

```
Änderungen:
  1. Neuer --include-historical Flag
  2. Index-Page erweitern:
     - Neue Sektionen: "Ehemalige BL-Trainer", "Vereinslose Trainer", "Co-Trainer"
     - Oder: Filter-Tabs statt fester Sektionen
  3. Dashboard-Generierung für alle Kandidaten
  4. Kategorie-Badge im Index (A/B/C/D oder beschreibend)
```

### Phase 4: Index-Page Redesign
```
Aktuelle Struktur:
  - BL1 (18 Trainer)
  - BL2 (18 Trainer)
  - BL3 (20 Trainer)

Neue Struktur:
  - Aktive BL1 (18)
  - Aktive BL2 (18)
  - Aktive BL3 (20)
  - Ehemalige BL-Cheftrainer (40-60)
  - Vereinslose Trainer (30-50)
  - Co-Trainer & Assistenten (50-80)

Oder besser: Einheitliche Tabelle mit Filter-Chips:
  [Alle] [BL1] [BL2] [BL3] [Ehemalige] [Vereinslos] [Co-Trainer]
```

## Reihenfolge
1. `identify_historical_coaches.py` schreiben + laufen lassen → Kandidatenliste validieren
2. Batch-Netzwerke für Kategorie A generieren (höchste Prio)
3. Index-Page mit neuer Sektion für Kat A deployen
4. Kategorie B+C nachladen
5. Kategorie D als letztes (am meisten Coaches, geringste Dringlichkeit)

## Abhängigkeiten
- Spielerkarriere-Integration (Sprint 11) sollte VOR historischen Coaches laufen → mehr Mitspieler
- P1+P2 Ligen-Daten verbessern Coverage der historischen Karrieren

## Erfolgskriterien
- [ ] 150+ Dashboards live
- [ ] Alle vereinslosen Ex-BL-Trainer haben ein Dashboard
- [ ] Index-Page zeigt klar aktive vs. historische Trainer
- [ ] Netzwerkqualität (Ø Kontakte) vergleichbar mit aktiven Trainern
