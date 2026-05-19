# Directive: Sprint 3 — Expand to BL3, NLZ, and Historical Coaches

## Goal
Expand the Coach Network Explorer from 36 current BL1+BL2 coaches to ~150-200 coaches covering:
1. **3. Liga head coaches** (current season 25/26)
2. **NLZ-Leiter** (U19/U17 Bundesliga head coaches)
3. **Historical head coaches** from BL1+BL2 (last 5 seasons: 20/21–24/25)

## Architecture Decisions

### Data availability
All required data already exists:
- `club_registry.json`: 119 clubs with league history since 2010 (includes BL3 + NLZ leagues)
- `staff/`: Current staff for all 119 clubs
- `squads/`: 1,091 squad files (all clubs × all seasons since 2010)
- `person_profiles/`: 2,794 coach profiles with career history

### BL3 coaches (current season)
Same approach as BL1+BL2. `get_bl_clubs()` already accepts `leagues` parameter.
```python
bl3_clubs = get_bl_clubs(club_registry, ["BL3"], season=2025)
```
Expected: ~20 additional coaches.

### NLZ coaches
NLZ league codes in club_registry: `"BJL"` (U19-BL), `"BJ2"` (U17-BL)
- Staff files include NLZ staff under `section: "Nachwuchsleistungszentrum"` or similar
- NLZ head coaches may not be the first entry in Trainerstab
- Need to identify NLZ-specific head coaches from staff data

**Implementation approach:**
1. Get clubs in BJL/BJ2 for current season
2. From staff files, find entries with section containing "Jugend"/"Nachwuchs"/"NLZ"/"U19"/"U17"
3. First entry per NLZ section = NLZ head coach

Expected: ~20-30 NLZ coaches (many clubs share senior + NLZ staff files).

### Historical coaches (BL1+BL2, seasons 20/21–24/25)
This is the most valuable expansion — shows former coaches who are now at other clubs, retired, or in other roles.

**Approach:** Use career_history from scraped coach profiles to find who was head coach at each BL1/BL2 club in each historical season.

```python
def get_historical_coaches(club_registry, profiles, seasons=[2020,2021,2022,2023,2024]):
    """Find all coaches who were head coach at a BL1/BL2 club in given seasons."""
    historical = []
    seen_ids = set()

    for season in seasons:
        bl_clubs = get_bl_clubs(club_registry, ["BL1", "BL2"], season)

        for club_id, club in bl_clubs.items():
            # Search all profiles for someone who was head coach at this club in this season
            for tm_id, profile in profiles.items():
                for entry in profile.get("career_history", []):
                    if entry.get("club_tm_id") != club_id:
                        continue
                    role = classify_role(entry.get("role", ""))
                    if role != "head_coach":
                        continue
                    entry_seasons = get_season_range(entry.get("date_from",""), entry.get("date_to",""))
                    if season in entry_seasons and tm_id not in seen_ids:
                        seen_ids.add(tm_id)
                        historical.append({
                            "tm_id": tm_id,
                            "name": profile["name"],
                            "club": club.get("name", ""),
                            "club_tm_id": club_id,
                            "season": season,
                            "league": "BL1" if "BL1" in ... else "BL2",
                        })
    return historical
```

**Optimization:** Use the inverted profile_index instead of scanning all profiles:
```python
for tm_id in profile_index.get((club_id, season), []):
    profile = profiles[tm_id]
    # Check if any career entry at this club in this season has head_coach role
```

Expected: ~80-120 additional coaches (many overlap with current coaches).

---

## Implementation Plan

### Step 1: Extend `generate_all_bl_coaches.py`

Add new CLI options:
```bash
python generate_all_bl_coaches.py --leagues BL1 BL2 BL3    # Add BL3
python generate_all_bl_coaches.py --include-nlz             # Add NLZ coaches
python generate_all_bl_coaches.py --historical 2020-2024    # Add historical
python generate_all_bl_coaches.py --all                     # Everything
```

### Step 2: Update index.html generator

Add new sections to the index page:
- **1. Bundesliga** (18 coaches)
- **2. Bundesliga** (18 coaches)
- **3. Liga** (~20 coaches)
- **NLZ** (~20-30 coaches)
- **Ehemalige BL1/BL2-Trainer** (~80-120 coaches, grouped by last season)

Each section follows the same card layout.

### Step 3: Handle deduplication

A coach who was BL2 head coach in 22/23 and is now BL1 head coach should only appear once (in the current BL1 section). Historical section only shows coaches NOT currently active in BL1/BL2/BL3.

### Step 4: Batch generation

Full pipeline:
```bash
# Generate all networks (may take 30-60 min with drill-down)
python execution/generate_all_bl_coaches.py --all

# Deploy
cd output && npx vercel deploy --prod --yes
```

---

## Edge Cases
- **Interim coaches:** Some clubs had 2-3 coaches per season. Each gets their own dashboard.
- **Coaches at multiple clubs in one season:** Their network covers all clubs.
- **Foreign coaches without German career:** Still included if they coached a BL club.
- **NLZ coaches who are also first-team staff:** Deduplicate by tm_id.

## Testing
1. Start with `--leagues BL3` only, verify ~20 new dashboards
2. Add `--include-nlz`, verify NLZ coaches are correctly identified
3. Add `--historical 2024` (1 season) to verify historical detection works
4. Then full `--all` run

## Learnings
(Update as you go)
