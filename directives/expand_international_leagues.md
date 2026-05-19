# Directive: Expand Club Registry to International Leagues

## Goal
Extend the existing 5-phase pipeline to cover major European leagues beyond Germany. This gives projectFIVE full visibility into coaches' international stations — any club a German coach worked at will have staff/squad data.

## Target Leagues

| Country | League | TM Wettbewerb-ID | TM Path | Short |
|---------|--------|-------------------|---------|-------|
| DE | 2. Bundesliga | L2 | /2-bundesliga/startseite/wettbewerb/L2 | BL2 |
| ES | La Liga | ES1 | /laliga/startseite/wettbewerb/ES1 | LIGA |
| EN | Premier League | GB1 | /premier-league/startseite/wettbewerb/GB1 | PL |
| FR | Ligue 1 | FR1 | /ligue-1/startseite/wettbewerb/FR1 | L1 |
| IT | Serie A | IT1 | /serie-a/startseite/wettbewerb/IT1 | SA |
| AT | Bundesliga (AT) | A1 | /bundesliga/startseite/wettbewerb/A1 | ABL |

**Note:** 2. Bundesliga (L2) is already in `scrape_club_registry.py` LEAGUES dict and in club_registry.json. No need to re-scrape — just verify it's included in downstream processing.

## Season Range
2010/11 through 2025/26 (matching existing German leagues)

## Estimated Scope

| Phase | Per League | 6 New Leagues | Time Est. |
|-------|-----------|---------------|-----------|
| Phase 1: Club Registry | ~16 pages (seasons) | ~80 pages | ~5 min |
| Phase 2: Squads | ~25 clubs × 16 seasons = ~400 | ~2,400 files | ~3-4 hours |
| Phase 2: Staff | ~25 per league | ~130 staff pages | ~10 min |
| Phase 3: Profiles | ~2,000-5,000 new persons/league | ~15,000-30,000 | ~15-30 hours |

**Total new persons estimated:** 15,000-30,000 (many will overlap with existing DB, e.g. players who moved between leagues)

## Implementation

### Step 1: Extend `scrape_club_registry.py`

Add new leagues to the LEAGUES dict. The scraper already handles arbitrary TM wettbewerb IDs:

```python
# Add to LEAGUES dict in scrape_club_registry.py:
"la_liga": {
    "name": "La Liga",
    "short": "LIGA",
    "path": "/laliga/startseite/wettbewerb/ES1",
    "wettbewerb_id": "ES1",
},
"premier_league": {
    "name": "Premier League",
    "short": "PL",
    "path": "/premier-league/startseite/wettbewerb/GB1",
    "wettbewerb_id": "GB1",
},
"ligue_1": {
    "name": "Ligue 1",
    "short": "L1FR",
    "path": "/ligue-1/startseite/wettbewerb/FR1",
    "wettbewerb_id": "FR1",
},
"serie_a": {
    "name": "Serie A",
    "short": "SA",
    "path": "/serie-a/startseite/wettbewerb/IT1",
    "wettbewerb_id": "IT1",
},
"bundesliga_at": {
    "name": "Bundesliga (AT)",
    "short": "ABL",
    "path": "/bundesliga/startseite/wettbewerb/A1",
    "wettbewerb_id": "A1",
},
```

### Step 2: Run Phase 1 (Club Registry)

```bash
python execution/scrape_club_registry.py
```

This will:
- Keep all existing clubs (incremental — only adds new ones)
- Add ~100-130 new clubs from 5 new leagues
- Cache all HTML pages (7-day TTL)

### Step 3: Run Phase 2 (Squads + Staff)

```bash
# Squads — use batching for large sets
python execution/scrape_squads.py --start=120 --limit=50

# Staff only (current Mitarbeiter)
python execution/scrape_squads.py --staff-only --start=120
```

**Important:** `scrape_squads.py` reads from `club_registry.json`. New clubs are at the end. Use `--start` offset to skip already-processed German clubs.

### Step 4: Rebuild Persons Index

```bash
python execution/scrape_squads.py --index-only
```

This merges all squad + staff data into `persons_index.json`.

### Step 5: Run Phase 3 (Person Profiles)

```bash
# Auto-skips already-scraped profiles
python execution/scrape_person_profiles.py --players-only --limit=500
python execution/scrape_person_profiles.py --coaches-only --limit=500
```

### Step 6: Rebuild Master

```bash
python execution/scrape_person_profiles.py --master-only
```

## Edge Cases & Notes

- **Duplicate clubs:** Some clubs appear in multiple leagues (e.g., relegated teams). The registry uses tm_id as key, so duplicates merge automatically.
- **Duplicate persons:** Same — tm_id deduplication. A player who moved from BL1 to PL already has a profile; they'll just get more squad_entries.
- **TM URL patterns vary by country:** English pages use `/premier-league/`, Spanish `/laliga/`. The base domain stays `transfermarkt.de` (German interface) for consistent HTML structure.
- **Squad page format is identical** across leagues on TM — same CSS classes, same table structure. No parser changes needed.
- **Staff pages for foreign clubs** may have fewer entries (not all clubs list full backroom staff). See `directives/scrape_foreign_club_staff.md` for known limitations.
- **Austrian league** has fewer clubs (~12 per season) — fast to scrape.
- **La Liga / PL / Serie A** have 18-20 clubs per season — moderate size.

## Execution Order

1. Extend LEAGUES dict ← quick code change
2. Phase 1: Club Registry (~5 min)
3. Phase 2: Squads + Staff (~3-4 hours, batchable)
4. Phase 3: Person Profiles (~15-30 hours, batchable, auto-resume)
5. Master rebuild (~2 min)
6. Network rebuild + dashboard deploy

## Success Criteria

- `club_registry.json` contains 220-250 clubs (up from 119)
- `persons_index.json` contains 30,000-45,000 persons (up from ~15,000)
- Coach networks show international contacts with club/station data
- No increase in TM block rate (maintain 3s delay)

## Execution Results (2026-03-24)

### Phase 1: Club Registry ✅
- 307 clubs total (+188 neue): PL, La Liga, Serie A, Ligue 1, Eredivisie
- Note: Eredivisie statt Österreich-BL gewählt (höherer Wert für Coach-Netzwerke)

### Phase 2: Squads + Staff ✅
- 2,776 squad files (+1,662), 308 staff files (+189)
- 34,513 unique persons indexed (27,832 Spieler, 6,694 Trainer/Staff, 1,002 Scouts, 594 SDs)
- 404 career transitions detected (+343)

### Phase 3: Profile Scraping ✅ (2026-03-26)
- **34,513 Profile** gescraped (27,734 Spieler + 6,779 Coaches/Staff)
- **Master-Datei:** 51.9 MB (`data/persons_master.json`)
- Auto-resume mit `--limit` Batches funktionierte zuverlässig

### Berater-Feld (Bonus) ✅
- 6,835/11,925 Spieler mit Berater (57%), 1,273 unique Firmen
- Wurde als Teil des Profile-Scrapings mitextrahiert

## Learnings
- Eredivisie war bessere Wahl als Österreich-BL (mehr relevante internationale Trainer-Stationen)
- Squad-Page-Format ist identisch über alle Ligen — kein Parser-Änderung nötig
- Staff-Pages funktionieren auch für internationale Clubs ohne Anpassung
- Berater-Feld kann effizient als Teil des normalen Profile-Scrapings extrahiert werden (kein separater Sprint nötig)
- 34k Personen im Index → SQLite-Rebuild wird ~15-20 MB statt 7.3 MB
