"""Extracted, individually-testable stages of build_coach_network.build_network().

Part of the 2026-06-20 decomposition of the 2,100-line build_network() monolith
into named pure stages. Each function here is verified byte-identical against a
golden network snapshot before landing (see /tmp golden harness in the audit work).
"""
from collections import defaultdict
from typing import Dict

from .normalization import is_pseudo_club, get_season_range, normalize_club


def parse_coach_stations(career: list):
    """Parse a coach's career_history into stations: club_tm_id → {name, seasons(set),
    roles(set)}. Skips TM virtual buckets (Frauenfußball / DFB-Lehrgang etc. via
    is_pseudo_club) which would otherwise +station-bonus coincidental peers. Returns
    a defaultdict so callers can keep indexing missing keys safely."""
    coach_stations = defaultdict(lambda: {"name": "", "seasons": set(), "roles": set()})
    for entry in career:
        club_id = entry.get("club_tm_id")
        if not club_id:
            continue
        club_name_raw = entry.get("club_name", "")
        if is_pseudo_club(club_name_raw):
            continue
        seasons = get_season_range(entry.get("date_from", ""), entry.get("date_to", ""))
        coach_stations[club_id]["name"] = normalize_club(club_name_raw, club_id)
        coach_stations[club_id]["seasons"].update(seasons)
        coach_stations[club_id]["roles"].add(entry.get("role", ""))
    return coach_stations


def enrich_cross_references(contacts_map: Dict) -> int:
    """Multi-Station Enrichment — "triangular" relationships.

    For every contact, find OTHER contacts that share >=1 career station with it,
    and record them as ``coaches_worked_with`` (head_coach/coaching_staff, cap 10)
    or ``sds_worked_with`` (sporting_director, cap 5), each as
    ``{"name", "shared": [stations]}``. Also stamps ``shared_station_count`` (the
    contact's own station count). Mutates contacts in place.

    Returns the total number of cross-reference connections added (for logging).
    """
    cross_refs = 0
    for tm_id, contact in contacts_map.items():
        contact_stations = set(contact.get("stations", []))
        coaches_w = []
        sds_w = []

        for other_id, other in contacts_map.items():
            if other_id == tm_id:
                continue
            shared = contact_stations & set(other.get("stations", []))
            if not shared:
                continue
            cat = other.get("category", "")
            if cat in ("head_coach", "coaching_staff"):
                coaches_w.append({"name": other["name"], "shared": sorted(shared)})
            elif cat == "sporting_director":
                sds_w.append({"name": other["name"], "shared": sorted(shared)})

        if coaches_w:
            contact["coaches_worked_with"] = sorted(coaches_w, key=lambda x: x["name"])[:10]
            cross_refs += len(contact["coaches_worked_with"])
        if sds_w:
            contact["sds_worked_with"] = sorted(sds_w, key=lambda x: x["name"])[:5]
            cross_refs += len(contact["sds_worked_with"])

        contact["shared_station_count"] = len(contact_stations)

    return cross_refs


def resolve_post_career_roles(contacts_map, parse_post_career_activity, normalize_club):
    """Resolve post-career activity for retired players in former_teammate /
    player_coached categories. TM profiles show "Karriereende" but often have a
    "Zuletzt tätig als:" box with the actual current role (Co-Trainer, Scout,
    TV-Experte, ...). We mark these with post_career_role=True so downstream
    (template role-display + logic_audit LP3) treats current_club as the player's
    REAL employer, not a stale coach-station stamp. Returns count resolved.

    Dependencies injected to keep this module import-light:
      parse_post_career_activity(tm_id) -> dict | None
      normalize_club(name) -> str
    """
    resolved = 0
    for tm_id, c in contacts_map.items():
        current = c.get("current_club", "")
        if current not in ("Karriereende", "") or c.get("category") not in (
                "former_teammate", "player_coached"):
            continue
        activity = parse_post_career_activity(tm_id)
        if not activity:
            continue
        role = activity["role"]
        club = activity.get("club")
        if club:
            club = normalize_club(club)
            c["current_club"] = club
            c["role"] = f"{role} ({club})"
        else:
            c["current_club"] = role
            c["role"] = role
        c["post_career_role"] = True
        resolved += 1
    return resolved


EXCLUDED_CATEGORIES = frozenset({"scouting", "medical"})


def drop_low_value_categories(contacts_map):
    """Drop contacts whose category is in EXCLUDED_CATEGORIES (scouting, medical)
    — they're not strategically relevant for projectFIVE Berater workflow.
    Returns (new_map, removed_count). Pure function — does not mutate input."""
    kept = {k: v for k, v in contacts_map.items()
            if v.get("category") not in EXCLUDED_CATEGORIES}
    return kept, len(contacts_map) - len(kept)


TM_BASE = "https://www.transfermarkt.de"


def normalize_contact_urls(contacts_list) -> int:
    """Make every contact's ``tm_url`` absolute. GemeinsameSpiele supplies relative
    URLs (e.g. '/lambertz/profil/spieler/8640') which 404 when rendered as <a href>.
    Mutates in place; returns the count fixed."""
    fixed = 0
    for c in contacts_list:
        url = c.get("tm_url") or ""
        if url.startswith("/"):
            c["tm_url"] = TM_BASE + url
            fixed += 1
    return fixed


def remove_connection_self_loops(contacts_list) -> int:
    """Drop self-references from ``coaches_worked_with`` / ``sds_worked_with`` — after
    spieler+trainer dedup a contact's connection arrays may still list the contact
    itself (same name). Mutates in place; returns the count removed."""
    removed_total = 0
    for c in contacts_list:
        nm = (c.get("name") or "").strip().lower()
        for key in ("coaches_worked_with", "sds_worked_with"):
            arr = c.get(key) or []
            if not arr:
                continue
            filtered = [x for x in arr if isinstance(x, dict)
                        and (x.get("name", "").strip().lower() != nm)]
            removed = len(arr) - len(filtered)
            if removed:
                removed_total += removed
                c[key] = filtered
    return removed_total
