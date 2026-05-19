#!/usr/bin/env python3
"""
Re-scrape all coach profiles from tmp/preloaded/ with fixed parser
"""

import json
import time
from pathlib import Path
from scrape_transfermarkt import scrape_coach
from preload_coach_data import save_preloaded

# Configuration
PRELOADED_DIR = Path(__file__).parent.parent / "tmp" / "preloaded"
CACHE_DIR = Path(__file__).parent.parent / "tmp" / "cache"
DELAY_BETWEEN_COACHES = 4  # 4 seconds to be safe

def main():
    print("=" * 70)
    print("RE-SCRAPING ALL COACH PROFILES WITH FIXED PARSER")
    print("=" * 70)

    # Get all existing profile JSONs
    profile_files = sorted(PRELOADED_DIR.glob("*.json"))
    total = len(profile_files)

    print(f"\n📊 Found {total} profiles to re-scrape")
    print(f"⏱️  Estimated time: {total * DELAY_BETWEEN_COACHES / 60:.1f} minutes")
    print(f"🗑️  Clearing cache first...\n")

    # Clear cache to force re-scraping
    cache_files = list(CACHE_DIR.glob("coach_*_profile.json"))
    for f in cache_files:
        f.unlink()
    print(f"   ✓ Deleted {len(cache_files)} cached profiles\n")

    # Track progress
    success_count = 0
    failed_count = 0
    with_career = 0
    failed_coaches = []

    start_time = time.time()

    for i, profile_file in enumerate(profile_files, 1):
        try:
            # Load existing profile to get URL
            data = json.loads(profile_file.read_text())
            url = data.get('url')
            name = data.get('name', profile_file.stem)

            if not url:
                print(f"[{i}/{total}] ⚠️  {name} - No URL found")
                failed_count += 1
                failed_coaches.append((name, "No URL"))
                continue

            # Progress indicator
            elapsed = time.time() - start_time
            rate = i / elapsed if elapsed > 0 else 0
            remaining = (total - i) / rate if rate > 0 else 0

            print(f"[{i}/{total}] {name}")
            print(f"   Rate: {rate:.2f}/min | ETA: {remaining/60:.1f}min")

            # Convert .com URLs to .de (demographics only available on .de)
            url_de = url.replace('transfermarkt.com', 'transfermarkt.de')

            # Re-scrape with fixed parser
            profile = scrape_coach(url=url_de)

            if profile:
                # Check if career history was populated
                career_count = len(profile.get('career_history', []))

                if career_count > 0:
                    with_career += 1
                    print(f"   ✅ Success! {career_count} career entries")
                else:
                    print(f"   ⚠️  Scraped but no career history")

                # Save updated profile
                save_preloaded(name, profile)
                success_count += 1
            else:
                print(f"   ❌ Scraping failed")
                failed_count += 1
                failed_coaches.append((name, "Scraping returned None"))

            # Rate limiting
            if i < total:
                time.sleep(DELAY_BETWEEN_COACHES)

        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user!")
            print(f"Progress saved: {success_count}/{total} completed")
            break
        except Exception as e:
            print(f"   ❌ Error: {e}")
            failed_count += 1
            failed_coaches.append((name, str(e)))
            continue

    # Final summary
    elapsed_total = time.time() - start_time

    print("\n" + "=" * 70)
    print("✅ RE-SCRAPING COMPLETE")
    print("=" * 70)
    print(f"Total processed: {success_count + failed_count}/{total}")
    print(f"Success: {success_count}")
    print(f"With career history: {with_career} ({with_career/success_count*100 if success_count > 0 else 0:.1f}%)")
    print(f"Failed: {failed_count}")
    print(f"Total time: {elapsed_total/60:.1f} minutes")
    print(f"Average rate: {(success_count + failed_count)/(elapsed_total/60):.1f} coaches/min")
    print("=" * 70)

    if failed_coaches:
        print(f"\n⚠️  Failed coaches ({len(failed_coaches)}):")
        for name, reason in failed_coaches[:10]:
            print(f"   - {name}: {reason}")
        if len(failed_coaches) > 10:
            print(f"   ... and {len(failed_coaches) - 10} more")

    # Save summary
    summary_file = Path(__file__).parent.parent / "data" / "rescrape_summary.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total": total,
            "success": success_count,
            "failed": failed_count,
            "with_career_history": with_career,
            "duration_minutes": elapsed_total / 60,
            "failed_coaches": [{"name": n, "reason": r} for n, r in failed_coaches]
        }, f, indent=2, ensure_ascii=False)

    print(f"\n📄 Summary saved to: {summary_file}")

if __name__ == "__main__":
    main()
