#!/usr/bin/env python3
"""
Weekly Pre-Loader for Football Coaches Database
Runs every Sunday at 3 AM to pre-cache all data for Bundesliga coaches.

This script:
1. Fetches all current Bundesliga coaches
2. Scrapes full profiles, teammates, players for each
3. Enriches ALL teammates with current roles (the slow part)
4. Caches everything so dashboard loads instantly

Usage:
    python preload_coach_data.py           # Run once now
    python preload_coach_data.py --daemon  # Run as daemon (waits for Sunday 3 AM)

Schedule via cron (every Sunday at 3 AM):
    0 3 * * 0 cd /Users/cmk/Documents/Football\ Coaches\ DB && python3 execution/preload_coach_data.py >> tmp/preload.log 2>&1
"""

import json
import time
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# Add parent to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent))

from scrape_league_coaches import scrape_bundesliga_coaches
from scrape_transfermarkt import scrape_coach
from scrape_teammates import scrape_teammates, enrich_teammates_with_current_roles
from scrape_players_used import scrape_players_used
from scrape_players_detail import scrape_players_for_coach_url
from scrape_companions import get_companions_for_coach

import re

# Paths
BASE_DIR = Path(__file__).parent.parent
TMP_DIR = BASE_DIR / "tmp"
CACHE_DIR = TMP_DIR / "cache"
PRELOAD_DIR = TMP_DIR / "preloaded"
LOG_FILE = TMP_DIR / "preload.log"

def ensure_dirs():
    """Create necessary directories."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    PRELOAD_DIR.mkdir(parents=True, exist_ok=True)

def log(message: str):
    """Log message with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {message}"
    print(log_line)

    # Also append to log file
    with open(LOG_FILE, "a") as f:
        f.write(log_line + "\n")

def save_preloaded(coach_name: str, data: dict):
    """Save preloaded data for a coach."""
    # Sanitize filename
    safe_name = re.sub(r'[^\w\-]', '_', coach_name.lower())
    filepath = PRELOAD_DIR / f"{safe_name}.json"

    data["_preloaded_at"] = datetime.now().isoformat()
    data["_coach_name"] = coach_name

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    log(f"  Saved preloaded data: {filepath.name}")

def load_preloaded(coach_name: str) -> dict:
    """Load preloaded data for a coach if available and fresh (within 7 days)."""
    safe_name = re.sub(r'[^\w\-]', '_', coach_name.lower())
    filepath = PRELOAD_DIR / f"{safe_name}.json"

    if not filepath.exists():
        return None

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Check if data is fresh (less than 7 days old)
    preloaded_at = datetime.fromisoformat(data.get("_preloaded_at", "2000-01-01"))
    age_hours = (datetime.now() - preloaded_at).total_seconds() / 3600
    age_days = age_hours / 24

    if age_days > 7:
        log(f"  Preloaded data too old ({age_days:.1f} days), will refresh")
        return None

    return data

def preload_single_coach(coach_name: str, force: bool = False) -> dict:
    """
    Preload all data for a single coach.
    Returns the full data dict.
    """
    log(f"\n{'='*60}")
    log(f"Preloading: {coach_name}")
    log(f"{'='*60}")

    # Check for existing fresh data
    if not force:
        existing = load_preloaded(coach_name)
        if existing:
            log(f"  Using existing preloaded data (age: fresh)")
            return existing

    result = {
        "coach_name": coach_name,
        "profile": None,
        "teammates": None,
        "players_used": None,
        "players_detail": None,
        "companions": None,
        "teammates_enriched": False,
    }

    try:
        # 1. Scrape profile
        log(f"  [1/7] Scraping profile...")
        profile = scrape_coach(name=coach_name)
        if not profile:
            log(f"  ERROR: Could not find coach profile")
            return result

        result["profile"] = profile
        coach_url = profile.get("url", "")
        coach_id = profile.get("coach_id")

        # 2. Scrape teammates
        log(f"  [2/7] Scraping teammates...")
        teammates = scrape_teammates(coach_profile_url=coach_url) if coach_url else None
        result["teammates"] = teammates

        # 3. Scrape players used
        log(f"  [3/7] Scraping players used...")
        players_used = scrape_players_used(coach_profile_url=coach_url) if coach_url else None
        result["players_used"] = players_used

        # 4. Scrape players detail
        log(f"  [4/7] Scraping players detail...")
        players_detail = scrape_players_for_coach_url(coach_url, top_n=None) if coach_url else None
        result["players_detail"] = players_detail

        # 5. Enrich ALL teammates with current roles (THE SLOW PART)
        if teammates and teammates.get("all_teammates"):
            all_tm = teammates["all_teammates"]
            total = len(all_tm)
            log(f"  [5/7] Enriching {total} teammates with current roles...")
            log(f"        (This will take ~{total * 3 / 60:.0f} minutes)")

            start_time = time.time()

            def progress(current, total, name):
                if current % 25 == 0 or current == total:
                    elapsed = time.time() - start_time
                    rate = current / elapsed if elapsed > 0 else 0
                    remaining = (total - current) / rate if rate > 0 else 0
                    log(f"        Progress: {current}/{total} ({current/total*100:.0f}%) - ETA: {remaining/60:.0f}min")

            enriched = enrich_teammates_with_current_roles(
                all_tm,
                max_to_enrich=None,  # ALL!
                progress_callback=progress
            )

            result["teammates"]["all_teammates"] = enriched
            result["teammates_enriched"] = True

            # Count results
            coaches_found = sum(1 for tm in enriched if tm.get("is_coach"))
            directors_found = sum(1 for tm in enriched if tm.get("is_director"))
            log(f"        Found: {coaches_found} coaches, {directors_found} directors")

        # 6. Scrape companions
        log(f"  [6/7] Scraping companions...")
        if players_used and players_used.get("stations") and coach_id:
            stations_for_companions = []
            for station in players_used["stations"]:
                club_url = station.get("club_url", "")
                club_id = None
                club_slug = ""

                id_match = re.search(r"/verein/(\d+)", club_url)
                if id_match:
                    club_id = int(id_match.group(1))

                slug_match = re.search(r"transfermarkt\.de/([^/]+)/", club_url)
                if slug_match:
                    club_slug = slug_match.group(1)

                if club_id:
                    stations_for_companions.append({
                        "club_id": club_id,
                        "club_slug": club_slug,
                        "club_name": station.get("club", "Unknown"),
                        "start_date": station.get("start_date"),
                        "end_date": station.get("end_date"),
                        "club_url": club_url,
                    })

            if stations_for_companions:
                companions = get_companions_for_coach(coach_id, coach_url, stations_for_companions)
                result["companions"] = companions

        # 7. Enrich decision makers
        log(f"  [7/7] Enriching decision makers...")
        if stations_for_companions:  # Use same stations list
            try:
                from enrich_decision_makers import get_all_decision_makers
                decision_makers = get_all_decision_makers(coach_name, stations_for_companions)
                result["decision_makers"] = decision_makers

                total = decision_makers.get("total", 0)
                hiring_managers = len(decision_makers.get("hiring_managers", []))
                sports_directors = len(decision_makers.get("sports_directors", []))
                executives = len(decision_makers.get("executives", []))

                log(f"        Total decision makers: {total}")
                log(f"        - Hiring Managers: {hiring_managers}")
                log(f"        - Sports Directors: {sports_directors}")
                log(f"        - Executives: {executives}")
            except Exception as e:
                log(f"        Warning: Could not enrich decision makers: {e}")
                result["decision_makers"] = None

        # Save preloaded data
        save_preloaded(coach_name, result)

        log(f"  ✅ Completed: {coach_name}")

    except Exception as e:
        log(f"  ERROR: {e}")
        import traceback
        log(traceback.format_exc())

    return result

def preload_all_bundesliga_coaches(force: bool = False):
    """
    Preload data for all current Bundesliga coaches.
    """
    log("\n" + "="*70)
    log("BUNDESLIGA COACHES PRE-LOADER")
    log(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("="*70)

    ensure_dirs()

    # Get current Bundesliga coaches
    log("\nFetching current Bundesliga coaches...")
    bundesliga_data = scrape_bundesliga_coaches()

    if not bundesliga_data or not bundesliga_data.get("clubs"):
        log("ERROR: Could not fetch Bundesliga coaches")
        return

    clubs = bundesliga_data["clubs"]
    coach_names = []

    for club_name, info in clubs.items():
        coach_name = info.get("coach_name")
        if coach_name:
            coach_names.append(coach_name)
            log(f"  - {club_name}: {coach_name}")

    log(f"\nTotal coaches to preload: {len(coach_names)}")

    # Estimate time
    # ~3 sec per teammate check, average ~200 teammates = 600 sec = 10 min per coach
    estimated_minutes = len(coach_names) * 10
    log(f"Estimated total time: {estimated_minutes} minutes ({estimated_minutes/60:.1f} hours)")

    # Preload each coach
    successful = 0
    failed = 0

    for i, coach_name in enumerate(coach_names, 1):
        log(f"\n[{i}/{len(coach_names)}] Processing {coach_name}...")

        try:
            result = preload_single_coach(coach_name, force=force)
            if result and result.get("profile"):
                successful += 1
            else:
                failed += 1
        except Exception as e:
            log(f"  FAILED: {e}")
            failed += 1

    # Summary
    log("\n" + "="*70)
    log("PRE-LOAD COMPLETE")
    log(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"Successful: {successful}/{len(coach_names)}")
    log(f"Failed: {failed}/{len(coach_names)}")
    log("="*70)

def wait_for_sunday_3am():
    """Wait until next Sunday at 3:00 AM."""
    now = datetime.now()

    # Find next Sunday
    days_until_sunday = (6 - now.weekday()) % 7  # 6 = Sunday
    if days_until_sunday == 0 and now.hour >= 3:
        # It's Sunday but past 3 AM, wait for next Sunday
        days_until_sunday = 7

    target = now.replace(hour=3, minute=0, second=0, microsecond=0)
    target += timedelta(days=days_until_sunday)

    wait_seconds = (target - now).total_seconds()
    log(f"Waiting until {target.strftime('%A %Y-%m-%d %H:%M')} ({wait_seconds/3600:.1f} hours / {wait_seconds/86400:.1f} days)")

    time.sleep(wait_seconds)

def run_daemon():
    """Run as daemon, executing preload every Sunday at 3 AM."""
    log("Starting pre-loader daemon...")
    log("Will run every Sunday at 3:00 AM")

    while True:
        wait_for_sunday_3am()
        log("\n🕐 Sunday 3:00 AM - Starting weekly preload...")
        preload_all_bundesliga_coaches(force=True)
        log("Weekly preload complete. Sleeping until next Sunday...")
        time.sleep(60)  # Wait a minute to avoid re-triggering

def main():
    parser = argparse.ArgumentParser(description="Pre-load coach data for faster dashboard access")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon (waits for 3 AM daily)")
    parser.add_argument("--force", action="store_true", help="Force refresh even if data exists")
    parser.add_argument("--coach", type=str, help="Preload single coach by name")

    args = parser.parse_args()

    ensure_dirs()

    if args.daemon:
        run_daemon()
    elif args.coach:
        preload_single_coach(args.coach, force=args.force)
    else:
        preload_all_bundesliga_coaches(force=args.force)

if __name__ == "__main__":
    main()
