# Directive: Build Master Football Database

## Goal
Build a comprehensive database of all Bundesliga players (active since 2010) and German coaches/staff in leagues 1-3 plus NLZ since 2010. Every person gets a persistent TM-ID. Career transitions (player → coach/SD/scout) are tracked automatically.

## Data Model

### Tables / JSON structures

| Entity | Key | Fields | Est. Size |
|--------|-----|--------|-----------|
| `clubs` | tm_id | name, slug, league_history[season→league[]] | ~150 |
| `persons` | tm_id | name, dob, nationality, current_role, current_club, image_url | ~8.000-12.000 |
| `squad_entries` | (person_id, club_id, season) | role (player/coach/staff/nlz_coach), position, shirt_number | ~50.000-80.000 |
| `career_transitions` | derived | person_id, from_role, to_role, transition_season, club | derived |

### Role taxonomy
- `player` — Active squad member
- `head_coach` — Cheftrainer
- `assistant_coach` — Co-/Assistenztrainer
- `goalkeeper_coach` — Torwarttrainer
- `fitness_coach` — Athletiktrainer / Fitnesstrainer
- `nlz_coach` — NLZ/Jugend-Trainer (U19/U17 BL)
- `sporting_director` — Sportdirektor / Sportvorstand
- `scout` — Kaderplaner / Scout
- `analyst` — Videoanalyst
- `other_staff` — Sonstige Mitarbeiter

### Career transition detection
A person has a career transition when they appear in `squad_entries` with different role types across seasons:
- Same tm_id, role changes from `player` → `head_coach` (e.g. Nouri, Reis)
- Same tm_id, role changes from `player` → `sporting_director` (e.g. Bobic, Mislintat)
- Transition date = first season where new role appears

---

## Phases

### Phase 1: Club Registry ✅ (2026-02-28)
**Script:** `execution/scrape_club_registry.py`
**Input:** League IDs (L1, L2, L3, BJL, BJ2) × Seasons (2010-2025)
**Output:** `data/club_registry.json`

Scrapes TM league pages to discover all clubs that ever played in BL1, BL2, BL3, U19-BL, U17-BL since 2010. Each club gets: tm_id, slug, name, seasons per league.

**Pages to scrape:** ~80 (5 leagues × 16 seasons)
**Est. time:** ~4-5 minutes

### Phase 2: Squad Crawling (Season × Club) ✅ (2026-03-01)
**Script:** `execution/scrape_squads.py`
**Input:** `data/club_registry.json`
**Output:** `data/squads/` (one JSON per club-season), `data/staff/` (one JSON per club), `data/persons_index.json`

**Results:**
- 1,091 squad files (119 clubs × ~9-16 seasons each)
- 119 staff files (current Mitarbeiter for all clubs)
- 35,134 player entries, 2,877 staff entries
- **14,790 unique persons** in persons_index.json
- 62 career transitions detected (player → staff/scout/SD)
- 31.9 MB total data

**Role breakdown:** 11,996 players, 2,116 other_staff, 305 scouts, 277 sporting_directors, 167 nlz_coaches

**CLI modes:**
- `--start=N --limit=N` — batch mode for splitting across sessions
- `--staff-only` — only crawl Mitarbeiter pages (Part B), with --start/--limit
- `--index-only` — rebuild persons_index.json from existing files

**Note:** Staff pages show CURRENT staff only. Historical coaches come from individual coach profile career histories (Phase 3).
**Note:** Trainerhistorie URL pattern returns 404 — use Phase 3 career history instead.

**Pages scraped:** ~1,210 (1,091 squad + 119 staff)
**Total time:** ~90 minutes across ~12 batch runs

### Phase 3: Person Profiles
**Script:** `execution/scrape_person_profiles.py` (TO BUILD)
**Input:** All unique person tm_ids from Phase 2
**Output:** `data/person_profiles/` (one JSON per person or batched)

For each unique person, fetch their TM profile:
- Full career history (all clubs, dates, roles)
- Personal info (DOB, nationality, birthplace)
- License (for coaches)
- Current role detection
- Profile image URL

**Priority order:**
1. Coaches first (smaller set, higher value)
2. Players with >3 seasons in data (established pros)
3. Remaining players

**Pages to scrape:** ~8,000-12,000
**Est. time:** ~7-10 hours (split across multiple sessions)

### Phase 4: Career Transitions & Enrichment
**Script:** `execution/detect_career_transitions.py` (TO BUILD)
**Input:** All squad_entries + person_profiles
**Output:** `data/career_transitions.json`, updated `data/persons_master.json`

Cross-reference:
- Find persons who appear as player AND coach/staff
- Calculate transition dates
- Build "second career" flags
- Generate network connections (who worked together where)

### Phase 5: Dashboard Integration
Update the existing dashboard system to use the new master database instead of single-coach networks.

---

## Rate Limiting & Resilience

- **Delay:** 3 seconds between requests (proven safe from MVP)
- **Caching:** 7-day cache for league pages, 30-day for profiles
- **Batch saves:** Save after each club-season to allow resuming
- **Error handling:** Log failures, skip and continue, retry once
- **User-Agent rotation:** Not needed at 3s delays (proven with 69 sequential requests)

## Learnings from MVP

- [2026-02-28] TM allows 3s-delayed sequential scraping without blocks (tested 69 requests)
- [2026-02-28] Use `lxml` parser for speed, `html.parser` as fallback
- [2026-02-24] Nationality field sometimes concatenates dual nationalities
- [2026-02-24] License coverage is low (~20%)
- [2026-02-28] Cache all raw HTML for debugging/re-parsing
- [2026-03-01] Phase 2 complete: 14,790 unique persons (11,996 players + 2,794 staff/coaches) from 119 clubs × 16 seasons
- [2026-03-01] Staff pages only show CURRENT staff — historical coaches require Phase 3 individual profile crawling
- [2026-03-01] Batch execution with --start/--limit works well for 10-minute timeout constraints (12 batches needed)
- [2026-03-01] Some DNS/timeout failures are transient — retry pass recommended before Phase 3
- [2026-03-01] Career transitions from squad+staff overlap: 62 found (e.g. player→scout, player→SD)
