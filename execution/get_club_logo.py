"""
Club Logo Helper
Provides club logos from Transfermarkt CDN
"""

import json
import os

def get_club_logo(club_name: str) -> str:
    """
    Get logo URL for a club

    Args:
        club_name: Name of the club (e.g., "Bayern München", "FC St. Pauli")

    Returns:
        Logo URL or empty string if not found

    Examples:
        >>> get_club_logo("Bayern München")
        'https://tmssl.akamaized.net/images/wappen/head/27.png'

        >>> get_club_logo("FC St. Pauli")
        'https://tmssl.akamaized.net/images/wappen/head/35.png'
    """

    # Load club logos mapping
    logos_path = os.path.join(os.path.dirname(__file__), 'club_logos.json')

    try:
        with open(logos_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Normalize club name for matching
        normalized_search = club_name.lower().strip()

        # Remove common prefixes
        for prefix in ['fc ', '1. fc ', 'vfl ', 'vfb ', 'tsg ', '1. fsv ']:
            if normalized_search.startswith(prefix):
                normalized_search = normalized_search[len(prefix):]

        # Search for club
        for club in data.get('clubs', []):
            club_normalized = club['name'].lower().strip()

            # Remove prefixes from mapping name too
            for prefix in ['fc ', '1. fc ', 'vfl ', 'vfb ', 'tsg ', '1. fsv ']:
                if club_normalized.startswith(prefix):
                    club_normalized = club_normalized[len(prefix):]

            # Check if names match
            if normalized_search in club_normalized or club_normalized in normalized_search:
                return club['logo_url']

        # Not found
        return ""

    except Exception as e:
        print(f"Error loading club logos: {e}")
        return ""


def get_logo_by_id(transfermarkt_id: int, size: str = "head") -> str:
    """
    Get logo URL by Transfermarkt club ID

    Args:
        transfermarkt_id: Transfermarkt club ID
        size: Logo size (tiny, small, medium, big, head, header)
              - tiny: 25x25px
              - small: 40x40px
              - medium: 80x80px
              - big: 120x120px
              - head: 150x150px (default)
              - header: 200x200px

    Returns:
        Logo URL

    Examples:
        >>> get_logo_by_id(27, "head")
        'https://tmssl.akamaized.net/images/wappen/head/27.png'

        >>> get_logo_by_id(35, "header")
        'https://tmssl.akamaized.net/images/wappen/header/35.png'
    """

    valid_sizes = ["tiny", "small", "medium", "big", "head", "header"]
    if size not in valid_sizes:
        size = "head"

    return f"https://tmssl.akamaized.net/images/wappen/{size}/{transfermarkt_id}.png"


if __name__ == "__main__":
    # Test
    print("=== TESTING CLUB LOGO HELPER ===\n")

    test_clubs = [
        "Bayern München",
        "FC St. Pauli",
        "Borussia Dortmund",
        "RB Leipzig",
        "1. FC Köln"
    ]

    for club in test_clubs:
        logo = get_club_logo(club)
        if logo:
            print(f"✓ {club:25s} → {logo}")
        else:
            print(f"✗ {club:25s} → NOT FOUND")

    print(f"\n=== TESTING BY ID ===\n")
    print(f"Bayern (ID 27, size=header): {get_logo_by_id(27, 'header')}")
    print(f"St. Pauli (ID 35, size=tiny): {get_logo_by_id(35, 'tiny')}")
