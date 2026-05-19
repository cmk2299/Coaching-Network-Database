# Directive: Scrape Foreign Club Staff

## Goal
Scrape staff (Mitarbeiter) pages from Transfermarkt for clubs **outside** the existing BL1/BL2/BL3/NLZ club registry. This fills the biggest gap in coach networks: when a coach worked abroad (e.g. Blessin at Union SG, Genua CFC, KV Oostende), we currently have 0-3 contacts from those stations instead of 20-50.

## Why This Matters
The network builder (`build_coach_network.py`) finds contacts via two paths:
1. **Staff files** (`data/staff/{club_id}.json`) — current colleagues at clubs we've crawled
2. **Profile index** — other coaches whose career history overlaps at the same (club, season)

Path 2 only finds people who are **already in our database** (BL coaches/staff). For foreign clubs, most colleagues never worked in German football, so they're invisible. We need to scrape those club's staff pages directly.

## Input
- A list of foreign club TM IDs, derived from the coach's career history
- These are clubs NOT in `data/club_registry.json`

The network builder already knows which clubs are missing — it can compute:
```python
career_clubs = {entry['club_tm_id'] for entry in coach['career_history']}
registry_clubs = set(club_registry.keys())
foreign_clubs = career_clubs - registry_clubs
```

## Script: `execution/scrape_foreign_staff.py`

### CLI Interface
```bash
# Scrape staff for specific clubs
python execution/scrape_foreign_staff.py --clubs 3948 252 2861

# Scrape all foreign clubs for a specific coach
python execution/scrape_foreign_staff.py --for-coach 26099

# Scrape all foreign clubs for all BL coaches
python execution/scrape_foreign_staff.py --all-bl-coaches

# Dry run — just list what would be scraped
python execution/scrape_foreign_staff.py --for-coach 26099 --dry-run
```

### URL Pattern
Same as existing staff scraper:
```
https://www.transfermarkt.de/{club_slug}/mitarbeiter/verein/{club_tm_id}
```

### Output
Same format as existing staff files → `data/staff/{club_id}.json`:
```json
{
  "club_tm_id": 3948,
  "club_name": "Union SG",
  "club_slug": "royale-union-saint-gilloise",
  "source": "foreign_staff_scrape",
  "scraped_at": "2026-03-21T14:30:00",
  "staff": [
    {
      "tm_id": 12345,
      "slug": "some-trainer",
      "name": "Some Trainer",
      "tm_url": "https://www.transfermarkt.de/some-trainer/profil/trainer/12345",
      "club_tm_id": 3948,
      "club_name": "Union SG",
      "section": "Trainerstab",
      "role": "coaching_staff",
      "image_url": "https://img.tm.de/..."
    }
  ]
}
```

### Key Difference from `scrape_squads.py --staff-only`
- `scrape_squads.py` iterates clubs from `club_registry.json` (BL1/2/3/NLZ only)
- This script takes **arbitrary** TM club IDs
- The parser logic (`parse_staff_page()`) is **identical** — reuse it directly
- Output format is identical → the network builder already reads `data/staff/{id}.json`

### Implementation Plan
1. **Reuse `parse_staff_page()`** from `scrape_squads.py` — import it, don't duplicate
2. **Club slug discovery**: If we only have the `club_tm_id`, we need the slug for the URL. Options:
   - The coach's `career_history` has `club_slug` field ✅
   - Fallback: fetch the club's main page and extract slug from redirect
3. **Cache**: Save raw HTML to `tmp/cache/staff/foreign_{club_id}.html` with 30-day TTL
4. **Dedup**: Skip clubs that already have a staff file in `data/staff/`
5. **Rate limiting**: 3s delay between requests (same as all TM scrapers)

## Integration with Network Builder

After foreign staff files exist, `build_coach_network.py` already picks them up automatically:

```python
# In build_network() — Step 1: Current staff colleagues
staff = load_staff(current_club_id)  # Already loads from data/staff/{id}.json
```

BUT: This only loads staff for the **current** club. For historical foreign clubs, we need to extend the network builder to also check staff files for **all career stations**, not just the current one.

### Required Change to `build_coach_network.py`
After the current staff block (Step 1), add:
```python
# ── 1b) Staff at historical foreign clubs ──
for club_id, info in coach_stations.items():
    if club_id == current_club_id:
        continue  # Already handled above
    staff = load_staff(club_id)
    if not staff:
        continue
    club_name = info["name"]
    for s in staff.get("staff", []):
        if s["tm_id"] == coach_tm_id:
            continue
        if s["tm_id"] not in contacts_map:
            contacts_map[s["tm_id"]] = {
                "name": s["name"],
                "stations": [club_name],
                "category": classify_staff_section(s.get("section", "")),
                "role": s.get("section", "Staff"),
                "tm_url": s.get("tm_url", ""),
                "tm_id": s["tm_id"],
                "seasons_together": 1,
            }
        elif club_name not in contacts_map[s["tm_id"]]["stations"]:
            contacts_map[s["tm_id"]]["stations"].append(club_name)
```

## Scope & Prioritization

### Phase A: BL Head Coach Foreign Clubs (highest value)
- 36 BL1+BL2 head coaches
- ~50-80 foreign clubs total (many overlap — RB Salzburg, Ajax, etc.)
- **Est. pages:** ~50-80
- **Est. time:** ~5-10 minutes at 3s delay

### Phase B: All Scraped Coaches' Foreign Clubs (nice-to-have)
- 2,794 coaches in database
- Could be thousands of foreign clubs
- Only do this if Phase A proves valuable

### Priority Estimation per Coach
Coaches with the most foreign stations benefit most:
- Blessin: 4 foreign clubs (Union SG, Genua, Oostende, RB Leipzig youth)
- Kompany: many foreign clubs (Anderlecht, Burnley, Man City era)
- Kovac: Croatia, Monaco, Frankfurt youth levels
- Hjulmand: Nordsjælland, Danish clubs

## Edge Cases

### Club page structure differs by country
- German TM pages: well-structured, tested
- International pages: **same HTML structure** (TM is consistent globally) but:
  - Section headers may be in different languages ("Coaching Staff" vs "Trainerstab")
  - Some smaller clubs may not have a Mitarbeiter page
- **Fix**: The parser uses CSS classes, not text matching. Should work cross-country. Test with 3-4 foreign clubs first.

### Club has been renamed or merged
- TM handles this with redirects
- Follow redirects, use final URL's club ID

### Staff page returns 404
- Club may not have a Mitarbeiter page (common for small/amateur clubs)
- Log warning, skip, continue

### Duplicate contacts across multiple foreign clubs
- Same person may appear at multiple of the coach's former clubs
- The network builder's `contacts_map` handles dedup by `tm_id`
- Merge station lists (person gets multiple stations)

## Rate Limiting
- **3 seconds** between requests (proven safe)
- **Cache** all HTML responses for 30 days
- **Skip** clubs with existing staff files (unless `--force` flag)
- No parallel requests

## Validation
After scraping, verify quality:
```bash
# Check how many contacts were added
python execution/build_coach_network.py --tm-id 26099
# Compare: before ~70 contacts → after should be 90-120+
```

## Learnings Log
_(Update this section as you discover issues)_

- [pending] Test international Mitarbeiter page structure (is it identical to German?)
- [pending] Verify section headers work cross-language
- [pending] Check if NLZ/youth club IDs (RB Leipzig U19 = 26621) have Mitarbeiter pages
