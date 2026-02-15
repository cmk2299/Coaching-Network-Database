#!/usr/bin/env python3
"""
Import all preloaded coach profiles from JSON into SQLite database.

Reads 1,059 JSON profiles from tmp/preloaded/ and populates:
- coaches table (demographics, agent info, image)
- career_stations table (career history with parsed dates)
- coach_current_status table (current club/role)

Usage:
    python3 execution/import_profiles_to_db.py [--dry-run] [--verbose]
"""

import json
import sys
import time
from pathlib import Path
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "execution"))

from coach_db import CoachDB, parse_german_date, parse_career_period

# Paths
PRELOADED_DIR = PROJECT_ROOT / "tmp" / "preloaded"
DB_PATH = PROJECT_ROOT / "data" / "coaches.db"


def import_all_profiles(dry_run: bool = False, verbose: bool = False):
    """
    Import all JSON profiles from tmp/preloaded/ into SQLite.

    Args:
        dry_run: If True, only validate and count — don't write to DB
        verbose: If True, print details per coach
    """
    # Collect all JSON files
    json_files = sorted(PRELOADED_DIR.glob("*.json"))

    if not json_files:
        print(f"ERROR: No JSON files found in {PRELOADED_DIR}")
        return

    print(f"Found {len(json_files)} profile files in {PRELOADED_DIR}")

    if dry_run:
        print("DRY RUN — validating only, no database writes")
    else:
        # Delete existing DB and recreate fresh
        if DB_PATH.exists():
            DB_PATH.unlink()
            print(f"Deleted existing {DB_PATH}")

        db = CoachDB(str(DB_PATH))
        print(f"Created fresh database at {DB_PATH}")

    # Counters
    success = 0
    errors = 0
    total_stations = 0
    with_dob = 0
    with_birthplace = 0
    with_license = 0
    with_contract = 0
    with_nationality = 0

    start_time = time.time()

    for i, json_file in enumerate(json_files):
        try:
            profile = json.loads(json_file.read_text(encoding="utf-8"))

            # Extract tm_id from profile
            tm_id = profile.get("coach_id")
            if not tm_id:
                # Try extracting from URL
                url = profile.get("url", "")
                parts = url.rstrip("/").split("/")
                tm_id = parts[-1] if parts else None

            if not tm_id:
                if verbose:
                    print(f"  SKIP {json_file.name}: no coach_id or URL")
                errors += 1
                continue

            tm_id = int(tm_id)
            name = profile.get("name", "Unknown")

            # Count field completeness
            if parse_german_date(profile.get("dob")):
                with_dob += 1
            if profile.get("birthplace"):
                with_birthplace += 1
            if profile.get("license"):
                with_license += 1
            if profile.get("contract_until"):
                with_contract += 1
            if profile.get("nationality"):
                with_nationality += 1

            career_count = len(profile.get("career_history", []))
            total_stations += career_count

            if verbose:
                print(f"  [{i+1}/{len(json_files)}] {name} (TM:{tm_id}) — {career_count} stations")

            if not dry_run:
                # Save profile (coaches + career_stations)
                coach_id = db.save_coach_profile(tm_id, profile)

                # Save current status
                current_club = profile.get("current_club")
                current_role = profile.get("current_role")
                if current_club or current_role:
                    db.save_current_status(tm_id, current_club, current_role)

            success += 1

        except Exception as e:
            errors += 1
            print(f"  ERROR {json_file.name}: {e}")
            if verbose:
                import traceback
                traceback.print_exc()

        # Progress indicator every 100 coaches
        if (i + 1) % 100 == 0 and not verbose:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed
            print(f"  Progress: {i+1}/{len(json_files)} ({rate:.0f} coaches/sec)")

    elapsed = time.time() - start_time

    # Summary
    print(f"\n{'='*60}")
    print(f"IMPORT {'VALIDATION' if dry_run else 'COMPLETE'}")
    print(f"{'='*60}")
    print(f"Total files:        {len(json_files)}")
    print(f"Imported:           {success}")
    print(f"Errors:             {errors}")
    print(f"Career stations:    {total_stations}")
    print(f"Time:               {elapsed:.1f}s")
    print(f"")
    print(f"Field completeness:")
    print(f"  Nationality:      {with_nationality}/{success} ({100*with_nationality/max(success,1):.0f}%)")
    print(f"  DOB:              {with_dob}/{success} ({100*with_dob/max(success,1):.0f}%)")
    print(f"  Birthplace:       {with_birthplace}/{success} ({100*with_birthplace/max(success,1):.0f}%)")
    print(f"  License:          {with_license}/{success} ({100*with_license/max(success,1):.0f}%)")
    print(f"  Contract until:   {with_contract}/{success} ({100*with_contract/max(success,1):.0f}%)")

    if not dry_run and success > 0:
        print(f"\nDatabase: {DB_PATH} ({DB_PATH.stat().st_size / 1024:.0f} KB)")

        # Verify counts
        import sqlite3
        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM coaches")
        db_coaches = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM career_stations")
        db_stations = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM coach_current_status")
        db_status = c.fetchone()[0]
        conn.close()

        print(f"\nDatabase verification:")
        print(f"  coaches table:           {db_coaches} rows")
        print(f"  career_stations table:   {db_stations} rows")
        print(f"  coach_current_status:    {db_status} rows")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    verbose = "--verbose" in sys.argv

    import_all_profiles(dry_run=dry_run, verbose=verbose)
