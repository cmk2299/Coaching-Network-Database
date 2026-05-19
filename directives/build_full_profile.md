# Directive: Build Full Coach Profile

## Goal
Build a comprehensive coach profile by orchestrating all scrapers, enriching with network data, and outputting to an interactive HTML dashboard.

## Input
- Coach name (string) OR
- Direct Transfermarkt URL

## Steps

### Step 1: Get Basic Profile
**Script:** `execution/scrape_transfermarkt.py`
**Command:** `python scrape_transfermarkt.py --name "Coach Name"`

**Output:** Profile JSON with:
- name, nationality, dob, age
- current_role, current_club
- license, agent_name
- career_history[]

### Step 2: Get Teammates (if applicable)
**Script:** `execution/scrape_teammates.py`
**Command:** `python scrape_teammates.py --url "{profile_url}"`

**Output:** Teammates JSON with:
- all_teammates[]
- coaches[] (teammates who became coaches)
- sporting_directors[] (teammates who became SDs)

**Skip if:** Coach has no playing career (no teammates page)

### Step 3: Get Players Coached
**Script:** `execution/scrape_players_used.py`
**Command:** `python scrape_players_used.py --url "{profile_url}"`

**Output:** Players used JSON with:
- all_players[]
- significant_players[] (20+ games, 45+ avg minutes)

### Step 4: Enrich Network Contacts
**Script:** `execution/enrich_transfermarkt_profiles.py`
**Command:** `python enrich_transfermarkt_profiles.py`

**Output:** `data/profile_enrichment.json` with per-contact fields:
- nationality, dob, age, license, current_club
- Scraped from TM profile pages of all contacts with tm_url

### Step 5: Cross-Reference & Enrich Relationships
**Script:** `execution/enrich_network.py` (or orchestrator logic)

**Output:** Per-contact enrichment:
- career_history (from master_coach_profiles.json matching)
- coaches_worked_with[] (coaches at shared stations)
- sds_worked_with[] (sporting directors at shared stations)
- top_players_coached[] (from players_used data, 20+ games, 45+ avg mins)

### Step 6: Generate Background Summaries
**Script:** `execution/generate_background_summaries.py`

**Output:** `data/background_summaries.json` — 1-2 sentence German summary per contact, template-based per category (no LLM API needed)

### Step 7: Build Dashboard
**Template:** `blessin_network_v3.html` (template with `__NETWORK_PLACEHOLDER__` / `__DRILLDOWN_PLACEHOLDER__`)

**Process:**
1. Merge all enrichment data into `data/blessin_full_network.json`
2. Minify network + drilldown JSON
3. Replace placeholders in template
4. Output production HTML file

**Output:** Single self-contained HTML file with embedded data

## Edge Cases

### Coach not found
- Show search results if available
- Ask user to verify spelling or provide direct URL

### Multiple coaches with same name
- List all matches with current club
- Use first match or ask user to select

### No teammates page
- Coach never played professionally
- Skip Step 2, continue with Step 3

### No players used data
- New coach with no significant history
- Set significant_players to empty

### Low career_history match rate
- master_coach_profiles.json matching by name yields ~9%
- Consider fuzzy matching or TM coach_id matching for improvement

### Agent/Berater data unavailable
- TM doesn't display agent info for coaches (0% hit rate)
- Field requires alternative data source — skip for now

## Timing
- Profile: ~5 seconds
- Teammates: ~5 seconds
- Players used: ~5 seconds
- Network enrichment (69 contacts): ~4 minutes (3s delay per request)
- Background summaries: ~1 second
- Dashboard build: ~2 seconds
- **Total: ~5 minutes per coach network**

## Learnings

- [2026-02-24]: TM profile pages have different HTML structures for coaches vs players. The info table uses `<span class="info-table__content">` for fields like nationality, DOB, license.
- [2026-02-24]: Agent/Berater info is rarely shown for coaches on TM (0% hit rate). This field may need an alternative data source.
- [2026-02-24]: TM nationality field sometimes concatenates dual nationalities without separator (e.g. "UngarnGriechenland"). Need to split by uppercase letters.
- [2026-02-24]: License field coverage is low (~20%). Many coaches don't list their license on TM.
- [2026-02-28]: Scraping with 3s delay and proper User-Agent works reliably. No blocks encountered on 69 sequential requests.
- [2026-02-28]: career_history from master_coach_profiles.json only matches ~9% of network contacts by name. Fuzzy matching or TM ID matching would improve this.
- [2026-02-28]: Players coached filter of "20+ games, 70+ min avg" was too strict — relaxed to 45 min avg for broader coverage (30/91 contacts).
- [2026-02-28]: Google Sheets export removed from MVP scope — replaced by interactive HTML dashboard with embedded data.
- [2026-02-28]: Background summaries generated deterministically from structured data (no LLM API needed) — template-based approach per category works well.
