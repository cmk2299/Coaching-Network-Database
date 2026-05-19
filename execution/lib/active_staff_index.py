"""
Active-Staff-Index — systemic fix for stale spieler-profiles whose owners
are TODAY actively coaching/managing somewhere.

Pattern (Makiadi-Bug, Schuster-Bug, etc.):
  persons_master has tm_id 29865 = spieler/Karriereende ("Julian Schuster")
  persons_master has tm_id 61575 = trainer/SC Freiburg ("Julian Schuster")
  Staff file SC Freiburg has tm_id 61575 in Trainerstab section

When a Coach-Network pulls Schuster as `player_coached` (via players_used data
pointing to 29865), we want to display HEUTIGE Tätigkeit (Trainerstab Freiburg)
and promote category to coaching_staff — automatically, without per-person
manual override.

Index keyed by NAME (because spieler-id != trainer-id). Returns staff context
when the same name exists in any active staff file.

Usage:
    from lib.active_staff_index import build_active_staff_index, lookup_active_staff
    idx = build_active_staff_index(BASE / "data" / "staff")
    info = lookup_active_staff(idx, contact_name)
    if info:
        c["category"] = ...  # promote
"""
import json
import unicodedata
from pathlib import Path
from typing import Dict, Optional


def _normalize_name(name: str) -> str:
    """Strip diacritics + lowercase + collapse whitespace for fuzzy match.
    Mirror of lib.normalization.slugify but for name-comparison only."""
    if not name:
        return ""
    s = unicodedata.normalize("NFD", name)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower().strip()
    # collapse whitespace
    return " ".join(s.split())


# Section → category mapping. Drives category-promotion.
SECTION_TO_CATEGORY = {
    "Trainerstab": "coaching_staff",   # default; refined further below
    "Trainer": "coaching_staff",
    "Co-Trainer": "coaching_staff",
    "Cheftrainer": "head_coach",
    "Sportdirektor": "sporting_director",
    "Sportvorstand": "executive",
    "Sportgeschäftsführer": "executive",
    "Sportlicher Leiter": "executive",
    "Geschäftsführer Sport": "executive",
    "Geschäftsführer Fußball": "executive",
    "Technischer Direktor": "sporting_director",
    "Director of Football": "executive",
    "Vorstand": "management",
    "Aufsichtsrat": "management",
    "Präsident": "executive",
    "Scout": "scouting",
    "Kaderplanung": "scouting",
    "Analyse": "analyst",
    "Jugend": "academy",
    "Nachwuchs": "academy",
    "NLZ": "academy",
    "Medizin": "medical",
    "Mannschaftsarzt": "medical",
    "Physio": "medical",
}


def _section_to_category(section: str) -> Optional[str]:
    if not section:
        return None
    s = section.strip()
    # Exact match first
    if s in SECTION_TO_CATEGORY:
        return SECTION_TO_CATEGORY[s]
    # Substring match
    for key, cat in SECTION_TO_CATEGORY.items():
        if key.lower() in s.lower():
            return cat
    return None


def _is_distinctive_name(name: str) -> bool:
    """Skip single-token names (Diego, Pelé) to avoid false-positive
    cross-matches. Require at least 2 name-parts of >=2 chars each."""
    if not name:
        return False
    parts = [p for p in name.split() if len(p) >= 2]
    return len(parts) >= 2


def build_active_staff_index(staff_dir: Path) -> Dict[str, dict]:
    """Scan ALL data/staff/*.json files and build {normalized_name: best_entry}.

    Safety guards:
      - Single-token names (Diego, Pelé) skipped — too ambiguous
      - Names appearing in >=2 distinct tm_ids across staff files marked
        as `_ambiguous=True` — caller decides whether to use

    Returns dict with normalized name as key, value:
      {
        name, tm_id, section, club_tm_id, club_name, category, _ambiguous
      }
    """
    SECTION_PRIORITY = [
        "Cheftrainer", "Trainer", "Sportdirektor", "Sportvorstand",
        "Sportgeschäftsführer", "Geschäftsführer Sport", "Sportlicher Leiter",
        "Director of Football", "Trainerstab", "Vorstand", "Präsident",
        "Aufsichtsrat", "Scout", "Jugend", "Nachwuchs", "NLZ", "Medizin",
    ]

    def _section_priority(section: str) -> int:
        if not section:
            return 99
        for i, key in enumerate(SECTION_PRIORITY):
            if key.lower() in section.lower():
                return i
        return 99

    # Valid category strings that the staff-scraper already produces in `role`
    VALID_CATEGORIES = {"head_coach", "coaching_staff", "sporting_director",
                         "executive", "management", "scouting", "academy",
                         "analyst", "medical", "other_staff"}

    # First pass: collect all entries per name (to detect ambiguity)
    raw: Dict[str, list] = {}
    if not staff_dir.exists():
        return {}

    for f in staff_dir.glob("*.json"):
        try:
            club_tm_id = int(f.stem)
        except ValueError:
            continue
        try:
            data = json.load(open(f))
        except Exception:
            continue
        club_name = data.get("club_name", "")
        for entry in data.get("staff", []):
            name = entry.get("name", "").strip()
            if not name or not _is_distinctive_name(name):
                continue
            tm_id = entry.get("tm_id")
            section = entry.get("section", "")
            # Prefer pre-classified `role` field (snake_case category), fall back
            # to section keyword matching. Niko Bungert: section="Management"
            # but role="sporting_director" — only the role is right.
            role_field = (entry.get("role") or "").strip()
            cat = role_field if role_field in VALID_CATEGORIES else _section_to_category(section)
            if not cat or cat == "other_staff":
                # Skip generic staff — too noisy for category-promotion
                continue
            norm = _normalize_name(name)
            raw.setdefault(norm, []).append({
                "name": name,
                "tm_id": tm_id,
                "section": section,
                "role": role_field,
                "club_tm_id": club_tm_id,
                "club_name": club_name,
                "category": cat,
                "_priority": _section_priority(section),
            })

    # Second pass: pick best (lowest priority) per name; flag ambiguous
    index: Dict[str, dict] = {}
    for norm, entries in raw.items():
        # Distinct tm_ids → ambiguous (multiple persons with same name)
        distinct_ids = {e["tm_id"] for e in entries if e.get("tm_id")}
        ambiguous = len(distinct_ids) > 1
        best = sorted(entries, key=lambda e: e["_priority"])[0]
        best["_ambiguous"] = ambiguous
        # Drop ambiguous from index — too risky to auto-promote
        if not ambiguous:
            index[norm] = best

    return index


def lookup_active_staff(index: Dict[str, dict], name: str,
                         contact_tm_id: Optional[int] = None) -> Optional[dict]:
    """Return active-staff entry for a given name (case-insensitive,
    diacritics-folded). Returns None if not in any current staff file.

    Safety (Mark-Zimmermann-Fix 2026-05-19): if `contact_tm_id` is provided AND
    the indexed staff entry has a different tm_id, the lookup REJECTS the
    match (different person, same name — e.g. Mark Zimmermann TM 492 player
    vs. TM 6509 coach). Without this guard, GS-Mitspieler with the same name
    as an unrelated active coach get falsely promoted to head_coach.
    Note: TM uses separate IDs for spieler/trainer profiles of the same person
    (Dual-ID quirk); a strict equality check would over-reject. Resolution:
    if either tm_id is unknown OR if both match, accept; only reject when
    BOTH are known and different.
    """
    if not name:
        return None
    entry = index.get(_normalize_name(name))
    if not entry:
        return None
    try:
        a = int(contact_tm_id) if contact_tm_id is not None else None
        b = int(entry.get("tm_id")) if entry.get("tm_id") is not None else None
    except (TypeError, ValueError):
        a = b = None
    if a is not None and b is not None and a != b:
        return None
    return entry
