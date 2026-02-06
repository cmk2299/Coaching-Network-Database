#!/usr/bin/env python3
"""
Scrape agent and contract details for players.
Fetches data from individual player profiles.
"""

import json
import os
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List

import requests
from bs4 import BeautifulSoup

# Base URL
TM_BASE = "https://www.transfermarkt.de"

# Directories
BASE_DIR = Path(__file__).parent.parent
CACHE_DIR = BASE_DIR / "tmp" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Request headers
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}


def get_cache_path(cache_key: str) -> Path:
    """Get path for cache file."""
    return CACHE_DIR / f"{cache_key}.json"


def load_from_cache(cache_key: str, max_age_hours: int = 24) -> Optional[dict]:
    """Load data from cache if fresh enough."""
    cache_path = get_cache_path(cache_key)
    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            cached_at = datetime.fromisoformat(data.get("cached_at", "2000-01-01"))
            if datetime.now() - cached_at < timedelta(hours=max_age_hours):
                return data
        except (json.JSONDecodeError, ValueError):
            pass
    return None


def save_to_cache(cache_key: str, data: dict):
    """Save data to cache."""
    data["cached_at"] = datetime.now().isoformat()
    cache_path = get_cache_path(cache_key)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def fetch_page(url: str, delay: float = 1.5) -> Optional[BeautifulSoup]:
    """Fetch a page and return BeautifulSoup object."""
    try:
        time.sleep(delay)  # Rate limiting
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return BeautifulSoup(response.text, "lxml")
    except requests.RequestException as e:
        print(f"  Error fetching {url}: {e}")
        return None


def scrape_player_details(player_url: str, player_id: int) -> dict:
    """
    Scrape agent and contract info from a player's profile page.

    Returns dict with:
    - agent: Agent name
    - agent_url: Link to agent
    - contract_until: Contract end date
    - agent_since: When player joined this agent (if available)
    """
    cache_key = f"player_{player_id}_agent"

    # Check cache
    cached = load_from_cache(cache_key, max_age_hours=168)  # 7 days cache
    if cached:
        return cached

    # Build profile URL if needed
    if "/profil/spieler/" not in player_url:
        # Convert other URL formats to profile
        player_url = re.sub(r"/leistungsdaten\w*/spieler/", "/profil/spieler/", player_url)

    soup = fetch_page(player_url, delay=1.0)
    if not soup:
        return {"player_id": player_id, "agent": None, "contract_until": None}

    result = {
        "player_id": player_id,
        "agent": None,
        "agent_url": None,
        "contract_until": None,
    }

    # Parse from info-table spans
    for span in soup.find_all("span", class_="info-table__content"):
        prev = span.find_previous("span")
        if not prev:
            continue

        label = prev.get_text(strip=True).lower()
        value = span.get_text(strip=True)

        if "spielerberater" in label or "berater" in label:
            result["agent"] = value
            link = span.find("a")
            if link and link.get("href"):
                result["agent_url"] = TM_BASE + link["href"]

        elif "vertrag bis" in label:
            result["contract_until"] = value

    # Also check table rows
    for row in soup.find_all("tr"):
        th = row.find("th")
        td = row.find("td")
        if th and td:
            label = th.get_text(strip=True).lower()
            value = td.get_text(strip=True)

            if "spielerberater" in label and not result["agent"]:
                result["agent"] = value
                link = td.find("a")
                if link and link.get("href"):
                    result["agent_url"] = TM_BASE + link["href"]

            elif "vertrag bis" in label and not result["contract_until"]:
                result["contract_until"] = value

    # Cache result
    save_to_cache(cache_key, result)

    return result


def enrich_players_with_agents(players: List[dict], max_players: int = 25) -> List[dict]:
    """
    Enrich a list of players with agent and contract info.

    Args:
        players: List of player dicts (must have 'url' or 'player_id')
        max_players: Maximum number of players to process

    Returns:
        Updated list with agent info added to each player
    """
    print(f"\n  Fetching agent info for {min(len(players), max_players)} players...")

    enriched = []
    for i, player in enumerate(players[:max_players]):
        player_id = player.get("player_id")
        player_url = player.get("url", "")

        if not player_id and player_url:
            # Extract ID from URL
            match = re.search(r"/spieler/(\d+)", player_url)
            if match:
                player_id = int(match.group(1))

        if player_id:
            print(f"    [{i+1}/{min(len(players), max_players)}] {player.get('name', 'Unknown')}...")
            agent_info = scrape_player_details(player_url, player_id)

            # Merge agent info into player dict
            player["agent"] = agent_info.get("agent")
            player["agent_url"] = agent_info.get("agent_url")
            player["contract_until"] = agent_info.get("contract_until")

        enriched.append(player)

    return enriched


if __name__ == "__main__":
    # Test with a single player
    result = scrape_player_details(
        "https://www.transfermarkt.de/frederik-jakel/profil/spieler/405679",
        405679
    )
    print(f"Agent: {result.get('agent')}")
    print(f"Contract until: {result.get('contract_until')}")
