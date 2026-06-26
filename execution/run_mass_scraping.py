#!/usr/bin/env python3
"""
Master script to run all three scraping phases sequentially.

Phase 1: Bundesliga Staff (~1,800 profiles, 3-4 hours)
Phase 2: 2. Bundesliga Staff (~400 profiles, 1-2 hours)
Phase 3: Companions Bulk (~15,000 connections, 4-6 hours)

Total: ~17,000 data points over 8-12 hours
"""

import subprocess
import sys
import time
import os
from datetime import datetime

# Ensure we're in the right directory
os.chdir("/Users/cmk/Documents/Football Coaches DB")

def log(message):
    """Print timestamped log message"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")
    sys.stdout.flush()

def run_phase(phase_num, phase_name, script_name, log_file):
    """Run a scraping phase and monitor progress"""
    log(f"\n{'='*80}")
    log(f"PHASE {phase_num}: {phase_name}")
    log(f"{'='*80}")
    log(f"Script: {script_name}")
    log(f"Log file: {log_file}")

    start_time = time.time()

    try:
        # Run the script
        with open(log_file, 'w') as f:
            process = subprocess.Popen(
                [sys.executable, script_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )

            # Stream output to both console and log file
            for line in process.stdout:
                print(line, end='')
                f.write(line)
                f.flush()

            process.wait()

        elapsed = time.time() - start_time
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)

        if process.returncode == 0:
            log(f"✅ Phase {phase_num} completed successfully in {hours}h {minutes}m")
            return True
        else:
            log(f"❌ Phase {phase_num} failed with exit code {process.returncode}")
            return False

    except Exception as e:
        log(f"❌ Phase {phase_num} error: {str(e)}")
        return False

def show_progress():
    """Show current scraping progress"""
    log("\n📊 Checking current progress...")
    try:
        result = subprocess.run(
            [sys.executable, "execution/monitor_scraping_progress.py"],
            capture_output=True,
            text=True
        )
        print(result.stdout)
    except Exception as e:
        log(f"Could not check progress: {e}")

def main():
    """Run all three scraping phases"""
    overall_start = time.time()

    log("🚀 STARTING MASS SCRAPING - 3 PHASES")
    log("Expected duration: 8-12 hours")
    log("Expected results: ~17,000 data points")
    log(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Phase 1: Bundesliga Staff
    phase1_success = run_phase(
        phase_num=1,
        phase_name="Bundesliga Staff Scraping (~1,800 profiles)",
        script_name="execution/scrape_club_staff_pages.py",
        log_file="/tmp/bundesliga_scrape.log"
    )

    if not phase1_success:
        log("\n⚠️  Phase 1 failed. Check /tmp/bundesliga_scrape.log for details.")
        log("Continue to Phase 2 anyway? Press Ctrl+C to abort, or wait 10 seconds...")
        try:
            time.sleep(10)
        except KeyboardInterrupt:
            log("\n❌ Scraping aborted by user")
            return 1

    show_progress()

    # Phase 2: 2. Bundesliga Staff
    phase2_success = run_phase(
        phase_num=2,
        phase_name="2. Bundesliga Staff Scraping (~400 profiles)",
        script_name="execution/scrape_2bundesliga_staff.py",
        log_file="/tmp/2bundesliga_scrape.log"
    )

    if not phase2_success:
        log("\n⚠️  Phase 2 failed. Check /tmp/2bundesliga_scrape.log for details.")
        log("Continue to Phase 3 anyway? Press Ctrl+C to abort, or wait 10 seconds...")
        try:
            time.sleep(10)
        except KeyboardInterrupt:
            log("\n❌ Scraping aborted by user")
            return 1

    show_progress()

    # Phase 3: Companions Bulk
    phase3_success = run_phase(
        phase_num=3,
        phase_name="Companions Bulk Scraping (~15,000 connections)",
        script_name="execution/scrape_companions_bulk.py",
        log_file="/tmp/companions_scrape.log"
    )

    # Final summary
    log("\n" + "="*80)
    log("🎉 MASS SCRAPING COMPLETE!")
    log("="*80)

    overall_elapsed = time.time() - overall_start
    hours = int(overall_elapsed // 3600)
    minutes = int((overall_elapsed % 3600) // 60)

    log(f"Total time: {hours}h {minutes}m")
    log(f"Phase 1 (Bundesliga): {'✅ Success' if phase1_success else '❌ Failed'}")
    log(f"Phase 2 (2. Bundesliga): {'✅ Success' if phase2_success else '❌ Failed'}")
    log(f"Phase 3 (Companions): {'✅ Success' if phase3_success else '❌ Failed'}")

    log("\n📊 Final Results:")
    show_progress()

    log("\n📋 Log Files:")
    log("  - /tmp/bundesliga_scrape.log")
    log("  - /tmp/2bundesliga_scrape.log")
    log("  - /tmp/companions_scrape.log")

    log("\n📂 Summary Files:")
    log("  - data/bundesliga_staff_scrape_summary.json")
    log("  - data/2bundesliga_staff_scrape_summary.json")
    log("  - data/companions_bulk_scrape_summary.json")

    log("\n🕸️  READY FOR SPIDER WEB BUILDING!")

    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("\n\n❌ Scraping interrupted by user (Ctrl+C)")
        log("Progress has been saved. You can resume later.")
        sys.exit(1)
