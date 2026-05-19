#!/usr/bin/env python3
"""
Re-scrape only the coaches that weren't updated today
"""

import json
import time
from pathlib import Path
from datetime import datetime
from scrape_transfermarkt import scrape_coach
from preload_coach_data import save_preloaded

# Configuration
PRELOADED_DIR = Path(__file__).parent.parent / "tmp" / "preloaded"
CACHE_DIR = Path(__file__).parent.parent / "tmp" / "cache"
DELAY_BETWEEN_COACHES = 4  # 4 seconds to be safe

def main():
    print("=" * 70)
    print("RE-SCRAPING REMAINING COACHES (NOT UPDATED TODAY)")
    print("=" * 70)

    # Get all profiles
    profile_files = sorted(PRELOADED_DIR.glob("*.json"))

    # Filter to only those NOT modified today
    today = datetime.now().date()
    to_scrape = []

    for pfile in profile_files:
        mod_date = datetime.fromtimestamp(pfile.stat().st_mtime).date()
        if mod_date != today:
            to_scrape.append(pfile)

    total = len(to_scrape)

    print(f"\n📊 Total profiles: {len(profile_files)}")
    print(f"📊 Already updated today: {len(profile_files) - total}")
    print(f"📊 Remaining to scrape: {total}")
    print(f"⏱️  Estimated time: {total * DELAY_BETWEEN_COACHES / 60:.1f} minutes\n")

    if total == 0:
        print("✅ All profiles already updated today!")
        return

    # Track progress
    success_count = 0
    failed_count = 0
    with_demo = 0
    failed_coaches = []

    start_time = time.time()

    for i, profile_file in enumerate(to_scrape, 1):
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
            rate = i / (elapsed / 60) if elapsed > 0 else 0
            remaining = (total - i) / rate if rate > 0 else 0

            print(f"[{i}/{total}] {name}")
            print(f"   Rate: {rate:.2f}/min | ETA: {remaining:.1f}min")

            # Convert .com URLs to .de (demographics only available on .de)
            url_de = url.replace('transfermarkt.com', 'transfermarkt.de')

            # Clear cache to force fresh scrape
            coach_id = data.get('coach_id')
            if coach_id:
                cache_file = CACHE_DIR / f"coach_{coach_id}_profile.json"
                if cache_file.exists():
                    cache_file.unlink()

            # Re-scrape with fixed parser
            profile = scrape_coach(url=url_de)

            if profile:
                # Check if demographics were populated
                has_demo = bool(profile.get('nationality') or profile.get('age'))

                if has_demo:
                    with_demo += 1
                    print(f"   ✅ Success! Demographics: Nat={profile.get('nationality', 'N/A')}, Age={profile.get('age', 'N/A')}")
                else:
                    print(f"   ⚠️  Scraped but no demographics")

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
    print(f"With demographics: {with_demo} ({with_demo/success_count*100 if success_count > 0 else 0:.1f}%)")
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
    summary_file = Path(__file__).parent.parent / "data" / "rescrape_remaining_summary.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total": total,
            "success": success_count,
            "failed": failed_count,
            "with_demographics": with_demo,
            "duration_minutes": elapsed_total / 60,
            "failed_coaches": [{"name": n, "reason": r} for n, r in failed_coaches]
        }, f, indent=2, ensure_ascii=False)

    print(f"\n📄 Summary saved to: {summary_file}")

if __name__ == "__main__":
    main()
