#!/usr/bin/env python3
"""
Scrape club websites for coach hiring announcements.
Extract hiring managers (Sportdirektor, CEO, President) from official press releases.
"""

import json
import re
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
import requests
from urllib.parse import urljoin, urlparse

# Cache directory
CACHE_DIR = Path(__file__).resolve().parent.parent / "tmp" / "cache" / "club_news"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Club websites mapping
CLUBS_FILE = Path(__file__).resolve().parent.parent / "data" / "club_websites.json"

# Cache duration: 90 days (coach announcements don't change)
CACHE_DURATION_DAYS = 90

# User agent to avoid blocking
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def load_club_websites() -> Dict:
    """Load club website mappings."""
    if not CLUBS_FILE.exists():
        return {"clubs": {}}

    with open(CLUBS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_cache_path(club_name: str, coach_name: str) -> Path:
    """Get cache file path for club + coach combination."""
    safe_club = re.sub(r'[^\w\s-]', '', club_name).strip().replace(' ', '_')
    safe_coach = re.sub(r'[^\w\s-]', '', coach_name).strip().replace(' ', '_')
    return CACHE_DIR / f"{safe_club}_{safe_coach}.json"


def load_cached_result(club_name: str, coach_name: str) -> Optional[Dict]:
    """Load cached result if available and not expired."""
    cache_path = get_cache_path(club_name, coach_name)

    if not cache_path.exists():
        return None

    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            cached = json.load(f)

        cached_time = datetime.fromisoformat(cached.get("cached_at", ""))
        age = datetime.now() - cached_time

        if age.days < CACHE_DURATION_DAYS:
            return cached.get("result")
    except:
        pass

    return None


def save_to_cache(club_name: str, coach_name: str, result: Dict):
    """Save result to cache."""
    cache_path = get_cache_path(club_name, coach_name)

    cache_data = {
        "cached_at": datetime.now().isoformat(),
        "club_name": club_name,
        "coach_name": coach_name,
        "result": result
    }

    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(cache_data, f, indent=2, ensure_ascii=False)


def fetch_page(url: str, delay: float = 2.0) -> Optional[BeautifulSoup]:
    """Fetch and parse a webpage."""
    try:
        time.sleep(delay)
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return BeautifulSoup(response.text, 'lxml')
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None


def search_club_news_via_google(club_website: str, coach_name: str, year: Optional[int] = None) -> List[str]:
    """
    Use DuckDuckGo to search for coach announcements on club website.
    More reliable than scraping news pages directly.
    """
    try:
        # Build search query
        query_parts = [
            f"site:{urlparse(club_website).netloc}",
            coach_name,
            "neuer trainer" if not any(char.isdigit() for char in club_website) else "nuovo allenatore"
        ]

        if year:
            query_parts.append(str(year))

        query = " ".join(query_parts)

        # Use DuckDuckGo HTML search (no JS required)
        search_url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"

        time.sleep(2)
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'lxml')

        # Extract result links
        article_urls = []
        for link in soup.find_all('a', class_='result__a'):
            href = link.get('href', '')
            if href and club_website in href:
                article_urls.append(href)

        return article_urls[:5]

    except Exception as e:
        print(f"  Google search failed: {e}")
        return []


def search_club_news(club_info: Dict, coach_name: str, year: Optional[int] = None) -> List[str]:
    """
    Search club news section for articles about the coach.
    Returns list of article URLs that might contain hiring announcement.

    Uses two strategies:
    1. Direct search via DuckDuckGo (more reliable)
    2. Fallback: Scrape news page
    """
    base_url = club_info.get("website", "")

    # Strategy 1: Use DuckDuckGo
    article_urls = search_club_news_via_google(base_url, coach_name, year)
    if article_urls:
        return article_urls

    # Strategy 2: Direct scraping (fallback)
    news_url = club_info.get("news_url")
    if not news_url:
        return []

    # Fetch news overview page
    soup = fetch_page(news_url, delay=2.0)
    if not soup:
        return []

    # Find all article links
    article_urls = []

    # Look for links containing coach name or "trainer" keywords
    coach_keywords = coach_name.lower().split()
    trainer_keywords = ["trainer", "coach", "neuer", "verpflichtet", "verkündet", "nuovo", "allenatore"]

    for link in soup.find_all('a', href=True):
        href = link.get('href', '')
        text = link.get_text(strip=True).lower()

        # Check if link or text mentions the coach
        has_coach = any(kw in text or kw in href.lower() for kw in coach_keywords)
        has_trainer = any(kw in text or kw in href.lower() for kw in trainer_keywords)

        if has_coach and has_trainer:
            # Convert relative to absolute URL
            full_url = urljoin(base_url, href)

            # Filter by year if provided
            if year:
                if str(year) in href or str(year) in text:
                    article_urls.append(full_url)
            else:
                article_urls.append(full_url)

    # Limit to top 5 most relevant articles
    return article_urls[:5]


def extract_hiring_managers(text: str, language: str = "de") -> List[Dict]:
    """
    Extract hiring manager names and titles from press release text.
    Uses pattern matching for German/Italian/Dutch announcements.
    """
    hiring_managers = []

    # German patterns
    de_patterns = [
        # "Sportdirektor Max Eberl sagt: ..."
        r'(?:Sportdirektor|Sportvorstand|Geschäftsführer|CEO|Präsident|Vorstandsvorsitzender)\s+([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)*)',
        # "Max Eberl, Sportdirektor, erklärt ..."
        r'([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)*),\s*(?:Sportdirektor|Sportvorstand|Geschäftsführer|CEO|Präsident)',
        # Direct quote introduction
        r'(?:sagt|erklärt|freut sich|betont)\s+([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)*),\s*(?:Sportdirektor|Sportvorstand|Geschäftsführer)',
    ]

    # Italian patterns
    it_patterns = [
        r'(?:Direttore Sportivo|Amministratore Delegato|Presidente)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*(?:Direttore Sportivo|Amministratore Delegato|Presidente)',
    ]

    # Dutch patterns
    nl_patterns = [
        r'(?:Technisch Directeur|CEO|Voorzitter)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*(?:Technisch Directeur|CEO|Voorzitter)',
    ]

    patterns = de_patterns
    if language == "it":
        patterns = it_patterns
    elif language == "nl":
        patterns = nl_patterns

    # Role mapping for German
    role_titles = {
        "Sportdirektor": "Sportdirektor",
        "Sportvorstand": "Sportvorstand",
        "Geschäftsführer": "Geschäftsführer",
        "CEO": "CEO",
        "Präsident": "Präsident",
        "Vorstandsvorsitzender": "Vorstandsvorsitzender",
        "Direttore Sportivo": "Direttore Sportivo",
        "Amministratore Delegato": "CEO",
        "Presidente": "Präsident",
        "Technisch Directeur": "Technisch Directeur",
        "Voorzitter": "Voorzitter",
    }

    found_names = set()

    for pattern in patterns:
        matches = re.finditer(pattern, text)
        for match in matches:
            name = match.group(1).strip()

            # Extract role from context
            context = text[max(0, match.start()-50):match.end()+50]
            role = "Executive"

            for role_key, role_value in role_titles.items():
                if role_key in context:
                    role = role_value
                    break

            # Avoid duplicates
            if name not in found_names and len(name.split()) >= 2:
                found_names.add(name)
                hiring_managers.append({
                    "name": name,
                    "role": role,
                    "source": "club_website",
                    "connection_type": "hiring_manager"
                })

    return hiring_managers


def scrape_coach_announcement(club_name: str, coach_name: str, year: Optional[int] = None) -> Dict:
    """
    Scrape club website for coach hiring announcement.

    Args:
        club_name: Name of the club
        coach_name: Name of the coach
        year: Year of hiring (optional, helps filter results)

    Returns:
        Dict with hiring_managers found, article_url, and metadata
    """
    # Check cache first
    cached = load_cached_result(club_name, coach_name)
    if cached:
        return cached

    # Load club websites
    clubs_data = load_club_websites()
    club_info = clubs_data.get("clubs", {}).get(club_name)

    if not club_info:
        print(f"No website info for club: {club_name}")
        return {"hiring_managers": [], "found": False}

    print(f"Searching {club_name} news for {coach_name}...")

    # Search for relevant articles
    article_urls = search_club_news(club_info, coach_name, year)

    if not article_urls:
        result = {
            "hiring_managers": [],
            "found": False,
            "searched_url": club_info.get("news_url")
        }
        save_to_cache(club_name, coach_name, result)
        return result

    print(f"  Found {len(article_urls)} relevant articles")

    # Scrape each article and extract hiring managers
    all_hiring_managers = []
    article_url = None
    language = club_info.get("language", "de")

    for url in article_urls:
        soup = fetch_page(url, delay=2.0)
        if not soup:
            continue

        # Extract main article text
        article_text = soup.get_text(separator=' ', strip=True)

        # Extract hiring managers
        managers = extract_hiring_managers(article_text, language)

        if managers:
            article_url = url
            all_hiring_managers.extend(managers)
            print(f"  ✓ Found {len(managers)} hiring manager(s) in article")
            break  # Found what we need

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
        "article_url": article_url,
        "club_name": club_name,
        "searched_url": club_info.get("news_url")
    }

    # Cache result
    save_to_cache(club_name, coach_name, result)

    return result


if __name__ == "__main__":
    # Test with Blessin at St. Pauli and Genua
    print("\n=== Testing Club News Scraper ===\n")

    # Test 1: Blessin at St. Pauli (2024)
    result1 = scrape_coach_announcement("FC St. Pauli", "Alexander Blessin", year=2024)
    print(f"\nResult for Blessin at St. Pauli:")
    print(json.dumps(result1, indent=2, ensure_ascii=False))

    # Test 2: Blessin at Genua (2022)
    result2 = scrape_coach_announcement("Genua CFC", "Alexander Blessin", year=2022)
    print(f"\nResult for Blessin at Genua:")
    print(json.dumps(result2, indent=2, ensure_ascii=False))

    # Test 3: Riera at Eintracht Frankfurt (2024)
    result3 = scrape_coach_announcement("Eintracht Frankfurt", "Albert Riera", year=2024)
    print(f"\nResult for Riera at Frankfurt:")
    print(json.dumps(result3, indent=2, ensure_ascii=False))
