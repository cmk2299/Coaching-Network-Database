#!/usr/bin/env python3
"""
Press Release Scraper for Coach-Sports Director Connections
Finds hiring announcements and extracts decision maker names

Strategy:
1. Search Google News for "{coach_name} {club_name} verpflichtet Trainer"
2. Parse press releases for keywords: "Sportdirektor", "verpflichtet", "präsentiert"
3. Extract names mentioned near these keywords
4. Build decision maker relationships from hiring context

Examples:
- "Sportdirektor Johannes Spors verpflichtet Alexander Blessin"
- "Max Eberl präsentiert neuen Trainer Vincent Kompany"
"""

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

# Directories
BASE_DIR = Path(__file__).parent.parent
CACHE_DIR = BASE_DIR / "tmp" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}


def search_coaching_announcement(coach_name: str, club_name: str, year: str = None) -> List[Dict]:
    """
    Search for coaching announcement articles.

    Args:
        coach_name: Coach name (e.g., "Alexander Blessin")
        club_name: Club name (e.g., "Genua")
        year: Optional year for more precise results

    Returns:
        List of article URLs and snippets
    """
    # Build search query
    search_terms = [
        f"{coach_name} {club_name} Trainer verpflichtet",
        f"{coach_name} {club_name} neuer Cheftrainer",
        f"{coach_name} {club_name} Sportdirektor",
    ]

    if year:
        search_terms = [f"{term} {year}" for term in search_terms]

    results = []

    for query in search_terms:
        # Use DuckDuckGo for privacy-friendly search
        search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"

        try:
            time.sleep(2)  # Rate limiting
            response = requests.get(search_url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(response.text, "lxml")

            # Find result links
            links = soup.find_all("a", class_="result__url", limit=5)

            for link in links:
                url = link.get("href", "")
                if url and any(source in url for source in ["kicker", "transfermarkt", "fcstpauli", "genoa"]):
                    results.append({
                        "url": url,
                        "query": query,
                        "source": "duckduckgo"
                    })
        except Exception as e:
            print(f"  Search error for '{query}': {e}")
            continue

    return results


def extract_decision_makers_from_article(url: str) -> List[Dict]:
    """
    Extract decision maker names from a press release article.

    Looks for patterns like:
    - "Sportdirektor [Name] verpflichtet"
    - "[Name], Sportdirektor des [Club]"
    - "präsentiert von [Name]"
    """
    try:
        time.sleep(2)
        response = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.text, "lxml")

        # Get article text
        article_text = ""

        # Try common article containers
        article = (
            soup.find("article") or
            soup.find("div", class_=lambda x: x and "article" in x.lower() if x else False) or
            soup.find("div", class_=lambda x: x and "content" in x.lower() if x else False)
        )

        if article:
            article_text = article.get_text(separator=" ", strip=True)
        else:
            # Fallback: get all text
            article_text = soup.get_text(separator=" ", strip=True)

        # Extract decision makers
        decision_makers = []

        # Pattern 1: "Sportdirektor [Name]"
        pattern1 = r'Sportdirektor\s+([A-ZÄÖÜ][a-zäöüß]+\s+[A-ZÄÖÜ][a-zäöüß]+)'
        matches1 = re.findall(pattern1, article_text)

        for name in matches1:
            decision_makers.append({
                "name": name,
                "role": "Sportdirektor",
                "context": "mentioned as Sportdirektor",
                "source_url": url
            })

        # Pattern 2: "Geschäftsführer Sport [Name]"
        pattern2 = r'Geschäftsführer\s+Sport\s+([A-ZÄÖÜ][a-zäöüß]+\s+[A-ZÄÖÜ][a-zäöüß]+)'
        matches2 = re.findall(pattern2, article_text)

        for name in matches2:
            decision_makers.append({
                "name": name,
                "role": "Geschäftsführer Sport",
                "context": "mentioned as Geschäftsführer Sport",
                "source_url": url
            })

        # Pattern 3: "[Name], Sportdirektor"
        pattern3 = r'([A-ZÄÖÜ][a-zäöüß]+\s+[A-ZÄÖÜ][a-zäöüß]+),?\s+Sportdirektor'
        matches3 = re.findall(pattern3, article_text)

        for name in matches3:
            if name not in [dm["name"] for dm in decision_makers]:
                decision_makers.append({
                    "name": name,
                    "role": "Sportdirektor",
                    "context": "mentioned as Sportdirektor",
                    "source_url": url
                })

        # Pattern 4: Look for specific hiring verbs
        # "Max Eberl verpflichtet" or "Max Eberl präsentiert"
        pattern4 = r'([A-ZÄÖÜ][a-zäöüß]+\s+[A-ZÄÖÜ][a-zäöüß]+)\s+(verpflichtet|präsentiert|holt)'
        matches4 = re.findall(pattern4, article_text)

        for name, verb in matches4:
            # Check if this name is near keywords
            name_context = article_text[max(0, article_text.find(name)-50):article_text.find(name)+100]
            if any(kw in name_context for kw in ["Sportdirektor", "Geschäftsführer", "Manager"]):
                if name not in [dm["name"] for dm in decision_makers]:
                    decision_makers.append({
                        "name": name,
                        "role": "Hiring Manager",
                        "context": f"used verb '{verb}' in hiring context",
                        "source_url": url
                    })

        return decision_makers

    except Exception as e:
        print(f"  Error extracting from {url}: {e}")
        return []


def find_decision_makers_for_hire(coach_name: str, club_name: str, year: str = None) -> Dict:
    """
    Find decision makers involved in hiring a coach.

    Returns:
        Dict with found decision makers and sources
    """
    print(f"\n🔍 Searching press releases for: {coach_name} at {club_name}")

    # Search for articles
    articles = search_coaching_announcement(coach_name, club_name, year)
    print(f"   Found {len(articles)} potential articles")

    # Extract decision makers from each article
    all_decision_makers = []

    for article in articles[:3]:  # Limit to first 3 to avoid rate limits
        print(f"   Analyzing: {article['url'][:60]}...")
        dms = extract_decision_makers_from_article(article["url"])
        all_decision_makers.extend(dms)

    # Deduplicate
    unique_dms = {}
    for dm in all_decision_makers:
        name = dm["name"]
        if name not in unique_dms:
            unique_dms[name] = dm
        else:
            # Merge context
            unique_dms[name]["context"] += f"; {dm['context']}"

    result = {
        "coach_name": coach_name,
        "club_name": club_name,
        "year": year,
        "decision_makers": list(unique_dms.values()),
        "articles_analyzed": len(articles),
        "scraped_at": datetime.now().isoformat()
    }

    return result


if __name__ == "__main__":
    import sys

    # Test cases from user examples
    test_cases = [
        ("Alexander Blessin", "Genua", "2022"),  # Should find Johannes Spors
        ("Albert Riera", "Eintracht Frankfurt", "2024"),  # Should find Krösche
        ("Daniel Thioune", "Werder Bremen", "2023"),  # Should find Fritz
    ]

    for coach, club, year in test_cases:
        result = find_decision_makers_for_hire(coach, club, year)

        print(f"\n{'='*60}")
        print(f"Results for {coach} at {club} ({year}):")
        print(f"{'='*60}")

        if result["decision_makers"]:
            for dm in result["decision_makers"]:
                print(f"✅ {dm['name']} - {dm['role']}")
                print(f"   Context: {dm['context']}")
                print(f"   Source: {dm['source_url'][:60]}...")
        else:
            print("❌ No decision makers found")

        print()
        time.sleep(3)  # Rate limiting between coaches
