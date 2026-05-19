# Directive: Sprint 2 — Complete Player Profile Scraping

## Goal
Scrape TM profiles for all ~11,500 remaining players in `persons_index.json`. This enriches player contacts in dashboards with nationality, DOB, position, foot, and image.

## Current State
- 2,794 coach/staff profiles scraped ✅
- ~625 player profiles scraped (~5%)
- ~11,570 player profiles remaining
- Script exists and works: `execution/scrape_person_profiles.py`

## Execution Plan

### Batch Strategy
The scraper runs at ~14 profiles/min (3s delay). To scrape all ~11,570 players:
- Total time: ~14 hours
- Split into manageable batches of 500 (`--limit=500`)
- Each batch: ~36 minutes
- Auto-skips already-scraped profiles (safe to re-run)

### Commands
```bash
# Check how many are left
python execution/scrape_person_profiles.py --players-only --dry-run

# Run batch (repeat until done)
python execution/scrape_person_profiles.py --players-only --limit=500

# Overnight run (large batch)
python execution/scrape_person_profiles.py --players-only --limit=3000
```

### Monitoring
After each batch:
```bash
ls data/person_profiles/ | wc -l    # Total profiles
```
Target: ~14,989 files (all persons in index)

### Error Handling
- Transient timeouts: handled gracefully (retry on next run)
- 403/429 blocks: increase delay to 5s with `--delay=5`
- If blocked: wait 30 min, then resume (TM blocks are temporary)
- All errors logged to stdout — redirect to file for overnight runs:
  ```bash
  python execution/scrape_person_profiles.py --players-only --limit=3000 2>&1 | tee tmp/scrape_players.log
  ```

### Post-Scraping
After all players are scraped:

1. **Rebuild persons_master.json** with enriched data:
   ```bash
   python execution/scrape_squads.py --index-only
   ```

2. **Regenerate all dashboards** to pick up new player data:
   ```bash
   python execution/generate_all_bl_coaches.py
   ```

3. **Redeploy**:
   ```bash
   cd output && npx vercel deploy --prod --yes
   ```

## Data Fields per Player Profile
| Field | Source | Expected Coverage |
|-------|--------|------------------|
| name | TM profile | 100% |
| nationality | TM profile | ~100% |
| dob | TM profile | ~94% |
| position | TM profile | ~100% |
| foot | TM profile | ~99% |
| image_url | TM profile | ~100% |
| career_history | NOT on player profile page | 0% (comes from squad data) |

**Important:** Player profiles on TM don't show career history the same way coach profiles do. Player career data comes from Phase 2 squad files (which club they were in, which season). This is already handled in `build_coach_network.py` via squad file loading.

## Impact on Dashboards
Before: Player contacts show name + position from squad data only
After: Player contacts additionally show nationality flag, DOB/age, profile image, preferred foot

## Learnings
(Update as you go)
