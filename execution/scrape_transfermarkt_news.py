#!/usr/bin/env python3
"""
Scrape Transfermarkt news articles for coach hiring announcements.
Uses the start_date from career stations to find relevant articles.
"""

import json
import re
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
import requests

# Cache directory
CACHE_DIR = Path(__file__).resolve().parent.parent / "tmp" / "cache" / "tm_news"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Cache duration: 90 days
CACHE_DURATION_DAYS = 90

TM_BASE = "https://www.transfermarkt.de"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def get_cache_path(coach_name: str, club_name: str) -> Path:
    """Get cache file path."""
    safe_coach = re.sub(r'[^\w\s-]', '', coach_name).strip().replace(' ', '_')
    safe_club = re.sub(r'[^\w\s-]', '', club_name).strip().replace(' ', '_')
    return CACHE_DIR / f"{safe_coach}_{safe_club}_news.json"


def load_from_cache(coach_name: str, club_name: str) -> Optional[Dict]:
    """Load cached result if available."""
    cache_path = get_cache_path(coach_name, club_name)

    if not cache_path.exists():
        return None

    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            cached = json.load(f)

        cached_time = datetime.fromisoformat(cached.get("cached_at", ""))
        age = (datetime.now() - cached_time).days

        if age < CACHE_DURATION_DAYS:
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


def search_transfermarkt_news(coach_name: str, club_name: str, start_date: str) -> Optional[str]:
    """
    Search Transfermarkt news for coach hiring announcement.

    Args:
        coach_name: e.g. "Alexander Blessin"
        club_name: e.g. "Genua CFC"
        start_date: e.g. "01.2022" or "07.2024"

    Returns:
        URL of the news article if found
    """
    try:
        # Extract year and month from start_date
        year_match = re.search(r'(\d{2})\.(\d{4})', start_date)
        if not year_match:
            # Try other formats
            year_match = re.search(r'(\d{4})', start_date)
            if year_match:
                year = year_match.group(1)
                month = None
            else:
                return None
        else:
            month = year_match.group(1)
            year = year_match.group(2)

        # Build search query for Transfermarkt news
        # Format: /schnellsuche/ergebnis/schnellsuche?query=blessin+genua
        query = f"{coach_name} {club_name}".replace(' ', '+')
        search_url = f"{TM_BASE}/schnellsuche/ergebnis/schnellsuche?query={query}"

        print(f"  Searching TM news: {coach_name} at {club_name} ({start_date})")

        time.sleep(2)
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(search_url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'lxml')

        # Find news results
        # Look for links in news section
        news_links = soup.find_all('a', href=re.compile(r'/view/news/\d+'))

        # Filter by year in URL or title
        for link in news_links[:5]:  # Check top 5 results
            href = link.get('href', '')
            title = link.get_text(strip=True).lower()

            # Check if year matches and contains relevant keywords
            if year in href or year in title:
                keywords = ['trainer', 'coach', 'verpflichtet', 'unterschreibt', 'neuer', 'verkündet']
                if any(kw in title for kw in keywords):
                    full_url = TM_BASE + href if href.startswith('/') else href
                    print(f"    ✓ Found article: {title[:80]}...")
                    return full_url

        print(f"    ✗ No matching article found")
        return None

    except Exception as e:
        print(f"    Error searching TM news: {e}")
        return None


def extract_hiring_managers_from_article(article_url: str) -> List[Dict]:
    """
    Extract hiring managers from a Transfermarkt news article.

    Uses pattern matching for German articles.
    """
    try:
        time.sleep(2)
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(article_url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'lxml')

        # Get article text
        article_div = soup.find('div', class_='news-text') or soup.find('article')
        if not article_div:
            return []

        text = article_div.get_text(separator=' ', strip=True)

        # Patterns for German sports articles
        patterns = [
            # "Sportdirektor Max Eberl erklärt: ..."
            r'(?:Sportdirektor|Sportvorstand|Geschäftsführer|CEO|Präsident)\s+([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+){1,3})',
            # "Max Eberl, Sportdirektor bei..."
            r'([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+){1,3}),\s*(?:Sportdirektor|Sportvorstand|Geschäftsführer)',
            # Quote attribution: "sagt Sportdirektor Johannes Spors"
            r'(?:sagt|erklärt|freut sich|betont)\s+(?:Sportdirektor|Sportvorstand|Geschäftsführer)\s+([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+){1,3})',
        ]

        # Role keywords for classification
        role_mapping = {
            "Sportdirektor": "Sportdirektor",
            "Sportvorstand": "Sportvorstand",
            "Geschäftsführer": "Geschäftsführer",
            "CEO": "CEO",
            "Präsident": "Präsident",
        }

        hiring_managers = []
        found_names = set()

        for pattern in patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                name = match.group(1).strip()

                # Get surrounding context to determine role
                context_start = max(0, match.start() - 100)
                context_end = min(len(text), match.end() + 100)
                context = text[context_start:context_end]

                role = "Executive"
                for role_key, role_value in role_mapping.items():
                    if role_key in context:
                        role = role_value
                        break

                # Validate: must be 2-4 words (reasonable name length)
                word_count = len(name.split())
                if 2 <= word_count <= 4 and name not in found_names:
                    found_names.add(name)
                    hiring_managers.append({
                        "name": name,
                        "role": role,
                        "source": "transfermarkt_news",
                        "connection_type": "hiring_manager",
                        "article_url": article_url
                    })

        return hiring_managers

    except Exception as e:
        print(f"    Error extracting from article: {e}")
        return []


def find_hiring_managers(coach_name: str, club_name: str, start_date: str) -> Dict:
    """
    Find hiring managers for a coach at a specific club.

    Args:
        coach_name: Coach name
        club_name: Club name
        start_date: Start date at club (format: MM.YYYY)

    Returns:
        Dict with hiring_managers, article_url, and metadata
    """
    # Check cache
    cached = load_from_cache(coach_name, club_name)
    if cached:
        print(f"  ✓ Using cached result for {coach_name} at {club_name}")
        return cached

    # Search for article
    article_url = search_transfermarkt_news(coach_name, club_name, start_date)

    if not article_url:
        result = {
            "hiring_managers": [],
            "found": False,
            "article_url": None
        }
        save_to_cache(coach_name, club_name, result)
        return result

    # Extract hiring managers from article
    hiring_managers = extract_hiring_managers_from_article(article_url)

    result = {
        "hiring_managers": hiring_managers,
        "found": len(hiring_managers) > 0,
        "article_url": article_url,
        "club_name": club_name
    }

    save_to_cache(coach_name, club_name, result)
    return result


if __name__ == "__main__":
    # Test with known examples
    print("\n=== Testing Transfermarkt News Scraper ===\n")

    tests = [
        ("Alexander Blessin", "Genua CFC", "01.2022"),
        ("Alexander Blessin", "FC St. Pauli", "07.2024"),
        ("Albert Riera", "Eintracht Frankfurt", "12.2024"),
        ("Vincent Kompany", "Bayern München", "05.2024"),
    ]

    for coach, club, date in tests:
        print(f"\n--- {coach} at {club} ({date}) ---")
        result = find_hiring_managers(coach, club, date)

        if result["found"]:
            print(f"✅ Found {len(result['hiring_managers'])} hiring manager(s)")
            for hm in result["hiring_managers"]:
                print(f"  - {hm['name']} ({hm['role']})")
            print(f"  Article: {result['article_url']}")
        else:
            print(f"❌ No hiring managers found")
