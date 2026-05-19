# League Expansion Tiers — Concrete Execution Plan

**Stand:** 26.03.2026
**Basis:** Gap Analysis (4.296 fehlende Clubs, 111/191 BL-Coach-Career-Clubs uncovered)
**Vorbedingung:** Foreign Staff Scraping (`--all-bl-coaches`) läuft/fertig

---

## P0 — Sofort hinzufügen (höchster BL-Coach Impact)

Kriterium: Liga hat 5+ Clubs in BL-Coach-Karrieren, oder multiple aktuelle BL-Trainer haben dort gearbeitet.

| Liga | TM Code | Short | Clubs ~est | BL-Coach-Bezug |
|------|---------|-------|-----------|----------------|
| **Belgian Pro League** | BE1 | BEL | ~18 | Blessin (Union SG, KV Oostende), Kompany (Anderlecht) |
| **Swiss Super League** | C1 | SUI | ~12 | RB-Kosmos (Salzburg→Leipzig-Pipeline), div. Trainer |
| **Turkish Süper Lig** | TR1 | TUR | ~20 | Div. BL-Coaches mit Türkei-Stints |
| **Danish Superliga** | DK1 | DEN | ~14 | Hjulmand (Nordsjælland, Lyngby), Rösler-Kontakte |
| **Swedish Allsvenskan** | SE1 | SWE | ~16 | Rösler (Malmö), skandinavische Netzwerke |
| **Norwegian Eliteserien** | NO1 | NOR | ~16 | Rösler (Viking), skandinavische Pipeline |

**Summe P0:** ~96 neue Clubs, ~96 Staff-Pages, ~960 Squad-Pages (×10 Saisons)
**Scraping-Zeit:** ~50 Min Staff + ~50 Min Squads = ~100 Min

### Config für `scrape_club_registry.py`

```python
# P0: Direct BL Coach Impact
"belgian_pro_league": {
    "name": "Jupiler Pro League",
    "short": "BEL",
    "path": "/jupiler-pro-league/startseite/wettbewerb/BE1",
    "wettbewerb_id": "BE1",
},
"swiss_super_league": {
    "name": "Super League",
    "short": "SUI",
    "path": "/super-league/startseite/wettbewerb/C1",
    "wettbewerb_id": "C1",
},
"turkish_super_lig": {
    "name": "Süper Lig",
    "short": "TUR",
    "path": "/super-lig/startseite/wettbewerb/TR1",
    "wettbewerb_id": "TR1",
},
"danish_superliga": {
    "name": "Superliga",
    "short": "DEN",
    "path": "/superligaen/startseite/wettbewerb/DK1",
    "wettbewerb_id": "DK1",
},
"swedish_allsvenskan": {
    "name": "Allsvenskan",
    "short": "SWE",
    "path": "/allsvenskan/startseite/wettbewerb/SE1",
    "wettbewerb_id": "SE1",
},
"norwegian_eliteserien": {
    "name": "Eliteserien",
    "short": "NOR",
    "path": "/eliteserien/startseite/wettbewerb/NO1",
    "wettbewerb_id": "NO1",
},
```

### Ausführung

```bash
# 1. Registry erweitern (P0 Ligen)
python execution/scrape_club_registry.py  # nach Code-Änderung mit neuen LEAGUES

# 2. Staff scrapen für neue Clubs
python execution/scrape_squads.py --staff-only --new-clubs-only

# 3. Squads scrapen (Saisons 2015-2025 reicht, älter bringt wenig)
python execution/scrape_squads.py --seasons 2015-2025 --new-clubs-only

# 4. Neue Personen indexieren + Profile scrapen
python execution/scrape_person_profiles.py --new-only

# 5. Netzwerke regenerieren + Deploy
python execution/generate_all_bl_coaches.py --leagues BL1 BL2
cd output && npx vercel deploy --prod --yes
```

---

## P1 — Zweite Divisions (Tiefe der bestehenden Top-5-Ligen)

Kriterium: 2. Liga von bereits abgedeckten Top-Ligen. Viele BL-Coaches haben dort Station gemacht (Abstieg/Aufstieg, Karrierestart).

| Liga | TM Code | Short | Clubs ~est | Warum relevant |
|------|---------|-------|-----------|----------------|
| **Championship** (ENG) | GB2 | ENG2 | ~24 | Kompany (Burnley), div. englische Karrieren |
| **Serie B** (ITA) | IT2 | ITA2 | ~20 | Genua war zeitweise Serie B, weitere |
| **Ligue 2** (FRA) | FR2 | FRA2 | ~20 | Französische Pipeline nach BL |
| **Segunda División** (ESP) | ES2 | ESP2 | ~22 | Spanische Pipeline |
| **2. Liga Österreich** | A2 | AUT2 | ~16 | RB Liefering, Grazer AK, etc. |
| **Eerste Divisie** (NL) | NL2 | NED2 | ~20 | Jong Ajax, Jong PSV, Almere City |

**Summe P1:** ~122 neue Clubs
**Scraping-Zeit:** ~120 Min Staff + ~120 Min Squads

### Config für `scrape_club_registry.py`

```python
# P1: Second Divisions of Top-5 + Austria
"championship": {
    "name": "Championship",
    "short": "ENG2",
    "path": "/championship/startseite/wettbewerb/GB2",
    "wettbewerb_id": "GB2",
},
"serie_b": {
    "name": "Serie B",
    "short": "ITA2",
    "path": "/serieb/startseite/wettbewerb/IT2",
    "wettbewerb_id": "IT2",
},
"ligue_2": {
    "name": "Ligue 2",
    "short": "FRA2",
    "path": "/ligue-2/startseite/wettbewerb/FR2",
    "wettbewerb_id": "FR2",
},
"laliga2": {
    "name": "LaLiga2",
    "short": "ESP2",
    "path": "/laliga2/startseite/wettbewerb/ES2",
    "wettbewerb_id": "ES2",
},
"2liga_at": {
    "name": "2. Liga (AT)",
    "short": "AUT2",
    "path": "/2-liga/startseite/wettbewerb/A2",
    "wettbewerb_id": "A2",
},
# NOTE: Slug "2-liga" collides with 2. Bundesliga ("2-bundesliga") — TM resolves by wettbewerb_id
"eerste_divisie": {
    "name": "Keuken Kampioen Divisie",
    "short": "NED2",
    "path": "/keuken-kampioen-divisie/startseite/wettbewerb/NL2",
    "wettbewerb_id": "NL2",
},
```

---

## P2 — Weitere europäische 1. Ligen (Breite)

Kriterium: Einzelne Clubs mit 10+ Personen-Referenzen, oder Liga wird von 3+ Personen in DB referenziert. Weniger direkter BL-Coach-Bezug, aber relevant für Kontakt-Netzwerke (Spieler die dort waren → jetzt bei BL-Club).

| Liga | TM Code | Short | Clubs ~est | Bezug |
|------|---------|-------|-----------|-------|
| **Portuguese Liga** | PO1 | POR | ~18 | Spieler-Pipeline nach BL |
| **Scottish Premiership** | SC1 | SCO | ~12 | Celtic/Rangers-Verbindungen |
| **Greek Super League** | GR1 | GRE | ~14 | Endstation/Karrierestart diverse |
| **Croatian HNL** | KR1 | CRO | ~10 | Kovac-Netzwerk, ex-Yu Pipeline |
| **Czech Liga** | CZ1 | CZE | ~16 | Osteuropäische Pipeline |
| **Polish Ekstraklasa** | PL1 | POL | ~18 | Polnische Spieler in BL zahlreich |
| **Russian Premier** | RU1 | RUS | ~16 | Historisch relevant (vor 2022) |
| **Ukrainian Premier** | UA1 | UKR | ~16 | Shakhtar/Dynamo-Verbindungen |
| **Saudi Pro League** | SA1 | KSA | ~18 | Neue Destination seit 2023 |

**Summe P2:** ~138 neue Clubs
**Hinweis:** P2 nur wenn P0+P1 erfolgreich und Gap Analysis zeigt relevanten Impact.

### Config

```python
# P2: Broader European & Emerging
"portuguese_liga": {
    "name": "Liga Portugal",
    "short": "POR",
    "path": "/liga-nos/startseite/wettbewerb/PO1",
    "wettbewerb_id": "PO1",
},
"scottish_premiership": {
    "name": "Scottish Premiership",
    "short": "SCO",
    "path": "/scottish-premiership/startseite/wettbewerb/SC1",
    "wettbewerb_id": "SC1",
},
"greek_super_league": {
    "name": "Super League 1",
    "short": "GRE",
    "path": "/super-league-1/startseite/wettbewerb/GR1",
    "wettbewerb_id": "GR1",
},
"croatian_hnl": {
    "name": "SuperSport HNL",
    "short": "CRO",
    "path": "/1-hnl/startseite/wettbewerb/KR1",
    "wettbewerb_id": "KR1",
},
"czech_liga": {
    "name": "Chance Liga",
    "short": "CZE",
    "path": "/fortuna-liga/startseite/wettbewerb/TS1",
    "wettbewerb_id": "TS1",
},
"polish_ekstraklasa": {
    "name": "PKO BP Ekstraklasa",
    "short": "POL",
    "path": "/pko-bp-ekstraklasa/startseite/wettbewerb/PL1",
    "wettbewerb_id": "PL1",
},
"russian_premier": {
    "name": "Premier Liga",
    "short": "RUS",
    "path": "/premier-liga/startseite/wettbewerb/RU1",
    "wettbewerb_id": "RU1",
},
"saudi_pro_league": {
    "name": "Saudi Pro League",
    "short": "KSA",
    "path": "/saudi-pro-league/startseite/wettbewerb/SA1",
    "wettbewerb_id": "SA1",
},
# NOTE: Saudi slug varies (saudi-pro-league vs saudi-professional-league) — TM resolves via wettbewerb_id
```

---

## Gesamt-Projektion

| Tier | Neue Clubs | Registry danach | Scraping-Zeit |
|------|-----------|----------------|---------------|
| P0 | ~96 | ~403 | ~100 Min |
| P0+P1 | ~218 | ~525 | ~340 Min (~6 Std) |
| P0+P1+P2 | ~356 | ~663 | ~600 Min (~10 Std) |

### Impact auf Netzwerk-Dichte

| Szenario | Ø Kontakte/Coach | Foreign Coverage |
|----------|-----------------|-----------------|
| Aktuell | 159 | ~60% |
| Nach P0 | ~200-220 | ~80% |
| Nach P0+P1 | ~230-260 | ~90% |
| Nach P0+P1+P2 | ~250-280 | ~95% |

---

## Sonder-Kategorie: Youth/Reserve Teams

Nicht über Liga-Expansion sondern über `scrape_foreign_staff.py`:

1. **RB Leipzig Youth** (U19: 26621, U17: 32942, U16: ?, Jgd: 39962, II: 24293) — Blessin-Karriere
2. **Bayern München U19/U17** — NLZ-Kontakte
3. **Dortmund U19/U17** — NLZ-Kontakte
4. **Alle BL-Club Youth IDs** aus TM extrahieren

Approach: `scrape_foreign_staff.py --clubs <list>` mit manuell gesammelten Youth-Team-IDs.

---

## Validierung nach jeder Tier

```bash
# Nach P0: Gap Analysis erneut laufen
python execution/analyze_coverage_gaps.py --output data/coverage_gaps_post_p0.json

# Vergleich
# Erwartung: missing_clubs sinkt von 4.296 auf ~4.200 (internationale),
#            aber BL-Coach-missing sinkt von 111 auf ~60-70
```

---

## Anpassung basierend auf Gap-Analysis-Output

⚠️ **Wichtig:** Die obige Tier-Zuordnung basiert auf bekannten BL-Coach-Karriereverläufen. Sobald `coverage_gaps.json` vorliegt (vom laufenden Claude Code Run), sollte die Reihenfolge angepasst werden falls:

- Eine Liga unerwartet viele Referenzen hat → hochstufen
- Eine P0-Liga kaum referenziert wird → runterstufen
- Einzelne Clubs mit sehr vielen Referenzen nicht in einer geplanten Liga sind → P2

Die Gap Analysis ist der Schiedsrichter, nicht diese Liste.
