# Coach Network Explorer — Project Roadmap

**Stand: 26.03.2026 (Session 2)** | **Live:** https://coach-network-explorer.vercel.app

---

## Status Quo (26.03.2026 — nach Sprint 10+11)

| Metrik | Wert | Vorher (26.03. morgens) | Vorher (21.03.) |
|--------|------|-------------------------|-----------------|
| Dashboards | **56** (BL1 + BL2 + BL3) | 36 (BL1 + BL2) | 36 |
| Kontakte gesamt | **16.497** (Ø 295/Coach) | 5.734 (Ø 159/Coach) | 5.734 |
| Mitspieler (former_teammate) | **4.077** | 0 | 0 |
| Personen in DB | **34.513** | 34.513 | 14.989 |
| Clubs in Registry | **480** (+6 P0-Ligen) | 307 | 119 |
| Squad-Files | **2.781** | 2.776 | 1.114 |
| Staff-Files | **566** | 308 | 119 |
| SQLite DB | **18.7 MB, 176k Rows** | 18.7 MB, 176k | 7.3 MB, 67k |
| Spielerkarrieren gescraped | **33/36 BL-Coaches** | 0 | 0 |
| Berater-Firmen | **1.273** (6.835 Spieler) | 1.273 | 0 |

### Was funktioniert
- Force-directed Canvas-Graph mit Drill-Down + Breadcrumb-Nav
- Station-Cluster mit Labels, Kategorie-Filter, Pro-Filter (Trainer/SD)
- **Mitspieler-Kategorie** mit "M"-Badge und eigenem Filter (former_teammate)
- Suche, Detail-Panel, TM-Links
- Sortierbare Index-Seite mit BL1/BL2/BL3-Sektionen, Flaggen, Kontakt-/Stationszahlen
- Ein-Klick-Update: `bash run_mvp.sh`
- Internationale Daten: PL, La Liga, Serie A, Ligue 1, Eredivisie + **BEL, SUI, TUR, DEN, SWE, NOR** (P0 komplett)
- **Spielerkarrieren** für 33/36 BL-Coaches integriert (Step 2b im Network Builder)
- SQLite mit vollem internationalem Dataset (18.7 MB, 0 FK-Violations)
- Audit-Fixes: Fonts, Farben, Nationalität, 404, Back-Link, Club-Normalisierung

### Bekannte Lücken
- Keine historischen BL-Trainer oder NLZ-Coaches als Dashboards (nur aktuelle Saison)
- P1-Ligen (Championship, Serie B, Ligue 2, LaLiga2, 2.Liga AT, Eerste Divisie) fehlen
- Spielerkarriere-Daten ohne Zeiträume (Dates "?") → Season-Matching schätzt anhand Coaching-Start
- 3 BL-Coaches ohne Spielerkarriere: Hjulmand, Walter, Vogel
- Einige Coaches mit playing_career aber 0 Teammates (z.B. Kovac 570 Kontakte, 0 Teammates) → Debug nötig
- Code-Qualität: normalize_club() 5× dupliziert, 17× bare except, 0 Tests
- INP Performance bei Canvas-Events (4-16s Blocking)

---

## Phasen-Übersicht

```
Sprint 8  ✅ DONE    Top-5-Ligen International (Registry + Squads + Staff)
Sprint 8b ✅ DONE    Profile Scraping (34.513 Profile, 51.9 MB Master)
Sprint 6  ✅ DONE    Berater-Feld (57% Coverage, 1.273 Firmen)
Sprint 4  ✅ DONE    Audit-Fixes (Fonts, Farben, Nationalität, 404, Back-Link, Auto-Refresh)
Sprint 5  ✅ DONE    SQLite Rebuild + Dashboard-Regenerierung mit vollem Dataset
Sprint 10 ✅ DONE    P0-Ligen (BEL/SUI/TUR/DEN/SWE/NOR) → 480 Clubs, 566 Staff, BL3 Dashboards
Sprint 11 ✅ DONE    Spielerkarriere-Integration (33/36 Coaches, 4.077 Mitspieler, Step 2b)
Sprint 7  ✅ DONE    BL3 Dashboards (absorbiert in Sprint 10) → 56 Dashboards live
Sprint 10b ← Jetzt  P1-Ligen + Weitere Expansion + Debugging (Kovac 0 Teammates)
Sprint 9             Performance + UX Polish + Graph-Redesign
```

---

## Sprint 4: Audit-Fixes ✅ DONE (2026-03-24)

**Directive:** `directives/audit_fixes_implementation.md`

### Ergebnis
| # | Fix | Status |
|---|-----|--------|
| 1 | Nationalität center_info (Kovac → "Kroatien") | ✅ |
| 2 | Fehlende Flaggen + dissolved state filter | ✅ |
| 3 | "Zurück zum Index" Link in Dashboards | ✅ |
| 4 | Font-Stack (IBM Plex Sans + JetBrains Mono) | ✅ |
| 5 | Rot-Akzent (#c8102e) | ✅ |
| 6 | 404-Seite | ✅ |
| + | Club-Name-Normalisierung (22 Mappings) | ✅ |
| + | Daily Auto-Refresh Cron (7:22 Uhr) | ✅ |
| + | Data Integrity Spot-Checks | ✅ |

---

## Sprint 5: SQLite Rebuild + Dashboard-Regenerierung

**Directive:** `directives/build_sqlite_database.md`

### SQLite Rebuild ✅ (2026-03-26)
| Tabelle | Zeilen | Vorher |
|---------|--------|--------|
| clubs | 4.604 | 1.788 |
| persons | 34.513 | 14.989 |
| career_history | 31.500 | 11.906 |
| squad_entries | 95.365 | 35.864 |
| staff_entries | 7.167 | 2.877 |
| career_transitions | 382 | 61 |
| club_seasons | 2.960 | — |
| **Gesamt** | **~176k** | **~67k** |

Build: 21.5s, 18.7 MB, 0 FK-Violations.

### SQLite Rebuild ✅ Done
Build: 21.5s, 18.7 MB, 0 FK-Violations. Bereit für projectFIVE.

### Dashboard-Regenerierung ⏳
Nächster Schritt: `python execution/generate_all_bl_coaches.py` + Deploy
- Netzwerke werden deutlich dichter durch internationale Kontakte
- Blessin: ~70 → ~150-200+ Kontakte erwartet
- Berater-Beziehungen im SQLite (Dashboard-Integration optional)

### Code-Quality-Fixes ⏳
Siehe `directives/code_quality_fixes.md`:
- Shared `lib/normalization.py` extrahieren
- Bare `except:` in Legacy-Scripts fixen
- Pytest Grundgerüst aufbauen
- Filter-Default im Dashboard-Template ändern

---

## Sprint 6: Berater-Scrape ✅ DONE (2026-03-24)

**Ergebnis:**
- **6,835/11,925 Spieler** mit Berater-Feld (57% Coverage)
- **1,273 unique Beraterfirmen** identifiziert
- Feld wird als Teil des Player-Profile-Scrapings extrahiert
- Coverage am stärksten in BL1/BL2 und Top-5-Ligen (TM pflegt dort am besten)

### Noch offen
- Berater in Dashboard-Netzwerke integrieren (als eigene Kategorie "Agent" mit "A"-Badge)
- Berater-zu-Trainer-Beziehungen: Welche Trainer teilen sich einen Berater?
- → Kann in Sprint 5 (Dashboard-Regenerierung) mit eingebaut werden

---

## Sprint 7: BL3 + NLZ + Historische Trainer

**Directive:** `directives/sprint3_expand_leagues.md`
**Aufwand:** ~4-6 Stunden (hauptsächlich Batch-Generierung)
**Risiko:** Gering (alle Daten bereits vorhanden)

### Ziel
Von 36 auf ~150-200 Dashboards expandieren.

| Gruppe | Geschätzte Anzahl | Datenquelle |
|--------|------------------|-------------|
| 3. Liga (aktuell) | ~20 | `club_registry.json` (BL3) |
| NLZ-Leiter (U19/U17-BL) | ~20-30 | `staff/` Dateien, Section "Jugend/NLZ" |
| Historische BL1/BL2 (20/21–24/25) | ~80-120 | `person_profiles/` Career History |

### Schritte
1. `generate_all_bl_coaches.py` um CLI-Flags erweitern (`--leagues`, `--include-nlz`, `--historical`)
2. Index-Seite: Neue Sektionen (BL3, NLZ, Ehemalige)
3. Deduplizierung: Aktuelle Trainer nicht auch als Historische zeigen
4. Batch-Generierung (~30-60 Min für Netzwerke + Drill-Down)
5. Deploy

### Erwartetes Ergebnis
- 150-200 Dashboards live
- Index-Seite mit 5 Sektionen (BL1, BL2, BL3, NLZ, Ehemalige)
- Historische Trainer zeigen komplette Karriere-Netzwerke

---

## Sprint 8: Top-5-Ligen International ✅ DONE (2026-03-24)

**Directive:** `directives/expand_international_leagues.md`

### Ergebnis
| Phase | Ergebnis |
|-------|----------|
| Club Registry | **307 Clubs** (+188 neue aus PL, La Liga, Serie A, Ligue 1, Eredivisie) |
| Squads | **2,776 Squad-Files** (+1,662) |
| Staff | **308 Staff-Files** (+189) |
| Persons Index | **34,513 Personen** (+19,524) |
| Career Transitions | **404** (+343) |

### Sprint 8b: Profile Scraping ✅ DONE (2026-03-26)
- **34,513 Profile** gescraped (27,734 Spieler + 6,779 Trainer/Staff)
- **Master-Datei:** 51.9 MB (`data/persons_master.json`)
- Vorbedingung für Sprint 5 (SQLite Rebuild) ist erfüllt

---

## Sprint 10: Systematische Expansion (demand-driven)

**Directive:** `directives/systematic_expansion.md` + `directives/league_expansion_tiers.md`
**Script:** `execution/analyze_coverage_gaps.py`
**Aufwand:** ~2-3 Sessions
**Philosophie:** Daten bestimmen, wo expandiert wird — nicht Bauchgefühl.

### Fortschritt

| Phase | Was | Status |
|-------|-----|--------|
| **1. Gap Analysis** | `analyze_coverage_gaps.py` auf 34.513 Profile | ✅ 4.296 fehlende Clubs, 111/191 BL-Coach-Stationen uncovered |
| **2. Foreign Staff** | `scrape_foreign_staff.py --all-bl-coaches` | ✅ 111 fehlende BL-Coach-Clubs gescraped |
| **3. Liga-Tiers definiert** | P0/P1/P2 mit verifizierten TM-Codes + Slugs | ✅ 21 Ligen, alle URLs verifiziert |
| **4. Registry Expansion** | P0-Ligen hinzufügen (BEL, SUI, TUR, DEN, SWE, NOR) | ✅ 480 Clubs (+173 neue) |
| **5. Batch Scrape** | Staff + Squads für neue Clubs | ✅ 566 Staff, 2.781 Squads |
| **6. Profile Enrichment** | Neue Personen scrapen (on-demand) | ✅ 34.513 Profile |
| **7. Dashboard Expansion** | BL3 Coaches hinzugefügt | ✅ 56 Dashboards (18 BL1 + 18 BL2 + 20 BL3) |
| **8. Measure** | Gap Analysis erneut laufen | ⏳ nach Deploy |

### Priorisierungs-Framework

| Prio | Kriterium | Aktion |
|------|-----------|--------|
| P0 | Liga hat 5+ Clubs in BL-Coach-Karrieren | Komplette Liga ins Registry |
| P1 | Liga hat 3+ Clubs in Gesamtdatenbank | Liga hinzufügen |
| P2 | Einzelclub mit 10+ Personen-Referenzen | Club einzeln hinzufügen |
| P3 | Youth/Reserve-Teams bekannter Clubs | Über Foreign Staff scrapen |

### Bekannte TM Liga-Codes

| Liga | Code | Land |
|------|------|------|
| Belgian Pro League | BE1 | 🇧🇪 |
| Turkish Süper Lig | TR1 | 🇹🇷 |
| Swiss Super League | C1 | 🇨🇭 |
| Danish Superliga | DK1 | 🇩🇰 |
| Scottish Premiership | SC1 | 🏴 |
| Championship (ENG) | GB2 | 🏴 |
| Serie B (ITA) | IT2 | 🇮🇹 |
| Ligue 2 (FRA) | FR2 | 🇫🇷 |
| Segunda División | ES2 | 🇪🇸 |

### Erwartete Ergebnisse

| Metrik | Vorher | Nachher |
|--------|--------|---------|
| Registry Clubs | 307 | 500+ |
| Ø Kontakte/Coach | 159 | 200+ |
| Dashboards | 36 | 150-200 |
| Foreign Station Coverage | ~60% | 90%+ |

---

## Sprint 11: Spielerkarriere-Integration (Mitspieler)

**Directive:** `directives/playing_career_integration.md`
**Aufwand:** ~2-3 Stunden
**Risiko:** Gering (additiv, bricht nichts)

### Konzept
Viele BL-Trainer waren Profi-Spieler. TM hat separate Spieler-Profile, die unser Scraper bislang ignoriert. Die Spielerkarriere wird als `playing_career` Feld ins Profil geschrieben → der bestehende Profile-Index findet automatisch Mitspieler über Squad-Files.

### Ergebnisse (Implementiert)

| Coach | Vorher | Nachher | Neue Mitspieler |
|-------|--------|---------|-----------------|
| Riera | ~189 | **1.349** | 1.160 |
| Klose | ~160 | **745** | 437 |
| Polanski | ~151 | **671** | 520 |
| Kompany | ~184 | **490** | 306 |
| Blessin | ~150 | **314** | 164 |
| **Gesamt (56 Coaches)** | — | **16.497** | **4.077** |

### Schritte

1. ✅ Konzept + Directive geschrieben
2. ✅ `scrape_playing_careers.py` — 33/36 BL-Coaches haben Spielerkarriere
3. ✅ Network Builder Step 2b (`former_teammate` Kategorie) implementiert
4. ✅ Dashboard-Template: Mitspieler-Kategorie mit eigenem Filter
5. ✅ Netzwerke regeneriert (56 Coaches × ~295 Kontakte = 16.497)

### Offene Punkte
- Kovac hat 570 Kontakte aber 0 Mitspieler trotz playing_career (5 Clubs) → Debug
- Spielerkarriere-Daten ohne Zeiträume → Season-Range wird geschätzt
- 3 Coaches ohne Spielerkarriere: Hjulmand, Walter, Vogel

### Edge Cases gelöst
- TM nutzt verschiedene IDs für Spieler/Trainer → Link auf Trainer-Profilseite liefert korrekte Spieler-ID
- Squad-Files nur ab 2010 → ältere Spielerkarrieren bleiben lückenhaft
- Große Netzwerke (Kompany ~490) → Mitspieler-Filter default OFF bei >200 Kontakten

---

## Sprint 9: Performance + UX Polish

**Directive:** Noch zu schreiben
**Aufwand:** ~3-4 Stunden
**Risiko:** Gering

### INP Performance
- Canvas-Events blocken UI 4-16 Sekunden
- Fix: Force-Simulation in Web Worker oder `requestAnimationFrame` chunks
- Alternativ: Node-Positionen cachen nach erstem Layout

### UX Verbesserungen
- Open Graph Tags (Social Preview bei Link-Sharing)
- Keyboard-Navigation (Tab durch Kontakte, Enter = Detail öffnen)
- Responsive: Mobile Layout für Detail-Panel
- Loading-State: Spinner während Force-Simulation
- Accessibility: ARIA-Labels, Focus-Indicators

---

## Empfohlene Reihenfolge

```
✅ Sprint 8  (International)       — DONE: 307 Clubs, 34.513 Personen, 5 Ligen
✅ Sprint 8b (Profile Scraping)    — DONE: 34.513 Profile, 51.9 MB Master
✅ Sprint 6  (Berater)             — DONE: 1.273 Firmen, 57% Coverage
✅ Sprint 4  (Audit-Fixes)         — DONE: Fonts, Farben, Nationalität, 404, Cron
✅ Sprint 5  (SQLite)              — DONE: 18.7 MB, 176k Rows, 0 FK-Violations
✅ Sprint 10 (Systematische Exp.)  — DONE: 480 Clubs, 566 Staff, P0-Ligen komplett, BL3 Dashboards
✅ Sprint 11 (Mitspieler)          — DONE: 33/36 Coaches, 4.077 Mitspieler, Ø 295 Kontakte/Coach
✅ Sprint 7  (BL3)                 — DONE: 56 Dashboards (absorbiert in Sprint 10)
   → Nächster Checkpoint: Deploy + Demo für SPORTFIVE-Stakeholder
⏳ Sprint 10b (P1-Ligen)           — Championship, Serie B, Ligue 2, LaLiga2, 2.Liga AT, Eerste Divisie
→ Sprint 9  (Performance/UX)      — Graph-Redesign + vor breitem Rollout
```

**Nächste Aktion:** Deploy (Vercel Auth nötig), dann Sprint 10b (P1-Ligen) + Kovac-Teammate-Debug.
