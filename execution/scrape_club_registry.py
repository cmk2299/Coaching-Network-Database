#!/usr/bin/env python3
"""
Phase 1: Club Registry Scraper
Scrapes all clubs that participated in BL1, BL2, BL3, and NLZ leagues
from Transfermarkt for seasons 2010/11 through 2024/25.

Output: data/club_registry.json
- Complete list of clubs with TM IDs, slugs, league participation per season
- ~120-150 unique clubs expected

Architecture: Layer 3 (Execution)
"""

import json
import time
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

# ── Config ──────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = BASE_DIR / "tmp" / "cache" / "club_registry"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

TM_BASE = "https://www.transfermarkt.de"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Cache-Control": "no-cache",
}
REQUEST_DELAY = 3  # seconds

# ── Leagues to crawl ────────────────────────────────
# TM league IDs and paths
LEAGUES = {
    "bundesliga": {
        "name": "1. Bundesliga",
        "short": "BL1",
        "path": "/1-bundesliga/startseite/wettbewerb/L1",
        "wettbewerb_id": "L1",
    },
    "2bundesliga": {
        "name": "2. Bundesliga",
        "short": "BL2",
        "path": "/2-bundesliga/startseite/wettbewerb/L2",
        "wettbewerb_id": "L2",
    },
    "3liga": {
        "name": "3. Liga",
        "short": "BL3",
        "path": "/3-liga/startseite/wettbewerb/L3",
        "wettbewerb_id": "L3",
    },
    # NLZ leagues — A-Junioren Bundesliga (U19) ist in 3 Staffeln aufgeteilt.
    # Parent BJL gibt nur Endrunden-Teilnehmer; einzelne Staffeln liefern die
    # vollständigen Saison-Kader. Werder Bremen U19, alle BL-Akademien etc.
    # werden so erfasst.
    "u19_nordnordost": {
        "name": "A-Junioren Bundesliga Nord/Nordost",
        "short": "U19-N",
        "path": "/a-junioren-bundesliga-staffel-nordnordost/startseite/wettbewerb/JBLN",
        "wettbewerb_id": "JBLN",
    },
    "u19_west": {
        "name": "A-Junioren Bundesliga West",
        "short": "U19-W",
        "path": "/a-junioren-bundesliga-staffel-west/startseite/wettbewerb/JBLW",
        "wettbewerb_id": "JBLW",
    },
    "u19_sudsudwest": {
        "name": "A-Junioren Bundesliga Süd/Südwest",
        "short": "U19-S",
        "path": "/a-junioren-bundesliga-staffel-sudsudwest/startseite/wettbewerb/JBLS",
        "wettbewerb_id": "JBLS",
    },
    "u19_endrunde": {
        "name": "A-Junioren Bundesliga Endrunde",
        "short": "U19-E",
        "path": "/a-junioren-bundesliga/startseite/wettbewerb/BJL",
        "wettbewerb_id": "BJL",
    },
    # U17 ist ähnlich in 3 Staffeln aufgeteilt
    "u17_nordnordost": {
        "name": "B-Junioren Bundesliga Nord/Nordost",
        "short": "U17-N",
        "path": "/b-junioren-bundesliga-staffel-nordnordost/startseite/wettbewerb/BJLN",
        "wettbewerb_id": "BJLN",
    },
    "u17_west": {
        "name": "B-Junioren Bundesliga West",
        "short": "U17-W",
        "path": "/b-junioren-bundesliga-staffel-west/startseite/wettbewerb/BJLW",
        "wettbewerb_id": "BJLW",
    },
    "u17_sudsudwest": {
        "name": "B-Junioren Bundesliga Süd/Südwest",
        "short": "U17-S",
        "path": "/b-junioren-bundesliga-staffel-sudsudwest/startseite/wettbewerb/BJLS",
        "wettbewerb_id": "BJLS",
    },
    "u17_endrunde": {
        "name": "B-Junioren Bundesliga Endrunde",
        "short": "U17-E",
        "path": "/b-junioren-bundesliga/startseite/wettbewerb/BJ2",
        "wettbewerb_id": "BJ2",
    },
    # International leagues
    "la_liga": {
        "name": "La Liga",
        "short": "LIGA",
        "path": "/laliga/startseite/wettbewerb/ES1",
        "wettbewerb_id": "ES1",
    },
    "premier_league": {
        "name": "Premier League",
        "short": "PL",
        "path": "/premier-league/startseite/wettbewerb/GB1",
        "wettbewerb_id": "GB1",
    },
    "ligue_1": {
        "name": "Ligue 1",
        "short": "L1FR",
        "path": "/ligue-1/startseite/wettbewerb/FR1",
        "wettbewerb_id": "FR1",
    },
    "serie_a": {
        "name": "Serie A",
        "short": "SA",
        "path": "/serie-a/startseite/wettbewerb/IT1",
        "wettbewerb_id": "IT1",
    },
    "bundesliga_at": {
        "name": "Bundesliga (AT)",
        "short": "ABL",
        "path": "/bundesliga/startseite/wettbewerb/A1",
        "wettbewerb_id": "A1",
    },
    # P0: Direct BL Coach Impact
    "belgian_pro_league": {
        "name": "Jupiler Pro League",
        "short": "BEL",
        "path": "/jupiler-pro-league/startseite/wettbewerb/BE1",
        "wettbewerb_id": "BE1",
    },
    "swiss_super_league": {
        "name": "Super League",
        "short": "SUI",
        "path": "/super-league/startseite/wettbewerb/C1",
        "wettbewerb_id": "C1",
    },
    "turkish_super_lig": {
        "name": "Süper Lig",
        "short": "TUR",
        "path": "/super-lig/startseite/wettbewerb/TR1",
        "wettbewerb_id": "TR1",
    },
    "danish_superliga": {
        "name": "Superliga",
        "short": "DEN",
        "path": "/superligaen/startseite/wettbewerb/DK1",
        "wettbewerb_id": "DK1",
    },
    "swedish_allsvenskan": {
        "name": "Allsvenskan",
        "short": "SWE",
        "path": "/allsvenskan/startseite/wettbewerb/SE1",
        "wettbewerb_id": "SE1",
    },
    "norwegian_eliteserien": {
        "name": "Eliteserien",
        "short": "NOR",
        "path": "/eliteserien/startseite/wettbewerb/NO1",
        "wettbewerb_id": "NO1",
    },
    # P1: Second Divisions of Top-5 + Austria
    "championship": {
        "name": "Championship",
        "short": "ENG2",
        "path": "/championship/startseite/wettbewerb/GB2",
        "wettbewerb_id": "GB2",
    },
    "serie_b": {
        "name": "Serie B",
        "short": "ITA2",
        "path": "/serieb/startseite/wettbewerb/IT2",
        "wettbewerb_id": "IT2",
    },
    "ligue_2": {
        "name": "Ligue 2",
        "short": "FRA2",
        "path": "/ligue-2/startseite/wettbewerb/FR2",
        "wettbewerb_id": "FR2",
    },
    "laliga2": {
        "name": "LaLiga2",
        "short": "ESP2",
        "path": "/laliga2/startseite/wettbewerb/ES2",
        "wettbewerb_id": "ES2",
    },
    "2liga_at": {
        "name": "2. Liga (AT)",
        "short": "AUT2",
        "path": "/2-liga/startseite/wettbewerb/A2",
        "wettbewerb_id": "A2",
    },
    "eerste_divisie": {
        "name": "Keuken Kampioen Divisie",
        "short": "NED2",
        "path": "/keuken-kampioen-divisie/startseite/wettbewerb/NL2",
        "wettbewerb_id": "NL2",
    },
    # P2: Broader European & Emerging
    "portuguese_liga": {
        "name": "Liga Portugal",
        "short": "POR",
        "path": "/liga-nos/startseite/wettbewerb/PO1",
        "wettbewerb_id": "PO1",
    },
    "scottish_premiership": {
        "name": "Scottish Premiership",
        "short": "SCO",
        "path": "/scottish-premiership/startseite/wettbewerb/SC1",
        "wettbewerb_id": "SC1",
    },
    "greek_super_league": {
        "name": "Super League 1",
        "short": "GRE",
        "path": "/super-league-1/startseite/wettbewerb/GR1",
        "wettbewerb_id": "GR1",
    },
    "croatian_hnl": {
        "name": "SuperSport HNL",
        "short": "CRO",
        "path": "/1-hnl/startseite/wettbewerb/KR1",
        "wettbewerb_id": "KR1",
    },
    "czech_liga": {
        "name": "Chance Liga",
        "short": "CZE",
        "path": "/chance-liga/startseite/wettbewerb/TS1",
        "wettbewerb_id": "TS1",
    },
    "polish_ekstraklasa": {
        "name": "Ekstraklasa",
        "short": "POL",
        "path": "/pko-bp-ekstraklasa/startseite/wettbewerb/PL1",
        "wettbewerb_id": "PL1",
    },
    "saudi_pro_league": {
        "name": "Saudi Pro League",
        "short": "KSA",
        "path": "/saudi-professional-league/startseite/wettbewerb/SA1",
        "wettbewerb_id": "SA1",
    },
}

# Seasons: 2010 = 2010/11 season, up to 2024 = 2024/25
SEASONS = list(range(2010, 2026))


# ── Helpers ─────────────────────────────────────────
def get_cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.html"


def fetch_page(url: str, cache_key: str) -> Optional[str]:
    """Fetch page with caching and rate limiting."""
    cache_path = get_cache_path(cache_key)

    # Check cache (7-day expiry for league tables)
    if cache_path.exists():
        age_hours = (datetime.now().timestamp() - cache_path.stat().st_mtime) / 3600
        if age_hours < 168:  # 7 days
            return cache_path.read_text(encoding="utf-8")

    time.sleep(REQUEST_DELAY)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        html = resp.text
        cache_path.write_text(html, encoding="utf-8")
        return html
    except Exception as e:
        print(f"  ERROR fetching {url}: {e}")
        return None


def extract_clubs_from_league_page(html: str) -> list[dict]:
    """Extract club names, TM IDs, and slugs from a league season page."""
    soup = BeautifulSoup(html, "html.parser")
    clubs = []
    seen_ids = set()

    # TM league tables have club links with pattern /club-slug/startseite/verein/ID
    # Also in squad tables: /club-slug/kader/verein/ID
    for link in soup.find_all("a", href=True):
        href = link["href"]
        # Match club profile links
        m = re.search(r"/([^/]+)/(?:startseite|kader)/verein/(\d+)", href)
        if m:
            slug = m.group(1)
            tm_id = int(m.group(2))
            if tm_id in seen_ids:
                continue
            seen_ids.add(tm_id)

            # Get club name from link text or title
            name = link.get("title", "") or link.get_text(strip=True)
            if not name or len(name) < 2:
                continue

            # Skip national teams, special entries
            if any(x in slug for x in ["nationalmannschaft", "fifa", "uefa"]):
                continue

            clubs.append({
                "tm_id": tm_id,
                "slug": slug,
                "name": name,
            })

    return clubs


def scrape_league_season(league_key: str, season: int) -> list[dict]:
    """Scrape all clubs for a league in a specific season."""
    league = LEAGUES[league_key]
    wid = league["wettbewerb_id"]

    # TM URL pattern for league table by season
    url = f"{TM_BASE}/{wid.lower()}/startseite/wettbewerb/{wid}/plus/?saison_id={season}"
    cache_key = f"{league_key}_{season}"

    print(f"  {league['short']} {season}/{season+1}...", end=" ", flush=True)
    html = fetch_page(url, cache_key)

    if not html:
        print("FAILED")
        return []

    clubs = extract_clubs_from_league_page(html)
    print(f"{len(clubs)} clubs")
    return clubs


def main():
    print("=" * 60)
    print("PHASE 1: Club Registry Scraper")
    print(f"Leagues: {', '.join(l['short'] for l in LEAGUES.values())}")
    print(f"Seasons: {SEASONS[0]}/{SEASONS[0]+1} – {SEASONS[-1]}/{SEASONS[-1]+1}")
    print("=" * 60)

    # Master registry: tm_id → club data
    registry = {}
    total_requests = 0

    for league_key, league_info in LEAGUES.items():
        print(f"\n── {league_info['name']} ({league_info['short']}) ──")

        for season in SEASONS:
            clubs = scrape_league_season(league_key, season)
            total_requests += 1

            for club in clubs:
                tm_id = club["tm_id"]
                if tm_id not in registry:
                    registry[tm_id] = {
                        "tm_id": tm_id,
                        "slug": club["slug"],
                        "name": club["name"],
                        "leagues": {},  # season → league
                        "first_season": season,
                        "last_season": season,
                    }

                # Track league participation
                season_key = f"{season}/{season+1}"
                if season_key not in registry[tm_id]["leagues"]:
                    registry[tm_id]["leagues"][season_key] = []
                registry[tm_id]["leagues"][season_key].append(league_info["short"])

                # Update name if we got a better one
                if len(club["name"]) > len(registry[tm_id]["name"]):
                    registry[tm_id]["name"] = club["name"]

                # Track date range
                registry[tm_id]["first_season"] = min(registry[tm_id]["first_season"], season)
                registry[tm_id]["last_season"] = max(registry[tm_id]["last_season"], season)

    # Post-process: add computed fields
    clubs_list = sorted(registry.values(), key=lambda c: c["name"])
    for club in clubs_list:
        club["total_seasons"] = len(club["leagues"])
        all_leagues = set()
        for leagues in club["leagues"].values():
            all_leagues.update(leagues)
        club["league_set"] = sorted(all_leagues)

    # Summary stats
    print("\n" + "=" * 60)
    print(f"TOTAL: {len(clubs_list)} unique clubs")
    print(f"Requests made: {total_requests}")

    # Breakdown by league
    for league_key, league_info in LEAGUES.items():
        short = league_info["short"]
        count = sum(1 for c in clubs_list if short in c["league_set"])
        print(f"  {short}: {count} clubs (ever)")

    # Save
    output = {
        "meta": {
            "scraped_at": datetime.now().isoformat(),
            "leagues": {k: v["name"] for k, v in LEAGUES.items()},
            "seasons": f"{SEASONS[0]}/{SEASONS[0]+1} – {SEASONS[-1]}/{SEASONS[-1]+1}",
            "total_clubs": len(clubs_list),
        },
        "clubs": clubs_list,
    }

    output_path = DATA_DIR / "club_registry.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nSaved to {output_path}")
    print(f"File size: {output_path.stat().st_size:,} bytes")

    return clubs_list


if __name__ == "__main__":
    main()
