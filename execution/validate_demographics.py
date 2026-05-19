#!/usr/bin/env python3
"""
Validate demographics data quality after re-scrape
"""

import json
from pathlib import Path
from collections import Counter
from datetime import datetime

# Paths
BASE_DIR = Path(__file__).parent.parent
PRELOADED_DIR = BASE_DIR / "tmp" / "preloaded"
DATA_DIR = BASE_DIR / "data"

def main():
    print("=" * 70)
    print("DEMOGRAPHICS DATA QUALITY VALIDATION")
    print("=" * 70)
    print()

    # Load all profiles
    profile_files = list(PRELOADED_DIR.glob("*.json"))
    total = len(profile_files)

    print(f"📊 Total profiles: {total}\n")

    # Track completeness
    stats = {
        'has_nationality': 0,
        'has_age': 0,
        'has_dob': 0,
        'has_birthplace': 0,
        'has_license': 0,
        'has_agent': 0,
        'has_career': 0,
        'nationalities': Counter(),
        'age_distribution': [],
        'license_types': Counter(),
    }

    # Process all profiles
    for pfile in profile_files:
        try:
            with open(pfile, encoding='utf-8') as f:
                profile = json.load(f)

            # Count completeness
            if profile.get('nationality'):
                stats['has_nationality'] += 1
                stats['nationalities'][profile['nationality']] += 1

            if profile.get('age'):
                stats['has_age'] += 1
                stats['age_distribution'].append(profile['age'])

            if profile.get('dob'):
                stats['has_dob'] += 1

            if profile.get('birthplace'):
                stats['has_birthplace'] += 1

            if profile.get('license'):
                stats['has_license'] += 1
                stats['license_types'][profile['license']] += 1

            if profile.get('agent'):
                stats['has_agent'] += 1

            if profile.get('career_history'):
                stats['has_career'] += 1

        except Exception as e:
            print(f"⚠️ Error reading {pfile.name}: {e}")

    # Calculate percentages
    def pct(count):
        return count / total * 100 if total > 0 else 0

    print("=" * 70)
    print("COMPLETENESS RESULTS")
    print("=" * 70)
    print()

    print(f"✅ Nationality:  {stats['has_nationality']:4d}/{total} ({pct(stats['has_nationality']):5.1f}%)")
    print(f"✅ Age:          {stats['has_age']:4d}/{total} ({pct(stats['has_age']):5.1f}%)")
    print(f"✅ DOB:          {stats['has_dob']:4d}/{total} ({pct(stats['has_dob']):5.1f}%)")
    print(f"✅ Birthplace:   {stats['has_birthplace']:4d}/{total} ({pct(stats['has_birthplace']):5.1f}%)")
    print(f"⭐ License:      {stats['has_license']:4d}/{total} ({pct(stats['has_license']):5.1f}%)")
    print(f"📧 Agent:        {stats['has_agent']:4d}/{total} ({pct(stats['has_agent']):5.1f}%)")
    print(f"📋 Career:       {stats['has_career']:4d}/{total} ({pct(stats['has_career']):5.1f}%)")
    print()

    # Age statistics
    if stats['age_distribution']:
        ages = stats['age_distribution']
        print("=" * 70)
        print("AGE DISTRIBUTION")
        print("=" * 70)
        print()
        print(f"Average age: {sum(ages)/len(ages):.1f} years")
        print(f"Min age: {min(ages)} years")
        print(f"Max age: {max(ages)} years")
        print(f"Median age: {sorted(ages)[len(ages)//2]} years")
        print()

    # Top nationalities
    if stats['nationalities']:
        print("=" * 70)
        print("TOP 10 NATIONALITIES")
        print("=" * 70)
        print()
        for nat, count in stats['nationalities'].most_common(10):
            print(f"  {nat:30s}: {count:4d} ({pct(count):5.1f}%)")
        print()

    # License types
    if stats['license_types']:
        print("=" * 70)
        print("LICENSE TYPES")
        print("=" * 70)
        print()
        for license_type, count in stats['license_types'].most_common(10):
            print(f"  {license_type:30s}: {count:4d}")
        print()

    # Quality grade
    print("=" * 70)
    print("OVERALL DATA QUALITY")
    print("=" * 70)
    print()

    # Calculate quality score
    core_fields = ['has_nationality', 'has_age', 'has_career']
    core_avg = sum(pct(stats[field]) for field in core_fields) / len(core_fields)

    extra_fields = ['has_dob', 'has_birthplace', 'has_license']
    extra_avg = sum(pct(stats[field]) for field in extra_fields) / len(extra_fields)

    overall_score = (core_avg * 0.7) + (extra_avg * 0.3)

    print(f"Core Fields Avg:  {core_avg:.1f}%")
    print(f"Extra Fields Avg: {extra_avg:.1f}%")
    print(f"Overall Score:    {overall_score:.1f}%")
    print()

    if overall_score >= 90:
        grade = "A+ (EXCELLENT)"
    elif overall_score >= 80:
        grade = "A (VERY GOOD)"
    elif overall_score >= 70:
        grade = "B (GOOD)"
    elif overall_score >= 60:
        grade = "C (FAIR)"
    else:
        grade = "D (NEEDS IMPROVEMENT)"

    print(f"Quality Grade: {grade}")
    print()

    # Save summary
    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_profiles": total,
        "completeness": {
            "nationality": {
                "count": stats['has_nationality'],
                "percentage": round(pct(stats['has_nationality']), 1)
            },
            "age": {
                "count": stats['has_age'],
                "percentage": round(pct(stats['has_age']), 1)
            },
            "dob": {
                "count": stats['has_dob'],
                "percentage": round(pct(stats['has_dob']), 1)
            },
            "birthplace": {
                "count": stats['has_birthplace'],
                "percentage": round(pct(stats['has_birthplace']), 1)
            },
            "license": {
                "count": stats['has_license'],
                "percentage": round(pct(stats['has_license']), 1)
            },
            "agent": {
                "count": stats['has_agent'],
                "percentage": round(pct(stats['has_agent']), 1)
            },
            "career_history": {
                "count": stats['has_career'],
                "percentage": round(pct(stats['has_career']), 1)
            }
        },
        "quality_score": round(overall_score, 1),
        "grade": grade,
        "age_stats": {
            "average": round(sum(stats['age_distribution'])/len(stats['age_distribution']), 1) if stats['age_distribution'] else 0,
            "min": min(stats['age_distribution']) if stats['age_distribution'] else 0,
            "max": max(stats['age_distribution']) if stats['age_distribution'] else 0
        },
        "top_nationalities": [
            {"country": nat, "count": count, "percentage": round(pct(count), 1)}
            for nat, count in stats['nationalities'].most_common(10)
        ]
    }

    summary_file = DATA_DIR / "demographics_validation_summary.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"📄 Summary saved to: {summary_file}")
    print()
    print("=" * 70)
    print("✅ VALIDATION COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    main()
