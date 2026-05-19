#!/usr/bin/env python3
"""
Generate AI background summaries for all 91 contacts in the Alexander Blessin network.

Reads:
- blessin_full_network.json: Main contact list with stations, roles, notes
- blessin_drilldown_data.json: Network data showing contact counts
- master_coach_profiles.json: Detailed coach profiles (career history, current role, etc.)

Generates:
- background_summaries.json: Dict of {contact_name: summary_text}
- Updates blessin_full_network.json with background_summary field per contact

Rules:
- Write in German
- Keep factual based on available data - don't invent facts
- Mention the shared station/context with Blessin
- For trainer/SD contacts, mention their current professional status
- Max 2 sentences per summary
- Use the note field as primary context source
"""

import json
import os
from pathlib import Path

# Paths
DATA_DIR = Path("/sessions/pensive-vigilant-brahmagupta/mnt/Football Coaches DB/data")
NETWORK_FILE = DATA_DIR / "blessin_full_network.json"
DRILLDOWN_FILE = DATA_DIR / "blessin_drilldown_data.json"
PROFILES_FILE = DATA_DIR / "master_coach_profiles.json"
OUTPUT_FILE = DATA_DIR / "background_summaries.json"

def load_json(filepath):
    """Load JSON file safely."""
    if not filepath.exists():
        print(f"WARNING: {filepath} not found")
        return None
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def build_profile_map(profiles_data):
    """Build a dict mapping coach name to profile data."""
    profile_map = {}
    if profiles_data and 'profiles' in profiles_data:
        for profile in profiles_data['profiles']:
            name = profile.get('name', '').strip()
            if name:
                profile_map[name] = profile
    return profile_map

def get_drilldown_network_size(contact_name, drilldown_data):
    """Get the number of sub-contacts for a person (network size)."""
    if not drilldown_data:
        return 0

    # Try to find the contact in drilldown data
    # Keys are usually lowercase with underscores
    key = contact_name.lower().replace(' ', '_').replace('ö', 'o').replace('ü', 'u').replace('ä', 'a')

    if key in drilldown_data:
        contacts = drilldown_data[key].get('contacts', [])
        return len(contacts)

    return 0

def generate_summary(contact, profile_map, drilldown_data, network_size_map):
    """
    Generate a 1-2 sentence German background summary for a contact.

    Args:
        contact: Dict with name, role, note, stations, category, pro_status
        profile_map: Dict of coach profiles by name
        drilldown_data: Network data with sub-contacts
        network_size_map: Precomputed network sizes

    Returns:
        A 1-2 sentence German summary string
    """
    name = contact.get('name', '')
    role = contact.get('role', '')
    note = contact.get('note', '')
    stations = contact.get('stations', [])
    category = contact.get('category', '')
    pro_status = contact.get('pro_status', '')

    profile = profile_map.get(name, {})
    current_club = profile.get('current_club', '')
    current_role_profile = profile.get('current_role', '')

    # Get network size if applicable
    network_size = network_size_map.get(name, 0)

    # Build summary based on category and available data
    summaries = []

    if category == 'lehrgang':
        # DFB-Lehrgang contact
        main = "Absolvierte den 62. Fußball-Lehrer-Lehrgang gemeinsam mit Blessin (2015/2016)."
        additional = ""

        # Add current role if available
        if current_club and current_role_profile:
            additional = f"Heute {current_role_profile} bei {current_club}."

        if additional:
            return main + " " + additional
        else:
            return main

    elif category == 'teammate':
        # Former playing teammate
        games = ""
        if "gemeinsame Spiele" in note:
            games_part = note.split('gemeinsame Spiele')[0].strip()
            games = games_part

        main = f"Ehemaliger Mitspieler von Blessin bei PAOK Saloniki mit {games} gemeinsamen Spielen."

        # Add current role
        additional = ""
        if current_club and current_role_profile:
            additional = f"Heute {current_role_profile} bei {current_club}."
        elif pro_status == 'trainer':
            additional = "Heute im Trainergeschäft tätig."

        if additional:
            return main + " " + additional
        else:
            return main

    elif category == 'player_coached':
        # Player coached by Blessin
        if stations:
            club = stations[0]
        else:
            club = "relevant klub"

        if note:
            einsaetze = note.split('Einsätze')[0].strip()
            main = f"Spieler unter Blessin ({einsaetze} Einsätze bei {club})."
        else:
            main = f"Spieler bei {club} unter Blessin."

        return main

    elif category == 'sporting_director':
        # Sporting Director
        if stations:
            club = stations[0]
        else:
            club = "relevant klub"

        main = f"Sporting Director bei {club} während Blessins Zeit als Cheftrainer."

        # Add current role
        additional = ""
        if current_club and current_club != club:
            additional = f"Aktuell bei {current_club} tätig."

        if additional:
            return main + " " + additional
        else:
            return main

    elif category == 'management':
        # Management/executive
        if stations:
            club = stations[0]
        else:
            club = ""

        # Use note for context
        if "Architekt des RB-Systems" in note:
            return f"Sportdirektor bei RB Leipzig. Architekt des RB-Systems, prägte Blessins Weg zu Leipzig."
        elif "Holte Blessin nach Oostende" in note:
            return f"{role} bei {club} mit Brighton-Netzwerk, holte Blessin zu KV Oostende."
        elif role:
            return f"{role} bei {club}."
        else:
            return f"Vorstandsmitglied bei {club} während Blessins Zeit."

    elif category == 'coaching_staff':
        # Co-trainer or assistant
        if stations:
            club = stations[0]
        else:
            club = ""

        if "Vorgänger-Cheftrainer" in role:
            return f"Vorgänger von Blessin bei {club}, später Brighton."
        elif "Interimstrainer" in role:
            return f"Co-Trainer unter Blessin bei {club}, später Interimstrainer."
        elif "Co-Trainer" in role:
            return f"Co-Trainer unter Blessin bei {club}."
        elif role:
            return f"{role} unter Blessin."
        else:
            return f"Trainerstab-Kollege bei {club}."

    elif category == 'academy':
        # Academy/youth staff
        if role and stations:
            club = stations[0]
            return f"{role} bei {club} während Blessins Zeit."
        elif role:
            return f"{role}."
        else:
            return "Nachwuchsleiter bei relevantem klub."

    elif category == 'scouting':
        # Scouting staff
        if role and stations:
            club = stations[0]
            return f"{role} bei {club} während Blessins Zeit."
        elif role:
            return f"{role}."
        else:
            return "Scouting-Mitarbeiter im Netzwerk."

    # Fallback if no summary generated
    if note:
        return note[:200]
    elif role and stations:
        return f"{role} bei {stations[0]}."
    else:
        return "Kontakt aus dem Netzwerk von Alexander Blessin."

def main():
    print("Loading data files...")
    network_data = load_json(NETWORK_FILE)
    drilldown_data = load_json(DRILLDOWN_FILE)
    profiles_data = load_json(PROFILES_FILE)

    if not network_data:
        print("ERROR: Could not load network data")
        return

    # Build helper maps
    profile_map = build_profile_map(profiles_data)
    network_size_map = {}

    print(f"Building network size map from {len(profile_map)} profiles...")
    if drilldown_data:
        for contact in network_data.get('contacts', []):
            name = contact['name']
            size = get_drilldown_network_size(name, drilldown_data)
            if size > 0:
                network_size_map[name] = size

    # Generate summaries for all contacts
    print(f"Generating summaries for {network_data.get('total_contacts', 0)} contacts...")
    summaries = {}

    for contact in network_data.get('contacts', []):
        name = contact['name']
        summary = generate_summary(contact, profile_map, drilldown_data, network_size_map)
        summaries[name] = summary
        contact['background_summary'] = summary

    # Save summaries to separate file
    print(f"Saving summaries to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(summaries, f, ensure_ascii=False, indent=2)

    # Update network file with summaries
    print(f"Updating network file with summaries...")
    with open(NETWORK_FILE, 'w', encoding='utf-8') as f:
        json.dump(network_data, f, ensure_ascii=False, indent=2)

    # Print 5 example summaries
    print("\n" + "="*80)
    print("EXAMPLE SUMMARIES (5 selected contacts):")
    print("="*80)

    # Select interesting examples from different categories
    example_names = [
        "Marco Antwerpen",
        "Pellegrino Matarazzo",
        "Julian Nagelsmann",
        "Ralf Rangnick",
        "Stefanos Athanasiadis"
    ]

    for contact in network_data.get('contacts', []):
        if contact['name'] in example_names:
            name = contact['name']
            summary = summaries[name]
            print(f"\n{name}:")
            print(f"  Role: {contact.get('role', 'N/A')}")
            print(f"  Category: {contact.get('category', 'N/A')}")
            print(f"  Stations: {', '.join(contact.get('stations', []))}")
            print(f"  Summary: {summary}")

    print("\n" + "="*80)
    print(f"SUCCESS: Generated {len(summaries)} summaries")
    print(f"Saved to: {OUTPUT_FILE}")
    print(f"Updated: {NETWORK_FILE}")
    print("="*80)

if __name__ == '__main__':
    main()
