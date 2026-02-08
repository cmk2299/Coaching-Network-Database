#!/usr/bin/env python3
"""
Export SD-Coach Relationships to CSV for Excel/Pitch Usage

Creates a simple, pitch-ready CSV with all SD-Coach relationships
for use in client presentations, Excel analysis, etc.

Output Format:
Person A, Person B, Relationship Type, Club(s), Period, Years Together, Hiring Likelihood, Strength Score
"""

import sys
import json
import csv
from pathlib import Path
from datetime import datetime

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))


def export_sd_coach_relationships_csv():
    """Export all SD-Coach relationships to CSV."""
    print("=" * 70)
    print("Exporting SD-Coach Relationships to CSV")
    print("=" * 70)

    # Load overlap data
    overlap_file = Path(__file__).parent.parent / "data" / "sd_coach_overlaps.json"

    if not overlap_file.exists():
        print("❌ Error: sd_coach_overlaps.json not found")
        print("Run: python execution/analyze_sd_coach_overlaps.py first")
        return

    with open(overlap_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    relationships = data.get("relationships", [])

    # Prepare CSV rows
    csv_rows = []

    for rel in relationships:
        sd_name = rel.get("sd_name", "")
        sd_club = rel.get("sd_current_club", "")
        sd_role = rel.get("sd_current_role", "")

        coach_name = rel.get("coach_name", "")
        coach_club = rel.get("coach_current_club", "")

        total_clubs = rel.get("total_clubs", 0)
        total_years = rel.get("total_years_together", 0)
        strength = rel.get("relationship_strength", 0)

        # Get all clubs where they worked together
        overlaps = rel.get("overlaps", [])
        clubs_list = ", ".join(set(o.get("club", "") for o in overlaps))

        # Get periods
        periods = []
        for overlap in overlaps:
            start = overlap.get("overlap_start", "")
            end = overlap.get("overlap_end", "")
            periods.append(f"{start}-{end}")

        period_str = ", ".join(set(periods))

        # Get hiring likelihood (use highest)
        hiring_levels = [o.get("hiring_likelihood", "unknown") for o in overlaps]
        if "high" in hiring_levels:
            hiring = "HIGH"
        elif "medium" in hiring_levels:
            hiring = "MEDIUM"
        else:
            hiring = "LOW"

        # Add row
        csv_rows.append({
            "Sporting Director": sd_name,
            "SD Current Club": sd_club,
            "SD Current Role": sd_role,
            "Head Coach": coach_name,
            "Coach Current Club": coach_club,
            "Clubs Worked Together": clubs_list,
            "Number of Clubs": total_clubs,
            "Periods": period_str,
            "Total Years Together": total_years,
            "Hiring Likelihood": hiring,
            "Relationship Strength": strength,
            "Most Recent Club": rel.get("most_recent_club", ""),
            "Most Recent Year": rel.get("most_recent_year", "")
        })

    # Sort by strength
    csv_rows.sort(key=lambda x: x["Relationship Strength"], reverse=True)

    # Write CSV
    output_path = Path(__file__).parent.parent / "data" / "sd_coach_relationships.csv"

    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        if csv_rows:
            fieldnames = csv_rows[0].keys()
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            writer.writerows(csv_rows)

    print(f"\n✅ COMPLETE! Saved to: {output_path}")
    print(f"📊 Total relationships exported: {len(csv_rows)}")
    print(f"📁 File size: {output_path.stat().st_size / 1024:.1f} KB")

    # Print preview
    print("\n📋 Preview (Top 5 Rows):")
    print("-" * 70)

    for i, row in enumerate(csv_rows[:5], 1):
        print(f"{i}. {row['Sporting Director']:20} ↔ {row['Head Coach']:20}")
        print(f"   Clubs: {row['Clubs Worked Together']}")
        print(f"   Years: {row['Total Years Together']} | Hiring: {row['Hiring Likelihood']} | Strength: {row['Relationship Strength']}")
        print()

    print("=" * 70)
    print("💡 Use this CSV for:")
    print("  - Excel analysis and pivots")
    print("  - Client pitch decks")
    print("  - Relationship mapping")
    print("  - Market intelligence reports")
    print("=" * 70)


def export_all_contacts_csv():
    """Export ALL contacts (SDs + Assistants + Teammates) to master CSV."""
    print("\n" + "=" * 70)
    print("Bonus: Exporting ALL Contacts Master CSV")
    print("=" * 70)

    # This would combine:
    # - SD-Coach relationships
    # - Assistant-Coach relationships
    # - Teammate networks
    # - License cohorts

    # For now, we'll create a placeholder
    print("⏭️  Skipping master contacts export (future enhancement)")
    print("   Current focus: SD-Coach relationships only")


if __name__ == "__main__":
    export_sd_coach_relationships_csv()
    # export_all_contacts_csv()  # Future
