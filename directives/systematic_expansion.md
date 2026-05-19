# Directive: Systematic Data Expansion (Demand-Driven)

## Philosophy

**Don't manually pick leagues. Let the data tell you where the gaps are.**

Previous expansions (Top-5 leagues, BL3, NLZ) were based on intuition. This directive replaces that with a systematic, repeatable process:

1. **Analyze** all 34,513 career histories → find every club NOT in registry
2. **Rank** missing clubs by how many BL-coach contacts reference them
3. **Group** by league/country → prioritize entire leagues, not individual clubs
4. **Expand** registry + scrape staff/squads for top-priority leagues
5. **Regenerate** networks + dashboards → measure density improvement

This process is idempotent — run it again after any expansion to find the next layer of gaps.

---

## Phase 1: Coverage Gap Analysis

### Script: `execution/analyze_coverage_gaps.py`

**Input:**
- `data/club_registry.json` (307 clubs)
- `data/person_profiles/*.json` (34,513 profiles)

**Output:** `data/coverage_gaps.json` + console report

```bash
python execution/analyze_coverage_gaps.py
python execution/analyze_coverage_gaps.py --bl-coaches-only  # Focus on 36 BL head coaches' networks
python execution/analyze_coverage_gaps.py --min-refs 5       # Only clubs with 5+ person references
```

### What it computes:

1. **Club Universe**: Every unique `club_tm_id` in all career histories
2. **Registry Coverage**: Which of those are in `club_registry.json`
3. **Missing Clubs**: Grouped and classified:
   - `youth_reserve`: Contains "U19", "U17", "U16", "U15", "II", "Jgd.", "Jugend", "B-Junioren", "A-Junioren"
   - `international`: Club not in German/covered leagues
   - `lower_german`: German club below BL3 (Regionalliga, Oberliga, etc.)
   - `defunct`: Club no longer active or renamed
4. **League Grouping**: Infer league from TM club pages or from career context
5. **BL-Coach Impact**: How many of the 36 BL head coaches' contacts are affected

### Key Metrics:

| Metric | Description |
|--------|-------------|
| `total_career_clubs` | Unique clubs across all career histories |
| `registry_clubs` | Clubs we have staff/squad data for |
| `missing_clubs` | Clubs with no staff/squad data |
| `coverage_pct` | registry / total × 100 |
| `bl_coach_missing` | Missing clubs that appear in BL head coaches' careers |
| `top_missing_leagues` | Leagues ranked by how many missing clubs they contain |

### Expected Findings (Hypotheses):

Based on the 36 BL coaches' known career paths:
- **Belgian Pro League** (Blessin: Union SG, KV Oostende; Kompany: Anderlecht)
- **Turkish Süper Lig** (multiple coaches with Turkish stints)
- **Swiss Super League** (multiple coaches, RB Salzburg feeder)
- **Danish Superliga** (Hjulmand: Nordsjælland)
- **Greek Super League**, **Portuguese Liga**, **Scottish Premiership**
- **2. Ligen**: Championship (ENG), Serie B (ITA), Ligue 2 (FRA), Segunda (ESP)
- **German youth/reserve teams**: RB Leipzig U19/U17, Bayern U19, etc.
- **Austrian 2. Liga**, **Dutch Eerste Divisie**

---

## Phase 2: Registry Expansion

### Decision Framework

After Phase 1 produces the ranked list, expand the registry using this priority:

| Priority | Criteria | Action |
|----------|----------|--------|
| **P0** | League has 5+ clubs referenced by BL coach careers | Add entire league to registry |
| **P1** | League has 3+ clubs referenced by any person in our DB | Add league |
| **P2** | Individual club referenced by 10+ persons | Add club individually |
| **P3** | Youth/reserve teams of existing registry clubs | Add via parent-club linkage |
| **Skip** | Clubs with <3 person references, amateur/regional leagues | Don't add (diminishing returns) |

### Script: `execution/expand_registry.py`

Extends `scrape_club_registry.py` to accept new league configurations:

```bash
# Add Belgian Pro League
python execution/scrape_club_registry.py --add-league jupiler_pro "Jupiler Pro League" BE

# Add Swiss Super League
python execution/scrape_club_registry.py --add-league super_league_ch "Super League" CH

# Add Championship (ENG 2nd division)
python execution/scrape_club_registry.py --add-league championship "Championship" ENG

# Add all P0 leagues from gap analysis
python execution/expand_registry.py --from-gaps data/coverage_gaps.json --priority P0
```

### TM League URL Pattern:
```
https://www.transfermarkt.de/{league_slug}/startseite/wettbewerb/{league_code}
```

Known league codes (verified 2026-03-26):
| League | TM Code | Slug | Country |
|--------|---------|------|---------|
| Belgian Pro League | BE1 | jupiler-pro-league | 🇧🇪 |
| Turkish Süper Lig | TR1 | super-lig | 🇹🇷 |
| Swiss Super League | C1 | super-league | 🇨🇭 |
| Danish Superliga | DK1 | superligaen | 🇩🇰 |
| Swedish Allsvenskan | SE1 | allsvenskan | 🇸🇪 |
| Norwegian Eliteserien | NO1 | eliteserien | 🇳🇴 |
| Scottish Premiership | SC1 | scottish-premiership | 🏴 |
| Greek Super League 1 | GR1 | super-league-1 | 🇬🇷 |
| Liga Portugal | PO1 | liga-nos | 🇵🇹 |
| Championship (ENG) | GB2 | championship | 🏴 |
| Serie B (ITA) | IT2 | serieb | 🇮🇹 |
| Ligue 2 (FRA) | FR2 | ligue-2 | 🇫🇷 |
| LaLiga2 (ESP) | ES2 | laliga2 | 🇪🇸 |
| 2. Liga (AT) | A2 | 2-liga | 🇦🇹 |
| Keuken Kampioen Divisie (NL) | NL2 | keuken-kampioen-divisie | 🇳🇱 |
| Chance Liga (CZ) | TS1 | fortuna-liga | 🇨🇿 |
| Ekstraklasa (PL) | PL1 | pko-bp-ekstraklasa | 🇵🇱 |
| SuperSport HNL (HR) | KR1 | 1-hnl | 🇭🇷 |
| Saudi Pro League | SA1 | saudi-pro-league | 🇸🇦 |
| Premier Liga (RU) | RU1 | premier-liga | 🇷🇺 |

### Youth/Reserve Handling

Youth teams (U19, U17) and reserve teams ("II") have their own TM IDs but often share staff with the parent club. Strategy:

1. **Don't add to league registry** — they're not traditional leagues
2. **Scrape staff pages individually** via `scrape_foreign_staff.py`
3. **Link to parent club** in network builder via naming convention:
   - "RB Leipzig U19" → parent = "RB Leipzig"
   - "Bayern München II" → parent = "FC Bayern München"
4. **Contacts from youth teams merge into parent station** in dashboard display

---

## Phase 3: Batch Staff + Squad Scraping

Once registry is expanded:

```bash
# Scrape staff for all new clubs
python execution/scrape_squads.py --staff-only --new-clubs-only

# Scrape squads for relevant seasons (based on BL coach career overlap)
python execution/scrape_squads.py --seasons 2015-2025 --new-clubs-only

# Scrape foreign staff for clubs still not in registry (individual clubs from P2)
python execution/scrape_foreign_staff.py --all-bl-coaches
```

### Estimated Volume per League:

| League | Est. Clubs | Staff Pages | Squad Pages (×10 seasons) |
|--------|-----------|-------------|--------------------------|
| Belgian Pro League | ~18 | 18 | 180 |
| Turkish Süper Lig | ~20 | 20 | 200 |
| Swiss Super League | ~12 | 12 | 120 |
| Danish Superliga | ~14 | 14 | 140 |
| Championship (ENG) | ~24 | 24 | 240 |
| **Total P0 estimate** | ~88 | 88 | 880 |

At 3s delay: ~45 min for staff, ~45 min for squads. Total: ~90 min for P0 leagues.

---

## Phase 4: Person Profile Enrichment

New clubs → new persons discovered in squads/staff → need TM profile scraping:

```bash
# Re-index all persons (discovers new ones from expanded squads/staff)
python execution/scrape_person_profiles.py --new-only

# Update persons_master.json
python execution/scrape_person_profiles.py --rebuild-master
```

### Estimated New Persons:
- P0 leagues (~88 clubs × ~30 squad players × 10 seasons): ~26,000 squad entries
- After dedup (many players play in multiple leagues): ~8,000–15,000 new unique persons
- Profile scraping at 3s delay: ~7–13 hours

**Optimization**: Only scrape profiles for persons who appear in BL coach networks. The network builder identifies which contacts need profiles. Scrape on-demand rather than exhaustively.

---

## Phase 5: Network Regeneration + Dashboard Expansion

### 5a: Regenerate existing 36 dashboards
```bash
python execution/generate_all_bl_coaches.py --leagues BL1 BL2
```

**Expected improvement**: Blessin goes from 118 → ~160+ contacts (Belgian clubs fill in). Similar gains for coaches with Turkish, Swiss, Danish career stations.

### 5b: Expand to BL3 + NLZ + Historical coaches
```bash
# BL3 current season
python execution/generate_all_bl_coaches.py --leagues BL3

# NLZ coaches (from Jugend staff sections)
python execution/generate_all_bl_coaches.py --include-nlz

# Historical BL1+BL2 coaches (last 5 seasons)
python execution/generate_all_bl_coaches.py --historical 2020-2024

# Everything
python execution/generate_all_bl_coaches.py --all
```

**Expected coach count:**
| Scope | Coaches | Status |
|-------|---------|--------|
| BL1 current | 18 | ✅ Live |
| BL2 current | 18 | ✅ Live |
| BL3 current | ~20 | Phase 5b |
| NLZ head coaches | ~20-30 | Phase 5b |
| Historical BL1+BL2 (5 seasons) | ~80-120 unique | Phase 5b |
| **Total** | **~150-200** | |

### 5c: Index Page Redesign

Current: flat table with 36 coaches.
New: sectioned layout:
- **1. Bundesliga** (18) — with league logo
- **2. Bundesliga** (18) — with league logo
- **3. Liga** (~20)
- **NLZ / Jugend-Bundesliga** (~20-30)
- **Ehemalige BL-Trainer** (~80-120, grouped by last club)

Each section: sortable table, search, flag icons, contact/station stats.

---

## Phase 6: Measure & Iterate

After full expansion, re-run Phase 1:

```bash
python execution/analyze_coverage_gaps.py --compare data/coverage_gaps_pre.json
```

This shows:
- Coverage improvement: e.g. 307/2000 (15%) → 500/2000 (25%)
- Remaining gaps: which leagues still missing
- Diminishing returns: at some point, adding more leagues adds <5 contacts per coach

### Success Metrics

| Metric | Before | Target |
|--------|--------|--------|
| Registry clubs | 307 | 500+ |
| Avg contacts per BL coach | 159 | 200+ |
| Coaches with dashboards | 36 | 150+ |
| Network density (contacts with drill-down) | 96% | 98%+ |
| Foreign station coverage | ~60% | 90%+ |

---

## Execution Order (for Claude Code)

### Sprint A: Gap Analysis + Quick Wins (1 session)
1. `python execution/analyze_coverage_gaps.py` → get the ranked list
2. `python execution/scrape_foreign_staff.py --all-bl-coaches` → immediate density boost
3. Regenerate 36 dashboards → deploy

### Sprint B: League Expansion (1-2 sessions)
4. Add P0 leagues to registry (based on gap analysis results)
5. Scrape staff + squads for new leagues
6. Re-scrape person profiles for new persons
7. Regenerate all dashboards → deploy

### Sprint C: Coach Scope Expansion (1 session)
8. Add BL3 coaches
9. Add NLZ coaches
10. Add historical coaches
11. Redesign index page
12. Deploy full expansion

### Sprint D: Measure + Second Wave (if needed)
13. Re-run gap analysis
14. Add P1 leagues if ROI justifies
15. Final quality pass

---

## Integration with Existing Directives

This directive **supersedes**:
- `scrape_foreign_club_staff.md` — absorbed into Phase 3 (foreign staff scraping)
- `sprint3_expand_leagues.md` — absorbed into Phase 5b (BL3/NLZ/Historical)
- `expand_international_leagues.md` — absorbed into Phase 2 (registry expansion)

Those directives remain as reference but this is the new master expansion plan.

---

## Learnings Log
_(Update as you discover issues)_

- [pending] Gap analysis results — which leagues are actually most impactful
- [pending] Youth team staff page availability (do U19 teams have Mitarbeiter pages?)
- [pending] Optimal registry size before diminishing returns kick in
- [pending] Profile scraping time for large expansions — may need batching strategy
