"""Extracted, individually-testable stages of build_coach_network.build_network().

Part of the 2026-06-20 decomposition of the 2,100-line build_network() monolith
into named pure stages. Each function here is verified byte-identical against a
golden network snapshot before landing (see /tmp golden harness in the audit work).
"""
from typing import Dict


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
