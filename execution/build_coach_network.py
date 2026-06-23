#!/usr/bin/env python3
"""
Build Coach Network — Schritt 1 des MVP

Generates a network JSON for any coach, using existing data:
- person_profiles/ (career history of 2,794 coaches)
- squads/ (players at each club × season)
- staff/ (current staff per club)
- club_registry.json (club metadata)

Output format matches blessin_full_network.json structure so it can be
injected into the dashboard template.

Usage:
    python build_coach_network.py --tm-id 26099           # Blessin
    python build_coach_network.py --tm-id 26099 --output data/networks/26099.json
    python build_coach_network.py --list-bl-coaches       # Show all BL1+BL2 head coaches

Performance:
    First call loads all 2,794 profiles into memory (~6 MB).
    Subsequent build_network() calls reuse cached data.
    Single coach: ~2-5 seconds. Batch of 36: ~2-3 minutes.
"""

import argparse
import json
import re
import time
from pathlib import Path
from collections import defaultdict
from typing import Optional, Dict, List, Tuple, Set

# ── Shared library imports ────────────────────────────────────────────
from lib import scoring
from lib.network_stages import (
    enrich_cross_references,
    normalize_contact_urls,
    remove_connection_self_loops,
)
from lib.normalization import (
    CLUB_NAME_NORMALIZE,
    normalize_club,
    classify_role,
    classify_staff_section,
    parse_season_from_date,
    get_season_range,
    format_season,
    validate_staff_tm_id,
    league_rank as _league_rank,
    filter_nationality,
    is_pseudo_club,
    slugify,
    # Systematik-Helper (2026-05-19) — single source of truth für Role/Stations/URL
    compute_role_display,
    compute_shared_playing_stations,
    build_trainer_url,
    resolve_trainer_tm_id,
)

# ── Paths ──────────────────────────────────────────────────────────────
BASE = Path(__file__).parent.parent
DATA = BASE / "data"
PROFILES_DIR = DATA / "person_profiles"
SQUADS_DIR = DATA / "squads"
STAFF_DIR = DATA / "staff"
CLUB_REGISTRY = DATA / "club_registry.json"
COACHING_LICENSES = DATA / "coaching_licenses.json"
PLAYERS_USED_DIR = DATA / "players_used"
OUTPUT_DIR = DATA / "networks"
TRAINER_OVERRIDES = DATA / "trainer_profile_overrides.json"

# Availability data (lazy-loaded singleton — used in contact enrichment)
AVAILABILITY = None
_avail_path = DATA / "coach_availability.json"
if _avail_path.exists():
    try:
        AVAILABILITY = json.load(open(_avail_path)).get("availability", {})
    except Exception:
        AVAILABILITY = {}

# Curated trainer-agent mapping (TM doesn't expose agents on Trainer-Profiles)
TRAINER_AGENTS = {}
_ta_path = DATA / "trainer_agents.json"
if _ta_path.exists():
    try:
        TRAINER_AGENTS = json.load(open(_ta_path)).get("agents", {})
    except Exception:
        TRAINER_AGENTS = {}

# Sprint F Phase 6: Decision-Maker enrichment (hire-history + co-DMs + agent patterns)
HIRE_HISTORY = {}
_hh_path = DATA / "hire_history.json"
if _hh_path.exists():
    try:
        HIRE_HISTORY = json.load(open(_hh_path)).get("per_dm", {})
    except Exception:
        HIRE_HISTORY = {}

DECISION_MAKERS = []
_dm_path = DATA / "decision_makers.json"
if _dm_path.exists():
    try:
        DECISION_MAKERS = json.load(open(_dm_path)).get("decision_makers", [])
    except Exception:
        DECISION_MAKERS = []
DM_BY_TM = {str(d["tm_id"]): d for d in DECISION_MAKERS}
# Index: club_tm_id -> list of DMs at that club
DM_BY_CLUB = defaultdict(list)
for _d in DECISION_MAKERS:
    DM_BY_CLUB[_d.get("club_tm_id")].append(_d)

SD_AGENT_PATTERNS = {}
_ap_path = DATA / "sd_agent_patterns.json"
if _ap_path.exists():
    try:
        SD_AGENT_PATTERNS = json.load(open(_ap_path)).get("per_dm", {})
    except Exception:
        SD_AGENT_PATTERNS = {}


# NOTE: CLUB_NAME_NORMALIZE, normalize_club, classify_role, classify_staff_section,
# parse_season_from_date, get_season_range, format_season, validate_staff_tm_id
# are now imported from lib.normalization (see imports above).
# They remain available as module-level names for backward compatibility
# (e.g., build_sqlite.py imports from this module).


# ── Global cache (loaded once, reused across calls) ────────────────────
_cache = {
    "profiles": None,        # {tm_id: profile_dict} (trainer-wins; for coach/SD centers)
    "profiles_ns": None,     # {"spieler_<id>"|"trainer_<id>": profile} (collision-safe)
    "club_registry": None,   # {tm_id: club_dict}
    "profile_index": None,   # {(club_tm_id, season): [tm_id, ...]} — inverted index
    "coaching_licenses": None,
    "trainer_overrides": None,  # {tm_id_str: {current_club, current_role, type, ...}}
}


def load_trainer_overrides() -> Dict[int, dict]:
    """Curated overrides for stale Spieler-Profiles (e.g. Hürzeler → Brighton).
    Returns: {int_tm_id: override_dict}.
    Fields prefixed with `_` (like `_meta`, `_high_confidence_2026`, `_todo_…`)
    are flat sections in the JSON; we collapse them into one tm_id-keyed dict.
    """
    if _cache["trainer_overrides"] is not None:
        return _cache["trainer_overrides"]

    if not TRAINER_OVERRIDES.exists():
        _cache["trainer_overrides"] = {}
        return {}

    try:
        raw = load_json(TRAINER_OVERRIDES)
    except Exception:
        _cache["trainer_overrides"] = {}
        return {}

    overrides = {}
    for section_key, section in raw.items():
        if not isinstance(section, dict):
            continue
        for tm_id_str, entry in section.items():
            if not isinstance(entry, dict):
                continue
            # Skip TODO entries (no `verified_at` or `current_club`)
            if not entry.get("current_club"):
                continue
            try:
                overrides[int(tm_id_str)] = entry
            except (ValueError, TypeError):
                continue

    _cache["trainer_overrides"] = overrides
    print(f"  ✓ Trainer overrides loaded: {len(overrides)} curated entries")
    return overrides


# ── Data loading (with caching) ───────────────────────────────────────

def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_club_registry() -> Dict[int, dict]:
    """Load club registry (cached)."""
    if _cache["club_registry"] is None:
        data = load_json(CLUB_REGISTRY)
        clubs_raw = data.get("clubs", [])
        if isinstance(clubs_raw, list):
            _cache["club_registry"] = {int(c["tm_id"]): c for c in clubs_raw}
        else:
            _cache["club_registry"] = {int(k): v for k, v in clubs_raw.items()}
    return _cache["club_registry"]


def load_players_used(coach_tm_id: int) -> Dict[int, dict]:
    """Load real player appearance data scraped from TM.

    Returns:
        {player_tm_id: {"appearances": int, "goals": int, "assists": int,
                         "minutes": int, "position": str}}
    """
    pu_path = PLAYERS_USED_DIR / f"{coach_tm_id}.json"
    if not pu_path.exists():
        return {}

    try:
        with open(pu_path) as f:
            data = json.load(f)
        result = {}
        for p in data.get("players", []):
            pid = p.get("player_id")
            if pid:
                result[pid] = {
                    "appearances": p.get("appearances", 0),
                    "goals": p.get("goals", 0),
                    "assists": p.get("assists", 0),
                    "minutes": p.get("minutes", 0),
                    "position": p.get("position", ""),
                }
        return result
    except (json.JSONDecodeError, KeyError):
        return {}


def load_coaching_licenses() -> Dict[int, list]:
    """Load coaching license cohort data and build tm_id → list-of-cohort-memberships.

    A person can be in MULTIPLE cohorts (e.g. UEFA Pro Lizenz AND later
    Management im Profifußball). The index value is a list, not a single dict,
    so we don't lose memberships on overwrite. Live-Audit 2026-04-30: Bungert
    is in Management-LG; if he's later also in Fußball-Lehrer, both surface.

    Returns:
        {tm_id: [
            {"cohort_num": "62", "year": "2015/2016", "course_name": "...",
             "colleagues": [{"name": ..., "tm_id": ...}, ...],
             "total_in_cohort": int},
            ...
        ]}
    """
    if _cache["coaching_licenses"] is not None:
        return _cache["coaching_licenses"]

    if not COACHING_LICENSES.exists():
        print("  ⚠ coaching_licenses.json not found — skipping lehrgang data")
        _cache["coaching_licenses"] = {}
        return {}

    data = load_json(COACHING_LICENSES)
    index = {}  # tm_id → list of cohort dicts

    for course in data.get("courses", []):
        course_name = course.get("name", "")
        course_id = course.get("course_id", "")
        for cohort_num, cohort in course.get("cohorts", {}).items():
            year = cohort.get("year", "")
            graduates = cohort.get("graduates", [])
            matched_grads = [g for g in graduates if g.get("tm_id")]

            for grad in matched_grads:
                tm_id = grad["tm_id"]
                colleagues = [
                    {"name": g["name"], "tm_id": g["tm_id"],
                     "confidence": g.get("confidence", 0)}
                    for g in matched_grads if g["tm_id"] != tm_id
                ]
                cohort_record = {
                    "cohort_num": cohort_num,
                    "year": year,
                    "course_name": course_name,
                    "course_id": course_id,
                    "colleagues": colleagues,
                    "total_in_cohort": len(graduates),
                }
                index.setdefault(tm_id, []).append(cohort_record)

    n_persons = len(index)
    n_memberships = sum(len(v) for v in index.values())
    print(f"  ✓ Coaching licenses loaded: {n_persons} persons, {n_memberships} memberships")
    _cache["coaching_licenses"] = index
    return index


CACHE_DIR = BASE / "tmp" / "cache" / "profiles"


def parse_post_career_activity(tm_id: int) -> Optional[Dict[str, str]]:
    """Parse post-career activity from cached TM HTML for retired players.

    Looks for the 'Zuletzt tätig als:' box on TM player profiles that shows
    what the player is doing after retiring (e.g. Co-Trainer, Scout, TV-Experte).

    Returns: {"role": "Co-Trainer", "club": "RB New York"} or None if not found.
    """
    # Try spieler (player) cache first
    html_path = CACHE_DIR / f"spieler_{tm_id}.html"
    if not html_path.exists():
        return None

    try:
        from bs4 import BeautifulSoup
        with open(html_path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f.read(), "html.parser")

        # Find the "Zuletzt tätig als:" / "Aktuell tätig als:" box
        for link in soup.find_all("a", class_="data-header__box--link"):
            headline = link.find("div", class_="data-header__link-headline")
            if not headline or "tätig" not in headline.text.lower():
                continue

            # Extract role (first data-header__content span)
            role_span = link.find("span", class_="data-header__content")
            role = role_span.text.strip() if role_span else None

            # Extract club (nested data-header__content inside data-header__label)
            club = None
            for label_span in link.find_all("span", class_="data-header__label"):
                if "verein" in label_span.text.lower() or "team" in label_span.text.lower():
                    club_span = label_span.find("span", class_="data-header__content")
                    if club_span:
                        club = club_span.text.strip()
                    break

            if role:
                return {"role": role, "club": club}

    except Exception:
        pass

    return None


def preload_all_profiles() -> Dict[int, dict]:
    """
    Load ALL person_profiles into memory. ~2,794 files, ~6 MB total.
    This is the key optimization: instead of reading 2,794 files per coach,
    we read them once and reuse.
    """
    if _cache["profiles"] is not None:
        return _cache["profiles"]

    print("  Loading all profiles into memory...")
    t0 = time.time()
    # Post-Sprint-A namespace migration: filenames are spieler_<id>.json or
    # trainer_<id>.json (legacy `<id>.json` still tolerated). Build an int-keyed
    # dict for backward compat: trainer-side wins if both exist, else spieler.
    #
    # NAMESPACE COLLISION (2026-06-04): TM REUSES the same numeric id across the
    # spieler and trainer namespaces for DIFFERENT people (e.g. spieler 63022 =
    # Jan Moravek, trainer 63022 = Andreas Mohr). The int-keyed dict therefore
    # silently returns the wrong person for player-context lookups. We keep the
    # int dict (trainer-wins is correct for coach/SD CENTERS) but ALSO build a
    # namespace-keyed dict so player-context code can fetch the right person.
    profiles_by_tmid: dict[int, dict] = {}
    profiles_by_ns: dict[str, dict] = {}
    trainer_seen: set[int] = set()
    for pf in sorted(PROFILES_DIR.glob("*.json")):
        stem = pf.stem
        kind = None
        tm_str = stem
        if stem.startswith("trainer_"):
            tm_str = stem[len("trainer_"):]
            kind = "trainer"
        elif stem.startswith("spieler_"):
            tm_str = stem[len("spieler_"):]
            kind = "spieler"
        if not tm_str.isdigit():
            continue
        tm_id = int(tm_str)
        try:
            data = load_json(pf)
        except (ValueError, json.JSONDecodeError):
            continue
        # Namespace-explicit store (always correct, no collisions).
        ns_key = f"{kind or 'trainer'}_{tm_id}"
        profiles_by_ns[ns_key] = data
        # Priority: trainer always wins (most callers want coach data).
        # Legacy files (kind is None) act like trainer for compatibility.
        if kind == "trainer" or kind is None:
            profiles_by_tmid[tm_id] = data
            trainer_seen.add(tm_id)
        elif kind == "spieler" and tm_id not in trainer_seen:
            profiles_by_tmid[tm_id] = data

    _cache["profiles"] = profiles_by_tmid
    _cache["profiles_ns"] = profiles_by_ns
    print(f"  ✓ {len(profiles_by_tmid)} profiles loaded in {time.time()-t0:.1f}s "
          f"({len(profiles_by_ns)} namespace-keyed)")
    return profiles_by_tmid


def _name_matches(a: str, b: str) -> bool:
    """Diacritic-insensitive, surname-anchored name match. Guards against TM
    namespace id-reuse attaching a wrong person's profile to a contact.
    True:  Szczesny==Szczęsny, Jagiełło==Jagiello, Hansi Flick==Hans-Dieter Flick
    False: Udo Knierim != Per Nilsson, Wolfgang Hotze != Marcel Schäfer."""
    import unicodedata

    # Explicit folds for chars NFKD doesn't decompose (Polish ł, Nordic ø/æ, ð/þ)
    _FOLD = {"ł": "l", "ø": "o", "æ": "ae", "œ": "oe", "ð": "d", "þ": "th", "ß": "ss"}

    def fold(s):
        s = (s or "").lower()
        s = "".join(_FOLD.get(ch, ch) for ch in s)
        s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
        return s

    na = re.sub(r"[^a-z]", "", fold(a))
    nb = re.sub(r"[^a-z]", "", fold(b))
    if not na or not nb:
        return False
    if na == nb:
        return True
    # Surname anchor: the LAST token of each name must match (firstnames vary:
    # "Hansi" vs "Hans-Dieter", nicknames, etc., but the surname is stable).
    ta = [t for t in re.split(r"[^a-z]+", fold(a)) if len(t) > 1]
    tb = [t for t in re.split(r"[^a-z]+", fold(b)) if len(t) > 1]
    if ta and tb and ta[-1] == tb[-1]:
        return True
    return False


def get_profile_ns(kind: str, tm_id) -> Optional[dict]:
    """Namespace-explicit profile lookup (collision-safe).

    kind: 'spieler' or 'trainer'. Falls back to the int dict / legacy file only
    if the namespace cache is unbuilt. Returns None if not found.
    """
    ns = _cache.get("profiles_ns")
    if ns is not None:
        hit = ns.get(f"{kind}_{tm_id}")
        if hit is not None:
            return hit
        # legacy <id>.json was stored as trainer_<id> in ns
        if kind == "trainer":
            return None
        return None
    return None


def build_profile_index(profiles: Dict[int, dict]) -> Dict[Tuple[int, int], List[int]]:
    """
    Build inverted index: (club_tm_id, season) → [tm_id, tm_id, ...]
    Allows O(1) lookup of "who was at club X in season Y" instead of scanning all profiles.
    """
    if _cache["profile_index"] is not None:
        return _cache["profile_index"]

    print("  Building profile index...")
    t0 = time.time()
    index = defaultdict(list)

    for tm_id, profile in profiles.items():
        for entry in profile.get("career_history", []):
            club_id = entry.get("club_tm_id")
            if not club_id:
                continue
            seasons = get_season_range(entry.get("date_from", ""), entry.get("date_to", ""))
            for s in seasons:
                index[(club_id, s)].append(tm_id)

    _cache["profile_index"] = dict(index)
    print(f"  ✓ Index built: {len(index)} club-season keys in {time.time()-t0:.1f}s")
    return _cache["profile_index"]


import re as _re_module


def filter_default_image(url):
    """PATTERN 36 FIX (2026-05-26): TM serves a placeholder avatar
    `https://img.a.transfermarkt.technology/portrait/medium/default.jpg`
    for persons without a photo. Storing this as `image_url` blocks the
    dashboard from rendering an initials-based fallback (clean look).
    Replace with empty string so the UI falls back to initials.
    5,966 contacts had this leak across 813 networks.
    """
    if not url:
        return url
    if "default.jpg" in url or "/default." in url:
        return ""
    return url


def normalize_dob(dob: str) -> str:
    """PATTERN 32 FIX (2026-05-23): normalize DOB to ISO yyyy-mm-dd format.

    Two formats coexist in source data:
      - "1972-01-23" (ISO, from person_profiles scraped after Sprint A)
      - "23.01.1972" (DE, from staff files / GS data / older scrapes)
    Same human appearing in two networks could have different formats. 2,880
    such inconsistencies counted in Iter 9 audit. Normalize all writes to ISO.
    """
    if not dob:
        return dob
    s = dob.strip()
    # Already ISO?
    iso = None
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        iso = s
    else:
        # DE format?
        m = re.match(r"^(\d{2})\.(\d{2})\.(\d{4})$", s)
        if m:
            iso = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
        elif re.match(r"^\d{4}$", s):
            return s  # year-only

    # PATTERN 35 FIX (2026-05-26): squad scraper occasionally writes the
    # join-date or season-start (e.g. "01.07.2024") into the player's `dob`
    # field. Filter implausible birth years (< 1920 or > 2015) — these are
    # never real DOBs for football professionals. 137 contact records had
    # contract-date-as-DOB values like 2024-07-01, 2026-01-01, 2022-07-01.
    if iso:
        try:
            y = int(iso[:4])
            if y < 1920 or y > 2015:
                return ""
        except Exception:
            pass
        return iso
    return s  # unknown format — passthrough


def profile_namespace_mismatch(contact_name: str, profile_name: str) -> bool:
    """F1 Dual-Namespace Guard (extracted 2026-05-23 — Pattern 25).

    Returns True if the loaded profile name doesn't match the contact name —
    indicating a TM dual-namespace collision (e.g. spieler/104=Fredi Bobic
    vs trainer/104=Walter Junghans). Callers should drop ALL profile-derived
    enrichment fields when this returns True.

    Compares surnames (last token) case-insensitively + diacritic-folded.
    Conservative — minimizes false-positives on legitimate short-form variants
    (Tom/Thomas, Andy/Andreas) while catching all confirmed F1 corruptions
    (Bobic/Junghans, Piwowarski/Hagg, Ayestaran/Keller, Stevens/Tuchel etc.).
    """
    if not contact_name or not profile_name:
        return False
    import unicodedata as _ud
    def _norm(s: str) -> str:
        s = _ud.normalize("NFD", s)
        s = "".join(ch for ch in s if not _ud.combining(ch))
        return s.lower().strip()
    sn = _norm(profile_name)
    cn = _norm(contact_name)
    if sn == cn or sn in cn or cn in sn:
        return False
    sn_last = sn.split()[-1] if sn.split() else ""
    cn_last = cn.split()[-1] if cn.split() else ""
    if sn_last and cn_last and sn_last != cn_last:
        return True
    return False


def is_future_career_entry(entry: dict) -> bool:
    """Return True if entry's date_from is a future season (26/27 or later).

    PATTERN 15 FIX (2026-05-23): TM pre-enters next-season contracts before they
    start.  These future entries can corrupt center_role and contact career_history.
    Skip any entry whose start season is after 2025 (i.e. 26/27 or later).

    Used in:
    - build_network() center-role computation (filter career[0] future entries)
    - Contact career_history enrichment (filter future entries from detail panel)
    """
    m = _re_module.match(r'(\d{2})/(\d{2})', entry.get('date_from', ''))
    if not m:
        return False
    return (2000 + int(m.group(1))) > 2025  # 26/27 starts 2026


def load_coach_profile(tm_id: int) -> Optional[dict]:
    """Load a single coach profile (from cache or file).
    Pattern-12-Fix (2026-05-22): After Phase-A namespace migration, files are
    named trainer_{id}.json / spieler_{id}.json — legacy {id}.json no longer exists.
    Check typed paths first, fall back to legacy for pre-migration files.
    """
    if _cache["profiles"] is not None:
        return _cache["profiles"].get(tm_id)
    # Namespace-aware path search: trainer wins over spieler, legacy fallback
    for prefix in ("trainer_", "spieler_", ""):
        path = PROFILES_DIR / f"{prefix}{tm_id}.json"
        if path.exists():
            return load_json(path)
    return None


def load_squad(club_tm_id: int, season: int) -> Optional[dict]:
    path = SQUADS_DIR / f"{club_tm_id}_{season}.json"
    if path.exists():
        return load_json(path)
    return None


def load_staff(club_tm_id: int) -> Optional[dict]:
    path = STAFF_DIR / f"{club_tm_id}.json"
    if path.exists():
        return load_json(path)
    return None


# ── Current BL coaches detection ───────────────────────────────────────

def get_bl_clubs(club_registry: Dict[int, dict], leagues: List[str] = None,
                 season: int = 2025) -> Dict[int, dict]:
    """Get clubs in specified leagues for a given season."""
    if leagues is None:
        leagues = ["BL1", "BL2"]

    bl_clubs = {}
    # Season keys can be "2025" or "2025/2026" format; field is "leagues" or "league_history"
    for club_id, club in club_registry.items():
        league_data = club.get("leagues") or club.get("league_history", {})
        for s, club_leagues in league_data.items():
            # Match both "2025" and "2025/2026" to season=2025
            s_year = int(s.split("/")[0]) if "/" in s else int(s)
            if s_year == season and any(l in leagues for l in club_leagues):
                bl_clubs[club_id] = club
                break
    return bl_clubs


def list_bl_coaches(club_registry: Dict[int, dict], season: int = 2025) -> List[dict]:
    """List all BL1+BL2 head coaches for the given season."""
    bl_clubs = get_bl_clubs(club_registry, ["BL1", "BL2"], season)
    coaches = []

    for club_id, club in sorted(bl_clubs.items(), key=lambda x: x[1].get("name", "")):
        staff = load_staff(club_id)
        if not staff:
            continue

        trainerstab = [s for s in staff.get("staff", []) if s.get("section") == "Trainerstab"]
        if not trainerstab:
            continue

        head = trainerstab[0]
        league_data = club.get("leagues") or club.get("league_history", {})
        # Try both "2025/2026" and "2025" key formats
        leagues = league_data.get(f"{season}/{season+1}", league_data.get(str(season), []))
        league = "BL1" if "BL1" in leagues else "BL2"

        profile = load_coach_profile(head["tm_id"])

        coaches.append({
            "tm_id": head["tm_id"],
            "name": head["name"],
            "club": club.get("name", staff.get("club_name", "?")),
            "club_tm_id": club_id,
            "league": league,
            "tm_url": head.get("tm_url", ""),
            "has_profile": profile is not None,
            "career_stations": len(profile.get("career_history", [])) if profile else 0,
        })

    return coaches


# ── Network building ───────────────────────────────────────────────────

def build_network(coach_tm_id: int, profiles: Dict[int, dict] = None,
                  profile_index: Dict[Tuple[int, int], List[int]] = None) -> Optional[dict]:
    """
    Build a complete network for a given coach.

    Args:
        coach_tm_id: TM ID of the center coach
        profiles: Pre-loaded profiles dict (optional, will load if None)
        profile_index: Pre-built inverted index (optional, will build if None)

    Returns:
        Network dict matching blessin_full_network.json format
    """
    # Ensure data is loaded
    if profiles is None:
        profiles = preload_all_profiles()
    if profile_index is None:
        profile_index = build_profile_index(profiles)

    profile = profiles.get(coach_tm_id)
    if not profile:
        print(f"  ✗ No profile for tm_id {coach_tm_id}")
        return None

    print(f"\n  Building network: {profile['name']} (ID: {coach_tm_id})")
    t0 = time.time()

    career = profile.get("career_history", [])
    if not career:
        print(f"  ✗ No career history")
        return None

    # ── Parse coach's career stations ──
    coach_stations = defaultdict(lambda: {"name": "", "seasons": set(), "roles": set()})
    for entry in career:
        club_id = entry.get("club_tm_id")
        if not club_id:
            continue
        club_name_raw = entry.get("club_name", "")
        # SCORING_AUDIT D3 / DB_LOGIC P0: skip TM virtual buckets (Frauenfußball,
        # DFB-Lehrgang, etc.). They aggregate staff across many real clubs and would
        # +15-station-bonus every coincidental peer. Lehrgang is added later as
        # a pure relationship via Step 4 (no station credit).
        if is_pseudo_club(club_name_raw):
            continue
        seasons = get_season_range(entry.get("date_from", ""), entry.get("date_to", ""))
        coach_stations[club_id]["name"] = normalize_club(club_name_raw, club_id)
        coach_stations[club_id]["seasons"].update(seasons)
        coach_stations[club_id]["roles"].add(entry.get("role", ""))

    # Quick lookup: which (club, season) was this coach at?
    coach_club_seasons = {}  # (club_tm_id, season) → club_name
    for club_id, info in coach_stations.items():
        for s in info["seasons"]:
            coach_club_seasons[(club_id, s)] = info["name"]

    # ── 1) Current staff colleagues ──
    contacts_map = {}  # tm_id → contact dict
    current_club = profile.get("current_club") or {}
    current_club_id = current_club.get("tm_id")

    if current_club_id:
        staff = load_staff(current_club_id)
        if staff:
            club_name = normalize_club(staff.get("club_name", current_club.get("name", "")), current_club_id)
            for s in staff.get("staff", []):
                if s["tm_id"] == coach_tm_id:
                    continue
                validated_id = validate_staff_tm_id(s["name"], s["tm_id"], profiles)
                # Category: section-based default, but refined via TM-title from
                # persons_master if available. classify_role now returns three
                # executive tiers: executive (Sport-GF/Sportvorstand),
                # executive_governance (Präsident/AR-Vorsitz),
                # executive_secondary (AR-Mitglied/Marketing).
                section_cat = classify_staff_section(s.get("section", ""))
                refined_cat = section_cat
                if section_cat == "executive":
                    cp = profiles.get(int(s["tm_id"]), {}) if profiles else {}
                    title = ""
                    for ce in (cp.get("career_history") or []):
                        if str(ce.get("date_to", "")).strip() in ("-", ""):
                            title = ce.get("role", "") or ""
                            break
                    if title:
                        title_cat = classify_role(title)
                        if title_cat in ("executive_secondary", "executive_governance"):
                            refined_cat = title_cat
                contacts_map[s["tm_id"]] = {
                    "name": s["name"],
                    "stations": [club_name],
                    "category": refined_cat,
                    "role": compute_role_display(
                        category=refined_cat,
                        section=s.get("section", ""),
                        club_name=club_name,
                    ),
                    "tm_url": s.get("tm_url", "") if validated_id else None,
                    "tm_id": validated_id or s["tm_id"],  # Keep original for map key
                    "_validated_tm_id": validated_id,  # Track if ID was validated
                    "_staff_section": s.get("section", ""),  # Track original section for upgrade logic
                    "seasons_together": 1,
                    "_latest_season": 2025,  # current staff = recent
                }

    # ── 1b) Staff at ALL career stations (not just current) ──
    # This picks up foreign club staff files created by scrape_foreign_staff.py
    # IMPORTANT: Staff files only contain CURRENT personnel, so we must check
    # temporal overlap — only include staff if the coach was at this club recently
    # enough that the current staff likely overlapped with them.
    CURRENT_SEASON = 2025  # 2025/26
    MAX_STAFF_SEASON_GAP = 1  # staff file is current; allow 1-season grace period
    for club_id, info in coach_stations.items():
        if club_id == current_club_id:
            continue  # Already handled in step 1
        # Only use staff file if coach was at this club recently
        # Staff files are snapshots of CURRENT staff, so they're only valid
        # if the coach's tenure overlaps with the current season (±1)
        coach_latest_season = max(info["seasons"]) if info["seasons"] else 0
        if coach_latest_season < CURRENT_SEASON - MAX_STAFF_SEASON_GAP:
            continue  # Coach left this club too long ago; staff file is stale
        staff = load_staff(club_id)
        if not staff:
            continue
        club_name = normalize_club(info["name"], info.get("tm_id"))
        for s in staff.get("staff", []):
            if s["tm_id"] == coach_tm_id:
                continue
            if s["tm_id"] not in contacts_map:
                validated_id = validate_staff_tm_id(s["name"], s["tm_id"], profiles)
                _sec_1b = s.get("section", "")
                _cat_1b = classify_staff_section(_sec_1b)
                contacts_map[s["tm_id"]] = {
                    "name": s["name"],
                    "stations": [club_name],
                    "category": _cat_1b,
                    "role": compute_role_display(
                        category=_cat_1b,
                        section=_sec_1b,
                        club_name=club_name,
                    ),
                    "tm_url": s.get("tm_url", "") if validated_id else None,
                    "tm_id": validated_id or s["tm_id"],
                    "_validated_tm_id": validated_id,
                    "_staff_section": _sec_1b,  # Track original section for upgrade logic
                    "seasons_together": 1,
                    "_latest_season": max(info["seasons"]) if info["seasons"] else 2020,
                }
            elif club_name not in contacts_map[s["tm_id"]]["stations"]:
                contacts_map[s["tm_id"]]["stations"].append(club_name)

    # ── 2) Shared career stations (using inverted index = FAST) ──
    # Instead of scanning all 2,794 profiles, we only look up profiles
    # that were at the same (club, season) as our coach.
    candidate_ids = set()
    for key in coach_club_seasons:
        for tm_id in profile_index.get(key, []):
            if tm_id != coach_tm_id:
                candidate_ids.add(tm_id)

    coaches_matched = 0
    for other_id in candidate_ids:
        other = profiles.get(other_id)
        if not other:
            continue

        other_career = other.get("career_history", [])
        if not other_career:
            continue

        # Find shared stations
        shared_stations = defaultdict(set)  # club_name → set of seasons
        for entry in other_career:
            other_club_id = entry.get("club_tm_id")
            if not other_club_id:
                continue
            for s in get_season_range(entry.get("date_from", ""), entry.get("date_to", "")):
                key = (other_club_id, s)
                if key in coach_club_seasons:
                    shared_stations[coach_club_seasons[key]].add(s)

        if not shared_stations:
            continue

        coaches_matched += 1
        latest_role = other_career[0].get("role", "") if other_career else ""
        category = classify_role(latest_role)
        other_current = other.get("current_club") or {}

        station_names = sorted(shared_stations.keys())  # sorted → deterministic order
        total_seasons = sum(len(s) for s in shared_stations.values())
        all_shared_seasons = set().union(*shared_stations.values())
        latest_shared = max(all_shared_seasons) if all_shared_seasons else 2015

        # Build note string
        station_details = []
        for sname, seasons in shared_stations.items():
            s_sorted = sorted(seasons)
            if len(s_sorted) == 1:
                station_details.append(f"{sname} ({format_season(s_sorted[0])})")
            else:
                station_details.append(f"{sname} ({format_season(s_sorted[0])}–{format_season(s_sorted[-1])})")
        note = "; ".join(station_details)

        # SYSTEMIC FIX (2026-05-22): use compute_role_display() instead of raw
        # latest_role string. Fixes TRAINER_NOT_CHEFTRAINER (285 contacts):
        # TM stores "Trainer" as generic title even for head coaches; category is
        # already "head_coach" via classify_role() → compute_role_display() maps it
        # to "Cheftrainer, Club". Also fixes executive/SD display to use specific title.
        cc_name = other_current.get("name", "") if other_current else ""
        role_display = compute_role_display(
            category=category,
            section="",
            club_name=cc_name,
            career_history=[{"role": latest_role, "club": cc_name}] if latest_role else [],
        )

        if other_id in contacts_map:
            existing = contacts_map[other_id]
            for sn in station_names:
                if sn not in existing["stations"]:
                    existing["stations"].append(sn)
            existing["seasons_together"] = max(existing.get("seasons_together", 0), total_seasons)
            existing["_latest_season"] = max(existing.get("_latest_season", 0), latest_shared)
            existing["note"] = note
            # Upgrade category from other_staff ONLY if the contact is NOT from
            # "Sonstiges" section (stadium speakers, mascots, etc.)
            if existing.get("category") == "other_staff" and category != "other_staff":
                staff_section = (existing.get("_staff_section") or "").lower()
                if staff_section != "sonstiges":
                    existing["category"] = category
        else:
            contacts_map[other_id] = {
                "name": other.get("name", f"ID {other_id}"),
                "stations": station_names,
                "category": category,
                "role": role_display,
                "note": note,
                "tm_url": other.get("tm_url", ""),
                "tm_id": other_id,
                "seasons_together": total_seasons,
                "_latest_season": latest_shared,
                "nationality": filter_nationality(other.get("nationality")),
                "dob": normalize_dob(other.get("dob","") or ""),
                "image_url": filter_default_image(other.get("image_url")),
                "current_club": other_current.get("name") if other_current else None,
                "license": other.get("license"),
            }

    print(f"  Candidates: {len(candidate_ids)}, matched: {coaches_matched}")

    # ── 2b) Former teammates from playing career ──
    playing_career = profile.get("playing_career", [])
    teammates_added = 0
    if playing_career:
        # Estimate playing career time range:
        # End of playing career = start of coaching career (first career_history entry)
        coaching_start = None
        if career:
            for entry in reversed(career):  # Oldest first
                date_from = entry.get("date_from", "")
                m = re.search(r"(\d{2})/(\d{2})", date_from)
                if m:
                    y = int(m.group(1))
                    coaching_start = 2000 + y if y < 90 else 1900 + y
                    break
        # Fallback: DOB + 35 years (typical retirement age)
        if not coaching_start and profile.get("dob"):
            try:
                birth_year = int(profile["dob"][:4])
                coaching_start = birth_year + 35
            except (ValueError, TypeError):
                coaching_start = 2010
        if not coaching_start:
            coaching_start = 2010

        # Playing career span: assume started at ~18, ended at coaching_start
        playing_end = coaching_start
        dob = profile.get("dob", "")
        try:
            playing_start = int(dob[:4]) + 18 if dob else playing_end - 15
        except (ValueError, TypeError):
            playing_start = playing_end - 15

        # Only search squad files within the actual playing career window.
        # Conservative: use coaching_start - 2 as playing_end to account for
        # the typical gap between retirement and first coaching role.
        # If this yields no seasons >= 2010 (our squad data start), we skip
        # entirely — avoids false matches (e.g. Blessin@Hoffenheim ~2004
        # matching 2010+ players who were never his teammates).
        playing_end_conservative = max(playing_end - 2, playing_start)
        valid_seasons = set(range(max(playing_start, 2010), playing_end_conservative + 1))

        playing_stations = {}
        for entry in playing_career:
            club_id = entry.get("club_tm_id")
            if club_id:
                club_name = normalize_club(entry.get("club_name", ""), club_id)
                playing_stations[club_id] = club_name

        for club_id, club_name in playing_stations.items():
            for season in valid_seasons:
                squad = load_squad(club_id, season)
                if not squad:
                    continue

                for player in squad.get("players", []):
                    pid = player.get("tm_id")
                    if not pid or pid == coach_tm_id:
                        continue
                    if pid == profile.get("player_tm_id"):
                        continue

                    if pid in contacts_map:
                        existing = contacts_map[pid]
                        if club_name not in existing["stations"]:
                            existing["stations"].append(club_name)
                        existing["_latest_season"] = max(existing.get("_latest_season", 0), season)
                        if existing.get("relationship_type") != "playing":
                            existing["relationship_type"] = "both"
                        # Fix C (A8 2026-05-13) — accumulate shared_stations per club/season
                        shared_st = existing.setdefault("shared_stations", [])
                        st_rec = next((s for s in shared_st if s.get("club") == club_name), None)
                        if st_rec is None:
                            st_rec = {"club": club_name, "seasons": [], "matches": 0}
                            shared_st.append(st_rec)
                        if season not in st_rec["seasons"]:
                            st_rec["seasons"].append(season)
                    else:
                        contacts_map[pid] = {
                            "name": player.get("name", f"Player {pid}"),
                            "stations": [club_name],
                            "category": "former_teammate",
                            "role": f"Mitspieler ({player.get('position', 'Spieler')})",
                            "note": f"Mitspieler bei {club_name}",
                            "tm_url": player.get("tm_url", ""),
                            "tm_id": pid,
                            "seasons_together": 1,
                            "_latest_season": season,
                            "relationship_type": "playing",
                            "nationality": filter_nationality(player.get("nationality")),
                            "image_url": filter_default_image(player.get("image_url")),
                            # Fix C (A8 2026-05-13) — per-club station breakdown
                            "shared_stations": [{"club": club_name, "seasons": [season], "matches": 0}],
                        }
                        teammates_added += 1

        print(f"  Former teammates: {len(playing_stations)} playing stations, "
              f"seasons {min(valid_seasons) if valid_seasons else '?'}–{max(valid_seasons) if valid_seasons else '?'}, "
              f"{teammates_added} new contacts")

    # ── 2c) GemeinsameSpiele — echte Spieldaten (ergänzt Squad-Overlap) ──
    gs_path = DATA / "gemeinsame_spiele" / f"{coach_tm_id}.json"
    gs_added = 0
    gs_enriched = 0
    if gs_path.exists():
        try:
            gs_data = json.load(open(gs_path, encoding="utf-8"))
            for tm in gs_data.get("teammates", []):
                pid = tm.get("tm_id")
                if not pid or pid == coach_tm_id:
                    continue
                shared_matches = tm.get("shared_matches", 0)
                if pid in contacts_map:
                    # Enrich existing contact with real match data
                    existing = contacts_map[pid]
                    existing["shared_matches"] = shared_matches
                    existing["shared_minutes"] = tm.get("total_minutes", 0)
                    existing["teams_together_count"] = tm.get("teams_together", 0)
                    if existing.get("category") == "former_teammate":
                        existing["_gs_verified"] = True
                    # Bug-2-Systematik (2026-05-19): wenn stations leer ist
                    # (z.B. weil contact aus anderer Source kam), nachziehen aus
                    # playing_career ∩ player career_history.
                    if not existing.get("stations") and profiles and playing_career:
                        try:
                            tm_profile = profiles.get(int(pid))
                        except (ValueError, TypeError):
                            tm_profile = None
                        if tm_profile:
                            shared_pl = compute_shared_playing_stations(
                                coach_playing_career=playing_career,
                                player_career_history=tm_profile.get("career_history") or [],
                            )
                            if shared_pl:
                                existing["stations"] = shared_pl
                    # Fix C (A8) — push match-count down to shared_stations if exactly
                    # one known overlap-station (TM teams_together can differ from squad
                    # overlap; conservative: only assign matches when unambiguous).
                    sst = existing.get("shared_stations") or []
                    if len(sst) == 1 and not sst[0].get("matches"):
                        sst[0]["matches"] = shared_matches
                    gs_enriched += 1
                else:
                    # New contact only if 5+ shared matches (lowered 10→5 2026-05-10
                    # to catch notable ex-teammates like Bobic with only 7 shared matches)
                    if shared_matches >= 5:
                        # Bug-2-Systematik (2026-05-19): zentrale Helper-Funktion
                        # füllt stations aus playing_career ∩ player career_history.
                        gs_stations = []
                        if profiles and playing_career:
                            try:
                                tm_profile = profiles.get(int(pid))
                            except (ValueError, TypeError):
                                tm_profile = None
                            if tm_profile:
                                gs_stations = compute_shared_playing_stations(
                                    coach_playing_career=playing_career,
                                    player_career_history=tm_profile.get("career_history") or [],
                                )
                        contacts_map[pid] = {
                            "name": tm.get("name", f"Player {pid}"),
                            "stations": gs_stations,
                            "category": "former_teammate",
                            "role": f"Mitspieler ({tm.get('position', 'Spieler')})",
                            "note": f"Mitspieler ({shared_matches} gemeinsame Spiele)",
                            "tm_url": tm.get("tm_url", ""),
                            "tm_id": pid,
                            "shared_matches": shared_matches,
                            "shared_minutes": tm.get("total_minutes", 0),
                            "teams_together_count": tm.get("teams_together", 0),
                            "seasons_together": max(1, tm.get("teams_together", 1)),
                            "_latest_season": 2010,
                            "relationship_type": "playing",
                            "_gs_verified": True,
                        }
                        gs_added += 1
            print(f"  GemeinsameSpiele: {gs_enriched} enriched, {gs_added} new contacts (10+ Spiele)")
        except Exception as e:
            print(f"  GemeinsameSpiele: error loading {gs_path}: {e}")

    # ── 3) Players coached — from squad files ──
    players_coached = defaultdict(lambda: {"seasons": set(), "stations": set()})

    for club_id, info in coach_stations.items():
        coaching_roles = [r for r in info["roles"] if any(
            x in r.lower() for x in ["trainer", "coach", "manager"]
        )]
        if not coaching_roles:
            continue

        for season in info["seasons"]:
            squad = load_squad(club_id, season)
            if not squad:
                continue
            for player in squad.get("players", []):
                pid = player["tm_id"]
                players_coached[pid]["seasons"].add(season)
                players_coached[pid]["stations"].add(info["name"])
                players_coached[pid]["data"] = player

    # Load real appearance data from TM scrape (if available)
    real_players_used = load_players_used(coach_tm_id)
    has_real_data = len(real_players_used) > 0

    # Filter: use real 20-game threshold if available, else 2-season proxy
    MIN_REAL_APPEARANCES = 20

    if has_real_data:
        # Use real appearance data — include any player with 20+ games
        top_players = {}
        for pid, info in players_coached.items():
            real = real_players_used.get(pid)
            if real and real["appearances"] >= MIN_REAL_APPEARANCES:
                top_players[pid] = info
        # Fallback: if too few real matches, also include 2-season squad overlap
        if len(top_players) < 10:
            for pid, info in players_coached.items():
                if pid not in top_players and len(info["seasons"]) >= 2:
                    top_players[pid] = info
        print(f"  Players coached: {len(players_coached)} total, {len(top_players)} top "
              f"(real data: {len(real_players_used)} TM entries)")
    else:
        # No real data — fall back to season-based estimation
        top_players = {pid: info for pid, info in players_coached.items()
                       if len(info["seasons"]) >= 2}
        if len(top_players) < 10:
            top_players = dict(sorted(
                players_coached.items(),
                key=lambda x: len(x[1]["seasons"]),
                reverse=True
            )[:30])
        print(f"  Players coached: {len(players_coached)} total, {len(top_players)} top (est. — no TM data)")

    for pid, pinfo in top_players.items():
        if pid in contacts_map:
            contacts_map[pid]["category"] = "player_coached"
            # Enrich existing contact with real data
            real = real_players_used.get(pid)
            if real:
                contacts_map[pid]["appearances"] = real["appearances"]
                contacts_map[pid]["goals"] = real["goals"]
                contacts_map[pid]["assists"] = real["assists"]
                contacts_map[pid]["minutes"] = real["minutes"]
            continue

        player_data = pinfo.get("data", {})
        station_names = sorted(pinfo["stations"])  # sorted → deterministic note/stations order
        seasons = sorted(pinfo["seasons"])

        n_seasons = len(seasons)

        # Use real data if available, else estimate
        real = real_players_used.get(pid)
        if real:
            est_games = real["appearances"]
            total_minutes = real["minutes"]
        else:
            est_games = n_seasons * 22  # fallback estimate
            total_minutes = 0

        if n_seasons == 1:
            note = f"{', '.join(station_names)} ({format_season(seasons[0])})"
        else:
            note = f"{', '.join(station_names)} ({format_season(seasons[0])}–{format_season(seasons[-1])})"

        contacts_map[pid] = {
            "name": player_data.get("name", f"Player {pid}"),
            "stations": station_names,
            "category": "player_coached",
            "role": player_data.get("position", "Spieler"),
            "note": note,
            "tm_url": player_data.get("tm_url", ""),
            "tm_id": pid,
            "seasons_together": n_seasons,
            "est_games": est_games,
            "appearances": real["appearances"] if real else None,
            "goals": real["goals"] if real else None,
            "assists": real["assists"] if real else None,
            "minutes": total_minutes if total_minutes else None,
            "_latest_season": max(seasons),
            "nationality": filter_nationality(player_data.get("nationality")),
            "dob": normalize_dob(player_data.get("dob","") or ""),
            "image_url": filter_default_image(player_data.get("image_url")),
            # current_club must be the player's ACTUAL current club (incl. "Karriereende"
            # for retired players) from their profile — NOT player_data.club_name, which
            # is the squad/station where the coach met them (Augsburg-retiree bug).
            # Use the SPIELER namespace explicitly AND verify the profile name matches
            # the contact name: bare `pid` can collide with an unrelated person of the
            # same id (TM namespace ID-reuse, e.g. trainer Udo Knierim 18100 vs
            # spieler Per Nilsson 18100). If names don't match → None (no wrong data).
            "current_club": (lambda _p, _nm: (
                (normalize_club(_p["current_club"].get("name", ""), _p["current_club"].get("tm_id"))
                 if isinstance(_p.get("current_club"), dict) and _p["current_club"].get("name")
                 else (_p.get("current_club") if isinstance(_p.get("current_club"), str) else None))
                if _name_matches(_p.get("name"), _nm) else None
            ))(get_profile_ns("spieler", pid) or {}, player_data.get("name", "")),
        }

        # POST-CAREER ROLE (2026-06-04): for a player_coached contact who has retired
        # / is vereinslos, surface their CURRENT football role (Trainer/SD/Direktor)
        # from a NAME+DOB-verified trainer profile — the value the scout actually wants.
        # Deterministic via TM, NO external search API. Collision-safe: we require
        # both name AND birthdate to match the spieler profile, because TM reuses the
        # same numeric id across namespaces for different people.
        try:
            _cc = contacts_map[pid].get("current_club")
            _ccn = _cc.get("name") if isinstance(_cc, dict) else _cc
            _sp = get_profile_ns("spieler", pid) or {}
            # Only trust the spieler profile if its name matches the contact —
            # else it's a namespace collision (wrong person) and DOB would be bogus.
            if not _name_matches(_sp.get("name"), player_data.get("name", "")):
                _sp = {}
            _sp_dob = (_sp.get("dob") or "").strip()
            _sp_name = (_sp.get("name") or "").strip().lower()
            if _ccn in ("Karriereende", "Vereinslos", None) and _sp_dob and _sp_name:
                _ns = _cache.get("profiles_ns") or {}
                _match = None
                for _k, _v in _ns.items():
                    if not _k.startswith("trainer_"):
                        continue
                    if (_v.get("name") or "").strip().lower() != _sp_name:
                        continue
                    if (_v.get("dob") or "").strip() != _sp_dob:
                        continue  # DOB gate → same person only
                    _match = _v
                    break
                _tr_career = (_match or {}).get("career_history") or []
                if _tr_career:
                    _cur = _tr_career[0]  # most recent role
                    _role = (_cur.get("role") or "").strip()
                    _club = normalize_club(_cur.get("club_name", ""), _cur.get("club_tm_id"))
                    if _role and _club:
                        contacts_map[pid]["role"] = f"{_role} ({_club})"
                        contacts_map[pid]["post_career_role"] = True
                        if (_cur.get("date_to") or "").strip() in ("-", "", "heute"):
                            contacts_map[pid]["current_club"] = _club
        except Exception:
            pass

    # ── 4) Lehrgangs-Kollegen (from coaching_licenses.json) ──
    # Person can be in multiple cohorts (UEFA Pro Lizenz + Management im Profifußball).
    # Iterate over all of them.
    lehrgang_data = load_coaching_licenses()
    lehrgang_records = lehrgang_data.get(coach_tm_id, [])
    # Backward-compat: old code stored a single dict
    if isinstance(lehrgang_records, dict):
        lehrgang_records = [lehrgang_records]

    lehrgang_added = 0
    if lehrgang_records:
        for lehrgang_info in lehrgang_records:
            cohort_year = lehrgang_info["year"]
            course_name = lehrgang_info["course_name"]
            course_id = lehrgang_info.get("course_id", "")
            # Station name varies by course so management LG doesn't collide with UEFA Pro
            if "management" in course_id.lower() or "management" in course_name.lower():
                station_name = f"Mgmt-Lehrgang {cohort_year}"
            else:
                station_name = f"DFB-Lehrgang {cohort_year}"

            for colleague in lehrgang_info["colleagues"]:
                coll_id = colleague["tm_id"]
                coll_name = colleague["name"]

                # LX3 guard (logic_audit 2026-06-07): coaching_licenses tm_ids are
                # fuzzy-matched and can point at the wrong person (e.g. Wildersinn→
                # 15516=gil). If the resolved profile name doesn't match the
                # colleague name, the tm_id/url are wrong — drop the link entirely
                # and add the colleague name-only (preserves the real Lehrgang tie
                # without showing a stranger's profile/career/photo).
                if coll_id is not None and profile_namespace_mismatch(
                        coll_name, (profiles.get(coll_id) or {}).get("name", "")):
                    coll_id = None

                if coll_id is not None and coll_id in contacts_map:
                    existing = contacts_map[coll_id]
                    if station_name not in existing["stations"]:
                        existing["stations"].append(station_name)
                    existing["lehrgang_cohort"] = cohort_year
                    # Category-Promotion: wenn die einzige Verbindung zum Center
                    # der Lehrgang ist (alle stations sind Lehrgang-Stationen),
                    # gehört der Kontakt visuell in die "Lehrgang"-Kategorie —
                    # sonst landet er fälschlich in "coaching_staff"/"head_coach"
                    # obwohl er den Center nur aus dem Lehrgang kennt.
                    # Stärkere Signale (head_coach mit echter Co-Tätigkeit beim
                    # Center, player_coached, former_teammate, sporting_director)
                    # bleiben erhalten.
                    other_stations = [s for s in existing["stations"]
                                      if not (s.startswith("DFB-Lehrgang ")
                                              or s.startswith("Mgmt-Lehrgang "))]
                    if not other_stations and existing.get("category") not in (
                        "lehrgang", "player_coached", "former_teammate",
                        "sporting_director"
                    ):
                        existing["category"] = "lehrgang"
                        existing["note"] = (
                            f"{course_name} ({cohort_year}), "
                            f"{lehrgang_info['cohort_num']}. Lehrgang"
                        )
                else:
                    coll_profile = profiles.get(coll_id, {})
                    coll_career = coll_profile.get("career_history", [])
                    # Fix Marcel-Schuhen-Pattern (2026-05-14): wenn Lehrgang-Absolvent
                    # noch aktiver Spieler ist, zeige Spieler-Position statt "Trainer".
                    # Beispiel: Marcel Schuhen ist Torwart Darmstadt 98 + LG 68 Absolvent.
                    coll_type = coll_profile.get("type", "")
                    coll_position = coll_profile.get("position", "")
                    if coll_type == "spieler" and coll_position:
                        coll_role = coll_position  # "Torwart", "Stürmer", etc.
                    elif coll_career:
                        coll_role = coll_career[0].get("role", "Trainer")
                    else:
                        coll_role = "Trainer"
                    coll_current = coll_profile.get("current_club") or {}
                    role_display = coll_role
                    if coll_current:
                        role_display = f"{coll_role}, {normalize_club(coll_current.get('name', ''), coll_current.get('tm_id'))}"

                    try:
                        _lehrgang_year = int(cohort_year[:4])
                    except (ValueError, TypeError):
                        _lehrgang_year = 2015

                    # name-only colleagues (coll_id dropped by LX3 guard) must not
                    # all collide on key None — synthesize a stable per-name key.
                    map_key = coll_id if coll_id is not None \
                        else f"_lehrgang_nameonly::{coll_name}"
                    contacts_map[map_key] = {
                        "name": coll_name,
                        "stations": [station_name],
                        "category": "lehrgang",
                        "role": role_display,
                        "note": f"{course_name} ({cohort_year}), {lehrgang_info['cohort_num']}. Lehrgang",
                        "tm_url": coll_profile.get("tm_url", ""),
                        "tm_id": coll_id,
                        "seasons_together": 1,
                        "_latest_season": _lehrgang_year,
                        "lehrgang_cohort": cohort_year,
                        "nationality": filter_nationality(coll_profile.get("nationality")),
                        "dob": normalize_dob(coll_profile.get("dob","") or ""),
                        "image_url": filter_default_image(coll_profile.get("image_url")),
                        "current_club": normalize_club(coll_current.get("name", ""), coll_current.get("tm_id")) if coll_current else None,
                        "license": coll_profile.get("license"),
                    }
                    lehrgang_added += 1

            print(f"  Lehrgang: {course_name} ({cohort_year}), "
                  f"{len(lehrgang_info['colleagues'])} colleagues")
        print(f"  Lehrgang total: {lehrgang_added} new contacts across "
              f"{len(lehrgang_records)} memberships")
    else:
        print(f"  Lehrgang: not found in cohort data")

    # ── Enrich contacts from person_profiles (images, nationality, etc.) ──
    # PATTERN 25 FIX (2026-05-23): apply F1 dual-namespace guard HERE too.
    # Previously this early-enrichment loop set current_club / image_url from
    # whichever profile won the int-keyed lookup in preload_all_profiles().
    # For dual-namespace IDs (e.g. tm_id=104: spieler=Bobic, trainer=Junghans),
    # the contact-name "Fredi Bobic" was incorrectly enriched with
    # "Bayern München II" (Junghans's club) and Junghans's image URL.
    # The later F1 guard at line ~1903 only protected career_history enrichment.
    enriched = 0
    ns_mismatch_skipped = 0
    for tm_id, c in contacts_map.items():
        p = profiles.get(tm_id)
        if not p:
            continue
        # F1 GUARD: skip enrichment if profile name doesn't match contact name
        if profile_namespace_mismatch(c.get("name", ""), p.get("name", "")):
            ns_mismatch_skipped += 1
            continue
        if not c.get("image_url") and p.get("image_url"):
            c["image_url"] = filter_default_image(p["image_url"])
            enriched += 1
        if not c.get("nationality") and p.get("nationality"):
            c["nationality"] = filter_nationality(p["nationality"])
        if not c.get("dob") and p.get("dob"):
            c["dob"] = normalize_dob(p["dob"])
        if not c.get("current_club") and p.get("current_club"):
            cc = p["current_club"]
            c["current_club"] = normalize_club(cc.get("name", ""), cc.get("tm_id")) if isinstance(cc, dict) else str(cc)
        if not c.get("license") and p.get("license"):
            c["license"] = p["license"]
    if enriched:
        print(f"  Enriched {enriched} contacts with images from profiles")
    if ns_mismatch_skipped:
        print(f"  F1-Guard skipped {ns_mismatch_skipped} dual-namespace contacts (early-enrich)")

    # ── Resolve post-career activity for retired players (former_teammates) ──
    # TM player profiles show "Karriereende" but often have a "Zuletzt tätig als:"
    # box showing their current role (Co-Trainer, Scout, TV-Experte, etc.)
    post_career_resolved = 0
    for tm_id, c in contacts_map.items():
        current = c.get("current_club", "")
        if current not in ("Karriereende", "") or c.get("category") not in ("former_teammate", "player_coached"):
            continue

        activity = parse_post_career_activity(tm_id)
        if activity:
            role = activity["role"]
            club = activity.get("club")
            if club:
                club = normalize_club(club)
                c["current_club"] = club
                c["role"] = f"{role} ({club})"
            else:
                c["current_club"] = role  # e.g. "TV-Experte"
                c["role"] = role
            # Mark as post-career so downstream (template role-display + logic_audit LP3)
            # treats current_club as the player's REAL current employer, not a stale
            # coach-station stamp. Without this flag the audit false-flags retired
            # players who now coach/work at the same club the coach passed through.
            c["post_career_role"] = True
            post_career_resolved += 1

    if post_career_resolved:
        print(f"  Post-career resolved: {post_career_resolved} contacts (from cached TM HTML)")

    # ── Multi-Station Enrichment: Cross-references between contacts ──
    # Extracted to lib.network_stages.enrich_cross_references (decomposition
    # 2026-06-20). Discovers "triangular" relationships: contacts that share a
    # station with each other (not just with the center coach).
    cross_refs = enrich_cross_references(contacts_map)
    if cross_refs > 0:
        print(f"  Cross-references: {cross_refs} coach/SD connections between contacts")

    # ── Remove low-value categories (scouting, medical) ──
    EXCLUDED_CATEGORIES = {"scouting", "medical"}
    before = len(contacts_map)
    contacts_map = {k: v for k, v in contacts_map.items()
                    if v.get("category") not in EXCLUDED_CATEGORIES}
    removed = before - len(contacts_map)
    if removed:
        print(f"  Removed {removed} scouting/medical contacts")

    # ── 5) Relevance scoring ──
    # Score each contact on 4 dimensions for projectFIVE use case:
    #   1. Beziehungsstärke (relationship depth)
    #   2. Entscheidungsmacht (decision-making power / role weight)
    #   3. Liga-Level (league prestige of current club)
    #   4. Netzwerk-Position (bridge value / shared station count)
    #
    # For former teammates: post-career role matters most (did they become a
    # coach, SD, or scout? That's more valuable than a still-active player)

    club_registry = load_club_registry()

    # Fix A (A1e 2026-05-13) — Build active-staff-index early so scoring can
    # determine each contact's TODAY-role (active trainer/SD/scout/etc.). Used
    # for: Mitspieler-Score-Bonus, Fix B "nur aktive im Fußball"-Toggle.
    from lib.active_staff_index import build_active_staff_index, lookup_active_staff
    try:
        _active_staff_idx_for_score = build_active_staff_index(STAFF_DIR)
    except Exception:
        _active_staff_idx_for_score = {}

    # ─ Center-type detection (SD/Executive networks invert the scoring) ─
    # For coach-centered networks, SDs/Executives are top contacts (they hire).
    # For SD-centered networks, head coaches are top contacts (the SD's pool).
    center_role = (profile.get("current_club") or {}).get("role", "") or ""
    if not center_role:
        ch = profile.get("career_history") or []
        center_role = ch[0].get("role", "") if ch else ""
    center_cat = classify_role(center_role)
    is_sd_center = center_cat in ("sporting_director", "executive", "management")

    # Build club_tm_id → best league lookup from registry
    club_best_league = {}  # club_name → best league code
    for cid, cdata in club_registry.items():
        best = None
        for league in cdata.get("league_set", []):
            if best is None or _league_rank(league) < _league_rank(best):
                best = league
        if best:
            club_best_league[cdata.get("name", "")] = best
            # Also index by normalized name
            norm = normalize_club(cdata.get("name", ""), cid)
            if norm:
                club_best_league[norm] = best

    for tm_id, c in contacts_map.items():
        cat = c.get("category", "")
        seasons = c.get("seasons_together", 1)
        stations = c.get("shared_station_count", len(c.get("stations", [])))
        latest = c.get("_latest_season", 2015)

        # ─ Dimension 1: Beziehungsstärke (0–40 pts) ─ (lib.scoring)
        relationship_score = scoring.score_relationship(
            stations, seasons, bool(c.get("lehrgang_cohort")) or cat == "lehrgang")

        # ─ Dimension 2: Entscheidungsmacht / Rollen-Gewicht (0–35 pts) ─
        # SCORING_AUDIT 2026-04-30 D1 (live): executive tier separated from management.
        # Präsident/Vorstand-Sport/CEO sind die echten Entscheider — gleichberechtigt
        # mit Sporting Director. Pressesprecher/Marketing bleiben management (8).
        # Tier-Hierarchie (Live-Audit 2026-05-15 Blessin):
        # executive (Geschäftsführer Sport / Sportvorstand / Director of Football)
        #   = operational hire-decider, day-to-day Berater-Ansprechpartner — TOP
        # executive_governance (Präsident / AR-Vorsitz / stellv.)
        #   = ratification / vote-of-confidence — wichtig aber Sekundär
        # executive_secondary (AR-Mitglied / Marketing / Finanzen)
        #   = formal Verbindung, kein Trainer-Hire-Einfluss
        # Role weights (Dimension 2) — coach- vs SD/Exec-centered (lib.scoring)
        role_weights = scoring.role_weights(is_sd_center)

        # Former teammates: score by their POST-playing career
        is_still_player = False  # Only relevant for former_teammate; init for league/recency modifiers
        if cat == "former_teammate":
            # Check their current role from profile.
            # NAME-VERIFY (2026-06-04): a Mitspieler's GS-derived tm_id can be
            # bogus / resolve only in the trainer namespace to a DIFFERENT person
            # (e.g. Marco Bode[Bremen] id 520 → trainer_520 = Serse Cosmi →
            # falsely shown as "Cheftrainer Salernitana"). Only trust the profile
            # if its name matches the contact; else treat as an unscraped player.
            teammate_profile = profiles.get(tm_id, {}) or {}
            if teammate_profile and not _name_matches(teammate_profile.get("name"), c.get("name", "")):
                teammate_profile = {}
            teammate_career = teammate_profile.get("career_history", [])
            # Detect if person is still an active player (lib.scoring)
            is_still_player = scoring.is_still_active_player(teammate_profile, teammate_career)

            # Fix A (A1e 2026-05-13) — derive `_today_role`: who are they NOW?
            # Priority order:
            #   1) Active-staff-index lookup (most reliable signal for TODAY)
            #   2) First career_history entry without date_to → currently in that role
            #   3) Any coaching/management entry in career → "ex_trainer"
            #   4) Otherwise → "none" (Karriereende without football role)
            _staff_info = lookup_active_staff(_active_staff_idx_for_score, c.get("name", "")) \
                if _active_staff_idx_for_score else None
            _today_role, _today_active = scoring.determine_today_role(_staff_info, teammate_career)
            # Expose for filter (Fix B) + downstream debugging
            c["_today_role"] = _today_role
            c["_today_active"] = _today_active

            # Former-teammate role_score + post-career promotion (lib.scoring).
            role_score, cat = scoring.score_former_teammate(
                c, teammate_profile, teammate_career, is_still_player,
                _today_role, _today_active, role_weights,
                profiles=profiles, spieler_tm_id=tm_id,
                is_future_career_entry=is_future_career_entry)
        elif cat == "player_coached":
            # Players coached: low base — players rarely influence hiring
            role_score = 2
            # Only loyal long-term players get a small bump
            if seasons >= 4:
                role_score += 2
        else:
            role_score = role_weights.get(cat, 2)

        # ─ Dimensions 3+4, floor, GS bonus, final (lib.scoring) ─
        current_club = c.get("current_club", "")
        league_score = scoring.score_league(
            current_club, club_best_league, cat, is_sd_center, role_score, is_still_player)
        recency_score = scoring.score_recency(
            latest, cat, is_sd_center, role_score, is_still_player)
        has_evidence = bool(c.get("stations")) or c.get("shared_matches", 0) > 0
        floor = scoring.category_floor(cat, is_sd_center, has_evidence)
        gs_b = scoring.gs_bonus(c.get("_gs_verified"), c.get("shared_matches", 0))

        total = relationship_score + role_score + league_score + recency_score + gs_b
        total = scoring.apply_multi_station_multiplier(total, cat, c.get("stations"))
        total = max(total, floor)
        c["relevance_score"] = min(total, 100)

    # Print score distribution
    scores = [c["relevance_score"] for c in contacts_map.values()]
    if scores:
        scores.sort(reverse=True)
        top10_names = sorted(
            contacts_map.values(), key=lambda x: -x.get("relevance_score", 0)
        )[:10]
        print(f"  Relevance scores: max={scores[0]}, median={scores[len(scores)//2]}, "
              f"min={scores[-1]}, >=50: {sum(1 for s in scores if s >= 50)}, "
              f">=30: {sum(1 for s in scores if s >= 30)}")
        top5_str = ", ".join(f"{c['name']} ({c['relevance_score']})" for c in top10_names[:5])
        print(f"  Top 5: {top5_str}")

    # ── Build output ──
    # Strength (1–5) and pro_status
    for c in contacts_map.values():
        st = c.get("seasons_together", 1)
        c["strength"] = min(5, max(1, (st + 1) // 2))

        cat = c.get("category", "")
        if cat in ("head_coach", "coaching_staff"):
            c["pro_status"] = "trainer"
        elif cat == "sporting_director":
            c["pro_status"] = "sd"
        elif cat == "executive":
            c["pro_status"] = "exec"     # Sport-GF/Sportvorstand — primary hire-decider
        elif cat == "executive_governance":
            c["pro_status"] = "exec_gov" # Präsident/AR-Vorsitz — ratification only (separate badge)
        elif cat == "executive_secondary":
            c["pro_status"] = "staff"    # AR-Mitglied / Marketing — NOT in Decision-Maker-Filter
        elif cat in ("player_coached", "former_teammate"):
            c["pro_status"] = "player"
        elif cat == "scouting":
            c["pro_status"] = "scout"
        elif cat == "lehrgang":
            c["pro_status"] = "trainer"
        else:
            c["pro_status"] = "staff"

    # Sort by relevance_score (primary), then category order (secondary)
    cat_order = {"head_coach": 0, "sporting_director": 1, "executive": 2,
                 "executive_governance": 3, "coaching_staff": 4, "lehrgang": 5,
                 "scouting": 6, "management": 7, "executive_secondary": 8,
                 "academy": 9, "player_coached": 10, "former_teammate": 11,
                 "analyst": 12, "other_staff": 13, "medical": 14}

    # SCORING_AUDIT D4: deterministic tiebreaker so rebuilds are reproducible.
    # Order: relevance DESC, category, name ASC, tm_id ASC.
    # Post-Sprint-A: tm_id can occasionally be a string (e.g. "trainer_8402")
    # because typed-alias keys leak from preload_all_profiles. Coerce to int.
    def _safe_int(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0
    contacts_list = sorted(
        contacts_map.values(),
        key=lambda c: (
            -c.get("relevance_score", 0),
            cat_order.get(c.get("category", ""), 99),
            (c.get("name") or "").lower(),
            _safe_int(c.get("tm_id")),
        )
    )

    # PATTERN 33 FIX (2026-05-23): exclude the center coach from own contact list.
    # Found 7 networks (Frank Lehmann, Kevin Koffi, Lukas Kohler, Sebastian Lange,
    # Michael Jürgen, Simon Beccari, René Vollath) where the center coach was
    # listed as a contact of himself — happens when name matches both as center
    # AND through GS/career path. Self-reference confuses users.
    _center_name = (profile.get("name") or "").strip().lower()
    _center_tm_id = profile.get("tm_id")
    if _center_name:
        _before = len(contacts_list)
        contacts_list = [c for c in contacts_list
                          if (c.get("name") or "").strip().lower() != _center_name
                          or c.get("_tm_id") == _center_tm_id]  # keep only if NOT self
        # Actually: drop all where name matches center name (no exception — center is the center)
        contacts_list = [c for c in contacts_list
                          if (c.get("name") or "").strip().lower() != _center_name]
        _removed = _before - len(contacts_list)
        if _removed:
            print(f"  Pattern 33: removed {_removed} self-reference contact(s)")

    # Load curated trainer overrides (Hidden-Gems-Patch 2026-04-30)
    trainer_overrides = load_trainer_overrides()

    # Build active-staff-index — systemic fix for stale-spieler patterns
    # (Makiadi-Bug, Schuster-Bug). 2026-05-04. If a contact's name matches a
    # current staff entry anywhere in BL1/BL2/BL3, promote category accordingly.
    # Reuse the index built earlier for scoring (Fix A 2026-05-13) if available.
    active_staff_idx = _active_staff_idx_for_score or build_active_staff_index(STAFF_DIR)

    # Clean up internal fields — keep _tm_id for drill-down lookup
    for c in contacts_list:
        # Use validated tm_id if available (prevents trainer/player ID collisions)
        validated = c.pop("_validated_tm_id", None)
        raw_id = c.pop("tm_id", None)
        c["_tm_id"] = validated if validated is not None else raw_id
        c.pop("seasons_together", None)
        c.pop("relationship_type", None)
        c.pop("_latest_season", None)
        # NOTE: do NOT pop "lehrgang_cohort" here — generate_background_summaries()
        # needs it for the "Gemeinsamer DFB Fußball-Lehrer-Lehrgang (cohort)" template.
        # Cleanup happens after summary generation (see end of generate_background_summaries).
        c.setdefault("has_drilldown", False)
        c.setdefault("background_summary", "")

        # Apply trainer override (Hidden-Gems-Patch) — supersedes stale spieler profile
        # for active trainers/SDs (Hürzeler@Brighton, Jaissle@Al-Ahli, Makiadi@Werder U19, etc.)
        tm_id = c.get("_tm_id")
        if tm_id is not None:
            try:
                ovr = trainer_overrides.get(int(tm_id))
            except (ValueError, TypeError):
                ovr = None
            if ovr:
                ovr_club = ovr.get("current_club") or {}
                ovr_role = ovr.get("current_role")
                ovr_type = ovr.get("type")
                if isinstance(ovr_club, dict) and ovr_club.get("name"):
                    c["current_club"] = normalize_club(
                        ovr_club.get("name"), ovr_club.get("tm_id")
                    )
                if ovr_role:
                    # Mitspieler/Lehrgang/Player-coached with override → show heutige Tätigkeit
                    if c.get("category") in ("former_teammate", "lehrgang", "player_coached"):
                        if isinstance(ovr_club, dict) and ovr_club.get("name") and ovr_club.get("tm_id"):
                            c["role"] = f"{ovr_role}, {c['current_club']}"
                        else:
                            c["role"] = ovr_role

                # Live-Audit 2026-05-04: promote category based on override type
                # Makiadi-Bug: ex-Spieler ist heute U19-Trainer → muss aus player_coached
                # in coaching_staff/academy umkategorisiert werden (sonst falsche
                # Score-Logik + falsche Filter-Sichtbarkeit)
                if ovr_type and c.get("category") in ("former_teammate", "lehrgang",
                                                       "player_coached", "other_staff"):
                    if ovr_type == "trainer":
                        # Use classify_role on the override-role to pick the right tier
                        new_cat = classify_role(ovr_role or "")
                        if new_cat in ("head_coach", "academy", "coaching_staff"):
                            c["category"] = new_cat
                            c["pro_status"] = "trainer"
                    elif ovr_type == "sd":
                        c["category"] = "sporting_director"
                        c["pro_status"] = "sd"
                    elif ovr_type == "executive":
                        c["category"] = "executive"
                        c["pro_status"] = "exec"
                    elif ovr_type == "manager":
                        c["category"] = "management"
                        c["pro_status"] = "staff"

                # Bug-3a-Systematik (2026-05-19): TM-URL auf Trainer-Profil setzen.
                # Override liefert `trainer_tm_id` direkt; fehlt es, resolve_trainer_tm_id()
                # findet es automatisch in persons_master per Name-Lookup.
                trainer_tmid = ovr.get("trainer_tm_id")
                if not trainer_tmid and ovr.get("type") == "trainer":
                    trainer_tmid = resolve_trainer_tm_id(
                        spieler_tm_id=tm_id,
                        person_name=c.get("name", ""),
                        persons_master=profiles or {},
                    )
                if trainer_tmid:
                    url = build_trainer_url(c.get("name", ""), trainer_tmid)
                    if url:
                        c["tm_url"] = url
                # Track that override applied (for debugging / verification)
                c["_override_applied"] = True

        # (Executive-Refinement moved to staff-ingestion step at line ~525
        # so role_weights are applied to the refined category during scoring.)

        # SYSTEMIC FIX (2026-05-04): cross-reference contact's name against the
        # active-staff-index of all BL1/BL2/BL3 staff files. If the contact is
        # TODAY actively a trainer/SD/manager somewhere, override the
        # stale-spieler-derived metadata. Catches Makiadi/Schuster-Pattern
        # without manual curation.
        if not c.get("_override_applied"):
            # Mark-Zimmermann-Fix 2026-05-19: pass tm_id so name+id mismatch
            # rejects promotion (TM 492 spieler != TM 6509 coach, same name).
            staff_info = lookup_active_staff(
                active_staff_idx,
                c.get("name", ""),
                contact_tm_id=tm_id,
            )
            # NAME-COLLISION GUARD (2026-06-04): a Mitspieler/teammate with no
            # tm_id (GS data) — or a bogus tm_id that only resolves in the wrong
            # namespace — must NOT be promoted to an active coach just because a
            # SAME-NAMED active staff member exists (Marco Bode[Bremen player]
            # promoted to "Cheftrainer Salernitana" via namesake). When the
            # contact has no verifiable tm_id, require the staff entry to NOT be
            # an ambiguous/multi-id name; otherwise reject.
            if staff_info and tm_id is None and staff_info.get("_ambiguous"):
                staff_info = None
            if staff_info:
                old_cat = c.get("category", "")
                new_cat = staff_info["category"]
                # Only promote if going from a player/teammate/lehrgang/staff
                # tier UP to a trainer/SD/management tier
                _PROMOTABLE_FROM = {"player_coached", "former_teammate",
                                     "lehrgang", "other_staff", "staff"}
                _PROMOTE_TO = {"head_coach", "coaching_staff", "sporting_director",
                                "executive", "academy", "scouting", "analyst",
                                "management"}
                if old_cat in _PROMOTABLE_FROM and new_cat in _PROMOTE_TO:
                    c["category"] = new_cat
                    c["pro_status"] = {
                        "head_coach": "trainer",
                        "coaching_staff": "trainer",
                        "academy": "trainer",
                        "sporting_director": "sd",
                        "executive": "exec",
                    }.get(new_cat, "staff")
                    c["current_club"] = staff_info["club_name"]
                    # Bug-1-Systematik (2026-05-19): zentrale Role-Display-Funktion
                    # — Bundestrainer/Cheftrainer/Section-spezifisch/Kategorie-Default
                    c["role"] = compute_role_display(
                        category=new_cat,
                        section=staff_info.get("section", ""),
                        club_name=staff_info["club_name"],
                        career_history=c.get("career_history"),
                    )
                    c["_active_staff_promoted"] = True

        # Enrich with career_history from person_profiles (for detail panel timeline)
        if tm_id and profiles:
            p = profiles.get(int(tm_id), {}) or {}

            # F1-QUICK-FIX (2026-05-21): TM dual-namespace-collision guard.
            # TM nutzt getrennte ID-Namespaces für /spieler/<id> und /trainer/<id>;
            # gleiche numerische ID kann zwei verschiedene Personen meinen
            # (z.B. spieler/104=Fredi Bobic vs trainer/104=Walter Junghans).
            # Unser persons_master keyed nur auf tm_id — der zuletzt gescrapete
            # überschreibt → Frankenstein-Anzeige (Bobic's Name, Junghans' Karriere).
            # Quick-Fix: validiere stored name gegen contact.name.
            # Bei klarem Mismatch (Levenshtein-ähnlich): drop ALLE Enrichment-Felder.
            # Behalt nur name + tm_id + category + role (= Original-Quelle).
            # Vollständige Migration (siehe DIRECTIVE_2026-05-21_evening_deploy.md §2.3)
            # folgt in separatem Sprint.
            # PATTERN 25 (2026-05-23): use shared helper for namespace check.
            # Same logic, single source of truth — see profile_namespace_mismatch()
            # module-level definition above.
            _profile_mismatch = profile_namespace_mismatch(
                c.get("name", ""), p.get("name", "")
            )

            if _profile_mismatch:
                # DROP enrichment — leave the contact with only its original
                # (network-builder-provided) data. Better empty career than
                # someone else's career.
                p = {}

            ch = p.get("career_history", [])
            if ch:
                # PATTERN 15 FIX (extended, 2026-05-23): filter future entries so the
                # detail-panel career table never shows "26/27 Sportlicher Leiter @
                # Heidenheim II" while the contact is still in their current role.
                ch_current = [e for e in ch if not is_future_career_entry(e)]
                # Fallback: if ALL entries are future (edge case), keep them all
                ch_display = ch_current if ch_current else ch
                # Compact format: list of {club, role, from, to} dicts
                c["career_history"] = [
                    {
                        "club": normalize_club(e.get("club_name", ""), e.get("club_tm_id")),
                        "role": e.get("role", ""),
                        "from": e.get("date_from", "").split(" ")[0] if e.get("date_from") else "",
                        "to": e.get("date_to", "").split(" ")[0] if e.get("date_to") else "",
                    }
                    for e in ch_display
                ]
                # FIX 2026-05-21 (F9): re-run compute_role_display now that
                # career_history is loaded.  Two paths need this:
                #
                # Path A: Active-staff-promotion (Section 2) ran BEFORE career_history
                # was enrichable → executives/SDs promoted via staff get specific title.
                #
                # Path B: Section 1a/1b contacts were built without career_history
                # (it isn't loaded yet at that point). Executives / SDs in the direct
                # staff file also need their role refreshed so "Management" → e.g.
                # "Geschäftsführer Sport".  We also cover section-less lehrgang or any
                # other executive/SD that was created before career_history was available.
                _EXEC_CATS = {"executive", "sporting_director", "management",
                              "executive_governance", "executive_secondary"}
                if c.get("_active_staff_promoted") or c.get("category") in _EXEC_CATS:
                    # Resolve display club name (precedence: current_club → stations[0])
                    # current_club may be a dict {name, tm_id} (Pattern 10)
                    _raw_cc = c.get("current_club") or ""
                    if isinstance(_raw_cc, dict):
                        _raw_cc = _raw_cc.get("name", "") or ""
                    _club_for_role = _raw_cc.strip()
                    if not _club_for_role:
                        # Section 1a/1b contacts use stations[0] as their club context
                        _stns = c.get("stations") or []
                        _club_for_role = _stns[0] if _stns else ""
                    try:
                        c["role"] = compute_role_display(
                            category=c.get("category"),
                            section=c.get("_staff_section") or "",
                            club_name=_club_for_role,
                            career_history=c.get("career_history"),
                            position=c.get("playing_position") or "",
                            person_type=p.get("type") or "",
                        )
                    except Exception:
                        pass

            # Enrich with agent/Berater from person_profiles
            # PATTERN 31 FIX (2026-05-23): blacklist filter applied AT WRITE-TIME,
            # not just at render-time. Previously the dashboard template stripped
            # values like "Familienangehörige", "Eltern", "ohne Berater" — but
            # they still polluted the JSON (2,331 contacts). Filtering at source
            # so JSON is clean for any consumer.
            _AGENT_BLACKLIST = {"ohne Berater", "Familienangehörige", "Familie",
                                  "Eltern", "Vater", "Bruder", "keine Angabe",
                                  "-", "N/A", "unbekannt", ""}
            agent = (p.get("agent", "") or "").strip()
            if agent and agent not in _AGENT_BLACKLIST:
                c["agent"] = agent
            else:
                # Fallback: curated trainer-agents (TM doesn't expose agents on Trainer-Profiles)
                ta = TRAINER_AGENTS.get(str(tm_id))
                if ta and ta.get("agent"):
                    ta_agent = (ta["agent"] or "").strip()
                    if ta_agent and ta_agent not in _AGENT_BLACKLIST:
                        c["agent"] = ta_agent

            # Enrich with contract data (Aktivierungs-Trigger)
            contract_until = p.get("contract_until")
            if contract_until:
                c["contract_until"] = contract_until
                # Calculate days_remaining inline
                import re as _re
                from datetime import datetime as _dt, timezone as _tz
                _s = (contract_until or "").replace("vsl.", "").replace("\xa0", " ").strip()
                _m = _re.match(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", _s)
                if _m:
                    try:
                        _date = _dt(int(_m.group(3)), int(_m.group(2)), int(_m.group(1))).date()
                        _today = _dt.now(_tz.utc).date()
                        c["contract_days_remaining"] = (_date - _today).days
                    except ValueError:
                        pass

            # Enrich with availability_status (Replacement-Pool-Filter)
            av = AVAILABILITY.get(str(tm_id)) if AVAILABILITY else None
            if av:
                c["availability_status"] = av.get("status")
                c["availability_reason"] = av.get("reason")

            # Live-Audit 2026-04-30: Mitspieler-Kontakte sollen ihre HEUTIGE Tätigkeit
            # zeigen (Trainer, SD, Aufsichtsrat …) statt nur ihrer damaligen Spielerposition.
            # Behalte playing-position als separates Feld für Detail-Panel.
            if c.get("category") == "former_teammate":
                playing_pos = None
                old_role = c.get("role", "") or ""
                m = re.match(r"Mitspieler\s*\(([^)]+)\)", old_role)
                if m:
                    playing_pos = m.group(1).strip()
                    c["playing_position"] = playing_pos

                # Pull current_role / current_club from profile if available
                cc = p.get("current_club") or {}
                current_club_name = ""
                if isinstance(cc, dict):
                    current_club_name = normalize_club(cc.get("name", ""), cc.get("tm_id")) or ""
                elif isinstance(cc, str):
                    current_club_name = cc

                # current_role logic: prefer explicit profile.current_role,
                # else first career_history entry, else fall back to playing-position label
                profile_role = (p.get("current_role") or "").strip()
                if not profile_role and ch:
                    profile_role = (ch[0].get("role", "") or "").strip()

                if profile_role:
                    c["role"] = (
                        f"{profile_role}, {current_club_name}" if current_club_name
                        else profile_role
                    )
                    if current_club_name:
                        c["current_club"] = current_club_name
                else:
                    # No post-playing career — keep "Mitspieler (Position)" but mark explicit
                    if playing_pos:
                        c["role"] = f"Karriereende ({playing_pos})"

    # Final normalization pass: ensure all contact stations are canonical
    for c in contacts_list:
        c["stations"] = [normalize_club(s) for s in c.get("stations", [])]
        # Deduplicate stations per contact
        c["stations"] = sorted(set(c["stations"]))

    # PATTERN 26 FIX (2026-05-23): merge spieler+trainer duplicates of the
    # same human (e.g. Tobias Rathgeb spieler_6131 + trainer_54665). Without
    # this, the dashboard shows the same person TWICE — once as
    # former_teammate / player_coached (spieler ID), once as coaching_staff /
    # head_coach (trainer ID). 382 such duplicates exist across networks.
    # Strategy:
    #   1. Group contacts by normalized full name.
    #   2. If a group has 2+ entries with different tm_ids: pick winner by
    #      category priority (head_coach > sporting_director > ... > player).
    #   3. Merge stations, career_history, shared_matches from all entries.
    #   4. Keep winner's tm_url + image_url (= matches their primary role).
    _CAT_PRIORITY = [
        "head_coach", "sporting_director", "executive", "executive_governance",
        "executive_secondary", "management", "coaching_staff", "academy",
        "analyst", "scouting", "coach_hired", "lehrgang",
        "former_teammate", "player_coached", "other_staff", "medical", "",
    ]
    _PRIORITY_RANK = {c: i for i, c in enumerate(_CAT_PRIORITY)}

    from collections import defaultdict as _dd
    _by_name = _dd(list)
    for c in contacts_list:
        nm = (c.get("name") or "").strip().lower()
        if not nm:
            continue
        _by_name[nm].append(c)

    _merged_count = 0
    _to_drop = set()
    for nm, entries in _by_name.items():
        if len(entries) <= 1:
            continue
        # Extract tm_ids from URLs for de-dup check
        def _tid(c):
            m = re.search(r"/(?:spieler|trainer)/(\d+)", c.get("tm_url","") or "")
            return int(m.group(1)) if m else id(c)
        tids = {_tid(c) for c in entries}
        if len(tids) <= 1:
            continue   # same tm_id already, no merge needed (separate code already dedupes)

        # Sort by priority — lowest rank = winner
        entries_sorted = sorted(entries,
            key=lambda c: (_PRIORITY_RANK.get(c.get("category",""), 99), -len(c.get("stations") or [])))
        winner = entries_sorted[0]
        losers = entries_sorted[1:]

        # Merge stations + career_history dates
        merged_st = set(winner.get("stations") or [])
        for l in losers:
            merged_st.update(l.get("stations") or [])
        winner["stations"] = sorted(merged_st)

        # Merge shared_matches / shared_minutes (sum)
        for l in losers:
            if l.get("shared_matches"):
                winner["shared_matches"] = max(winner.get("shared_matches",0), l["shared_matches"])
            if l.get("shared_minutes"):
                winner["shared_minutes"] = max(winner.get("shared_minutes",0), l["shared_minutes"])

        # Track merge so future audits can verify. Use ONLY real tm_ids here —
        # _tid() falls back to id(c) (a non-deterministic memory address) for
        # contacts without a parseable tm_url, which must never be persisted.
        def _real_tid(c):
            m = re.search(r"/(?:spieler|trainer)/(\d+)", c.get("tm_url", "") or "")
            if m:
                return int(m.group(1))
            v = c.get("_tm_id") or c.get("tm_id")
            try:
                return int(v)
            except (TypeError, ValueError):
                return None
        _wt = _real_tid(winner)
        winner["_merged_aliases"] = sorted(
            {t for c in entries if (t := _real_tid(c)) is not None and t != _wt})

        for l in losers:
            _to_drop.add(id(l))
            _merged_count += 1

    if _merged_count:
        contacts_list = [c for c in contacts_list if id(c) not in _to_drop]
        print(f"  Pattern 26 dedup: merged {_merged_count} spieler/trainer duplicates")

    # PATTERN 27 (2026-05-23): normalize tm_url to absolute form.
    # GemeinsameSpiele data provides relative URLs (e.g. '/lambertz/profil/spieler/8640')
    # which break when rendered as <a href=...> in the dashboard (would resolve to
    # coach-network-explorer.vercel.app/lambertz/... → 404).
    # 44,600 contacts across networks had broken relative URLs.
    # Extracted to lib.network_stages (decomposition 2026-06-20).
    _url_fixed = normalize_contact_urls(contacts_list)
    if _url_fixed:
        print(f"  Pattern 27: normalized {_url_fixed} relative tm_urls → absolute")

    _self_loops_removed = remove_connection_self_loops(contacts_list)
    if _self_loops_removed:
        print(f"  Pattern 26b: removed {_self_loops_removed} self-loops/stale dedup refs")

    all_stations = sorted(set(s for c in contacts_list for s in c.get("stations", [])))
    all_categories = sorted(set(c.get("category", "") for c in contacts_list))

    # Center info — resolve nationality (filter dissolved states + U-teams)
    nationality = filter_nationality(profile.get("nationality", ""))

    # SYSTEMIC FIX (2026-05-22): use compute_role_display() for center role.
    # Prev: f"{latest_role} {club}" → "Trainer Deutschland" for Nagelsmann.
    # After: compute_role_display(category, club_name) → "Bundestrainer, Deutschland".
    #
    # PATTERN 15 FIX (2026-05-23): skip future career entries (26/27+) at career[0].
    # TM pre-enters next-season contracts → career[0] points to future role.
    # E.g., Eta has "Frauenfußball (26/27)" at career[0] but is still at Union Berlin.
    # is_future_career_entry() is now a module-level function (Pattern 15 extension).
    current_role = "Trainer"
    if career:
        # Use first non-future entry; fall back to career[0] if all are future
        _career_current = [e for e in career if not is_future_career_entry(e)]
        latest = _career_current[0] if _career_current else career[0]
        _center_club = normalize_club(latest.get('club_name', ''), latest.get('club_tm_id'))
        current_role = compute_role_display(
            category=center_cat,
            section="",
            club_name=_center_club,
            career_history=career,
        )

    # ─── Sprint F Phase 6: Decision-Maker enrichment ───
    # If center is a DM (in hire_history), mark hires + add co-DMs + attach agent patterns.
    center_dm = DM_BY_TM.get(str(coach_tm_id))
    dm_metadata = None
    if center_dm or str(coach_tm_id) in HIRE_HISTORY:
        # Tag hires on existing contacts; add new contact for hires not already in list
        hh = HIRE_HISTORY.get(str(coach_tm_id), {}) or {}
        # Fix A1: Normalize tm_id keys to int (contacts have mixed int/str)
        # Plus name-based fallback for contacts without tm_id (z.B. career_history-only)
        existing_ids = {}
        existing_by_name = {}
        for c in contacts_list:
            tid = c.get("tm_id")
            if tid is not None:
                try:
                    existing_ids[int(tid)] = c
                except (ValueError, TypeError):
                    pass
            nm = (c.get("name") or "").strip().lower()
            if nm:
                # Prefer entry with tm_id if duplicate names exist
                if nm not in existing_by_name or not existing_by_name[nm].get("tm_id"):
                    existing_by_name[nm] = c
        added_hires = 0
        for h in hh.get("hires", []) or []:
            ht_id = h.get("coach_tm_id")
            ht_id_int = None
            if ht_id is not None:
                try:
                    ht_id_int = int(ht_id)
                except (ValueError, TypeError):
                    ht_id_int = None
            existing = None
            if ht_id_int is not None and ht_id_int in existing_ids:
                existing = existing_ids[ht_id_int]
            else:
                # Name-based fallback (e.g. existing contact without tm_id)
                hname = (h.get("coach_name") or "").strip().lower()
                if hname and hname in existing_by_name:
                    existing = existing_by_name[hname]
                    # Backfill tm_id on the existing contact so subsequent
                    # logic (drilldown, dedup) works correctly
                    if ht_id_int is not None and not existing.get("tm_id"):
                        existing["tm_id"] = ht_id_int
                        existing["_tm_id"] = ht_id_int
                        existing_ids[ht_id_int] = existing
            if existing is not None:
                # Mark category as coach_hired if currently a generic coaching slot
                existing["_dm_hire"] = {
                    "year": h.get("year"),
                    "club": h.get("club"),
                    "confidence": h.get("confidence"),
                    "tenure_years": h.get("tenure_years"),
                }
                # LX2 dedup (logic_audit 2026-06-07): a coach hired in multiple
                # stints (e.g. Falko Götz 2002 + 2004) used to create duplicate
                # contacts. Accumulate all hire years on the single contact and
                # reflect them in the "Trainer (geholt …)" role.
                _yrs = existing.setdefault("_hire_years", [])
                if h.get("year") and h.get("year") not in _yrs:
                    _yrs.append(h.get("year"))
                if (existing.get("role") or "").startswith("Trainer (geholt"):
                    existing["role"] = ("Trainer (geholt "
                                        + ", ".join(str(y) for y in sorted(_yrs)) + ")")
                # Promote to coach_hired (more specific than head_coach)
                existing["category"] = "coach_hired"
                # Fix A2: Score-Boost für existing hires (NICHT für neu-erzeugte)
                hire_conf = (h.get("confidence") or "medium")
                boost = 10 if hire_conf == "high" else 5
                existing["relevance_score"] = min(
                    100,
                    (existing.get("relevance_score", 0) or 0) + boost
                )
            else:
                # Add minimal hire-only contact
                new_hire = {
                    "name": h.get("coach_name", "?"),
                    "tm_id": ht_id,
                    "_tm_id": ht_id,
                    "category": "coach_hired",
                    "stations": [h.get("club", "?")],
                    "role": f"Trainer (geholt {h.get('year','?')})",
                    "relevance_score": 75 if h.get("confidence") == "high" else 55,
                    "_dm_hire": {
                        "year": h.get("year"),
                        "club": h.get("club"),
                        "confidence": h.get("confidence"),
                        "tenure_years": h.get("tenure_years"),
                    },
                    "_hire_years": [h.get("year")] if h.get("year") else [],
                    "pro_status": "trainer",
                    "shared_station_count": 1,
                }
                contacts_list.append(new_hire)
                # LX2 dedup: register so a later hire of the SAME coach merges
                # into this contact instead of appending a second one.
                if ht_id_int is not None:
                    existing_ids[ht_id_int] = new_hire
                _hn = (h.get("coach_name") or "").strip().lower()
                if _hn:
                    existing_by_name[_hn] = new_hire
                added_hires += 1

        # Add co-DMs at the same primary club (Tier 2/3 + nlz)
        center_club_tm_id = (center_dm or {}).get("club_tm_id")
        added_codms = 0
        if center_club_tm_id:
            for codm in DM_BY_CLUB.get(center_club_tm_id, []):
                if codm["tm_id"] == coach_tm_id:
                    continue
                if codm["tier"] not in ("2", "3", "nlz"):
                    continue
                codm_id_int = None
                try:
                    codm_id_int = int(codm["tm_id"])
                except (ValueError, TypeError):
                    codm_id_int = None
                if codm_id_int is not None and codm_id_int in existing_ids:
                    continue
                tier_label = {"2": "Sport-Koord./Scout", "3": "Vorstand/Präsident", "nlz": "NLZ"}
                contacts_list.append({
                    "name": codm["name"],
                    "tm_id": codm["tm_id"],
                    "_tm_id": codm["tm_id"],
                    "category": "co_decision_maker",
                    "stations": [codm.get("club_name", "")],
                    "role": codm.get("tm_title") or tier_label.get(codm["tier"], "Co-DM"),
                    "relevance_score": 60 if codm["tier"] == "2" else 50,
                    "_co_dm": {
                        "tier": codm["tier"],
                        "tm_title": codm.get("tm_title", ""),
                    },
                    "pro_status": {"2": "staff", "3": "exec", "nlz": "staff"}.get(codm["tier"], "staff"),
                    "shared_station_count": 1,
                })
                added_codms += 1

        # Re-sort with newly added contacts
        if added_hires or added_codms:
            cat_order_post = {"head_coach": 0, "sporting_director": 1, "executive": 2,
                              "coach_hired": 3, "co_decision_maker": 4,
                              "coaching_staff": 5, "lehrgang": 6, "scouting": 7,
                              "management": 8, "academy": 9, "player_coached": 10,
                              "former_teammate": 11, "analyst": 12, "other_staff": 13,
                              "medical": 14}
            contacts_list = sorted(
                contacts_list,
                key=lambda c: (
                    -c.get("relevance_score", 0),
                    cat_order_post.get(c.get("category", ""), 99),
                    (c.get("name") or "").lower(),
                    c.get("tm_id") or 0,
                )
            )
            # Update categories
            for c in contacts_list:
                cat = c.get("category")
                if cat and cat not in all_categories:
                    all_categories.append(cat)
            print(f"  Phase 6 DM-Enrichment: +{added_hires} coach_hired, +{added_codms} co_decision_maker")

        # Attach agent patterns + tier metadata for detail panel display
        ap = SD_AGENT_PATTERNS.get(str(coach_tm_id), {}) or {}
        dm_metadata = {
            "tier": (center_dm or {}).get("tier"),
            "tm_title": (center_dm or {}).get("tm_title"),
            "club_name": (center_dm or {}).get("club_name"),
            "total_hires": len(hh.get("hires") or []),
            "patterns": hh.get("patterns") or {},
            "agent_relationships": (ap.get("agent_relationships") or [])[:3],
        }

    # ── FINAL ID-INTEGRITY SANITIZER (2026-06-04) ──────────────────────────
    # Single chokepoint guarding against TM namespace id-reuse: if a contact's
    # _tm_id resolves (in EITHER namespace) only to a DIFFERENT person, any
    # role/current_club enriched from that wrong profile is bogus. Strip such
    # fields back to a safe player-base. Catches every upstream path at once
    # (GS bogus ids, lookup_active_staff namesakes, career-history leaks).
    _ns_cache = _cache.get("profiles_ns") or {}
    _san = 0
    for c in contacts_list:
        tid = c.get("_tm_id")
        if not tid:
            continue
        sp = _ns_cache.get(f"spieler_{tid}")
        tr = _ns_cache.get(f"trainer_{tid}")
        names = [p.get("name") for p in (sp, tr) if p]
        if not names:
            continue  # no profile to contradict the contact — leave as-is
        if any(_name_matches(n, c.get("name", "")) for n in names):
            continue  # at least one namespace confirms the person — OK
        # Neither namespace matches → the id points at someone else. EVERY field
        # enriched from that wrong profile is bogus, regardless of the contact's
        # CURRENT category — because an upstream path may have FALSELY PROMOTED a
        # player/teammate to head_coach/scouting/exec using the foreign profile
        # (Marco Bode → "head_coach US Salernitana"; Ilsanker → wrong id 1040).
        cat = c.get("category")
        # Detect a player/teammate ORIGIN even if currently mislabeled.
        is_player_origin = (
            cat in ("former_teammate", "player_coached")
            or c.get("shared_matches") is not None
            or str(c.get("note", "")).lower().startswith(("mitspieler", "spieler"))
            or c.get("relationship_type") == "playing"
        )
        c["current_club"] = None
        c["career_history"] = None
        c.pop("post_career_role", None)
        if is_player_origin:
            # revert any false promotion back to teammate/player
            base_cat = "player_coached" if cat == "player_coached" else "former_teammate"
            c["category"] = base_cat
            c["pro_status"] = "player"
            if not str(c.get("role", "")).lower().startswith(("mitspieler", "spieler")):
                c["role"] = "Mitspieler" if base_cat == "former_teammate" else "Spieler"
        else:
            # unknown-origin contact with a wrong id: neutralize the role/club but
            # keep the name; don't invent a category.
            if c.get("role") and "(" in str(c.get("role")):
                c["role"] = str(c["role"]).split("(")[0].strip() or "Unbekannt"
        _san += 1
    if _san:
        print(f"  ID-sanitizer: reset {_san} contact(s) with mismatched namespace id")

    # Same-profile dedup (logic_audit LX2 2026-06-07): one person can enter via
    # two different _tm_id values that BOTH resolve to the same TM profile url
    # (e.g. Hans-Jörg Honold: staff id 10853 + academy id 24762, both pointing at
    # /trainer/10853). Merge by tm_url namespace: keep the higher-relevance
    # contact, union its stations. Only touches exact same-profile pairs, so
    # networks without such a collision are unaffected.
    _by_url = {}
    _dedup_drop = set()
    for c in contacts_list:
        m = _re_module.search(r"/(spieler|trainer)/(\d+)", c.get("tm_url") or "")
        if not m:
            continue
        key = (m.group(1), m.group(2))
        prev = _by_url.get(key)
        if prev is None:
            _by_url[key] = c
            continue
        rank = lambda x: ((x.get("relevance_score") or 0), len(x.get("stations") or []))
        better, worse = (c, prev) if rank(c) > rank(prev) else (prev, c)
        su = better.setdefault("stations", [])
        for s in worse.get("stations", []) or []:
            if s not in su:
                su.append(s)
        _dedup_drop.add(id(worse))
        _by_url[key] = better
    if _dedup_drop:
        contacts_list = [c for c in contacts_list if id(c) not in _dedup_drop]
        print(f"  Same-URL dedup: merged {len(_dedup_drop)} duplicate-profile contact(s)")

    # ── SCORING FINALIZER (2026-06-20) ─────────────────────────────────────
    # Single chokepoint after ALL contacts exist (incl. Phase-6 DM-Enrichment
    # additions: coach_hired / co_decision_maker, which are appended after the
    # main strength loop + sort). Guarantees two invariants validated by
    # execution/scoring_audit.py: every contact has a strength (1-5 from
    # relationship duration), and contacts are ordered by relevance_score DESC.
    for c in contacts_list:
        if c.get("strength") is None:
            _st = c.get("seasons_together", 1) or 1
            c["strength"] = min(5, max(1, (_st + 1) // 2))
    contacts_list.sort(key=lambda c: (
        -(c.get("relevance_score") or 0),
        cat_order.get(c.get("category", ""), 99),
        (c.get("name") or "").lower(),
        _safe_int(c.get("tm_id")),
    ))

    network = {
        "center": profile["name"],
        "center_info": {
            "role": current_role,
            "dob": normalize_dob(profile.get("dob", "")),
            "nationality": nationality,
            "license": profile.get("license"),
            "tm_url": profile.get("tm_url", ""),
            "image_url": filter_default_image(profile.get("image_url", "")),
        },
        "total_contacts": len(contacts_list),
        "stations": all_stations,
        "categories": all_categories,
        "contacts": contacts_list,
    }
    if dm_metadata:
        network["dm_info"] = dm_metadata

    elapsed = time.time() - t0
    print(f"  ✓ Done: {len(contacts_list)} contacts, {len(all_stations)} stations ({elapsed:.1f}s)")
    return network


def generate_background_summaries(network: dict) -> dict:
    """Generate template-based German summaries per contact.

    Enhanced to include multi-station information and cross-references.
    """
    center = network["center"]

    for c in network.get("contacts", []):
        cat = c.get("category", "")
        stations_str = ", ".join(c.get("stations", []))
        note = c.get("note", "")
        shared_count = c.get("shared_station_count", 0)

        lehrgang_cohort = c.get("lehrgang_cohort", "")
        templates = {
            "player_coached": f"Spielte unter {center} bei {stations_str}.",
            "former_teammate": f"Mitspieler von {center} bei {stations_str}.",
            "head_coach": f"Trainerkollege von {center} ({note}).",
            "coaching_staff": f"Im Trainerstab mit {center} ({note}).",
            "sporting_director": f"Sportdirektor während {center}s Zeit bei {stations_str}.",
            "scouting": f"Scout bei {stations_str}, gleichzeitig mit {center}.",
            "management": f"Management bei {stations_str} während {center}s Zeit.",
            "academy": f"NLZ/Jugend bei {stations_str}.",
            "analyst": f"Analyst bei {stations_str}, gleichzeitig mit {center}.",
            "lehrgang": f"Gemeinsamer DFB Fußball-Lehrer-Lehrgang ({lehrgang_cohort}) mit {center}.",
        }

        summary = templates.get(cat, f"Mitarbeiter bei {stations_str}.")

        # Enhance with multi-station information
        if shared_count >= 2:
            summary += f" Gemeinsam bei {shared_count} Stationen."

        # Enhance with coach/SD cross-references
        coaches_w = c.get("coaches_worked_with", [])
        sds_w = c.get("sds_worked_with", [])

        if coaches_w or sds_w:
            connections = []
            if coaches_w:
                coach_names = [cw["name"] for cw in coaches_w[:3]]
                connections.append(f"Trainer: {', '.join(coach_names)}")
            if sds_w:
                sd_names = [sd["name"] for sd in sds_w[:2]]
                connections.append(f"SDs: {', '.join(sd_names)}")

            if connections:
                summary += f" Auch verbunden über: {'; '.join(connections)}."

        c["background_summary"] = summary

    # D1-Fix (2026-05-11): drop the internal field AFTER summaries are generated.
    # Previously popped in build_network() before generate_background_summaries() ran
    # → produced empty parens "Lehrgang ()" in hundreds of summaries.
    for c in network.get("contacts", []):
        c.pop("lehrgang_cohort", None)

    return network


def build_drilldown(center_network: dict, profiles: Dict[int, dict],
                    profile_index: Dict[Tuple[int, int], List[int]],
                    max_contacts: int = 15,
                    max_drilldowns: int = 50) -> dict:
    """
    Build DRILLDOWN dict for drill-downable contacts in a network.
    Each contact with a scraped profile gets their own sub-network (one level deep).

    max_drilldowns caps the total number of sub-networks built.  Contacts are
    processed in relevance-score order (highest first, as output by build_network),
    so the cap naturally preserves the most important connections.

    Returns:
        {contact_name: sub_network_dict, ...}
    """
    drilldown = {}
    drilldown_count = 0

    for contact in center_network["contacts"]:
        # Skip players — they usually don't have career history
        if contact.get("category") == "player_coached":
            continue

        # Hard cap — contacts are sorted by relevance score so top-N non-player
        # contacts are kept.  Players are excluded from this count.
        if drilldown_count >= max_drilldowns:
            break

        # Need tm_id to look up profile
        tm_id = contact.get("_tm_id")
        if not tm_id or tm_id not in profiles:
            continue

        # Build their network
        sub_network = build_network(tm_id, profiles, profile_index)
        if not sub_network:
            continue

        # Skip background summaries for sub-networks (saves ~60% drilldown size)
        # Trim to max_contacts (keep top contacts by strength)
        if len(sub_network["contacts"]) > max_contacts:
            sub_network["contacts"] = sub_network["contacts"][:max_contacts]
            sub_network["total_contacts"] = len(sub_network["contacts"])

        # Sub-networks: strip heavy fields to minimize inline JSON size.
        # NOTE: keep _tm_id so drill-down contacts can cross-link to their own dashboards
        # (Eta → Fischer → … chain).
        for c in sub_network["contacts"]:
            c["has_drilldown"] = False
            c.pop("background_summary", None)  # Biggest text field
            c.pop("coaches_worked_with", None)  # Not needed in sub-view
            c.pop("sds_worked_with", None)

        # Key must match template: name.toLowerCase().replace(/ /g, '_')
        key = contact["name"].lower().replace(" ", "_")
        drilldown[key] = sub_network
        contact["has_drilldown"] = True
        drilldown_count += 1

    print(f"  Drilldown: {drilldown_count} sub-networks")
    return drilldown


def strip_internal_fields(network: dict) -> dict:
    """No-op as of 2026-04-29: _tm_id is now retained for dashboard cross-linking
    (template uses DASHBOARD_INDEX[c._tm_id] in detail panel + table NET badge).
    Kept as a function for backward compatibility with import sites in
    generate_all_bl_coaches.py.
    """
    return network


# ── Main ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Build coach network from existing data")
    parser.add_argument("--tm-id", type=int, help="Coach Transfermarkt ID")
    parser.add_argument("--output", type=str, help="Output JSON path")
    parser.add_argument("--list-bl-coaches", action="store_true", help="List all BL1+BL2 head coaches")
    parser.add_argument("--season", type=int, default=2025, help="Season (default: 2025)")
    args = parser.parse_args()

    if args.list_bl_coaches:
        club_registry = load_club_registry()
        coaches = list_bl_coaches(club_registry, args.season)

        print(f"\n{'='*70}")
        print(f"  BL1 + BL2 Head Coaches — Season {format_season(args.season)}")
        print(f"{'='*70}")

        for league in ["BL1", "BL2"]:
            lc = sorted([c for c in coaches if c["league"] == league], key=lambda x: x["club"])
            print(f"\n  {league} ({len(lc)} coaches):")
            print(f"  {'─'*60}")
            for c in lc:
                mark = "✓" if c["has_profile"] else "✗"
                info = f"{c['career_stations']} stations" if c["has_profile"] else "no profile"
                print(f"  {mark} {c['name']:<30} {c['club']:<25} (ID: {c['tm_id']}, {info})")

        print(f"\n  Total: {len(coaches)} coaches")
        return

    if not args.tm_id:
        parser.error("--tm-id required (or use --list-bl-coaches)")

    # Preload data once
    profiles = preload_all_profiles()
    profile_index = build_profile_index(profiles)

    network = build_network(args.tm_id, profiles, profile_index)
    if not network:
        print("  ✗ Failed")
        return

    network = generate_background_summaries(network)

    # FIX 2026-05-21 (F7): Finale Display-Normalisierung.
    # National-Federation-Mapping für current_club: "Deutschland" → "DFB" etc.
    # Wird hier zentral angewendet, damit alle Downstream-Konsumenten (Dashboard,
    # Drilldown, Index, Club-Pages) die Verband-Abkürzung sehen.
    try:
        from lib.normalization import federation_label
        for c in network.get("contacts", []) or []:
            cc = c.get("current_club")
            if isinstance(cc, str) and cc:
                c["current_club"] = federation_label(cc)
            # Stations können ebenfalls Country-Namen enthalten (z.B. bei Bundes-Trainern)
            stations = c.get("stations")
            if isinstance(stations, list):
                c["stations"] = [federation_label(s) if isinstance(s, str) else s for s in stations]
    except Exception as e:
        print(f"  ⚠ Federation-Label-Normalisierung übersprungen: {e}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = Path(args.output) if args.output else OUTPUT_DIR / f"{args.tm_id}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(network, f, ensure_ascii=False, indent=2)

    print(f"\n  ✓ Saved: {output_path}")
    print(f"  {network['total_contacts']} contacts | {len(network['stations'])} stations")


if __name__ == "__main__":
    main()
