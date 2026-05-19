# Directive: Build SQLite Database for projectFIVE

## Goal
Replace the 20 MB JSON master file with a structured SQLite database. This enables:
- Fast queries without loading everything into memory
- Easy data delivery to projectFIVE (single .db file)
- SQL-based reporting and ad-hoc analysis
- Foundation for a future API layer

## Input Data (Updated 2026-03-26)
All data lives in `data/`:
- `person_profiles/` — **34,513** individual JSON files (27,734 players + 6,779 coaches/staff)
- `club_registry.json` — **307 clubs** with league history (BL1/2/3/NLZ + PL/Liga/SA/L1/Eredivisie)
- `squads/` — **2,776** squad files (club × season)
- `staff/` — **308** staff files (current Mitarbeiter per club)
- `persons_master.json` — **51.9 MB** merged index (34,513 persons)
- `networks/` — 36 pre-built network JSONs

### New fields since last build
- `agent` — Berater/Spielerberater (6,835 players have this, 1,273 unique firms)
- International clubs with `country` derived from league (PL→England, Liga→Spanien, etc.)

## Schema

### `clubs`
```sql
CREATE TABLE clubs (
    tm_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT,
    country TEXT DEFAULT 'Deutschland'
);
```

### `club_seasons`
```sql
CREATE TABLE club_seasons (
    club_tm_id INTEGER NOT NULL,
    season INTEGER NOT NULL,        -- e.g. 2025 for 25/26
    league TEXT NOT NULL,            -- BL1, BL2, BL3, BJL, BJ2
    PRIMARY KEY (club_tm_id, season, league),
    FOREIGN KEY (club_tm_id) REFERENCES clubs(tm_id)
);
```

### `persons`
```sql
CREATE TABLE persons (
    tm_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT,                       -- 'trainer', 'spieler', 'staff'
    nationality TEXT,                -- Primary nationality (resolved from TM list)
    nationalities TEXT,              -- JSON array of all nationalities
    dob TEXT,                        -- ISO date: '1971-10-15'
    birthplace TEXT,
    position TEXT,                   -- For players: 'Torwart', 'Innenverteidiger', etc.
    foot TEXT,                       -- 'rechts', 'links', 'beidfüßig'
    license TEXT,                    -- For coaches: 'UEFA-Pro-Lizenz', etc.
    current_club_tm_id INTEGER,
    current_club_name TEXT,
    current_role TEXT,
    image_url TEXT,
    tm_url TEXT,
    agent TEXT,                      -- Berater (if scraped)
    profile_scraped INTEGER DEFAULT 0,  -- 1 if TM profile was scraped
    scraped_at TEXT,                 -- ISO datetime
    FOREIGN KEY (current_club_tm_id) REFERENCES clubs(tm_id)
);
```

### `career_history`
```sql
CREATE TABLE career_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_tm_id INTEGER NOT NULL,
    club_tm_id INTEGER,
    club_name TEXT,                   -- Normalized via club_registry
    role TEXT,                        -- 'Trainer', 'Co-Trainer', 'Spieler', etc.
    role_category TEXT,               -- 'head_coach', 'coaching_staff', 'player', etc.
    date_from TEXT,                   -- Raw TM format: '23/24 (19.03.2024)'
    date_to TEXT,
    season_from INTEGER,             -- Parsed: 2023
    season_to INTEGER,               -- Parsed: 2024 (NULL if still active)
    games INTEGER,
    points_per_game REAL,
    FOREIGN KEY (person_tm_id) REFERENCES persons(tm_id),
    FOREIGN KEY (club_tm_id) REFERENCES clubs(tm_id)
);
CREATE INDEX idx_career_person ON career_history(person_tm_id);
CREATE INDEX idx_career_club_season ON career_history(club_tm_id, season_from);
```

### `squad_entries`
```sql
CREATE TABLE squad_entries (
    person_tm_id INTEGER NOT NULL,
    club_tm_id INTEGER NOT NULL,
    season INTEGER NOT NULL,
    role TEXT DEFAULT 'player',       -- 'player' from squad files
    position TEXT,
    shirt_number INTEGER,
    PRIMARY KEY (person_tm_id, club_tm_id, season),
    FOREIGN KEY (person_tm_id) REFERENCES persons(tm_id),
    FOREIGN KEY (club_tm_id) REFERENCES clubs(tm_id)
);
CREATE INDEX idx_squad_club_season ON squad_entries(club_tm_id, season);
```

### `staff_entries`
```sql
CREATE TABLE staff_entries (
    person_tm_id INTEGER NOT NULL,
    club_tm_id INTEGER NOT NULL,
    section TEXT,                     -- 'Trainerstab', 'Scouting', etc.
    role TEXT,                        -- 'other_staff', etc.
    is_head_coach INTEGER DEFAULT 0, -- 1 if first entry in Trainerstab
    PRIMARY KEY (person_tm_id, club_tm_id),
    FOREIGN KEY (person_tm_id) REFERENCES persons(tm_id),
    FOREIGN KEY (club_tm_id) REFERENCES clubs(tm_id)
);
```

### `career_transitions`
```sql
CREATE TABLE career_transitions (
    person_tm_id INTEGER NOT NULL,
    from_role TEXT,                   -- 'player'
    to_role TEXT,                     -- 'head_coach', 'sporting_director'
    transition_season INTEGER,       -- First season in new role
    club_tm_id INTEGER,              -- Where transition happened
    FOREIGN KEY (person_tm_id) REFERENCES persons(tm_id)
);
```

---

## Build Script

### Script: `execution/build_sqlite.py`

```
Usage:
    python execution/build_sqlite.py                    # Full build
    python execution/build_sqlite.py --output data/coaches.db
    python execution/build_sqlite.py --skip-squads      # Faster: skip squad_entries (largest table)
```

### Implementation Steps

1. **Create database + schema** (DDL above)
2. **Import clubs** from `club_registry.json` → `clubs` + `club_seasons`
3. **Import persons** from `person_profiles/*.json` → `persons` + `career_history`
   - Parse nationality list: resolve to primary nationality using the same logic as `build_coach_network.py`
   - Store raw nationalities as JSON in `nationalities` column
   - Parse career_history entries: extract `season_from`/`season_to` using `parse_season_from_date()`
   - Normalize club names via `club_tm_id` lookup against `clubs` table
   - Classify roles using `classify_role()` from `build_coach_network.py`
4. **Import squad entries** from `squads/*.json` → `squad_entries`
   - ~35,000 entries (1,091 files × ~32 players avg)
5. **Import staff entries** from `staff/*.json` → `staff_entries`
   - Mark first Trainerstab entry per club as `is_head_coach = 1`
6. **Detect career transitions** → `career_transitions`
   - Find persons who appear as player in `squad_entries` AND as coach/staff in `staff_entries` or `career_history`
   - Transition season = first season where new role appears
7. **Create views** for common queries (see below)
8. **VACUUM** and print stats

### Reuse existing code
Import from `build_coach_network.py`:
- `parse_season_from_date()` — season parsing
- `classify_role()` — role classification
- `normalize_club()` — club name normalization
- `load_club_registry()` — club data loading

---

## Useful Views

```sql
-- Current BL1+BL2 head coaches
CREATE VIEW v_bl_coaches AS
SELECT p.tm_id, p.name, p.nationality, p.dob, p.license, p.image_url,
       s.club_tm_id, c.name as club_name, cs.league
FROM staff_entries s
JOIN persons p ON p.tm_id = s.person_tm_id
JOIN clubs c ON c.tm_id = s.club_tm_id
JOIN club_seasons cs ON cs.club_tm_id = s.club_tm_id AND cs.season = 2025
WHERE s.is_head_coach = 1
  AND cs.league IN ('BL1', 'BL2');

-- Career overlap: who worked together at the same club+season
CREATE VIEW v_shared_stations AS
SELECT a.person_tm_id as person_a, b.person_tm_id as person_b,
       a.club_tm_id, c.name as club_name,
       a.season_from as season
FROM career_history a
JOIN career_history b ON a.club_tm_id = b.club_tm_id
  AND a.season_from = b.season_from
  AND a.person_tm_id < b.person_tm_id
JOIN clubs c ON c.tm_id = a.club_tm_id;

-- Player → Coach transitions
CREATE VIEW v_transitions AS
SELECT p.name, ct.from_role, ct.to_role, ct.transition_season,
       c.name as club_name
FROM career_transitions ct
JOIN persons p ON p.tm_id = ct.person_tm_id
LEFT JOIN clubs c ON c.tm_id = ct.club_tm_id
ORDER BY ct.transition_season DESC;

-- Coach career summary
CREATE VIEW v_coach_careers AS
SELECT p.tm_id, p.name, p.nationality,
       COUNT(DISTINCT ch.club_tm_id) as clubs_count,
       MIN(ch.season_from) as career_start,
       MAX(COALESCE(ch.season_to, 2025)) as career_end,
       GROUP_CONCAT(DISTINCT c.name) as clubs
FROM persons p
JOIN career_history ch ON ch.person_tm_id = p.tm_id
LEFT JOIN clubs c ON c.tm_id = ch.club_tm_id
WHERE p.type = 'trainer'
GROUP BY p.tm_id;
```

---

## Expected Output (Updated 2026-03-26)

| Table | Rows (est.) |
|-------|-------------|
| clubs | ~5,000+ (307 registry + foreign clubs from careers) |
| club_seasons | ~2,500 |
| persons | 34,513 |
| career_history | ~40,000+ (coaches have career_history, players from squad overlap) |
| squad_entries | ~80,000+ |
| staff_entries | ~5,000+ |
| career_transitions | ~404 |

**Database size:** ~25-35 MB (significantly larger with international data)

---

## Delivery to projectFIVE

The SQLite file is self-contained and portable:
```bash
# Copy to output for sharing
cp data/coaches.db output/coaches.db

# Quick check
sqlite3 data/coaches.db "SELECT COUNT(*) FROM persons"
sqlite3 data/coaches.db "SELECT * FROM v_bl_coaches"
```

Can be opened in any SQLite viewer (DB Browser, DBeaver, DataGrip) or queried via Python:
```python
import sqlite3
conn = sqlite3.connect("data/coaches.db")
coaches = conn.execute("SELECT * FROM v_bl_coaches").fetchall()
```

---

## Testing

1. Build: `python execution/build_sqlite.py`
2. Verify counts: `sqlite3 data/coaches.db "SELECT type, COUNT(*) FROM persons GROUP BY type"`
3. Spot-check Kovac: `sqlite3 data/coaches.db "SELECT * FROM career_history WHERE person_tm_id = 97"`
4. Verify transitions: `sqlite3 data/coaches.db "SELECT * FROM v_transitions LIMIT 20"`
5. Compare with JSON: network contact counts should match

## Rebuild Notes (2026-03-26)

### What changed since initial build
1. **Scale:** 14,989 → 34,513 persons, 119 → 307 clubs, 1,091 → 2,776 squads, 119 → 308 staff
2. **Agent field:** `persons.agent` now populated for 6,835 players (57%)
3. **Career transitions:** 61 → 404 detected
4. **Country field:** Clubs now have proper country based on league (not just "Deutschland" vs "Ausland/Sonstige")
5. **Master file:** 51.9 MB — `build_sqlite.py` should still load this in <5s

### Country mapping for international clubs
```python
LEAGUE_COUNTRY = {
    "BL1": "Deutschland", "BL2": "Deutschland", "BL3": "Deutschland",
    "BJL": "Deutschland", "BJ2": "Deutschland",
    "PL": "England", "GB1": "England",
    "LIGA": "Spanien", "ES1": "Spanien",
    "SA": "Italien", "IT1": "Italien",
    "L1": "Frankreich", "FR1": "Frankreich", "L1FR": "Frankreich",
    "ERE": "Niederlande", "NL1": "Niederlande",
}
```

### Execution
```bash
# Rebuild from scratch (delete old DB first)
rm -f data/coaches.db output/coaches.db
python execution/build_sqlite.py

# Verify
sqlite3 data/coaches.db "SELECT type, COUNT(*) FROM persons GROUP BY type"
# Expected: spieler ~27,734, trainer ~6,779

sqlite3 data/coaches.db "SELECT country, COUNT(*) FROM clubs GROUP BY country ORDER BY COUNT(*) DESC"
# Expected: Deutschland top, then England, Spanien, Italien, Frankreich, Niederlande

sqlite3 data/coaches.db "SELECT COUNT(DISTINCT agent) FROM persons WHERE agent IS NOT NULL"
# Expected: ~1,273

# Copy to output
cp data/coaches.db output/coaches.db
```

## Learnings
- (Update as you go)
