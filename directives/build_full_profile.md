# Directive: Build Full Coach Profile

## Goal
Build a comprehensive coach profile by orchestrating all scrapers and exporting to Google Sheets.

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
- significant_players[] (20+ games, 70+ avg minutes)

### Step 4: Export to Google Sheets
**Script:** `execution/export_to_sheets.py`
**Command:** `python export_to_sheets.py --profile {profile.json}`

**Output:** Row added/updated in Google Sheet

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

### Google Sheets auth fails
- Delete token.json
- Re-run to trigger new OAuth flow

## Timing
- Profile: ~5 seconds
- Teammates: ~5 seconds
- Players used: ~5 seconds
- Export: ~2 seconds
- **Total: ~17 seconds per coach**

## Learnings
(Add discoveries here as the system runs)

- [Date]: Learning
