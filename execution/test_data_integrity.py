#!/usr/bin/env python3
"""
Data Integrity Test Suite — projectFIVE

Automated validation of SQLite database, JSON data, and network outputs.
Run after any data change, scrape, or rebuild.

Usage:
    python execution/test_data_integrity.py                # Full suite
    python execution/test_data_integrity.py --quick        # DB-only (5s)
    python execution/test_data_integrity.py --verbose      # Show all details
"""

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

BASE = Path(__file__).parent.parent
DATA = BASE / "data"
DB_PATH = DATA / "coaches.db"

passed = 0
failed = 0
warnings = 0


def ok(msg):
    global passed
    passed += 1
    print(f"  \033[32m✓\033[0m {msg}")

def fail(msg):
    global failed
    failed += 1
    print(f"  \033[31m✗\033[0m {msg}")

def warn(msg):
    global warnings
    warnings += 1
    print(f"  \033[33m!\033[0m {msg}")

def check(condition, pass_msg, fail_msg):
    if condition:
        ok(pass_msg)
    else:
        fail(fail_msg)


# ═════════════════════════════════════════════════════════════════════
# SECTION 1: DATABASE EXISTS + SCHEMA
# ═════════════════════════════════════════════════════════════════════

def test_db_exists():
    print("\n[1] Database existence + schema")
    check(DB_PATH.exists(), f"Database exists ({DB_PATH})", "Database missing!")
    if not DB_PATH.exists():
        return False

    conn = sqlite3.connect(str(DB_PATH))
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()]

    expected = ["career_history", "career_transitions", "clubs",
                "club_seasons", "persons", "squad_entries", "staff_entries"]
    for t in expected:
        check(t in tables, f"Table '{t}' exists", f"Table '{t}' MISSING")

    # Views
    views = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='view' ORDER BY name"
    ).fetchall()]
    for v in ["v_bl_coaches", "v_coach_careers", "v_transitions"]:
        check(v in views, f"View '{v}' exists", f"View '{v}' MISSING")

    conn.close()
    return True


# ═════════════════════════════════════════════════════════════════════
# SECTION 2: ROW COUNTS + BOUNDS
# ═════════════════════════════════════════════════════════════════════

def test_row_counts():
    print("\n[2] Row counts + bounds")
    conn = sqlite3.connect(str(DB_PATH))

    counts = {}
    for table in ["clubs", "club_seasons", "persons", "career_history",
                   "squad_entries", "staff_entries", "career_transitions"]:
        counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    # Minimum expected counts (should never drop below these)
    minimums = {
        "clubs": 119,           # BL registry alone
        "persons": 14_000,      # ~14,720 scraped + stubs
        "career_history": 10_000,
        "squad_entries": 30_000,
        "staff_entries": 2_500,
        "career_transitions": 40,
    }

    for table, minimum in minimums.items():
        actual = counts[table]
        check(actual >= minimum,
              f"{table}: {actual:,} rows (>= {minimum:,})",
              f"{table}: {actual:,} rows — BELOW minimum {minimum:,}!")

    # Type distribution
    types = dict(conn.execute(
        "SELECT type, COUNT(*) FROM persons GROUP BY type"
    ).fetchall())
    check(types.get("trainer", 0) >= 2700,
          f"Trainers: {types.get('trainer', 0):,}",
          f"Trainers: {types.get('trainer', 0):,} — too few!")
    check(types.get("spieler", 0) >= 11000,
          f"Players: {types.get('spieler', 0):,}",
          f"Players: {types.get('spieler', 0):,} — too few!")

    conn.close()


# ═════════════════════════════════════════════════════════════════════
# SECTION 3: REFERENTIAL INTEGRITY
# ═════════════════════════════════════════════════════════════════════

def test_referential_integrity():
    print("\n[3] Referential integrity (FK checks)")
    conn = sqlite3.connect(str(DB_PATH))

    # PRAGMA check
    fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    check(len(fk_violations) == 0,
          "PRAGMA foreign_key_check: 0 violations",
          f"PRAGMA foreign_key_check: {len(fk_violations)} violations!")

    # Manual FK checks
    fk_tests = [
        ("career_history.person → persons",
         "SELECT COUNT(*) FROM career_history WHERE person_tm_id NOT IN (SELECT tm_id FROM persons)"),
        ("career_history.club → clubs",
         "SELECT COUNT(*) FROM career_history WHERE club_tm_id IS NOT NULL AND club_tm_id NOT IN (SELECT tm_id FROM clubs)"),
        ("squad_entries.person → persons",
         "SELECT COUNT(*) FROM squad_entries WHERE person_tm_id NOT IN (SELECT tm_id FROM persons)"),
        ("squad_entries.club → clubs",
         "SELECT COUNT(*) FROM squad_entries WHERE club_tm_id NOT IN (SELECT tm_id FROM clubs)"),
        ("staff_entries.person → persons",
         "SELECT COUNT(*) FROM staff_entries WHERE person_tm_id NOT IN (SELECT tm_id FROM persons)"),
        ("staff_entries.club → clubs",
         "SELECT COUNT(*) FROM staff_entries WHERE club_tm_id NOT IN (SELECT tm_id FROM clubs)"),
        ("persons.current_club → clubs",
         "SELECT COUNT(*) FROM persons WHERE current_club_tm_id IS NOT NULL AND current_club_tm_id NOT IN (SELECT tm_id FROM clubs)"),
    ]

    for label, sql in fk_tests:
        violations = conn.execute(sql).fetchone()[0]
        check(violations == 0, f"FK {label}: 0", f"FK {label}: {violations} violations!")

    conn.close()


# ═════════════════════════════════════════════════════════════════════
# SECTION 4: DATA QUALITY
# ═════════════════════════════════════════════════════════════════════

def test_data_quality():
    print("\n[4] Data quality")
    conn = sqlite3.connect(str(DB_PATH))

    # No NULL or empty names
    bad_names = conn.execute(
        "SELECT COUNT(*) FROM persons WHERE name IS NULL OR name = '' OR name LIKE 'Spieler #%'"
    ).fetchone()[0]
    check(bad_names == 0, "No NULL/empty/placeholder names",
          f"{bad_names} persons with bad names!")

    # No duplicate tm_ids
    dupes = conn.execute(
        "SELECT COUNT(*) FROM (SELECT tm_id FROM persons GROUP BY tm_id HAVING COUNT(*) > 1)"
    ).fetchone()[0]
    check(dupes == 0, "No duplicate person tm_ids", f"{dupes} duplicate tm_ids!")

    # Club name normalization — check known problem cases
    known_shorts = ["Bor. Dortmund", "1.FC K'lautern", "TSG 1899 Hoffenheim",
                    "SC Paderborn 07", "SV 07 Elversberg", "Bor. M'gladbach"]
    for short in known_shorts:
        cnt = conn.execute(
            "SELECT COUNT(*) FROM career_history WHERE club_name = ?", (short,)
        ).fetchone()[0]
        check(cnt == 0, f'No "{short}" in career_history',
              f'"{short}" found {cnt} times — normalization broken!')

    # Nationality resolution — spot check
    fischer = conn.execute(
        "SELECT nationality FROM persons WHERE name = 'Urs Fischer'"
    ).fetchone()
    if fischer:
        check(fischer[0] == "Schweiz",
              f"Fischer nationality: {fischer[0]}",
              f"Fischer nationality: {fischer[0]} — expected Schweiz!")

    kovac = conn.execute(
        "SELECT nationality FROM persons WHERE name = 'Niko Kovac'"
    ).fetchone()
    if kovac:
        check(kovac[0] == "Kroatien",
              f"Kovac nationality: {kovac[0]}",
              f"Kovac nationality: {kovac[0]} — expected Kroatien!")

    # Career history has seasons parsed
    no_season = conn.execute(
        "SELECT COUNT(*) FROM career_history WHERE season_from IS NULL"
    ).fetchone()[0]
    total_career = conn.execute("SELECT COUNT(*) FROM career_history").fetchone()[0]
    pct = (total_career - no_season) / total_career * 100 if total_career else 0
    check(pct >= 90, f"Career season_from parsed: {pct:.1f}%",
          f"Career season_from parsed: {pct:.1f}% — too many NULL!")

    conn.close()


# ═════════════════════════════════════════════════════════════════════
# SECTION 5: VIEWS CORRECTNESS
# ═════════════════════════════════════════════════════════════════════

def test_views():
    print("\n[5] Views correctness")
    conn = sqlite3.connect(str(DB_PATH))

    # BL coaches view
    bl = conn.execute("SELECT * FROM v_bl_coaches").fetchall()
    bl1 = [r for r in bl if r[-1] == "BL1"]
    bl2 = [r for r in bl if r[-1] == "BL2"]
    check(len(bl1) == 18, f"v_bl_coaches BL1: {len(bl1)}", f"v_bl_coaches BL1: {len(bl1)} — expected 18!")
    check(len(bl2) == 18, f"v_bl_coaches BL2: {len(bl2)}", f"v_bl_coaches BL2: {len(bl2)} — expected 18!")

    # Spot-check known assignments
    kompany = conn.execute(
        "SELECT club_name FROM v_bl_coaches WHERE name = 'Vincent Kompany'"
    ).fetchone()
    if kompany:
        check(kompany[0] == "FC Bayern München",
              f"Kompany → {kompany[0]}", f"Kompany → {kompany[0]} — expected Bayern!")
    else:
        fail("Kompany not in v_bl_coaches!")

    # Transitions view
    trans = conn.execute("SELECT COUNT(*) FROM v_transitions").fetchone()[0]
    check(trans >= 40, f"v_transitions: {trans} rows", f"v_transitions: {trans} — too few!")

    # No false positive transitions (active 25/26 players)
    false_pos = conn.execute("""
        SELECT COUNT(*) FROM career_transitions ct
        WHERE ct.person_tm_id IN (SELECT person_tm_id FROM squad_entries WHERE season >= 2025)
    """).fetchone()[0]
    check(false_pos == 0, f"No active-player transitions: {false_pos}",
          f"Active-player transitions: {false_pos} — false positives!")

    conn.close()


# ═════════════════════════════════════════════════════════════════════
# SECTION 6: FILESYSTEM ↔ DB CONSISTENCY
# ═════════════════════════════════════════════════════════════════════

def test_filesystem_consistency():
    print("\n[6] Filesystem ↔ DB consistency")
    conn = sqlite3.connect(str(DB_PATH))

    # Profile files = persons with profile_scraped=1
    profile_files = len(list((DATA / "person_profiles").glob("*.json")))
    db_scraped = conn.execute("SELECT COUNT(*) FROM persons WHERE profile_scraped = 1").fetchone()[0]
    check(profile_files == db_scraped,
          f"Profile files ({profile_files:,}) = DB scraped ({db_scraped:,})",
          f"Profile files ({profile_files:,}) != DB scraped ({db_scraped:,})")

    # Staff files count
    staff_files = len(list((DATA / "staff").glob("*.json")))
    check(staff_files >= 119, f"Staff files: {staff_files}", f"Staff files: {staff_files} — expected >= 119")

    # Network files
    network_files = len(list((DATA / "networks").glob("*.json")))
    check(network_files >= 36, f"Network files: {network_files}", f"Network files: {network_files} — expected >= 36")

    # Dashboard files
    dashboard_dir = BASE / "output" / "dashboards"
    if dashboard_dir.exists():
        dashboard_files = len(list(dashboard_dir.glob("*.html")))
        check(dashboard_files >= 36, f"Dashboard files: {dashboard_files}",
              f"Dashboard files: {dashboard_files} — expected >= 36")

    conn.close()


# ═════════════════════════════════════════════════════════════════════
# SECTION 7: NETWORK DATA QUALITY
# ═════════════════════════════════════════════════════════════════════

def test_network_quality():
    print("\n[7] Network data quality (sample)")
    networks_dir = DATA / "networks"
    if not networks_dir.exists():
        warn("Networks directory missing — skipping")
        return

    issues = 0
    for f in sorted(networks_dir.glob("*.json"))[:10]:  # Sample 10
        with open(f) as fh:
            net = json.load(fh)

        center = net.get("center", "?")
        contacts = net.get("contacts", [])
        stations = net.get("stations", [])

        # Must have center
        if not center or center == "?":
            fail(f"{f.stem}: missing center")
            issues += 1
            continue

        # Must have contacts
        if len(contacts) < 10:
            warn(f"{center}: only {len(contacts)} contacts")

        # No 'Unbekannt' stations
        unknowns = [c for c in contacts if "Unbekannt" in (c.get("stations") or [])]
        if unknowns:
            fail(f"{center}: {len(unknowns)} contacts with 'Unbekannt' station")
            issues += 1

        # All contacts must have name + category
        bad = [c for c in contacts if not c.get("name") or not c.get("category")]
        if bad:
            fail(f"{center}: {len(bad)} contacts missing name/category")
            issues += 1

    if issues == 0:
        ok("All sampled networks pass quality checks")


# ═════════════════════════════════════════════════════════════════════
# SECTION 8: TM PARSER REGRESSION TESTS
# ═════════════════════════════════════════════════════════════════════

def test_parser_regressions():
    print("\n[8] Parser regression tests")
    sys.path.insert(0, str(Path(__file__).parent))
    from build_coach_network import (
        parse_season_from_date, get_season_range, format_season,
        classify_role, normalize_club,
    )

    # Season parsing
    check(parse_season_from_date("23/24 (19.03.2024)") == 2023,
          "parse '23/24 (19.03.2024)' → 2023",
          "parse '23/24 (19.03.2024)' failed!")
    check(parse_season_from_date("98/99 (01.07.1998)") == 1998,
          "parse '98/99' → 1998",
          "parse '98/99' failed!")
    check(parse_season_from_date("-") is None,
          "parse '-' → None",
          "parse '-' should be None!")
    check(parse_season_from_date("") is None,
          "parse '' → None",
          "parse '' should be None!")

    # Season ranges
    check(get_season_range("23/24 (01.07.2023)", "24/25 (30.06.2025)") == [2023, 2024],
          "range 23/24–24/25 → [2023, 2024]",
          "season range failed!")
    check(get_season_range("24/25 (01.07.2024)", "-") == [2024, 2025],
          "range 24/25–current → includes 2025",
          "open-ended range failed!")

    # Role classification
    check(classify_role("Trainer") == "head_coach", "classify 'Trainer' → head_coach", "role classification failed!")
    check(classify_role("Co-Trainer") == "coaching_staff", "classify 'Co-Trainer' → coaching_staff", "!")
    check(classify_role("Sportdirektor") == "sporting_director", "classify 'Sportdirektor' → sporting_director", "!")
    check(classify_role("Torwarttrainer") == "coaching_staff", "classify 'Torwarttrainer' → coaching_staff", "!")

    # Club normalization
    check(normalize_club("Bor. Dortmund") == "Borussia Dortmund", "normalize Bor. Dortmund", "!")
    check(normalize_club("1.FC K'lautern") == "1.FC Kaiserslautern", "normalize K'lautern", "!")
    check(normalize_club("FC St. Pauli") == "FC St. Pauli", "normalize St. Pauli (no change)", "!")

    # Format season
    check(format_season(2023) == "23/24", "format 2023 → 23/24", "!")
    check(format_season(2000) == "00/01", "format 2000 → 00/01", "!")


# ═════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Data integrity test suite")
    parser.add_argument("--quick", action="store_true", help="DB-only checks (fast)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print("  Data Integrity Test Suite")
    print(f"{'='*60}")

    t0 = time.time()

    if not test_db_exists():
        print("\n  Database missing — cannot continue.")
        sys.exit(1)

    test_row_counts()
    test_referential_integrity()
    test_data_quality()
    test_views()

    if not args.quick:
        test_filesystem_consistency()
        test_network_quality()
        test_parser_regressions()

    elapsed = time.time() - t0

    print(f"\n{'='*60}")
    print(f"  Results: \033[32m{passed} passed\033[0m, \033[31m{failed} failed\033[0m, \033[33m{warnings} warnings\033[0m")
    print(f"  Time: {elapsed:.1f}s")
    print(f"{'='*60}\n")

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
