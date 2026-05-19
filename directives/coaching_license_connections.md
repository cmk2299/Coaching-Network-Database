# Directive: Coaching License Connections (Lehrgangs-Absolventen)

## Ziel
Neuer Relationship-Typ: **Lehrgangs-Kollege** — Trainer, die denselben offiziellen Trainerlehrgang im gleichen Jahrgang absolviert haben. Diese Verbindungen sind oft stärker als Vereins-Connections, weil die Teilnehmer monatelang zusammen lernen, Praktika machen und ein Netzwerk aufbauen.

## Warum das wichtig ist
- Der **DFB Fußball-Lehrer-Lehrgang** (Hennes-Weisweiler-Akademie, Köln) ist DER zentrale Knotenpunkt im deutschen Trainernetzwerk
- ~20-25 Absolventen pro Jahrgang, die sich über 10 Monate intensiv kennenlernen
- Berühmte Kohorten: Klopp & Tuchel (2005), Nagelsmann (2016), Flick (1999), etc.
- Auch UEFA-A/B-Lehrgänge und Management-Lehrgänge (z.B. DFB-Akademie, FIFA/CIES) schaffen Verbindungen
- Für projectFIVE hochrelevant: "Wer kennt wen vom Lehrgang?" ist eine Standardfrage im Scouting

## Verfügbare Daten

### Was wir haben (TM-Profil)
- `license` Feld bei 1,722 Personen:
  - UEFA-Pro-Lizenz: 523
  - UEFA-A-Lizenz: 361
  - UEFA-B-Lizenz: 290
  - Torwarttrainer-Lizenz: 140
  - DFB-Elite-Jugend-Lizenz: 29
  - Weitere: 379

### Was fehlt
- **Lehrgangs-Jahrgang** — TM speichert NICHT, wann/wo die Lizenz erworben wurde
- **Lehrgangs-Ort** — DFB (Hennef/Köln), ÖFB (Wien), SFV (Magglingen), etc.
- **Kohorten-Zugehörigkeit** — wer war mit wem im selben Jahrgang

## Datenquellen für Kohorten

### Quelle 1: DFB Fußball-Lehrer-Liste (Primär)
- Die DFB-Akademie / Hennes-Weisweiler-Akademie veröffentlicht regelmäßig Absolventenlisten
- Wikipedia: "Liste der DFB-Fußball-Lehrer" — enthält Jahrgänge seit ~1970
- URL: `https://de.wikipedia.org/wiki/Liste_der_DFB-Fußball-Lehrer`
- Struktur: Jahrgang → Name → aktueller Verein
- **Aktion:** Scrapen, parsen, tm_id matchen

### Quelle 2: Medienberichte pro Jahrgang
- Kicker, Sportbild, DFB.de berichten regelmäßig über neue Absolventen
- Suchquery: `"Fußball-Lehrer" "Lehrgang" "{year}" site:dfb.de OR site:kicker.de`
- **Aktion:** Web-Suche pro Jahrgang (2010-2025), Namen extrahieren

### Quelle 3: Internationale Äquivalente
- **ÖFB-Trainerkurs** (Österreich) — UEFA-Pro in Wien
- **SFV (Schweiz)** — UEFA-Pro in Magglingen
- **FA (England)** — Pro License at St George's Park
- **KNVB (Niederlande)** — Trainer cursus Zeist
- Schwieriger zu scrapen, aber für P0-Ligen (BEL, SUI, TUR) relevant

### Quelle 4: Management-/Sportdirektor-Lehrgänge
- **DFB-Akademie Management-Kurs** — für angehende Sportdirektoren
- **FIFA/CIES International University Network** — Executive Programme in Sports Management
- **UEFA MIP** (Master for International Players) — Übergangs-Lehrgang
- Absolventenlisten teilweise auf dfb.de oder CIES-Website

### Quelle 5: Heuristische Schätzung (Fallback)
- Wenn Kohorte unbekannt: Schätze Lehrgangs-Jahr aus Karrieredaten
  - Fußball-Lehrer ≈ Karriereende + 2-3 Jahre (für Spieler-zu-Trainer)
  - Oder: Erster Cheftrainer-Posten - 1-2 Jahre
- Ermöglicht "wahrscheinliche Zeitgenossen" auch ohne exakte Kohorte

## Implementierung

### Phase 1: DFB Fußball-Lehrer-Liste scrapen
**Script:** `execution/scrape_coaching_licenses.py` (neu)

```
1. Wikipedia-Seite "Liste der DFB-Fußball-Lehrer" abrufen + cachen
2. Tabelle parsen: Jahrgang, Name, ggf. weitere Felder
3. Name → tm_id Matching:
   - Exakter Namens-Match gegen persons_master.json
   - Bei Mehrdeutigkeit: Nationalität + Geburtsjahr als Disambiguierung
   - Manuelles Mapping für Sonderfälle (z.B. Namensänderung)
4. Output: data/coaching_licenses.json
   {
     "dfb_fussball_lehrer": {
       "2005": [
         {"name": "Jürgen Klopp", "tm_id": 118, "matched": true},
         {"name": "Thomas Tuchel", "tm_id": 7471, "matched": true},
         ...
       ],
       "2016": [
         {"name": "Julian Nagelsmann", "tm_id": 55tried, "matched": true},
         ...
       ]
     },
     "other_courses": { ... }
   }
```

### Phase 2: Kohorten als Relationship-Typ integrieren
**Script:** `execution/build_coach_network.py` (erweitern)

```
Neuer Step 4: Lehrgangs-Kollegen
  1. coaching_licenses.json laden
  2. Für den Ziel-Coach: In welchem Jahrgang war er?
  3. Alle anderen Absolventen desselben Jahrgangs → neue Kontakte
  4. Kategorie: "lehrgang_colleague" (neue Farbe, z.B. #9b59b6 Lila)
  5. Station: "DFB Fußball-Lehrer {Jahrgang}" (z.B. "DFB Fußball-Lehrer 2005")
  6. Falls auch über Verein verbunden → doppelte Verbindung, stärkere Gewichtung
```

### Phase 3: Dashboard-Template erweitern
```
- Neue Kategorie in Legend: "Lehrgang" mit Farbe #9b59b6
- Station-Cluster für Lehrgangs-Kohorten
- Im Detail-Panel: "Fußball-Lehrer-Lehrgang 2005 (gemeinsam mit X, Y, Z)"
- Filter-Chip: [Lehrgang] neben [Spieler] [Staff] [Mitspieler]
```

### Phase 4: Management-Lehrgänge ergänzen
```
- DFB-Akademie Sportdirektor-Kurs: Absolventen scrapen
- FIFA/CIES: Alumni-Listen, falls verfügbar
- Eigener Lehrgangs-Typ in coaching_licenses.json
```

## Datenmodell

### coaching_licenses.json Schema
```json
{
  "courses": [
    {
      "course_id": "dfb_fussball_lehrer",
      "name": "DFB Fußball-Lehrer-Lehrgang",
      "provider": "DFB",
      "location": "Hennes-Weisweiler-Akademie, Köln",
      "license_level": "UEFA-Pro-Lizenz",
      "cohorts": {
        "2005": {
          "graduates": [
            {"name": "Jürgen Klopp", "tm_id": 118},
            {"name": "Thomas Tuchel", "tm_id": 7471}
          ],
          "source": "wikipedia",
          "verified": true
        }
      }
    },
    {
      "course_id": "dfb_management",
      "name": "DFB-Akademie Management-Kurs",
      "provider": "DFB",
      "cohorts": { ... }
    }
  ]
}
```

### Neuer Kontakt-Typ im Netzwerk
```json
{
  "name": "Thomas Tuchel",
  "tm_id": 7471,
  "category": "lehrgang_colleague",
  "stations": ["DFB Fußball-Lehrer 2005"],
  "relationship_detail": "Gemeinsamer Fußball-Lehrer-Lehrgang 2005",
  "license": "UEFA-Pro-Lizenz"
}
```

## Reihenfolge
1. Wikipedia DFB-FL-Liste scrapen → Jahrgänge + Namen → tm_id Matching
2. Kohorten-Daten in `coaching_licenses.json` speichern
3. `build_coach_network.py` um Step 4 erweitern
4. Dashboard-Template: neue Kategorie + Farbe
5. Alle 56 Dashboards neu generieren + testen
6. Management-Lehrgänge als Phase 2

## Geschätzter Impact
- DFB Fußball-Lehrer seit 2000: ~25 Jahrgänge × ~22 Absolventen ≈ **550 Personen**
- Davon im System (UEFA-Pro in persons_master): geschätzt 200-300
- Pro BL-Coach: +10-20 Lehrgangs-Kontakte (davon ~5-10 auch BL-Trainer)
- **Einzigartig:** Dieser Relationship-Typ existiert in keinem anderen Tool

## Edge Cases
- Trainer mit Lizenz aus anderem Verband (z.B. Marsch, Glasner → ÖFB)
- Trainer die den Lehrgang abgebrochen haben
- Nachrücker / Sonderlehrgänge (verkürzte Programme für Ex-Nationalspieler)
- Personen die SOWOHL als Trainer als auch als Sportdirektor Lehrgänge besucht haben
- Name-Matching: Sonderzeichen (ö→oe, ć→c), Doppelnamen, Namensänderungen

## Abhängigkeiten
- Persons_master muss aktuell sein (✅ 34,513 Einträge)
- Wikipedia-Seite muss erreichbar + parsebar sein
- DFB-FL-Liste muss Jahrgänge enthalten (historisch gut dokumentiert)
- Kein API-Schlüssel nötig (öffentliche Quellen)

## Erfolgskriterien
- [ ] DFB-FL-Liste gescraped, ≥80% der Namen zu tm_ids gemappt
- [ ] coaching_licenses.json mit ≥15 Jahrgängen (2000-2025)
- [ ] Neuer Kategorie-Typ im Dashboard sichtbar und filterbar
- [ ] Klopp-Dashboard zeigt Tuchel als Lehrgangs-Kollege (und umgekehrt)
- [ ] Durchschnittlich +10 Kontakte pro BL-Coach durch Lehrgangs-Daten
