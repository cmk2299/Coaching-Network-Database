#!/usr/bin/env python3
"""
Enrich coaches database with Transfermarkt profile data.

Reads blessin_full_network.json and for each contact with tm_url:
- Scrapes nationality, DOB, age, license, agent info, current club
- Saves enrichment data to profile_enrichment.json
- Updates blessin_full_network.json with new fields
"""

import json
import time
import sys
from pathlib import Path
from typing import Dict, Optional, Any, Tuple
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# Configuration
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
TMP_DIR = BASE_DIR / ".." / "tmp"
TMP_DIR.mkdir(parents=True, exist_ok=True)

INPUT_FILE = DATA_DIR / "blessin_full_network.json"
OUTPUT_FILE = DATA_DIR / "profile_enrichment.json"
CACHE_FILE = TMP_DIR / "transfermarkt_cache.json"

TM_BASE = "https://www.transfermarkt.de"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9",
}

# Rate limiting
DELAY_BETWEEN_REQUESTS = 3.0  # seconds


def load_cache() -> Dict[str, Any]:
    """Load the cache of previously scraped profiles."""
    if CACHE_FILE.exists():
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_cache(cache: Dict[str, Any]):
    """Save the cache."""
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def normalize_url(tm_url: str) -> Optional[str]:
    """Normalize Transfermarkt URLs."""
    if not tm_url:
        return None

    # If it's a relative URL, prepend the base
    if tm_url.startswith('/'):
        tm_url = TM_BASE + tm_url

    # Ensure .de domain (convert .com to .de if needed)
    tm_url = tm_url.replace('transfermarkt.com', 'transfermarkt.de')

    return tm_url


def fetch_profile_page(url: str) -> Optional[str]:
    """Fetch a Transfermarkt profile page."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"    ERROR fetching: {e}", file=sys.stderr)
        return None


def extract_from_info_table(soup: BeautifulSoup, search_key: str) -> Optional[str]:
    """
    Extract value from info table row by searching for label containing search_key.
    Returns None if not found.
    """
    try:
        rows = soup.find_all('tr')
        for row in rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True).lower()
                if search_key.lower() in label:
                    value = cells[1].get_text(strip=True)
                    return value if value else None
    except Exception:
        pass

    return None


def parse_nationality(soup: BeautifulSoup) -> Optional[str]:
    """Extract nationality from profile page."""
    value = extract_from_info_table(soup, "nationalität")
    if value:
        # Remove flag emojis
        value = ''.join(c for c in value if ord(c) < 0x1F000)
        return value.strip() if value.strip() else None
    return None


def parse_dob_and_age(soup: BeautifulSoup) -> Tuple[Optional[str], Optional[str]]:
    """Extract date of birth and age from profile page."""
    value = extract_from_info_table(soup, "geb")
    if value:
        # Format: "22.08.1962 (63)" or "29.04.1980 (45)"
        # Extract the date part and the age part separately
        dob = None
        age = None

        if '(' in value and ')' in value:
            # Extract date before the parenthesis
            dob_part = value[:value.index('(')].strip()
            age_part = value[value.index('(')+1:value.index(')')].strip()

            dob = dob_part if dob_part else None
            age = age_part if age_part else None
        else:
            # Just date, no age
            dob = value.strip() if value.strip() else None

        return dob, age
    return None, None


def parse_license(soup: BeautifulSoup) -> Optional[str]:
    """Extract coaching license from profile page."""
    # Try direct lookup
    value = extract_from_info_table(soup, "lizenz")
    if value:
        return value

    # Look for license keywords in page text
    page_text = soup.get_text()
    for license_type in ['UEFA-Pro-Lizenz', 'UEFA A-Lizenz', 'UEFA B-Lizenz', 'UEFA C-Lizenz',
                         'DFB-A-Lizenz', 'DFB-B-Lizenz', 'DFB-C-Lizenz',
                         'UEFA Pro', 'UEFA A', 'UEFA B', 'UEFA C']:
        if license_type.lower() in page_text.lower():
            return license_type

    return None


def parse_agent_info(soup: BeautifulSoup) -> Tuple[Optional[str], Optional[str]]:
    """Extract agent name and agency from profile page."""
    value = extract_from_info_table(soup, "spielerberater")
    if value:
        # Often formatted as "Agent Name (Agency Name)" or just "Agent Name"
        if '(' in value and ')' in value:
            agent_name = value[:value.index('(')].strip()
            agent_agency = value[value.index('(')+1:value.index(')')].strip()
            return agent_name if agent_name else None, agent_agency if agent_agency else None
        else:
            return value if value else None, None

    # Try looking for "agent" directly
    value = extract_from_info_table(soup, "agent")
    if value:
        return value if value else None, None

    return None, None


def parse_current_club(soup: BeautifulSoup) -> Optional[str]:
    """Extract current club from profile page."""
    try:
        # Look for first club in career history table
        # The career table usually has rows with "wappen" (empty cell with club crest) and club name
        rows = soup.find_all('tr')

        # Skip header rows and find first actual club entry
        skip_until = -1
        for i, row in enumerate(rows):
            if 'wappen' in row.get_text().lower():
                skip_until = i
                break

        if skip_until >= 0 and skip_until + 1 < len(rows):
            # Next row after the header should be the current club
            row = rows[skip_until + 1]
            cells = row.find_all('td')
            if len(cells) >= 2:
                # Second cell usually contains the club name and role
                value = cells[1].get_text(strip=True)
                if value:
                    # Remove role suffixes to get just the club name
                    for role in ['Trainer', 'Co-Trainer', 'Interimstrainer', 'Assistenztrainer', 'Athletiktrainer']:
                        value = value.replace(role, '').strip()
                    # Clean up extra whitespace
                    value = ' '.join(value.split())
                    return value if value and len(value) > 2 else None
    except Exception:
        pass

    return None


def scrape_coach_profile(contact_name: str, tm_url: str, cache: Dict) -> Dict[str, Any]:
    """
    Scrape a coach's Transfermarkt profile.

    Returns a dict with keys: nationality, dob, age, license, agent_name, agent_agency, current_club
    """
    result = {
        "name": contact_name,
        "tm_url": tm_url,
        "timestamp": datetime.now().isoformat(),
        "nationality": None,
        "dob": None,
        "age": None,
        "license": None,
        "agent_name": None,
        "agent_agency": None,
        "current_club": None,
    }

    # Normalize URL
    normalized_url = normalize_url(tm_url)
    if not normalized_url:
        print("    SKIP: Invalid URL", file=sys.stderr)
        return result

    # Check cache
    if normalized_url in cache:
        cached = cache[normalized_url]
        return {**result, **cached}

    # Fetch page
    print("    Fetching...", file=sys.stderr)
    html = fetch_profile_page(normalized_url)
    if not html:
        return result

    # Parse
    soup = BeautifulSoup(html, 'html.parser')

    result["nationality"] = parse_nationality(soup)
    result["dob"], result["age"] = parse_dob_and_age(soup)
    result["license"] = parse_license(soup)
    result["agent_name"], result["agent_agency"] = parse_agent_info(soup)
    result["current_club"] = parse_current_club(soup)

    # Cache the result (without timestamp for cleaner cache)
    cache_entry = {
        "nationality": result["nationality"],
        "dob": result["dob"],
        "age": result["age"],
        "license": result["license"],
        "agent_name": result["agent_name"],
        "agent_agency": result["agent_agency"],
        "current_club": result["current_club"],
    }
    cache[normalized_url] = cache_entry

    return result


def main():
    """Main orchestration function."""
    print(f"\n{'='*80}")
    print("TRANSFERMARKT PROFILE ENRICHMENT")
    print(f"{'='*80}\n")

    # Load input data
    print("Loading input data...")
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        network_data = json.load(f)

    contacts = network_data.get('contacts', [])
    print(f"Total contacts: {len(contacts)}")

    # Filter contacts with tm_url
    contacts_with_url = [c for c in contacts if 'tm_url' in c and c['tm_url']]
    print(f"Contacts with tm_url: {len(contacts_with_url)}\n")

    # Load cache
    cache = load_cache()
    print(f"Loaded cache with {len(cache)} entries\n")

    # Scrape profiles
    enrichment_results = {}

    for idx, contact in enumerate(contacts_with_url, 1):
        name = contact.get('name', 'Unknown')
        tm_url = contact.get('tm_url')

        print(f"[{idx:2d}/{len(contacts_with_url)}] {name}")

        result = scrape_coach_profile(name, tm_url, cache)
        enrichment_results[name] = result

        # Print what we found
        found = [k for k, v in result.items() if v and k not in ['name', 'tm_url', 'timestamp']]
        if found:
            print(f"    Found: {', '.join(found)}")
        else:
            print("    Found: (no fields)")

        # Save intermediate results every 10 contacts
        if idx % 10 == 0:
            print("  [Checkpoint] Saving intermediate results...")
            with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                json.dump(enrichment_results, f, indent=2, ensure_ascii=False)
            save_cache(cache)

        # Rate limiting
        if idx < len(contacts_with_url):
            time.sleep(DELAY_BETWEEN_REQUESTS)

    # Save final results
    print(f"\n{'='*80}")
    print("Saving results...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(enrichment_results, f, indent=2, ensure_ascii=False)
    print(f"Enrichment results: {OUTPUT_FILE}")

    # Save cache
    save_cache(cache)
    print(f"Cache: {CACHE_FILE}")

    # Update original network file
    print("\nUpdating original network file...")
    for contact in contacts:
        name = contact.get('name')
        if name in enrichment_results:
            enriched = enrichment_results[name]
            # Add enriched fields to contact
            contact['nationality'] = enriched.get('nationality')
            contact['dob'] = enriched.get('dob')
            contact['age'] = enriched.get('age')
            contact['license'] = enriched.get('license')
            contact['agent_name'] = enriched.get('agent_name')
            contact['agent_agency'] = enriched.get('agent_agency')
            contact['current_club'] = enriched.get('current_club')

    with open(INPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(network_data, f, indent=2, ensure_ascii=False)
    print(f"Updated: {INPUT_FILE}")

    # Summary statistics
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    for field in ['nationality', 'dob', 'age', 'license', 'agent_name', 'agent_agency', 'current_club']:
        count = sum(1 for r in enrichment_results.values() if r.get(field))
        print(f"{field:20s}: {count:3d} / {len(contacts_with_url)}")

    print("\nDone!")


if __name__ == "__main__":
    main()
