#!/usr/bin/env python3
"""
Football Coaches Database - Main Orchestrator
Builds comprehensive coach profiles from Transfermarkt for projectFIVE.

Usage:
    python main.py "Alexander Blessin"
    python main.py --url "https://www.transfermarkt.de/..."
    python main.py --batch coaches.txt
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Add execution directory to path
sys.path.insert(0, str(Path(__file__).parent / "execution"))

from scrape_transfermarkt import scrape_coach
from scrape_teammates import scrape_teammates
from scrape_players_used import scrape_players_used
from export_to_sheets import export_coach


def build_full_profile(name: str = None, url: str = None, export: bool = True) -> dict:
    """
    Build a complete coach profile by running all scrapers.

    Args:
        name: Coach name to search
        url: Direct Transfermarkt URL
        export: Whether to export to Google Sheets

    Returns:
        Complete profile dict with all data
    """
    print("\n" + "=" * 60)
    print("  FOOTBALL COACHES DATABASE")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # Step 1: Get basic profile
    print("\n📋 STEP 1: Fetching coach profile...")
    profile = scrape_coach(name=name, url=url)

    if not profile:
        print("\n❌ Could not find coach. Check the name/URL and try again.")
        return None

    coach_url = profile.get("url", "")
    coach_name = profile.get("name", "Unknown")

    # Step 2: Get teammates (if former player)
    print("\n👥 STEP 2: Fetching teammates...")
    teammates = None
    if coach_url:
        teammates = scrape_teammates(coach_profile_url=coach_url)

    # Step 3: Get players used
    print("\n⚽ STEP 3: Fetching players coached...")
    players_used = None
    if coach_url:
        players_used = scrape_players_used(coach_profile_url=coach_url)

    # Combine all data
    full_profile = {
        "profile": profile,
        "teammates": teammates,
        "players_used": players_used,
        "built_at": datetime.now().isoformat()
    }

    # Save combined profile locally
    output_dir = Path(__file__).parent / "tmp" / "profiles"
    output_dir.mkdir(parents=True, exist_ok=True)

    coach_id = profile.get("coach_id", "unknown")
    output_file = output_dir / f"coach_{coach_id}_full.json"

    with open(output_file, "w") as f:
        json.dump(full_profile, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Saved full profile to: {output_file}")

    # Step 4: Export to Google Sheets
    if export:
        print("\n📊 STEP 4: Exporting to Google Sheets...")
        export_coach(
            profile=profile,
            teammates=teammates,
            players_used=players_used
        )

    # Summary
    print("\n" + "=" * 60)
    print("  ✅ PROFILE COMPLETE")
    print("=" * 60)
    print(f"\n  Coach: {coach_name}")
    print(f"  Club: {profile.get('current_club', 'Unknown')}")
    print(f"  Role: {profile.get('current_role', 'Unknown')}")

    if teammates:
        print(f"\n  Teammates: {teammates.get('total_teammates', 0)}")
        print(f"    - Became coaches: {len(teammates.get('coaches', []))}")
        print(f"    - Became SDs: {len(teammates.get('sporting_directors', []))}")

    if players_used:
        print(f"\n  Players coached: {players_used.get('total_players', 0)}")
        print(f"    - Significant (20+ games): {len(players_used.get('significant_players', []))}")

    print(f"\n  Profile saved: {output_file}")
    print("=" * 60 + "\n")

    return full_profile


def batch_process(file_path: str, export: bool = True):
    """Process multiple coaches from a text file (one name per line)."""
    with open(file_path, "r") as f:
        coaches = [line.strip() for line in f if line.strip()]

    print(f"\n📋 Batch processing {len(coaches)} coaches...")

    results = []
    for i, coach_name in enumerate(coaches, 1):
        print(f"\n{'─' * 40}")
        print(f"  Processing {i}/{len(coaches)}: {coach_name}")
        print(f"{'─' * 40}")

        try:
            result = build_full_profile(name=coach_name, export=export)
            results.append({"name": coach_name, "success": result is not None})
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({"name": coach_name, "success": False, "error": str(e)})

    # Summary
    successful = sum(1 for r in results if r["success"])
    print(f"\n{'=' * 60}")
    print(f"  BATCH COMPLETE: {successful}/{len(coaches)} successful")
    print(f"{'=' * 60}\n")

    return results


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Build comprehensive football coach profiles from Transfermarkt",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py "Alexander Blessin"
  python main.py --url "https://www.transfermarkt.de/alexander-blessin/profil/trainer/35274"
  python main.py --batch coaches.txt
  python main.py "Fabian Hürzeler" --no-export
        """
    )

    parser.add_argument("name", nargs="?", help="Coach name to search")
    parser.add_argument("--url", "-u", help="Direct Transfermarkt coach URL")
    parser.add_argument("--batch", "-b", help="Text file with coach names (one per line)")
    parser.add_argument("--no-export", action="store_true", help="Skip Google Sheets export")

    args = parser.parse_args()

    export = not args.no_export

    if args.batch:
        return batch_process(args.batch, export=export)
    elif args.name or args.url:
        return build_full_profile(name=args.name, url=args.url, export=export)
    else:
        parser.print_help()
        print("\n❌ Please provide a coach name, URL, or batch file.")
        return None


if __name__ == "__main__":
    main()
