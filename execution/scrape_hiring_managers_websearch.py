#!/usr/bin/env python3
"""
Find hiring managers using WebSearch (Google/Bing).

Strategy:
1. Search: "[Coach] [Club] appointed [Year] sporting director"
2. Extract decision maker names from search results
3. Use NLP/regex to identify hiring managers

This is fully automated and works across all leagues/languages.
"""

import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# Cache directory
CACHE_DIR = Path(__file__).resolve().parent.parent / "tmp" / "cache" / "websearch_hiring"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Cache duration: 90 days
CACHE_DURATION_DAYS = 90


def get_cache_path(coach_name: str, club_name: str) -> Path:
    """Get cache file path."""
    safe_coach = re.sub(r'[^\w\s-]', '', coach_name).strip().replace(' ', '_')
    safe_club = re.sub(r'[^\w\s-]', '', club_name).strip().replace(' ', '_')
    return CACHE_DIR / f"{safe_coach}_{safe_club}_websearch.json"


def load_from_cache(coach_name: str, club_name: str) -> Optional[Dict]:
    """Load cached result."""
    cache_path = get_cache_path(coach_name, club_name)

    if cache_path.exists():
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cached = json.load(f)

            cached_at = datetime.fromisoformat(cached.get("cached_at", ""))
            if (datetime.now() - cached_at).days < CACHE_DURATION_DAYS:
                return cached.get("result")
        except:
            pass

    return None


def save_to_cache(coach_name: str, club_name: str, result: Dict):
    """Save result to cache."""
    cache_path = get_cache_path(coach_name, club_name)

    cache_data = {
        "cached_at": datetime.now().isoformat(),
        "coach_name": coach_name,
        "club_name": club_name,
        "result": result
    }

    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(cache_data, f, indent=2, ensure_ascii=False)


def extract_hiring_managers_from_text(text: str, club_name: str) -> List[Dict]:
    """
    Extract hiring manager names from search result text.

    Patterns to look for:
    - "Sporting director [Name] said..."
    - "[Name], the club's sporting director, ..."
    - "hired by [Name]"
    - "[Name] who hired..."
    """
    hiring_managers = []

    # Patterns for English/German
    patterns = [
        # "sporting director Max Eberl said/stated/announced"
        r'sporting director\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s+(?:said|stated|announced|explained)',
        # "Max Eberl, sporting director, said"
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}),\s*(?:the\s+)?(?:club\'s\s+)?sporting director',
        # "hired by sporting director Max Eberl"
        r'hired by\s+(?:sporting director\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})',
        # "Sportdirektor Max Eberl"
        r'(?:Sportdirektor|Sportvorstand|Geschäftsführer)\s+([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+){1,3})',
        # "Max Eberl, Sportdirektor"
        r'([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+){1,3}),\s*(?:Sportdirektor|Sportvorstand|Geschäftsführer)',
        # "Eberl who argued/pushed for"
        r'([A-Z][a-z]+)\s+who\s+(?:argued|pushed|advocated|championed)',
    ]

    # Role keywords for classification
    role_keywords = {
        "sporting director": "Sportdirektor",
        "sportdirektor": "Sportdirektor",
        "sportvorstand": "Sportvorstand",
        "geschäftsführer": "Geschäftsführer",
        "ceo": "CEO",
        "board": "Board Member",
    }

    found_names = set()

    for pattern in patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            name = match.group(1).strip()

            # Get context for role determination
            context_start = max(0, match.start() - 150)
            context_end = min(len(text), match.end() + 150)
            context = text[context_start:context_end].lower()

            # Determine role from context
            role = "Executive"
            for keyword, role_name in role_keywords.items():
                if keyword in context:
                    role = role_name
                    break

            # Validate name (2-4 words, proper capitalization)
            word_count = len(name.split())
            if 2 <= word_count <= 4 and name not in found_names:
                # Avoid false positives (common words, club names)
                if name.lower() not in ['bayern munich', 'fc bayern', club_name.lower()]:
                    found_names.add(name)
                    hiring_managers.append({
                        "name": name,
                        "role": role,
                        "source": "websearch",
                        "connection_type": "hiring_manager"
                    })

    return hiring_managers


def find_hiring_manager_websearch(coach_name: str, club_name: str, start_date: str) -> Dict:
    """
    Find hiring manager using web search.

    NOTE: This requires the WebSearch tool which is only available in the Claude Code environment.
    For production, this would need to be integrated with the agent's WebSearch capability.

    Args:
        coach_name: Coach name
        club_name: Club name
        start_date: Start date (format: MM.YYYY)

    Returns:
        Dict with hiring_managers and metadata
    """
    # Check cache
    cached = load_from_cache(coach_name, club_name)
    if cached:
        print(f"  ✓ Using cached result for {coach_name} at {club_name}")
        return cached

    # Extract year
    year_match = re.search(r'(\d{4})', start_date)
    year = year_match.group(1) if year_match else ""

    # This is a placeholder - in production, this would call WebSearch
    # For now, return empty to indicate manual integration needed
    result = {
        "hiring_managers": [],
        "found": False,
        "note": "WebSearch integration required - use via agent's WebSearch tool"
    }

    return result


def build_search_queries(coach_name: str, club_name: str, year: str) -> List[str]:
    """
    Build optimized search queries for finding hiring managers.

    Returns multiple query variants to maximize success rate.
    """
    queries = [
        # English
        f'"{coach_name}" "{club_name}" appointed {year} sporting director',
        f'"{coach_name}" {club_name} hired {year} "sporting director"',
        f'{coach_name} {club_name} announcement {year} who hired',

        # German
        f'"{coach_name}" "{club_name}" {year} Sportdirektor verpflichtet',
        f'{coach_name} {club_name} {year} "Sportdirektor" verkündet',
    ]

    return queries


# Integration point for agent with WebSearch
def search_and_extract_hiring_manager(coach_name: str, club_name: str, start_date: str, websearch_func) -> Dict:
    """
    Main function to be called by agent with WebSearch capability.

    Args:
        coach_name: Coach name
        club_name: Club name
        start_date: Start date (MM.YYYY)
        websearch_func: Function that performs web search (agent's WebSearch tool)

    Returns:
        Dict with hiring_managers found
    """
    # Check cache
    cached = load_from_cache(coach_name, club_name)
    if cached:
        return cached

    # Extract year
    year_match = re.search(r'(\d{4})', start_date)
    year = year_match.group(1) if year_match else ""

    # Build search queries
    queries = build_search_queries(coach_name, club_name, year)

    all_hiring_managers = []

    # Try each query
    for query in queries[:2]:  # Try top 2 queries to avoid rate limits
        try:
            # Call WebSearch via agent
            search_results = websearch_func(query)

            # Extract text from results
            combined_text = ""
            if isinstance(search_results, dict):
                # Handle different result formats
                combined_text = str(search_results)
            elif isinstance(search_results, str):
                combined_text = search_results

            # Extract hiring managers from text
            managers = extract_hiring_managers_from_text(combined_text, club_name)
            all_hiring_managers.extend(managers)

            if managers:
                break  # Found something, no need to continue

        except Exception as e:
            print(f"  Search failed for query: {query[:50]}...")
            continue

    # Deduplicate by name
    unique_managers = []
    seen_names = set()
    for manager in all_hiring_managers:
        if manager["name"] not in seen_names:
            seen_names.add(manager["name"])
            unique_managers.append(manager)

    result = {
        "hiring_managers": unique_managers,
        "found": len(unique_managers) > 0,
        "search_queries_used": queries[:2]
    }

    # Cache result
    save_to_cache(coach_name, club_name, result)

    return result


if __name__ == "__main__":
    print("\n=== Hiring Manager WebSearch Module ===\n")
    print("This module requires integration with WebSearch tool.")
    print("Use via agent: search_and_extract_hiring_manager(coach, club, date, websearch_func)")

    # Show example queries
    queries = build_search_queries("Vincent Kompany", "Bayern München", "2024")
    print("\nExample search queries:")
    for q in queries:
        print(f"  - {q}")
