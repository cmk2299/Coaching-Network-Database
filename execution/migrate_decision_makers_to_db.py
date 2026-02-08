#!/usr/bin/env python3
"""
Migrate existing Decision Makers data to database.

This script:
1. Reads data/manual_decision_makers.json
2. Creates SD profiles in sportdirektoren table
3. Creates SD ↔ Coach relationships in sd_coach_relationships table

This enables the new Trainerberater features:
- "Wer kennt meinen Trainer?" (SD connections)
- "Welcher SD hired welchen Trainer-Typ?" (Hiring patterns)
- "Welche SDs passen zu meinem Trainer?" (Reverse search)
"""

import json
from pathlib import Path
from coach_db import get_db

# Paths
BASE_DIR = Path(__file__).parent.parent
MANUAL_DM_FILE = BASE_DIR / "data" / "manual_decision_makers.json"

def migrate_decision_makers():
    """Migrate all decision makers from JSON to database."""

    # Load JSON
    with open(MANUAL_DM_FILE, 'r', encoding='utf-8') as f:
        dm_data = json.load(f)

    db = get_db()

    total_relationships = 0
    coaches_processed = set()

    for entry in dm_data:
        coach_name = entry.get("coach_name")
        club = entry.get("club")
        period = entry.get("period", "")

        decision_makers = entry.get("decision_makers", [])

        # We need coach TM ID to link relationships
        # For now, we'll store coach_name and manually map later
        # TODO: Add tm_id to manual_decision_makers.json

        print(f"\nProcessing: {coach_name} @ {club}")

        for dm in decision_makers:
            sd_name = dm.get("name")
            sd_role = dm.get("role", "Sportdirektor")
            connection_type = dm.get("connection_type", "hiring_manager")
            notes = dm.get("notes", "")

            # Determine relationship type
            if connection_type == "hiring_manager":
                relationship_type = "hired"
            elif connection_type == "sports_director":
                relationship_type = "worked_together"
            else:
                relationship_type = connection_type

            # Determine outcome (from notes)
            outcome = None
            if "promotion" in notes.lower() or "promoted" in notes.lower():
                outcome = "Promoted"
            elif "success" in notes.lower():
                outcome = "Successful"
            elif "fired" in notes.lower() or "sacked" in notes.lower():
                outcome = "Fired"

            print(f"  - {sd_name} ({sd_role}): {relationship_type} @ {club}")

            # TODO: We need coach TM IDs to actually insert relationships
            # For now, just create SD profiles

            # Create or update SD profile
            sd_id = db.get_or_create_sd(sd_name, club)

            total_relationships += 1

        coaches_processed.add(coach_name)

    print(f"\n{'='*60}")
    print(f"Migration Summary:")
    print(f"  Coaches processed: {len(coaches_processed)}")
    print(f"  Total relationships: {total_relationships}")
    print(f"  Sportdirektoren created: {total_relationships}")  # Approximate
    print(f"\n⚠️  NOTE: Relationships not yet linked to coaches")
    print(f"    Need to add tm_id to manual_decision_makers.json first")
    print(f"{'='*60}")

if __name__ == "__main__":
    print("="*60)
    print("DECISION MAKERS → DATABASE MIGRATION")
    print("="*60)

    migrate_decision_makers()

    print("\n✅ Migration complete!")
    print("\nNext steps:")
    print("1. Add 'coach_tm_id' to data/manual_decision_makers.json")
    print("2. Re-run migration to create actual relationships")
    print("3. Test with: python execution/test_sd_features.py")
