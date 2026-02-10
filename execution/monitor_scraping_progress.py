#!/usr/bin/env python3
"""
Monitor scraping progress in real-time
Shows stats from preload/ directory
"""

import json
import time
from pathlib import Path
from datetime import datetime

def count_preload_stats():
    """Count coaches and companions in preload directory"""
    preload_dir = Path(__file__).parent.parent / "preload"

    if not preload_dir.exists():
        return None

    coach_dirs = [d for d in preload_dir.iterdir() if d.is_dir()]

    stats = {
        'total_coaches': len(coach_dirs),
        'with_profile': 0,
        'with_companions': 0,
        'with_teammates': 0,
        'with_playing_career': 0,
        'total_companions': 0,
        'total_teammates': 0,
        'total_management': 0,
    }

    for coach_dir in coach_dirs:
        # Check files
        if (coach_dir / "profile.json").exists():
            stats['with_profile'] += 1

        if (coach_dir / "companions.json").exists():
            stats['with_companions'] += 1

            # Count companions
            try:
                with open(coach_dir / "companions.json") as f:
                    companions = json.load(f)
                    teammates = len(companions.get('all_teammates', []))
                    management = len(companions.get('all_management', []))
                    stats['total_teammates'] += teammates
                    stats['total_management'] += management
                    stats['total_companions'] += teammates + management
            except:
                pass

        if (coach_dir / "teammates.json").exists():
            stats['with_teammates'] += 1

        if (coach_dir / "playing_career.json").exists():
            stats['with_playing_career'] += 1

    return stats

def display_progress(previous_stats=None):
    """Display current progress"""
    stats = count_preload_stats()

    if not stats:
        print("❌ No preload directory found")
        return None

    print("\n" + "=" * 70)
    print(f"📊 SCRAPING PROGRESS - {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 70)

    print(f"\n📁 COACHES:")
    print(f"  Total coaches: {stats['total_coaches']}")
    print(f"  With profile: {stats['with_profile']} ({stats['with_profile']/stats['total_coaches']*100:.1f}%)")
    print(f"  With companions: {stats['with_companions']} ({stats['with_companions']/stats['total_coaches']*100:.1f}%)")
    print(f"  With teammates: {stats['with_teammates']} ({stats['with_teammates']/stats['total_coaches']*100:.1f}%)")
    print(f"  With playing career: {stats['with_playing_career']} ({stats['with_playing_career']/stats['total_coaches']*100:.1f}%)")

    print(f"\n🕸️  NETWORK CONNECTIONS:")
    print(f"  Total companions: {stats['total_companions']}")
    print(f"  - Teammates: {stats['total_teammates']}")
    print(f"  - Management: {stats['total_management']}")
    if stats['with_companions'] > 0:
        print(f"  Average per coach: {stats['total_companions']/stats['with_companions']:.1f}")

    # Show delta if previous stats available
    if previous_stats:
        print(f"\n📈 CHANGES (since last check):")
        print(f"  Coaches: +{stats['total_coaches'] - previous_stats['total_coaches']}")
        print(f"  Companions: +{stats['total_companions'] - previous_stats['total_companions']}")
        print(f"  With companions: +{stats['with_companions'] - previous_stats['with_companions']}")

    print("=" * 70)

    return stats

def monitor_continuous(interval=30):
    """Monitor progress continuously"""
    print("🔄 Starting continuous monitoring (Ctrl+C to stop)")
    print(f"Refresh interval: {interval} seconds")

    previous_stats = None

    try:
        while True:
            previous_stats = display_progress(previous_stats)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n\n✋ Monitoring stopped")

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "watch":
        # Continuous monitoring mode
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        monitor_continuous(interval)
    else:
        # Single snapshot
        display_progress()
