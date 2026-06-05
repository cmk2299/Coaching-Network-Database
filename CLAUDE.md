# CLAUDE.md - Football Coaches Database System

## Agent Instructions

This file contains instructions for building an automated football coaches database that scrapes and compiles comprehensive profiles from Transfermarkt for projectFIVE.

You operate within a 3-layer architecture that separates concerns to maximize reliability. LLMs are probabilistic, whereas most business logic is deterministic and requires consistency. This system fixes that mismatch.

---

## The 3-Layer Architecture

### **Layer 1: Directive (What to do)**

- Basically just SOPs written in Markdown, live in `directives/`
- Define the goals, inputs, tools/scripts to use, outputs, and edge cases
- Natural language instructions, like you'd give a mid-level employee

### **Layer 2: Orchestration (Decision making)**

- This is you. Your job: intelligent routing.
- Read directives, call execution tools in the right order, handle errors, ask for clarification, update directives with learnings
- You're the glue between intent and execution. E.g., you don't try scraping websites yourself—you read `directives/build_full_profile.md` and come up with inputs/outputs and then run `execution/scrape_transfermarkt.py`

### **Layer 3: Execution (Doing the work)**

- Deterministic Python scripts in `execution/`
- Environment variables, api tokens, etc are stored in `.env`
- Handle web scraping, data processing, database operations, dashboard generation
- Reliable, testable, fast. Use scripts instead of manual work. Commented well.

**Why this works:** If you do everything yourself, errors compound. 90% accuracy per step = 59% success over 5 steps. The solution is push complexity into deterministic code. That way you just focus on decision-making.

---

## Operating Principles

### **1. Check for tools first**

Before writing a script, check `execution/` per your directive. Only create new scripts if none exist.

### **2. Self-anneal when things break**

- Read error message and stack trace
- Fix the script and test it again (unless it uses paid tokens/credits/etc—in which case you check w user first)
- Update the directive with what you learned (rate limits, timing, edge cases, HTML structure changes)
- Example: Transfermarkt blocks your IP → you research → find they require headers/delays → rewrite script to add user agents and rate limiting → test → update directive

### **3. Update directives as you learn**

Directives are living documents. When you discover:
- Transfermarkt HTML structure changes
- Better CSS selectors or XPath queries
- Common parsing errors or missing data patterns
- Optimal scraping delays to avoid blocks

...update the directive. But don't create or overwrite directives without asking unless explicitly told to. Directives are your instruction set and must be preserved (and improved upon over time, not extemporaneously used and then discarded).

### **4. Respect website policies**

- Always implement reasonable delays between requests (2-5 seconds minimum)
- Use proper User-Agent headers
- Cache results to avoid repeat scraping
- Never overwhelm the server with parallel requests

### **5. Systematik vor Ad-Hoc — IMMER** ⭐

**Operating Principle (User-Mandat 2026-05-19):** Bei JEDEM Fix die Frage stellen: "Ist das systemisch oder nur Ad-Hoc?"

Ad-Hoc-Fixes erzeugen Wieder-Auftritts-Bugs: in 2 Wochen meldet sich der gleiche Fehler aus einem anderen Coach/Verein/Pfad. Systematik-Fixes greifen automatisch für alle gleichartigen Fälle.

**Vorgehen für jeden Fix:**

1. **Root-Cause identifizieren** — wo wird die fehlerhafte Logik gebildet?
2. **Pfade kartieren** — wo wird die Logik noch verwendet? Grep auf Funktions-Aufrufe, Pattern-Matches, ähnliche Code-Stellen
3. **Bewerten — Systematik-Score**:
   - ✅ **Voll systemisch**: Fix in zentraler Funktion/Helper, alle Pfade profitieren automatisch
   - ⚠️ **Teilweise systemisch**: Fix deckt Hauptpfad ab, aber andere Pfade können leaken
   - ❌ **Ad-Hoc**: Fix nur für die konkrete Instanz (z.B. Hard-Code-Override für 1 Person)
4. **Bei ⚠️/❌**: Vor Deploy diskutieren — kann es zur ✅ erhoben werden? Aufwand ~30min ist meist gerechtfertigt
5. **Klassiker systemischer Patterns**:
   - **Helper-Funktion in `lib/`** statt Logik-Duplikat (z.B. `compute_role_display()`, `compute_shared_playing_stations()`)
   - **Override-Loader auto-fills** statt manuelle Whitelist-Pflege
   - **Zentrale Lookups mit Safety-Guards** (z.B. `lookup_active_staff` mit tm_id-Check)
   - **Validator-Helper** statt inline-Checks (z.B. `validate_staff_tm_id`)
6. **Bei Build-Logic-Fixes**: alle Networks rebuilden, nicht nur Stichprobe — sonst inkonsistente Output-States

**Beispiele aus der Historie** (zur Orientierung):
- ✅ `lib/normalization.py` Extraktion (Sprint April 2026) — `normalize_club()`, `classify_role()`, `filter_nationality()` zentral. Vor Extraktion: 33 Club-Normalize-Stellen verstreut, inkonsistent.
- ✅ `lib/dashboard_index.py` (Sprint Mai 2026) — Slug-Resolution zentral. Vor Extraktion: SD-Suffix-Handling 4× dupliziert.
- ⚠️ Bug Mark-Zimmermann-Dopplung 2026-04-07 (Hecking) — wurde damals nur für Hecking gefixt, kam jetzt bei Blessin wieder. Lehre: tm_id-strict in zentralem Lookup hätte beides verhindert.
- ❌ Anti-Pattern: Hard-Code-Override pro Person — funktioniert für die Person, nicht für nächste Instanz des Patterns.

**Wenn unsicher** → Lieber 30min systematisieren als 2 Wochen später nochmal debuggen.

---

## Self-annealing Loop

Errors are learning opportunities. When something breaks:

1. **Fix it** - Debug the scraping logic, update selectors, handle edge cases
2. **Update the tool** - Modify the Python script with improved error handling
3. **Test tool** - Run against multiple coaches to ensure it works reliably
4. **Update directive** - Document the new flow, edge cases, and lessons learned
5. **System is now stronger** - Next time this scenario occurs, it's handled automatically

---

## File Organization

### **Directory structure:**

```
/tmp/                           # All intermediate files (never commit)
  ├── cache/                    # Cached Transfermarkt responses
  └── raw_html/                 # Raw HTML for debugging

execution/                              # Python scripts (the deterministic tools)
  ├── build_coach_network.py            # Build contact network for a single coach
  ├── generate_dashboard.py             # Generate HTML dashboard from network JSON
  ├── generate_all_bl_coaches.py        # Batch: all 36 BL coaches + index page
  ├── scrape_club_registry.py           # Phase 1: Discover all clubs in BL1/2/3/NLZ
  ├── scrape_squads.py                  # Phase 2: Squad + Staff crawling (batch mode)
  ├── scrape_person_profiles.py         # Phase 3: Individual TM profile scraper (coaches + players)
  ├── scrape_transfermarkt.py           # Single coach profile scraper (legacy MVP)
  ├── scrape_teammates.py              # Get player career teammates
  ├── scrape_players_used.py           # Get players coached statistics
  ├── scrape_coaching_licenses.py        # Build coaching_licenses.json (DFB FL cohorts)
  ├── enrich_transfermarkt_profiles.py  # Batch-scrape TM fields for network contacts
  ├── enrich_network.py                # Cross-reference career/players/relationships
  ├── generate_background_summaries.py  # Template-based German summaries
  ├── build_sqlite.py                  # Build SQLite DB from all JSON data
  ├── regenerate_dashboards.py          # Re-inject template into all dashboards (--lazy for external drilldown)
  ├── fix_name_mismatches.py            # Repair TM trainer/player ID collision mismatches
  └── lib/
      └── normalization.py              # Shared: normalize_club, classify_role, season parsing, etc.

directives/                             # SOPs in Markdown (the instruction set)
  ├── ROADMAP.md                        # Sprint tracking + project roadmap
  ├── systematic_expansion.md           # Sprint 10: Demand-driven expansion master plan
  ├── league_expansion_tiers.md         # P0/P1/P2 liga configs with verified TM slugs
  ├── playing_career_integration.md     # Sprint 11: Mitspieler/former teammates concept
  ├── build_master_database.md          # Master pipeline: 5-phase database build
  ├── build_full_profile.md             # Single coach profile orchestration
  ├── build_sqlite_database.md          # SQLite schema, build script, delivery
  ├── scrape_foreign_club_staff.md      # Scrape Mitarbeiter for non-German clubs
  ├── code_quality_fixes.md             # Normalize lib extraction, bare except, pytest
  ├── expand_international_leagues.md   # Top-5 leagues expansion (DONE)
  ├── sprint1_drilldown.md              # Drill-down sub-networks (DONE)
  ├── sprint2_player_profiles.md        # Player profile scraping (DONE)
  ├── sprint3_expand_leagues.md         # BL3 + NLZ + Historical (absorbed into Sprint 10)
  ├── audit_fixes.md                    # Original audit findings
  └── audit_fixes_implementation.md     # Implementation directive (DONE)

data/                           # Persistent data
  ├── club_registry.json              # Phase 1: 307 clubs (BL1/2/3/NLZ + PL/Liga/SA/L1/Eredivisie)
  ├── squads/                          # Phase 2: 2,776 squad files (club×season)
  ├── staff/                           # Phase 2: 308 staff files (current Mitarbeiter)
  ├── persons_index.json               # Phase 2: 34,513 unique persons index
  ├── person_profiles/                 # Phase 3: Individual TM profiles (JSON per person)
  │   └── {tm_id}.json                #   34,513 profiles (27,734 players + 6,779 coaches/staff)
  ├── persons_master.json              # Phase 3: Merged master (51.9 MB, 34,513 entries)
  ├── coaching_licenses.json            # DFB Fußball-Lehrer cohort data (LG 61-69)
  ├── blessin_full_network.json       # MVP: Main network (91 contacts, enriched)
  ├── blessin_drilldown_data.json     # MVP: Sub-networks for drill-down (119 entries)
  ├── master_coach_profiles.json      # Legacy: 1,057 coach profiles
  ├── blessin_players_used.json       # MVP: Players coached by Blessin
  ├── profile_enrichment.json         # MVP: TM-scraped fields per contact
  ├── background_summaries.json       # MVP: German summaries per contact
  └── enrichment_summary.json         # MVP: Stats on enrichment coverage

data/networks/                          # Generated network JSONs per coach
  └── {tm_id}.json                      #   36 BL1+BL2 coach networks

output/                                 # Deployment artifacts (Vercel)
  ├── index.html                        # Coach selection page (table layout)
  ├── dashboards/                       # One HTML dashboard per coach + external drilldown JSONs
  │   └── {slug}_network.html           #   36 self-contained dashboards
  └── vercel.json                       # Routing config

run_mvp.sh                              # One-click: staff update → build → deploy

tmp/cache/profiles/             # Cached TM HTML responses (30-day TTL)
  └── {type}_{tm_id}.html       #   ~18,000+ cached pages (growing)

.env                            # Environment variables and API keys
```

---

## Output Structure (Interactive HTML Dashboard)

Single self-contained HTML file with embedded JSON data. Template uses `__NETWORK_PLACEHOLDER__` and `__DRILLDOWN_PLACEHOLDER__` markers.

### Per-Contact Data Fields

| Field | Source | Coverage (Blessin MVP) |
|-------|--------|----------------------|
| name | Profile / Network | 91/91 |
| nationality | TM scraping | 21/91 |
| dob / age | TM scraping | 16/91 |
| current_role | Network | 91/91 |
| current_club | TM scraping | 26/91 |
| license | TM scraping | 14/91 |
| tm_url | Network | 69/91 |
| pro_status | TM role detection | 91/91 (47 trainers, 8 SDs) |
| career_history | master_coach_profiles match | 8/91 |
| coaches_worked_with[] | Cross-reference shared stations | 59/91 |
| sds_worked_with[] | Cross-reference shared stations | 37/91 |
| top_players_coached[] | Players used (20+ games, 45+ avg min) | 30/91 |
| background_summary | Template-based German text | 91/91 |

### Dashboard Features
- Canvas-based force-directed network graph (clean data-terminal aesthetic, no decorative effects)
- Fonts: IBM Plex Sans (UI) + JetBrains Mono (stats/labels) — NO emojis anywhere
- Station cluster regions (dashed circle boundaries with labels)
- Dot-grid background, straight-line edges, no particles/glow/pulse animations
- Recursive drill-down (click contact → becomes center)
- Breadcrumb navigation
- Positive-inclusion filters (station chips, category legend, pro filter)
- Detail panel with meta info, summary, career, connections, top players
- Search by name
- TM profile links

---

## Pipeline Progress (Updated 2026-03-27)

### Phase 1: Club Registry ✅ (expanded 2026-03-27)
- **854 clubs** across BL1, BL2, BL3, NLZ + 24 international leagues (29 total)
- P0: BEL, SUI, TUR, DEN, SWE, NOR ✅
- P1: Championship, Serie B, Ligue 2, LaLiga2, 2.Liga AT, Eerste Divisie ✅
- P2: Liga Portugal, Scottish Premiership, Greek SL, Croatian HNL, Czech Liga, Ekstraklasa, Saudi PL ✅
- All configs in `scrape_club_registry.py` LEAGUES dict (29 leagues total)

### Phase 2: Squad & Staff Crawling ✅ (expanded 2026-03-27)
- **3,324 squad files**, **939 staff files** (854 registry + 85 foreign = 0 missing)
- **34,513 unique persons** indexed
  - 27,832 players, 6,694 coaches/staff, 1,002 scouts, 594 sporting directors
- **404 career transitions** detected — player→coach/SD/scout

### Phase 3: Individual TM Profiles ✅ (2026-03-26)
- **34,513 profiles scraped** (27,734 players + 6,779 coaches/staff)
- **Master file:** `data/persons_master.json` (51.9 MB)
- Coverage: name 100%, nationality ~100%, DOB ~90%, position 100% (players), foot 99% (players), image ~85%

### Berater (Agent) Field ✅ (2026-03-24)
- **6,835/11,925 players with agent data** (57% coverage)
- **1,273 unique agent firms** identified

### Phase 4: Career Transitions & Data Merge ⏳
- 404 transitions already detected from squad/staff overlap
- Merge squad-based career data into player profiles

### Phase 5: Dashboard Integration ✅ (2026-03-27, expanded)
- **126 dashboards** (56 active BL + 19 Kat-A ex-coaches + 48 Kat-D historical + 3 legacy)
- **Index page:** BL1/BL2/BL3 + historische Sektionen (Ehemalige, Co-Trainer, Historisch)
- Network graph: force-directed canvas, drill-down, station cluster labels, breadcrumb nav
- Mitspieler category: orange `#e76f51`, from playing career squad overlap
- Club name normalization via `CLUB_NAME_NORMALIZE` dict + `normalize_club()`
- **Multi-Station Enrichment:** `coaches_worked_with[]`, `sds_worked_with[]`, `shared_station_count` per contact
- **Performance:** Drilldown max_contacts=15, no background_summary in sub-networks → max 4.7 MB per dashboard
- **Update workflow:** `bash run_mvp.sh` (scrape staff → build networks → generate dashboards → deploy)

### Historical Coaches Expansion ✅ (2026-03-27)
- **Script:** `python execution/identify_historical_coaches.py` → `data/historical_coaches_candidates.json`
- **310 historical coaches** identified: A (19 ex-BL since 2020), B (0 vereinslos), C (243 co-trainers), D (48 historical)
- **126 dashboards generated** (56 active + 67 historical + 3 legacy)
- **Index page:** `--include-historical` flag in `generate_all_bl_coaches.py`
- Category A: Frank Kramer, Markus Weinzierl, Hannes Wolf, Pellegrino Matarazzo, etc.
- Category D: Karel Geraerts, José Luis Rueda, Cameron Campbell (abroad), etc.

### SQLite Database ✅ (2026-03-26, rebuilt with international data)
- **Script:** `python execution/build_sqlite.py` (21.5s build, **18.7 MB** output)
- **Tables:** clubs (4,604), persons (34,513), career_history (31,500), squad_entries (95,365), staff_entries (7,167), career_transitions (382), club_seasons (2,960)
- **Total:** ~176k rows across 7 tables
- **Referential integrity:** 0 FK violations (`PRAGMA foreign_key_check` clean)
- **Views:** `v_bl_coaches`, `v_transitions`, `v_coach_careers`
- **Delivery:** `data/coaches.db` + `output/coaches.db`

### Audit Fixes ✅ (2026-03-24)
- Club name normalization: 22 mappings + registry lookup, 0 duplicates
- Fonts unified: IBM Plex Sans (body) + JetBrains Mono (stats)
- Red accent unified: #c8102e everywhere
- Nationality logic fixed: dissolved states filtered, Kovac→Kroatien
- Custom 404 page live, "Zurück zum Index" back-link

### Daily Auto-Refresh ✅ (2026-03-24)
- Cron: 7:22 Uhr daily → staff scrape → network rebuild → tests → deploy
- Push notification via ntfy.sh on success/failure

### Coverage Gap Analysis ✅ (2026-03-26)
- **4,296 clubs missing** from registry (93.4% of all career-referenced clubs)
- **111/191 BL-Coach career clubs** uncovered (58.1%)
- Script: `execution/analyze_coverage_gaps.py`, Output: `data/coverage_gaps.json`

### Foreign Staff Scraping ✅ (2026-03-26)
- **111 missing BL-Coach career clubs** scraped via `scrape_foreign_staff.py --all-bl-coaches`

### Spielerkarriere / Mitspieler ✅ (2026-03-26)
- Playing career integration complete: coaches' ex-teammates from squad overlap
- Results: Kompany 160→490, Klose 160→745, Kovac 334→829
- Pre-2010 retirement bug fixed: `min_end = max(playing_end, 2012)` ensures coverage
- Edge case solved: TM uses different IDs for player/coach profiles of same person

### Sprint 10: Systematic League Expansion ✅ (2026-03-26)
- P0 leagues (BEL, SUI, TUR, DEN, SWE, NOR) scraped + integrated
- P1+P2 league configs added to registry script (ready to scrape)
- BL3 dashboards generated (20 coaches)
- 424 historical BL coaches identified as expansion candidates

### SQLite Rebuild ✅ (2026-03-27)
- **21.4 MB**, 120s build time
- **Tables:** clubs (4,792), persons (41,586), career_history (31,500), squad_entries (120,085), staff_entries (13,440), career_transitions (784), club_seasons (8,136)
- 7,073 stub persons added from squad references
- 784 career transitions (up from 382) — includes international league data
- 5,709 staff→persons FK violations (staff without profile — known limit)

### Coaching License Connections ✅ (2026-03-27)
- **Script:** `execution/scrape_coaching_licenses.py` — hardcoded cohort data from DFB.de, Kicker, ran.de etc.
- **Data:** `data/coaching_licenses.json` — 9 cohorts (LG 61–69, 2014–2024), 203 graduates, 93 matched to tm_ids (45.8%)
- **Integration:** `build_coach_network.py` Step 4 — loads cohort data, adds `category: "lehrgang"` contacts
- **Dashboard:** Purple `#9b59b6`, station `DFB-Lehrgang {year}`, template already configured
- **Tested:** Blessin (LG 62) → 11 lehrgang colleagues (Nagelsmann, Matarazzo, Thioune, Kocak, etc.)
- **All cohorts complete:** LG 63 (25 graduates, source: reviersport.de), LG 69 (16 graduates, source: dfb.de)
- **Unmatched:** 110/203 graduates not in persons_master (coaches at clubs outside scraped leagues)

### Lazy Loading ✅ (2026-04-03)
- **Script:** `python3 execution/regenerate_dashboards.py --lazy 500000`
- **17 dashboards** externalized: drilldown JSON saved as `{slug}_drilldown.json` next to HTML
- **26.6 MB** moved from inline HTML to on-demand JSON fetches
- **Max HTML size:** 3.4 MB → 1.2 MB (biggest: `albert_riera_network.html`)
- **Template:** `getDrilldown()` uses `fetch(DRILLDOWN_URL)` with in-memory cache
- **Vercel:** `vercel.json` updated with JSON Content-Type + Cache-Control headers
- **Also updated:** `generate_dashboard.py` now defaults to `lazy_threshold=500_000`

### Graph Visual Overhaul ✅ (2026-04-03)
- Removed center pulse animation → static glow
- Removed score-ring arcs (circular progress bars around nodes)
- Dot-grid: opacity 0.015→0.008, spacing 40→48
- Wedge fills: alpha 0.06→0.03, hover 0.12→0.08
- Radial edges: threshold 0.5→0.6, alpha reduced, lineWidth 0.3→0.25
- NODE_MIN_R: 14→12 (compact, clean nodes)
- **Script:** `python3 execution/regenerate_dashboards.py` — re-injects template into all dashboards

### Code Quality ✅ (2026-04-03)
- **Extracted `execution/lib/normalization.py`**: 33 CLUB_NAME_NORMALIZE entries + 9 shared functions
- **Functions extracted:** `normalize_club`, `classify_role`, `classify_staff_section`, `parse_season_from_date`, `get_season_range`, `format_season`, `validate_staff_tm_id`, `league_rank`, `filter_nationality`
- **Backward compatible:** `build_coach_network.py` re-exports all names, `build_sqlite.py` imports unchanged
- **Tests:** `tests/test_normalization.py` — 47 tests covering all shared functions
- **Bare `except:` fixed:** 18 occurrences across 13 scripts → `except Exception:`
- **Run tests:** `python3 -m pytest tests/ -v`

### Stakeholder-Feedback Systematik ✅ (2026-05-19)
4 Bugs aus Live-Stakeholder-Demo. Pro Bug: erst Ad-Hoc-Fix → User-Frage "systemisch oder Ad-Hoc?" → Erhebung auf voll systemisch via zentrale lib/-Helper. Operating Principle "Systematik vor Ad-Hoc" in CLAUDE.md verankert (siehe Operating Principles #5).

- **Bug 1 (Trainerstab → Bundestrainer):** Vorher 4 Pfade die Role-Display setzten — Nagelsmann zeigte "Trainerstab, Deutschland" statt "Bundestrainer". Systematik-Fix: `compute_role_display(category, section, club, career_history, position, person_type)` als single source of truth in `lib/normalization.py`. Priorität: Active-Player-Position > National-Team-Bundestrainer > Cheftrainer > Specific-Section > Category-Default > Career-History-Fallback. Tests: 9 in TestComputeRoleDisplay.
- **Bug 2 (Stationen für GS-Mitspieler):** Vorher: stations leer bei 148/148 Blessin-Mitspielern. Systematik-Fix: `compute_shared_playing_stations(coach_career, player_career)` in `lib/normalization.py`. Beide Pfade (new contact + existing enrichment) nutzen sie. Tests: 6 in TestComputeSharedPlayingStations.
- **Bug 3a (Marcel Rapp TM-URL):** Vorher: manuelle Whitelist pro Person, neue Trainer mussten einzeln gepflegt werden. Systematik-Fix: `build_trainer_url(name, trainer_tm_id)` + `resolve_trainer_tm_id(spieler_id, name, persons_master)` — wenn Override `trainer_tm_id=null` hat, sucht Helper automatisch im persons_master nach distinct trainer-Profile mit gleichem Namen. Tests: 5+5 in TestBuildTrainerUrl/TestResolveTrainerTmId.
- **Bug 3b (Mark Zimmermann Dopplung):** Vorher: `lookup_active_staff` nur Name-Match → GS-Mitspieler TM 492 (Spieler) erbte HC-Rolle von Mark Zimmermann TM 6509 (Kickers Offenbach). Systematik-Fix: Optionaler `contact_tm_id`-Parameter; bei tm_id-Mismatch (beide bekannt) → Reject. Zentraler Guard, profitiert alle Aufrufer.
- **NATIONAL_TEAMS Konstante** in lib/normalization.py — DACH + Big-5 + häufige Euro-Nationen. Erkennt Nationalmannschaften für "Bundestrainer"-Label.
- **Tests Stand**: 76 passed, 2 pre-existing failures (unrelated). Run: `python3 -m pytest tests/test_normalization.py -v`
- **Bewertung**: alle 4 Bugs jetzt voll systemisch (✅), nicht mehr Ad-Hoc.

### QA Fixes ✅ (2026-04-04)
- **Nationality youth-team leak fixed:** New `filter_nationality()` in `lib/normalization.py` filters "Deutschland U20/U19/..." entries. Applied at all 5 nationality assignment points in `build_coach_network.py` + `generate_all_bl_coaches.py`. Replaces 3 inline filter blocks.
- **Index page club normalization:** `generate_all_bl_coaches.py` now runs `normalize_club()` on club names → "1.FC Heidenheim 1846" → "1.FC Heidenheim", "Borussia Mönchengladbach" → "Borussia M'gladbach"
- **Drilldown station counter bug:** Template `updateStats()` now uses `currentStations.length` instead of counting from (potentially trimmed) contacts. Station chips were showing correct count but badge was wrong.
- **Mitspieler summary text:** Added `former_teammate` and `analyst` templates to `generate_background_summaries()`. Previously fell through to generic "Mitarbeiter bei ..." text.
- **Drilldown regression fix:** `regenerate_dashboards.py` now loads external drilldown JSONs by convention (`{stem}_drilldown.json`) when inline DRILLDOWN is empty. Previously, regeneration after lazy-loading destroyed drilldown references.
- **Rebuild required:** Networks need rebuild (`build_coach_network.py`) for nationality + summary fixes. Index + dashboards need regeneration.

### Playing Career Batch Scrape ✅ (2026-04-07)
- **Script:** `execution/scrape_coach_playing_careers.py` — scrapes `/leistungsdatendetails/spieler/{id}` for coaches with separate TM player profiles
- **Results:** 210 coaches with playing career data (2,268 total entries, avg 10.8 per coach), 63 empty (amateur/redirect), 123 remaining (no spieler link found)
- **TM dual-ID solved:** Trainer HTML contains `href="/slug/profil/spieler/{spieler_id}"` link → extract spieler_id + slug → fetch leistungsdatendetails page
- **Edge case:** Amateur coaches (e.g., Hjulmand, Heiko Vogel) have spieler IDs that redirect to TM homepage → marked as empty career
- **Club name parsing:** Priority order: `link.title` > `img.alt` > `img.title` > `link.text` (img.title is often `\xa0`)
- **Needs rebuild:** `build_coach_network.py` for affected coaches to pick up new Mitspieler contacts

### Category C Assessment ✅ (2026-04-07)
- **245 BL Trainerstab members** without networks (co-trainers, fitness coaches, analytics, etc.)
- **Estimated runtime:** ~3.5 hours (network build ~45s each + dashboard generation)
- **Decision: SKIP** — diminishing returns: co-trainers share 60-80% contacts with head coach, many are specialists (fitness/GK/analytics) with low strategic networking value
- **On-demand option:** Can generate specific co-trainer networks if requested

### Temporal Overlap + Category Fixes ✅ (2026-04-07)
- **Bug 1 (Temporal Overlap):** Section 1b loaded staff files (which contain only *current* personnel) for ALL of a coach's past clubs, creating false links between people who never overlapped. Example: Hecking (Gladbach 2016-19) was linked to Schröder (joined Gladbach 2025). Fix: Only use staff files for clubs where `coach_latest_season >= CURRENT_SEASON - 1` (1-season grace period).
- **Bug 2 (Sonstiges Upgrade):** Contacts from "Sonstiges" section (stadium speakers, mascots, etc.) were upgraded from `other_staff` to `head_coach` by Section 2's career-match logic. Example: Michael Wurst (Stadionsprecher Bochum, amateur Trainer-career) was classified as `head_coach`. Fix: Track `_staff_section` from staff files; skip category upgrade for "Sonstiges" contacts.
- **Bug 3 (classify_role gaps):** `classify_role()` didn't recognize "Aufsichtsratsmitglied", "Sportlicher Leiter", "Leiter Sport" as management roles. Fix: Added to management keyword list in `lib/normalization.py`.
- **Impact:** Hecking network: 611→530 contacts (-81), 106 false staff contacts removed from stale clubs
- **Tests:** 47/47 passed, including new assertions for Aufsichtsrat and Stadionsprecher

### Career Timeline in Detail Panel ✅ (2026-04-09)
- **Enrichment:** `build_coach_network.py` now copies `career_history` from person_profiles to contact objects
- **Format:** Compact list of `{club, role, from, to}` dicts (normalized club names, season-only dates)
- **Template:** Detail panel renders a `<table class="career-table">` with Verein/Rolle/Zeitraum columns
- **Coverage:** ~15% of contacts have career_history (mainly coaches/staff; players have playing career data)
- **Fallback:** Legacy string format still supported for backward compatibility

### Club-Centric View ✅ (2026-04-09)
- **Script:** `python3 execution/generate_club_pages.py` → `output/clubs.html` index + `output/clubs/{slug}.html` per club
- **56 German-league clubs** (BL1 + BL2 + BL3)
- **Staff grouped by section:** Cheftrainer, Torwarttrainer, Co-Trainer, Fitness, Analyse, etc.
- **NET badges:** Cross-links to coach dashboards where available
- **Navigation:** "Vereine →" button on coach index header; "← Trainer-Netzwerke" link on club pages
- **Vercel route:** `/clubs` → `/clubs.html`

### Full Network Rebuild ✅ (2026-04-09)
- **461/461 networks rebuilt** with career_history enrichment, 0 errors
- **All dashboards regenerated** with updated template (career table, club nav)
- **Build time:** ~100 min (13.1s per coach incl. drilldown)
- **Dashboard count:** 988 files in output/dashboards/ (461 primary + drilldown JSONs)

### GemeinsameSpiele Integration ✅ (2026-04-10)
- **Scraping:** `execution/scrape_gemeinsame_spiele.py` — 308 coaches scraped, 57,214 teammates total
- **Data:** `data/gemeinsame_spiele/{trainer_tm_id}.json` — 301 coaches with data, 7 empty
- **Bug fix:** Claude Code used `DATA_DIR` (undefined) instead of `DATA` in build_coach_network.py line 649
- **Integration:** Step 2c in `build_coach_network.py` (line 648-691) — loads GS data, enriches existing contacts with `shared_matches`/`shared_minutes`, adds new contacts with 10+ shared games
- **Relevance score boost:** `_gs_verified` +5, 50+ matches +5, 100+ matches +5
- **Validation:** Klose network: 230/672 contacts with shared_matches (Lahm 215, Schweinsteiger 204, Borowski 143)
- **Template:** Detail panel shows "Gemeinsame Spiele: X Spiele · Yh" for contacts with GS data
- **Directive:** `directives/scrape_gemeinsame_spiele.md`

### Berater (Agent) Display ✅ (2026-04-10)
- **Data:** `agent` field in person_profiles — ~38.5% coverage (6,835 players), 1,515 unique agencies
- **Top agents:** CAA Stellar (71), The.Team (66), Unique Sports Group (53), SEG (43)
- **Integration:** `build_coach_network.py` copies `agent` field to contact objects (line 1216-1219)
- **Template:** Detail panel row "Berater: {agent}" below meta section
- **Directive:** `directives/berater_und_refresh.md`

### Daten-Refresh-Strategie (Directive)
- **Directive:** `directives/berater_und_refresh.md` — 3-tier refresh architecture
- **Tier 1 (Hot):** Staff daily, Squads weekly during transfer windows
- **Tier 2 (Warm):** Agent monthly refresh, profile quarterly
- **Tier 3 (Cold):** GemeinsameSpiele + playing careers at season end
- **Transfer Window Mode:** Auto-detection (Jan, Jul-Aug) → increased refresh frequency
- **Implementation:** Phase 2 (run_mvp.sh erweitern, monthly_refresh.sh, --refresh-agents flag)

### Audit + Quick-Wins (2026-04-19) ✅
- **Audit-Report:** `AUDIT_2026-04-19.md` — 5-dimensionaler Review (Trainerwechsel, 24-Trainer-Stichprobe, SDs+Spieler, Deploy, UX)
- **Fix-Plan:** `FIX_PLAN_2026-04-19.md` — 4 Batches, 1 Deploy
- **Root-Cause Staff-Refresh:** `scrape_squads.py _run_staff_only()` hatte keinen Age-Check → seit Einführung kein echter Refresh via `run_mvp.sh`. Fix: `--max-age-days=N` Flag + `--force`. `run_mvp.sh` nutzt jetzt `--max-age-days=1`.
- **Berater-Blacklist im Template:** `AGENT_BLACKLIST = {'ohne Berater', 'Familienangehörige', 'Eltern', 'keine Angabe', '-', 'N/A', 'unbekannt'}` — filtert Rauschwerte aus Detail-Panel
- **Falscher Regression-Alarm:** `top_players_coached` war kein Defekt — `player_coached` ist eine **Kategorie** (371/461 Netzwerke, 22.495 Kontakte), kein Array-Feld auf anderen Kontakten.
- **404.html:** fehlender `haptik.css` Link nachgezogen.
- **Confirmed stale Trainerwechsel (mussten nachgepflegt werden):** Köln (Kwasniok→Wagner), Union Berlin (Baumgart→Eta), Fortuna Düsseldorf (Anfang→Ende), Preußen Münster (Ende→Schwartz), Jahn Regensburg (Wimmer→Hildmann)

### Strategischer Pivot (2026-05-04) ✅
- **Stakeholder-Feedback:** "Starker progress, aber mehr Fokus auf (DACH-)Trainer. Coachinside zahlt projectFIVE 20k EUR/Jahr, Ziel 200+ Kontakte/Trainer."
- **USP-Korrektur:** "Hot-Seat-Frühwarnsystem ist NICHT der USP — Berater haben Markt-Intuition selbst, kein Algorithmus überholt das."
- **Neue USP-Hierarchie:**
  1. **Beziehungs-Tiefe** — Mitspieler-Daten (57.214 GS-Verbindungen), Cross-Drilldown, Karriere-Überlappung. Coachinside listet Kontakte, wir zeigen Bindungs-Tiefe.
  2. **Nachwuchs-Pipeline** — NLZ-Trainer als Aufstiegs-Kandidaten 2027+ (Variant 2 Sub-Vereins-Discovery)
  3. **Lehrgang-Cohorten** — Cold-Calling-Hebel ("Wer war 2018 mit Coach X im Lehrgang?")
  4. **Berater-Workflow** — CRM-light, Pipeline-Stages, Daily-Driver statt read-only
- **Hot-Seat-Score:** behält Position als Sortier-Hilfe + Sidebar-Filter, NICHT mehr im Pitch-Hero
- **stakeholder.html:** komplett re-framed — Hero, Pillars (#1 Beziehungs-Tiefe statt Hot-Seat), Demo-Flow, Roadmap (Sprints A-E), ROI-Argument (20k EUR/Jahr Ersparnis + 4 USPs)

### Sprint A · Lehrgang-Tiefe verdoppeln (2026-05-04) ⏳
- **Step 1 ✅:** LG 70 (2024/25) + LG 71 (2025/26) Pro Lizenz Cohorten ergänzt
  - Quellen: dfb.de news (28.01.2025 + 28.01.2026), je 17 Absolventen verbatim
  - Script: `python3 execution/add_pro_lizenz_70_71.py` (76% match rate, 26/34 Grads → tm_id)
  - Notable matches: Polzin (HSV, LG 70), Backhaus (Aachen, LG 70), Wagner (Augsburg, LG 71), Polzin/Wittmann/Hilbert/Westermann
  - Coaching_licenses: 258 → 292 grads (+34), 144 → 170 matched (+26, 56% → 58%)
- **Step 2 ⏳:** Network-Rebuild für 14 betroffene LG 70/71 Trainer (`bash run_sprint_a.sh`)
- **Step 3 ⏳:** Backfill LG 60 (2012/13) + Sportmanagement-Cohorten + DFB-Akademie A-Lizenz
  - A-Lizenz Auftakt 2026 erfolgte 27.01.2026 mit Andreas Rettig (Quelle: dfb-akademie.de) — Cohort wird Anfang 2027 publik
  - DFB-Akademie publiziert Cohort-Listen NICHT öffentlich; Scrape-Quellen sind kicker.de, dfb.de news, reviersport.de pro Cohort

### Chrome-Audit + Systemic Fixes 2026-05-21 ✅
Live UI/Daten-Audit via Chrome MCP an Blessin (Trainer-Perspektive) + Bornemann (SD-Perspektive). Plus 4 weitere Coaches Spot-Check (Eta, Hecking, Schwartz, Krösche). **11 Findings** dokumentiert in `AUDIT_2026-05-21.md` mit Severity + systemic-fix Proposals.

**Implementiert:**
- ✅ **F2 (P0): Coach-Hired-Name-Bug** — naive `replace("Alexander Blessin", coach_name)` im Template-Generator korrumpierte Contact-Namen im embedded JSON. Bornemann SD-Network zeigte Blessin als "Andreas Bornemann". Fix: unique Placeholder `__CENTER_NAME_PLACEHOLDER__` + canonical-source (`data/networks/{tm_id}.json`) statt korrupte HTML als Datenquelle in `regenerate_dashboards.py`. 660+ Dashboards regeneriert.
- ✅ **F1 Quick-Guard (P0): TM-Namespace-Kollision** — TM nutzt getrennte ID-Namespaces für `/spieler/<id>` vs `/trainer/<id>`. `persons_master` keyed nur auf tm_id → zuletzt gescrapeter überschreibt → Frankenstein-Profile (Bobic-Anzeige zeigt Walter Junghans-Karriere, Hagg zeigt Piwowarski, Tuchel zeigt Sam Stevens, etc.). Quantifiziert: **679 dual-namespace IDs** in Cache, ~500-700 korrumpierte Mitspieler-Display-Einträge. Quick-Guard in `build_coach_network.py`: vor Profile-Enrichment Name-Validation (Surname-fuzzy-match). Bei Mismatch → DROP enrichment. Verhindert Display-Korruption ohne full Migration. Volle Migration in separater Sprint.
- ✅ **F7 (P2): DFB-Display** — `NATIONAL_FEDERATIONS` Dict + `federation_label()` Helper in `lib/normalization.py`. "Geschäftsführer Sport, Deutschland" → "...DFB". Wiring im finalize-Pass in `build_coach_network.py`.
- ✅ **F8 (P2): "gehirt"-Typo** — `build_coach_network.py:1917` "Trainer (gehirt YYYY)" → "Trainer (geholt YYYY)".
- ✅ **F6 (P1): Filter-Count UX** — Template `buildTableCategoryFilters()` zeigt jetzt `"Mitspieler · 26 / 167"` statt `"Mitspieler (26)"`. Sidebar-Total + sichtbare-Filtered-Count beide visible. Tooltip differenziert.
- ✅ **F9 (P2): Role-Display Konsistenz** — `compute_role_display()` neue Priority 3.5 für executive/SD/management Kategorien: career_history[0].role mit Specific-Keywords (Geschäftsführer, Sportvorstand, Direktor) gewinnt gegen generische section ("Management"). Bornemann zeigt jetzt "Geschäftsführer Sport" statt "Management". Re-run nach career_history-load in `build_coach_network.py`.
- ✅ **F11 (P1): vercel.json + 404.html restored** — Worktree-Disaster vom 21.05 hatte beide aus `output/` weggewischt. Neu erstellt: vercel.json mit Cache-Control + Routing, 404.html mit SPORTFIVE-Brand + "Zurück zum Index" CTA.

**Pending (Directive):**
- ⏳ **F1 Full Migration** — `persons_master` Key-Schema auf `<type>_<tm_id>` migrieren, 679 IDs re-scrapen, Reader updaten. ~2-3h, separater Sprint.
- ⏳ **F3+F4+F5** — Coverage-Expansion PL/LaLiga/Bayern-Akademie. Mitspieler mit aktiver Rolle in nicht-gescrapten Vereinen werden vom Quick-Guard mitigiert (Display zeigt nur "Mitspieler" ohne falsche Karriere), aber für volle Auflösung müssen die Vereine gescraped werden.
- ⏳ **F11.b**: National-Team-Coaches (Nagelsmann + 31 weitere) sind in `persons_master`, haben aber kein Network/Dashboard. Pipeline-Erweiterung in separater Sprint.

**Audit-Report:** `AUDIT_2026-05-21.md`
**Directive:** `directives/DIRECTIVE_2026-05-21_evening_deploy.md`
**Run-Reihenfolge:** Phase 1 (Deploy F2, ~5min) → Phase 2 (run_mvp.sh full rebuild, ~100min) → Phase 3 (Polish optional) → Phase 4 (F1 Migration, separater Sprint).

### Trainerwechsel-Snapshot Refactor (2026-05-04) ✅
- **Bug:** TM-Endpunkt `/{liga}/trainer/wettbewerb/{Lx}` liefert seit April 2026 HTTP 404 — kompletter Pfad ist tot, nicht nur Vercel-IP-Block
- **Fix:** `execution/check_coach_changes.py` komplett refactored — liest jetzt **lokale** `data/staff/*.json` + `data/club_registry.json` statt TM-Live
- **Datenfrische:** abhängig von `run_mvp.sh` Staff-Refresh (`--max-age-days=1`), nicht von Live-TM-Aufruf
- **Output:** `output/api/check-coaches.json` mit BL1 (18) + BL2 (18) + BL3 (19) coaches, 0 errors

### Next Steps (Priority Order, 2026-05-21)
1. **F2-Deploy (5 min)** — `cd output && npx vercel deploy --prod --yes --scope cmk2299s-projects`. F2-Fix ist lokal verifiziert, nur Vercel-Push fehlt.
2. **Phase 2 Full Rebuild (~100min)** — `bash run_mvp.sh` mit `--all-bl-coaches`. Aktiviert F1-Quick-Guard, F6, F7, F8, F9 für alle Networks. Inkludiert Sprint 1+2 (Filter-Count + Marcel Schuhen Spieler-Klassifikation, LG 70/71 Trainer Networks).
3. **Daily-Refresh aktivieren** — `bash setup_daily_refresh.sh` (5 min). LaunchAgent `com.footballdb.daily-refresh` täglich 06:00 + ntfy-Push.
4. **F1 Full Migration (~2-3h, separater Sprint)** — `persons_master` Key-Migration auf `<type>_<id>`. Eliminiert die Namespace-Korruption komplett. Details in `directives/DIRECTIVE_2026-05-21_evening_deploy.md` §2.3.
5. **Sprint 3: Variant 2 NLZ-Discovery** — `bash run_youth_discovery.sh` (3-5h, overnight).
6. **Sprint 10b: P1+P2 Ligen scrapen** — configs ready, need `scrape_club_registry.py` + `scrape_squads.py` run.

### Next Steps (Priority Order, 2026-05-19)
1. **Daily Refresh aktivieren** — User-Action:
   ```bash
   bash setup_daily_refresh.sh
   ```
   → LaunchAgent `com.footballdb.daily-refresh` läuft täglich 06:00 Uhr, triggert `run_mvp.sh` + ntfy-Push (`cmk-coachdb`).
2. **Sprint 1: Filter-Count + Marcel-Schuhen-Rebuild** — Code committed, fehlt `--all-bl-coaches` rebuild + regen + deploy. Smoke-Test: Eta-Dashboard, Schuhen als Torwart, Filter-Counter konsistent.
3. **Sprint 2: Sprint A Step 2** — `bash run_sprint_a.sh` (14 LG-70/71-Coaches). Kann mit Sprint 1 kombiniert werden, da `--all-bl-coaches` sie enthält.
4. **Sprint 3: Variant 2 NLZ-Discovery** — `bash run_youth_discovery.sh` (3-5h, am besten over night)
5. **Sprint 10b: P1+P2 Ligen scrapen** — configs ready, need `scrape_club_registry.py` + `scrape_squads.py` run
6. ~~Light-Mode SPORTFIVE-Migration~~ — **gestrichen (User-Request 2026-05-19)**, Dark-Mode bleibt final.

**Sprint-Prep-Detail:** `SPRINT_PREP_2026-05-19.md`

### Known TM HTML Parsing Quirks (Self-annealed)
- **Name concatenation:** `<h1>` concatenates first+last without space (e.g., "RainerBonhof"). Fix: use `<title>` tag as primary source (has proper spacing), h1 as fallback with regex `re.sub(r"([a-zäöüß])([A-ZÄÖÜ])", r"\1 \2", raw_name)`
- **Career table classes:** TM doesn't use `tr.odd/tr.even` anymore. Fix: parse all `tr` rows containing `td` elements without class filter
- **Info table structure differs by page type:**
  - Coach profiles: `<span class="info-table__content">` nested in `<li>` or `<tr>`
  - Player profiles: Paired spans in `<div class="info-table">` — `--regular` (label) followed by `--bold` (value)
  - Some profiles: `<li class="data-header__label">` with `<span class="data-header__content">`
  - `parse_info_table_value()` now checks all 4 patterns in order
- **Nationality field is a list:** TM stores `["Deutschland", "Schweiz"]` where first entry is often Verbandsgebiet (country of work), not actual nationality. For display, filter out U-teams/DDR, then use second entry if multiple remain. Single-entry lists are the real nationality.

### Known Dashboard Template Quirks
- **Drilldown contact mapping:** Template reads `c.stations` (Array), NOT `c.station` (String). Always pass `stations: c.stations || [c.station || 'Unbekannt']` when mapping drilldown contacts.
- **Hardcoded center name:** All `loadLevel()` calls for root navigation MUST use `NETWORK.center`, never a hardcoded name. Breadcrumb init, `navigateBack()`, and breadcrumb click handler all need this.
- **Drilldown keys:** Use `name.toLowerCase().replace(/ /g, '_')` — must match between network builder and template.
- **Canvas station regions:** `drawStationLabels()` draws dashed circle boundaries + JetBrains Mono labels for clusters with 3+ nodes.
- **No emojis policy:** All UI uses text/CSS labels. Pro badges are "T"/"SD" text, drill-down indicator is `»`, search icon is `⌕` (CSS).
- **Asset-CSS Regenerations-Pflicht:** Nach Änderungen an `output/assets/*.css` müssen **alle** Output-HTMLs (461 dashboards + 56 clubs + 404) regeneriert werden — sie backen das Template zum Generationszeitpunkt ein. Vorgehen: `python3 execution/regenerate_dashboards.py --lazy 500000` + `python3 execution/generate_club_pages.py`. `run_mvp.sh` deckt das ab.
- **Berater-Blacklist:** Template `AGENT_BLACKLIST` Set filtert Rauschwerte aus `persons_master.agent` (`"ohne Berater"`, `"Familienangehörige"`, `"Eltern"`, `"keine Angabe"`, etc.) — nur echte Agenturen werden im Detail-Panel angezeigt.
- **`player_coached` ist Kategorie, kein Feld:** Top-Spieler erscheinen als **eigene Kontakte** mit `category: "player_coached"` und Feldern `appearances`/`goals`/`assists`/`minutes`, NICHT als Array-Feld auf anderen Kontakten. 371/461 Netzwerke haben solche Kontakte (Ø 60,6).

### Known Data Pipeline Quirks
- **Staff-Refresh ohne Age-Check (pre-2026-04-19):** `scrape_squads.py --staff-only` überspringt JEDE existierende Staff-Datei ohne Altersprüfung. Folge: seit Einführung gab es **nie** einen echten Refresh über `run_mvp.sh`, Daten waren 22-45+ Tage alt. Fix: `--max-age-days=N` Flag + `--force`. `run_mvp.sh` nutzt jetzt `--max-age-days=1`.
- **C9 Station-Stamp Staleness (2026-06-05):** Netzwerke, die VOR dem current_club-Lambda-Fix (2026-06-04) in `build_coach_network.build_network` gebaut wurden, tragen auf `player_coached`-Kontakten den **Coach-Station-Namen** statt des echten Spieler-current_club aus dem Profil (z.B. alle Klon-Spieler zeigten "SV Werder Bremen II"). Der aktuelle Builder liest current_club korrekt aus `spieler_{id}.json`. **137 stale Netzwerke** detektiert (inkl. Nagelsmann, Streich, Bosz, Ilzer). Detection: `platform_audit.py` Check C9 (Profil-autoritativ, flaggt bei ≥30% mismatch der player_coached-Kontakte). **Fix-Tool:** `python3 execution/rebuild_stale_networks.py --ids-file <liste>` — baut Netzwerk-JSON neu via aktuellem `build_network`, bewahrt `_*meta` (NLZ-Tier/parent_club), und regeneriert ALLE existierenden Dashboard-Varianten (`_network` + `_nlz_network`; **NICHT** `_sd_network` — das ist SD-zentriert, anderer Builder). **Lehre:** Nach Builder-Logik-Fixes ALLE betroffenen Netzwerke neu bauen, nicht nur Stichprobe (Systematik vor Ad-Hoc) — sonst bleibt stale Output auf Disk, weil `regenerate_dashboards.py` die eingebackene NETWORK-Konstante aus dem alten HTML wiederverwendet (es liest NICHT die frische `data/networks/{id}.json`).

---

## Brand · SPORTFIVE Design System (2026-05-11)

projectFIVE Trainerberatung gehört zu **SPORTFIVE**. Tool nutzt SPORTFIVE-Brand-Tokens.

### Color-Tokens (verbatim aus `Sportfive_vMM` Power-BI-Theme)

| Token | Hex | Verwendung im Tool |
|-------|-----|--------------------|
| `--sf-red` / `--accent` | `#F40009` | Brand-Akzent, Index-Section-Titles, Pillar-Badges, Hot-Seat-Critical, Score-Highlights |
| `--sf-ink` | `#262626` | nicht aktiv (Dark-Mode bleibt) |
| `--sf-charcoal` | `#4D4D4D` | nicht aktiv (Dark-Mode bleibt) |
| `--sf-grey` | `#737373` | nicht aktiv (Dark-Mode bleibt) |
| `--sf-rule` | `#E5E5E5` | nicht aktiv (Dark-Mode bleibt) |
| `--sf-good` | `#34C23A` | Positive Sentiment (z.B. PPG-Trend up) |
| `--sf-bad` | `#F40009` | Negative Sentiment (alias `--sf-red`, by design) |

**Aktueller Modus:** Dark-Mode (`--bg: #0a0a0e`) — SPORTFIVE-Spec ist eigentlich Light-Mode "Always white". Dark-Mode wurde beibehalten als pragmatischer Trade-off (Berater-Daily-Driver, Force-Graph-Optimierung). **Brand-Akzent ist SPORTFIVE-konform**, Layout-Mode nicht. **Light-Mode-Migration ist gestrichen (User-Request 2026-05-19)** — Dark-Mode bleibt finaler Zustand.

### Typography (finaler Stand)

`IBM Plex Sans` + `Space Grotesk` + `JetBrains Mono`. SPORTFIVE-Spec verlangt zwar `Segoe UI`, der Font-Stack bleibt aber als pragmatischer Trade-off bestehen (Force-Graph + Mono-Stats lesen sich besser, Konsistenz mit Dark-Mode).

### Forbidden ohne explicit semantic reason
- Multiple Rot-Töne (nur `#F40009`)
- Grün ausserhalb von Sentiment-Kontext
- Blau ausser für Categorical-Contrast in Multi-Series-Charts
- Zebra-stripe Tabellen
- Vertikale Grid-Linien in Tabellen

### Quelldatei
`/Users/cmk/.../uploads/SPORTFIVE_DESIGN_SYSTEM.md` — Single Source of Truth.

---

## Deployment
- **Host:** Vercel (scope: cmk2299s-projects)
- **Deploy:** `cd output && npx vercel deploy --prod --yes --scope cmk2299s-projects`
- **URL:** https://coach-network-explorer.vercel.app
- **One-click:** `bash run_mvp.sh` (includes staff refresh + build + deploy)

---

## Summary

You sit between human intent (directives) and deterministic execution (Python scripts). Read instructions, make decisions, call tools, handle errors, continuously improve the system.

Be pragmatic. Be reliable. Self-anneal.
