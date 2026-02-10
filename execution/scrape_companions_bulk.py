#!/usr/bin/env python3
"""
Bulk scrape companions for ALL coaches in preload/ directory
This will massively expand the network connections
"""

import sys
import time
import json
from pathlib import Path
from scrape_companions import get_companions_for_coach
from preload_coach_data import load_preloaded

# Rate limiting
DELAY_BETWEEN_COACHES = 4  # seconds (companions scraping is heavier)

def scrape_companions_for_all():
    """
    Load all preloaded coaches and scrape companions for each
    """
    print("=" * 70)
    print("BULK COMPANIONS SCRAPING")
    print("=" * 70)

    # Get all preloaded coaches
    preload_dir = Path(__file__).parent.parent / "preload"

    if not preload_dir.exists():
        print("❌ Preload directory not found!")
        return

    # Find all coach directories
    coach_dirs = [d for d in preload_dir.iterdir() if d.is_dir() and (d / "profile.json").exists()]

    print(f"\nFound {len(coach_dirs)} coaches in preload/")
    print(f"Estimated time: {len(coach_dirs) * DELAY_BETWEEN_COACHES / 60:.1f} minutes")
    print("=" * 70)

    results = {
        'total_coaches': len(coach_dirs),
        'successful': 0,
        'failed': 0,
        'total_companions': 0,
        'details': []
    }

    for i, coach_dir in enumerate(coach_dirs, 1):
        coach_name = coach_dir.name
        print(f"\n[{i}/{len(coach_dirs)}] {coach_name}")
        print("-" * 50)

        # Check if companions already exist
        companions_file = coach_dir / "companions.json"
        if companions_file.exists():
            print("  ⏭️  Companions already exist, skipping...")

            # Load and count
            try:
                with open(companions_file) as f:
                    companions_data = json.load(f)
                    total = len(companions_data.get('all_teammates', [])) + len(companions_data.get('all_management', []))
                    results['total_companions'] += total
                    results['successful'] += 1
                    print(f"  ✓ {total} companions already saved")
            except:
                pass
            continue

        # Load coach profile
        try:
            coach_data = load_preloaded(coach_name)
            if not coach_data:
                print(f"  ⚠ Failed to load profile")
                results['failed'] += 1
                continue

            coach_url = coach_data.get('url', '')
            if not coach_url:
                print(f"  ⚠ No URL found")
                results['failed'] += 1
                continue

        except Exception as e:
            print(f"  ❌ Error loading profile: {e}")
            results['failed'] += 1
            continue

        # Scrape companions
        try:
            print(f"  🔍 Scraping companions from {coach_url}...")
            companions_data = get_companions_for_coach(coach_url)

            if companions_data:
                # Count companions
                total_teammates = len(companions_data.get('all_teammates', []))
                total_management = len(companions_data.get('all_management', []))
                total = total_teammates + total_management

                # Save to preload directory
                with open(companions_file, 'w', encoding='utf-8') as f:
                    json.dump(companions_data, f, indent=2, ensure_ascii=False)

                print(f"  ✓ Saved {total} companions ({total_teammates} teammates, {total_management} management)")

                results['successful'] += 1
                results['total_companions'] += total
                results['details'].append({
                    'name': coach_name,
                    'total': total,
                    'teammates': total_teammates,
                    'management': total_management
                })
            else:
                print(f"  ⚠ No companions data returned")
                results['failed'] += 1

        except Exception as e:
            print(f"  ❌ Error scraping companions: {e}")
            results['failed'] += 1

        # Rate limiting
        if i < len(coach_dirs):
            print(f"  ⏱️  Waiting {DELAY_BETWEEN_COACHES}s...")
            time.sleep(DELAY_BETWEEN_COACHES)

    # Final summary
    print("\n" + "=" * 70)
    print("✅ BULK COMPANIONS SCRAPING COMPLETE")
    print("=" * 70)
    print(f"Total coaches: {results['total_coaches']}")
    print(f"Successful: {results['successful']}")
    print(f"Failed: {results['failed']}")
    print(f"Total companions scraped: {results['total_companions']}")
    print(f"Average per coach: {results['total_companions'] / results['successful']:.1f}" if results['successful'] > 0 else "N/A")
    print("=" * 70)

    # Save summary
    summary_file = Path(__file__).parent.parent / "data" / "companions_bulk_scrape_summary.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            **results
        }, f, indent=2, ensure_ascii=False)

    print(f"\nSummary saved to: {summary_file}")

    # Top 10 coaches by connections
    if results['details']:
        print("\n🔥 Top 10 Coaches by Connections:")
        sorted_details = sorted(results['details'], key=lambda x: x['total'], reverse=True)
        for i, detail in enumerate(sorted_details[:10], 1):
            print(f"  {i:2d}. {detail['name']}: {detail['total']} ({detail['teammates']} teammates, {detail['management']} mgmt)")

if __name__ == "__main__":
    scrape_companions_for_all()
