#!/usr/bin/env python3
"""
Discover Historical Executives via Structured Web Search.

STRATEGY: Use Claude's WebSearch tool to find executive appointments via
structured queries. Much more reliable than raw scraping.

Process:
1. For each club + role + year: Generate targeted search query
2. Use WebSearch to find relevant articles
3. Extract names and dates from search results/snippets
4. Build historical executives database

This leverages search engines' indexing and Claude's extraction capabilities.
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

# Target clubs (start with key clubs where coaches have youth history)
PRIORITY_CLUBS = [
    "RB Leipzig",
    "Bayern München",
    "Borussia Dortmund",
    "VfB Stuttgart",
    "Bayer Leverkusen",
    "Hoffenheim",
    "Mainz",
]

# Role searches
ROLE_SEARCHES = {
    "Scouting": [
        "Chefscout",
        "Leiter Scouting",
        "Head of Scouting",
    ],
    "Academy": [
        "Nachwuchskoordinator",
        "Leiter Nachwuchs",
        "Nachwuchschef",
    ],
    "Technical": [
        "Technischer Direktor",
    ]
}

# Time periods to focus on (based on current Bundesliga coaches' career spans)
PRIORITY_YEARS = [2012, 2015, 2018, 2020, 2022, 2024]


def generate_search_queries(club: str, role: str, year: int) -> list:
    """Generate effective search queries for finding executive appointments."""
    queries = []

    # German queries (primary)
    queries.append(f'"{club}" "{role}" "ernennt" {year}')
    queries.append(f'"{club}" "{role}" "verpflichtet" {year}')
    queries.append(f'"{club}" "{role}" "wird" {year}')

    # Alternative phrasing
    queries.append(f'{club} neuer {role} {year}')
    queries.append(f'{club} {role} {year} site:transfermarkt.de')

    return queries


def create_search_plan():
    """
    Create a structured search plan for historical executive discovery.

    Returns a list of search tasks with priority levels.
    """
    search_plan = []

    for club in PRIORITY_CLUBS:
        for category, roles in ROLE_SEARCHES.items():
            for role in roles:
                for year in PRIORITY_YEARS:
                    # Generate queries
                    queries = generate_search_queries(club, role, year)

                    search_plan.append({
                        "club": club,
                        "role": role,
                        "category": category,
                        "year": year,
                        "queries": queries,
                        "status": "pending"
                    })

    return search_plan


def main():
    """Generate search plan for executive discovery."""
    print("=" * 70)
    print("HISTORICAL EXECUTIVE DISCOVERY - SEARCH PLAN GENERATOR")
    print("=" * 70)
    print()

    # Generate search plan
    search_plan = create_search_plan()

    print(f"📋 Generated search plan:")
    print(f"   - {len(PRIORITY_CLUBS)} priority clubs")
    print(f"   - {sum(len(roles) for roles in ROLE_SEARCHES.values())} role types")
    print(f"   - {len(PRIORITY_YEARS)} time periods")
    print(f"   - Total: {len(search_plan)} search tasks")
    print()

    # Show sample queries
    print("📝 Sample search queries:")
    for task in search_plan[:5]:
        print(f"\n   Club: {task['club']}")
        print(f"   Role: {task['role']} ({task['category']})")
        print(f"   Year: {task['year']}")
        print(f"   Queries:")
        for q in task['queries'][:2]:
            print(f"     - {q}")

    # Save search plan
    output_file = Path(__file__).parent.parent / "data" / "executive_discovery_plan.json"

    output_data = {
        "created_date": datetime.now().isoformat(),
        "description": "Search plan for discovering historical executives",
        "total_tasks": len(search_plan),
        "clubs": PRIORITY_CLUBS,
        "role_categories": list(ROLE_SEARCHES.keys()),
        "years": PRIORITY_YEARS,
        "search_plan": search_plan
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Search plan saved to: {output_file}")
    print()
    print("=" * 70)
    print("NEXT STEP:")
    print("  This search plan can now be executed using WebSearch tool")
    print("  or manually processed to discover historical executives.")
    print("=" * 70)


if __name__ == "__main__":
    main()
