#!/usr/bin/env python3
"""
Build SQLite Database — projectFIVE data delivery

Converts all JSON data (profiles, squads, staff, club registry) into a
single SQLite database for easy querying and delivery.

Usage:
    python execution/build_sqlite.py                    # Full build
    python execution/build_sqlite.py --output data/p5.db
    python execution/build_sqlite.py --skip-squads      # Faster: skip squad_entries

Output:
    data/coaches.db (~15-20 MB)
"""

import argparse
import json
import os
import re
import sqlite3
import time
from pathlib import Path

# Reuse helpers from build_coach_network
import sys
sys.path.insert(0, str(Path(__file__).parent))
from build_coach_network import (
    normalize_club, classify_role, classify_staff_section,
    parse_season_from_date, load_club_registry,
    CLUB_NAME_NORMALIZE,
)

BASE = Path(__file__).parent.parent
DATA = BASE / "data"
PROFILES_DIR = DATA / "person_profiles"
SQUADS_DIR = DATA / "squads"
STAFF_DIR = DATA / "staff"
DEFAULT_OUTPUT = DATA / "coaches.db"


# ── Schema ────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS clubs (
    tm_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT,
    country TEXT DEFAULT 'Deutschland'
);

CREATE TABLE IF NOT EXISTS club_seasons (
    club_tm_id INTEGER NOT NULL,
    season INTEGER NOT NULL,
    league TEXT NOT NULL,
    PRIMARY KEY (club_tm_id, season, league),
    FOREIGN KEY (club_tm_id) REFERENCES clubs(tm_id)
);

CREATE TABLE IF NOT EXISTS persons (
    tm_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT,
    nationality TEXT,
    nationalities TEXT,
    dob TEXT,
    birthplace TEXT,
    position TEXT,
    foot TEXT,
    height_cm INTEGER,
    license TEXT,
    current_club_tm_id INTEGER,
    current_club_name TEXT,
    current_role TEXT,
    image_url TEXT,
    tm_url TEXT,
    agent TEXT,
    profile_scraped INTEGER DEFAULT 0,
    scraped_at TEXT,
    FOREIGN KEY (current_club_tm_id) REFERENCES clubs(tm_id)
);

CREATE TABLE IF NOT EXISTS career_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_tm_id INTEGER NOT NULL,
    club_tm_id INTEGER,
    club_name TEXT,
    role TEXT,
    role_category TEXT,
    date_from TEXT,
    date_to TEXT,
    season_from INTEGER,
    season_to INTEGER,
    games INTEGER,
    points_per_game REAL,
    FOREIGN KEY (person_tm_id) REFERENCES persons(tm_id),
    FOREIGN KEY (club_tm_id) REFERENCES clubs(tm_id)
);
CREATE INDEX IF NOT EXISTS idx_career_person ON career_history(person_tm_id);
CREATE INDEX IF NOT EXISTS idx_career_club_season ON career_history(club_tm_id, season_from);

CREATE TABLE IF NOT EXISTS squad_entries (
    person_tm_id INTEGER NOT NULL,
    club_tm_id INTEGER NOT NULL,
    season INTEGER NOT NULL,
    role TEXT DEFAULT 'player',
    position TEXT,
    shirt_number INTEGER,
    PRIMARY KEY (person_tm_id, club_tm_id, season),
    FOREIGN KEY (person_tm_id) REFERENCES persons(tm_id),
    FOREIGN KEY (club_tm_id) REFERENCES clubs(tm_id)
);
CREATE INDEX IF NOT EXISTS idx_squad_club_season ON squad_entries(club_tm_id, season);

CREATE TABLE IF NOT EXISTS staff_entries (
    person_tm_id INTEGER NOT NULL,
    club_tm_id INTEGER NOT NULL,
    section TEXT,
    role TEXT,
    is_head_coach INTEGER DEFAULT 0,
    PRIMARY KEY (person_tm_id, club_tm_id),
    FOREIGN KEY (person_tm_id) REFERENCES persons(tm_id),
    FOREIGN KEY (club_tm_id) REFERENCES clubs(tm_id)
);

CREATE TABLE IF NOT EXISTS career_transitions (
    person_tm_id INTEGER NOT NULL,
    from_role TEXT,
    to_role TEXT,
    transition_season INTEGER,
    club_tm_id INTEGER,
    club_name TEXT,
    FOREIGN KEY (person_tm_id) REFERENCES persons(tm_id)
);

-- Views
CREATE VIEW IF NOT EXISTS v_bl_coaches AS
SELECT p.tm_id, p.name, p.nationality, p.dob, p.license, p.image_url,
       s.club_tm_id, c.name as club_name, cs.league
FROM staff_entries s
JOIN persons p ON p.tm_id = s.person_tm_id
JOIN clubs c ON c.tm_id = s.club_tm_id
JOIN club_seasons cs ON cs.club_tm_id = s.club_tm_id AND cs.season = 2025
WHERE s.is_head_coach = 1
  AND cs.league IN ('BL1', 'BL2');

CREATE VIEW IF NOT EXISTS v_transitions AS
SELECT p.name, ct.from_role, ct.to_role, ct.transition_season,
       ct.club_name
FROM career_transitions ct
JOIN persons p ON p.tm_id = ct.person_tm_id
ORDER BY ct.transition_season DESC;

CREATE VIEW IF NOT EXISTS v_coach_careers AS
SELECT p.tm_id, p.name, p.nationality,
       COUNT(DISTINCT ch.club_tm_id) as clubs_count,
       MIN(ch.season_from) as career_start,
       MAX(COALESCE(ch.season_to, 2025)) as career_end,
       GROUP_CONCAT(DISTINCT ch.club_name) as clubs
FROM persons p
JOIN career_history ch ON ch.person_tm_id = p.tm_id
WHERE p.type = 'trainer'
GROUP BY p.tm_id;
"""


# ── Nationality resolution ────────────────────────────────────────────

def resolve_nationality(nat_raw) -> str:
    """Resolve TM nationality list to primary nationality."""
    if not nat_raw:
        return None
    if isinstance(nat_raw, str):
        return nat_raw
    if isinstance(nat_raw, list):
        real = [n for n in nat_raw if not any(x in n for x in [' U', 'DDR'])]
        if len(real) >= 2:
            return real[1]  # Second = actual nationality (first is often work country)
        elif real:
            return real[0]
        return nat_raw[0] if nat_raw else None
    return None


# ── Import functions ──────────────────────────────────────────────────

def import_clubs(conn):
    """Import clubs + club_seasons from club_registry.json."""
    registry = load_club_registry()
    clubs_inserted = 0
    seasons_inserted = 0

    for tm_id, club in registry.items():
        name = normalize_club(club.get("name", ""))
        slug = club.get("slug", "")
        conn.execute(
            "INSERT OR IGNORE INTO clubs (tm_id, name, slug) VALUES (?, ?, ?)",
            (int(tm_id), name, slug)
        )
        clubs_inserted += 1

        # League history
        leagues = club.get("leagues") or club.get("league_history", {})
        for season_key, league_list in leagues.items():
            # Parse season: "2025/2026" → 2025, "2025" → 2025
            m = re.match(r"(\d{4})", str(season_key))
            if not m:
                continue
            season = int(m.group(1))
            if isinstance(league_list, str):
                league_list = [league_list]
            for league in league_list:
                conn.execute(
                    "INSERT OR IGNORE INTO club_seasons (club_tm_id, season, league) VALUES (?, ?, ?)",
                    (int(tm_id), season, league)
                )
                seasons_inserted += 1

    conn.commit()
    print(f"  clubs: {clubs_inserted} rows")
    print(f"  club_seasons: {seasons_inserted} rows")


def import_persons(conn):
    """Import persons + career_history from person_profiles/*.json."""
    persons_inserted = 0
    career_inserted = 0
    errors = 0

    files = sorted(PROFILES_DIR.glob("*.json"))
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as fh:
                p = json.load(fh)
        except (json.JSONDecodeError, OSError):
            errors += 1
            continue

        # Profile filenames are namespaced post-migration: trainer_<id>.json /
        # spieler_<id>.json (also legacy <id>.json). int(f.stem) crashes on the
        # prefixed form, so derive tm_id from JSON first, then fall back to the
        # numeric tail of the stem.
        tm_id = p.get("tm_id")
        if tm_id is None:
            stem = f.stem
            for pfx in ("trainer_", "spieler_"):
                if stem.startswith(pfx):
                    stem = stem[len(pfx):]
                    break
            try:
                tm_id = int(stem)
            except ValueError:
                errors += 1
                continue
        nat_raw = p.get("nationality")
        nationality = resolve_nationality(nat_raw)
        nationalities_json = json.dumps(nat_raw) if isinstance(nat_raw, list) else None

        current_club = p.get("current_club") or {}
        current_club_id = current_club.get("tm_id")
        current_club_name = normalize_club(current_club.get("name", "")) if current_club.get("name") else None

        conn.execute("""
            INSERT OR REPLACE INTO persons
            (tm_id, name, type, nationality, nationalities, dob, birthplace,
             position, foot, height_cm, license,
             current_club_tm_id, current_club_name, image_url, agent,
             profile_scraped, scraped_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
        """, (
            int(tm_id), p.get("name", ""), p.get("type"),
            nationality, nationalities_json,
            p.get("dob"), p.get("birthplace"),
            p.get("position"), p.get("foot"), p.get("height_cm"),
            p.get("license"),
            int(current_club_id) if current_club_id else None,
            current_club_name,
            p.get("image_url"), p.get("agent"),
            p.get("scraped_at"),
        ))
        persons_inserted += 1

        # Career history (coaches only — players don't have this on TM)
        for entry in p.get("career_history", []):
            club_tm_id = entry.get("club_tm_id")
            club_name = normalize_club(entry.get("club_name", ""))
            role = entry.get("role", "")
            role_category = classify_role(role)
            season_from = parse_season_from_date(entry.get("date_from", ""))
            season_to = parse_season_from_date(entry.get("date_to", ""))
            games = entry.get("games")
            if isinstance(games, str):
                games = None
            pps = entry.get("pps")

            conn.execute("""
                INSERT INTO career_history
                (person_tm_id, club_tm_id, club_name, role, role_category,
                 date_from, date_to, season_from, season_to, games, points_per_game)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                int(tm_id), int(club_tm_id) if club_tm_id else None,
                club_name, role, role_category,
                entry.get("date_from"), entry.get("date_to"),
                season_from, season_to, games, pps,
            ))
            career_inserted += 1

    conn.commit()
    print(f"  persons: {persons_inserted} rows ({errors} errors)")
    print(f"  career_history: {career_inserted} rows")


def import_squads(conn):
    """Import squad_entries from squads/*.json."""
    inserted = 0
    skipped = 0

    files = sorted(SQUADS_DIR.glob("*.json"))
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as fh:
                sq = json.load(fh)
        except (json.JSONDecodeError, OSError):
            continue

        club_tm_id = sq.get("club_tm_id")
        season = sq.get("season")
        if not club_tm_id or not season:
            continue

        for player in sq.get("players", []):
            pid = player.get("tm_id")
            if not pid:
                continue
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO squad_entries
                    (person_tm_id, club_tm_id, season, role, position, shirt_number)
                    VALUES (?, ?, ?, 'player', ?, ?)
                """, (
                    int(pid), int(club_tm_id), int(season),
                    player.get("position"),
                    player.get("shirt_number"),
                ))
                inserted += 1
            except sqlite3.IntegrityError:
                skipped += 1

    conn.commit()
    print(f"  squad_entries: {inserted} rows ({skipped} skipped dupes)")


def import_staff(conn):
    """Import staff_entries from staff/*.json."""
    inserted = 0

    files = sorted(STAFF_DIR.glob("*.json"))
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as fh:
                st = json.load(fh)
        except (json.JSONDecodeError, OSError):
            continue

        club_tm_id = st.get("club_tm_id")
        if not club_tm_id:
            continue

        # Track first Trainerstab entry = head coach
        head_coach_found = False
        for staff in st.get("staff", []):
            sid = staff.get("tm_id")
            if not sid:
                continue

            section = staff.get("section", "")
            role = classify_staff_section(section)
            is_head = 0
            if section == "Trainerstab" and not head_coach_found:
                is_head = 1
                head_coach_found = True

            try:
                conn.execute("""
                    INSERT OR IGNORE INTO staff_entries
                    (person_tm_id, club_tm_id, section, role, is_head_coach)
                    VALUES (?, ?, ?, ?, ?)
                """, (int(sid), int(club_tm_id), section, role, is_head))
                inserted += 1
            except sqlite3.IntegrityError:
                pass

    conn.commit()
    print(f"  staff_entries: {inserted} rows")


def detect_transitions(conn):
    """Detect player → coach/SD/scout career transitions."""
    # Strategy: find persons in squad_entries who ALSO appear in staff_entries or career_history as non-player
    # Two sources of post-player roles:
    #   1. staff_entries (current staff at German clubs)
    #   2. career_history (TM career table for coaches)

    transitions = 0

    # Source 1: squad player → current staff member
    rows = conn.execute("""
        SELECT sq.person_tm_id, p.name,
               MAX(sq.season) as last_player_season,
               se.section, se.role, se.club_tm_id, c.name as club_name
        FROM squad_entries sq
        JOIN staff_entries se ON se.person_tm_id = sq.person_tm_id
        JOIN persons p ON p.tm_id = sq.person_tm_id
        LEFT JOIN clubs c ON c.tm_id = se.club_tm_id
        GROUP BY sq.person_tm_id
    """).fetchall()

    seen = set()
    for pid, name, last_season, section, role, club_id, club_name in rows:
        # Skip if still an active player in the current season
        still_active = conn.execute(
            "SELECT 1 FROM squad_entries WHERE person_tm_id = ? AND season >= 2025", (pid,)
        ).fetchone()
        if still_active:
            continue
        to_role = role or "other_staff"
        # Map section to more specific role
        if section and "Trainer" in section:
            to_role = "coaching_staff"
        elif section and "Scout" in section:
            to_role = "scouting"
        elif section and ("Vorstand" in section or "Management" in section):
            to_role = "management"

        conn.execute("""
            INSERT INTO career_transitions
            (person_tm_id, from_role, to_role, transition_season, club_tm_id, club_name)
            VALUES (?, 'player', ?, ?, ?, ?)
        """, (pid, to_role, last_season + 1, club_id, club_name))
        transitions += 1
        seen.add(pid)

    # Source 2: squad player → career_history as coach (not already found)
    rows = conn.execute("""
        SELECT sq.person_tm_id, p.name,
               MAX(sq.season) as last_player_season,
               MIN(ch.season_from) as first_coach_season,
               ch.role_category, ch.club_tm_id, ch.club_name
        FROM squad_entries sq
        JOIN career_history ch ON ch.person_tm_id = sq.person_tm_id
            AND ch.role_category IN ('head_coach', 'coaching_staff', 'sporting_director', 'scouting', 'academy')
        JOIN persons p ON p.tm_id = sq.person_tm_id
        GROUP BY sq.person_tm_id
        HAVING first_coach_season >= last_player_season
    """).fetchall()

    for pid, name, last_season, first_coach, role_cat, club_id, club_name in rows:
        if pid in seen:
            continue
        conn.execute("""
            INSERT INTO career_transitions
            (person_tm_id, from_role, to_role, transition_season, club_tm_id, club_name)
            VALUES (?, 'player', ?, ?, ?, ?)
        """, (pid, role_cat, first_coach, club_id, club_name))
        transitions += 1

    conn.commit()
    print(f"  career_transitions: {transitions} rows")


# ── Referential integrity fix ─────────────────────────────────────────

def fix_referential_integrity(conn):
    """
    Ensure all FK references are valid:
    1. Insert stub clubs for any club_tm_id referenced but not in clubs table
    2. Insert stub persons for any person_tm_id in squad_entries but not in persons
    """
    # 1. Missing clubs — from career_history, persons.current_club, squad_entries
    missing_clubs = conn.execute("""
        SELECT DISTINCT club_tm_id, club_name FROM career_history
        WHERE club_tm_id IS NOT NULL AND club_tm_id NOT IN (SELECT tm_id FROM clubs)
        UNION
        SELECT DISTINCT current_club_tm_id, current_club_name FROM persons
        WHERE current_club_tm_id IS NOT NULL AND current_club_tm_id NOT IN (SELECT tm_id FROM clubs)
        UNION
        SELECT DISTINCT club_tm_id, NULL FROM squad_entries
        WHERE club_tm_id NOT IN (SELECT tm_id FROM clubs)
    """).fetchall()

    clubs_added = 0
    for club_id, club_name in missing_clubs:
        conn.execute(
            "INSERT OR IGNORE INTO clubs (tm_id, name, country) VALUES (?, ?, 'Ausland/Sonstige')",
            (club_id, normalize_club(club_name or f"Club {club_id}"))
        )
        clubs_added += 1

    # 2. Missing persons — from squad_entries (players with no TM profile)
    orphan_players = conn.execute("""
        SELECT DISTINCT sq.person_tm_id, sq.position
        FROM squad_entries sq
        WHERE sq.person_tm_id NOT IN (SELECT tm_id FROM persons)
    """).fetchall()

    # Build lookup: pid → name from squad JSON files (they have the real names)
    squad_names = {}
    for squad_file in sorted(SQUADS_DIR.glob("*.json")):
        try:
            with open(squad_file, "r", encoding="utf-8") as fh:
                sq = json.load(fh)
            for player in sq.get("players", []):
                pid = player.get("tm_id")
                if pid and pid not in squad_names:
                    squad_names[pid] = player.get("name", "")
        except (json.JSONDecodeError, OSError):
            pass

    persons_added = 0
    for pid, position in orphan_players:
        name = squad_names.get(pid, f"Spieler #{pid}")
        conn.execute("""
            INSERT OR IGNORE INTO persons (tm_id, name, type, position, profile_scraped)
            VALUES (?, ?, 'spieler', ?, 0)
        """, (pid, name, position))
        persons_added += 1

    conn.commit()
    print(f"  Stub clubs added: {clubs_added}")
    print(f"  Stub persons added: {persons_added}")

    # Verify: zero FK violations remaining
    fk_checks = [
        ("career_history → clubs",
         "SELECT COUNT(*) FROM career_history WHERE club_tm_id IS NOT NULL AND club_tm_id NOT IN (SELECT tm_id FROM clubs)"),
        ("persons → clubs",
         "SELECT COUNT(*) FROM persons WHERE current_club_tm_id IS NOT NULL AND current_club_tm_id NOT IN (SELECT tm_id FROM clubs)"),
        ("squad_entries → persons",
         "SELECT COUNT(*) FROM squad_entries WHERE person_tm_id NOT IN (SELECT tm_id FROM persons)"),
        ("staff_entries → persons",
         "SELECT COUNT(*) FROM staff_entries WHERE person_tm_id NOT IN (SELECT tm_id FROM persons)"),
        ("staff_entries → clubs",
         "SELECT COUNT(*) FROM staff_entries WHERE club_tm_id NOT IN (SELECT tm_id FROM clubs)"),
    ]
    all_clean = True
    for label, sql in fk_checks:
        violations = conn.execute(sql).fetchone()[0]
        status = "✅" if violations == 0 else "❌"
        if violations > 0:
            all_clean = False
        print(f"  {status} FK {label}: {violations} violations")

    if all_clean:
        print("  ✅ All foreign keys validated")


# ── Main ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Build SQLite database")
    parser.add_argument("--output", type=str, default=str(DEFAULT_OUTPUT))
    parser.add_argument("--skip-squads", action="store_true", help="Skip squad_entries (faster)")
    args = parser.parse_args()

    db_path = Path(args.output)
    if db_path.exists():
        db_path.unlink()
        print(f"  Removed existing {db_path}")

    print(f"\n{'='*60}")
    print(f"  Building SQLite: {db_path}")
    print(f"{'='*60}\n")

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")

    # Create schema
    conn.executescript(SCHEMA)
    print("  Schema created\n")

    t0 = time.time()

    # 1. Clubs
    print("[1/7] Importing clubs...")
    import_clubs(conn)

    # 2. Persons + Career History
    print("\n[2/7] Importing persons + career history...")
    import_persons(conn)

    # 3. Squads
    if args.skip_squads:
        print("\n[3/7] Skipping squad_entries (--skip-squads)")
    else:
        print("\n[3/7] Importing squad entries...")
        import_squads(conn)

    # 4. Staff
    print("\n[4/7] Importing staff entries...")
    import_staff(conn)

    # 5. Transitions
    print("\n[5/7] Detecting career transitions...")
    detect_transitions(conn)

    # 6. Fix referential integrity
    print("\n[6/7] Fixing referential integrity...")
    fix_referential_integrity(conn)

    # 7. Vacuum
    print("\n[7/7] Optimizing...")
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.execute("VACUUM")

    # Referential-integrity GATE (2026-06-20): FKs are declared but SQLite does
    # not enforce them by default, so prior "0 FK violations" claims were a
    # one-time manual check, not a guarantee. Verify here and report loudly so
    # doc claims can't drift from reality. --strict makes it a hard build failure.
    violations = list(conn.execute("PRAGMA foreign_key_check"))
    conn.close()
    if violations:
        from collections import Counter
        by_tbl = Counter(v[0] for v in violations)
        print(f"\n  ⚠ FK INTEGRITY: {len(violations)} violation(s) — "
              + ", ".join(f"{t}:{n}" for t, n in by_tbl.most_common()))
        if "--strict" in sys.argv:
            print("  ✗ --strict set → failing build on FK violations")
            sys.exit(1)
    else:
        print("\n  ✓ FK integrity: 0 violations")

    elapsed = time.time() - t0
    size_mb = db_path.stat().st_size / 1024 / 1024

    print(f"\n{'='*60}")
    print(f"  Done in {elapsed:.1f}s")
    print(f"  Output: {db_path} ({size_mb:.1f} MB)  FK-violations: {len(violations)}")
    print(f"{'='*60}")

    # Quick verification
    conn = sqlite3.connect(str(db_path))
    for table in ["clubs", "club_seasons", "persons", "career_history",
                   "squad_entries", "staff_entries", "career_transitions"]:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table:25s} {count:>8,} rows")

    print()
    # Show some transitions
    rows = conn.execute("SELECT * FROM v_transitions LIMIT 5").fetchall()
    if rows:
        print("  Sample transitions:")
        for r in rows:
            print(f"    {r[0]:25s} {r[1]} → {r[2]} ({r[3]}) @ {r[4]}")

    # Show BL coaches
    rows = conn.execute("SELECT * FROM v_bl_coaches ORDER BY league, club_name").fetchall()
    print(f"\n  BL coaches: {len(rows)}")
    for r in rows[:5]:
        print(f"    {r[1]:25s} {r[7]:25s} {r[8]}")

    conn.close()


if __name__ == "__main__":
    main()
