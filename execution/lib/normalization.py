"""
Shared normalization and classification functions for the coach network pipeline.

Extracted from build_coach_network.py to avoid duplication across scripts.
All scripts should import from here instead of defining their own versions.

Usage:
    from lib.normalization import normalize_club, classify_role, classify_staff_section
    from lib.normalization import CLUB_NAME_NORMALIZE, slugify, PSEUDO_CLUBS
"""

import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional

BASE = Path(__file__).parent.parent.parent  # execution/lib/ → project root


# ── Pseudo-clubs (TM virtual buckets that pollute network coach_club_seasons) ──
# These TM "clubs" are not real teams — they aggregate people across many real
# clubs. Treating them as a station produces false connections (e.g. every
# Frauenfußball staff member in any club gets +15 station-points for an Eta network).
# See AUDIT 2026-04-29 D3.
PSEUDO_CLUBS = {
    "Frauenfußball",        # TM tm_id 36877: women's-football aggregator
    "Frauenfussball",
    "Damenfußball",
}

# Pseudo-club name patterns → matched as substring (covers DFB-Lehrgang YYYY/YYYY)
PSEUDO_CLUB_PATTERNS = (
    "DFB-Lehrgang",
    "Trainerausbildung",
    "Trainerlehrgang",
)


def is_pseudo_club(name: str) -> bool:
    """True if a club name is a TM virtual bucket and should be excluded from
    coach_club_seasons / station scoring."""
    if not name:
        return False
    if name in PSEUDO_CLUBS:
        return True
    return any(p in name for p in PSEUDO_CLUB_PATTERNS)


# ── Slug helpers — used by 4+ scripts; centralized here ──────────────
# German + romance transliteration map. Applied BEFORE the [^a-z0-9] collapse
# so "Marie-Louise Eta" → "marie_louise_eta", "Schönweitz" → "schoenweitz",
# "André" → "andre", "Pereira" → "pereira", "İlkay" → "ilkay".
_TRANSLITERATE = str.maketrans({
    "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
    "Ä": "ae", "Ö": "oe", "Ü": "ue",
    "é": "e", "è": "e", "ê": "e", "ë": "e",
    "á": "a", "à": "a", "â": "a", "ã": "a", "å": "a",
    "í": "i", "ì": "i", "î": "i", "ï": "i", "İ": "i",
    "ó": "o", "ò": "o", "ô": "o", "õ": "o", "ø": "o",
    "ú": "u", "ù": "u", "û": "u",
    "ý": "y", "ÿ": "y",
    "ñ": "n", "ç": "c", "ł": "l", "ž": "z", "š": "s", "č": "c", "ć": "c",
    "ř": "r", "đ": "d",
})


def slugify(name: str) -> str:
    """Canonical slug rule for the entire pipeline.

    Steps:
      1. Lower-case
      2. Transliterate diacritics (ä→ae, é→e, ß→ss, …)
      3. NFD-normalize + strip remaining combining marks (catches anything missed)
      4. Collapse non-alphanum runs to underscore
      5. Trim underscores

    Examples:
      "Marie-Louise Eta"   → "marie_louise_eta"
      "Meikel Schönweitz"  → "meikel_schoenweitz"
      "André Hofschneider" → "andre_hofschneider"
      "Dr. André Filipovic"→ "dr_andre_filipovic"
      "O'Brien"            → "o_brien"
    """
    if not name:
        return ""
    s = name.lower().translate(_TRANSLITERATE)
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s


# ── Club name normalization ──────────────────────────────────────────

CLUB_NAME_NORMALIZE = {
    # Short → Long forms (from TM career tables)
    "Bor. Dortmund": "Borussia Dortmund",
    "Bor. M'gladbach": "Borussia M'gladbach",
    "Borussia Mönchengladbach": "Borussia M'gladbach",
    "1.FC K'lautern": "1.FC Kaiserslautern",
    "B. Leverkusen": "Bayer 04 Leverkusen",
    "E. Frankfurt": "Eintracht Frankfurt",
    "F. Düsseldorf": "Fortuna Düsseldorf",
    "B. München": "Bayern München",
    "B. München II": "Bayern München II",
    "B. München U17": "Bayern München U17",
    "B. München U19": "Bayern München U19",
    "B. München Jgd.": "Bayern München Jgd.",
    "B. München YL": "Bayern München YL",
    # Suffix variants (TM uses both forms)
    "1.FC Heidenheim 1846": "1.FC Heidenheim",
    "TSG 1899 Hoffenheim": "TSG Hoffenheim",
    "SC Paderborn 07": "SC Paderborn",
    "SV 07 Elversberg": "SV Elversberg",
    # FC Ingolstadt 04 is the canonical name (04 is part of it, like Schalke 04)
    "Hertha BSC II": "Hertha BSC II",
    # Youth team suffix variants
    "FC Ingolstadt": "FC Ingolstadt 04",
    "Ingolstadt Jgd.": "FC Ingolstadt 04 Jgd.",
    "Ingolstadt U17": "FC Ingolstadt 04 U17",
    "Ingolstadt U19": "FC Ingolstadt 04 U19",
    "Ingolstadt II": "FC Ingolstadt 04 II",
    "TSG 1899 Hoffenheim II": "TSG Hoffenheim II",
    "TSG 1899 Hoffenheim U17": "TSG Hoffenheim U17",
    "TSG 1899 Hoffenheim U19": "TSG Hoffenheim U19",
    "SC Paderborn 07 II": "SC Paderborn II",
    "SC Paderborn 07 U17": "SC Paderborn U17",
    "SC Paderborn 07 U19": "SC Paderborn U19",
    "Borussia Mönchengladbach II": "Borussia M'gladbach II",
    "Borussia Mönchengladbach U17": "Borussia M'gladbach U17",
    "Borussia Mönchengladbach U19": "Borussia M'gladbach U19",
    # SCB Viktoria variants
    "SCB Vikt. U19": "SCB Viktoria U19",
}

# Module-level cache for club registry
_club_registry_cache: Optional[Dict] = None


def load_club_registry() -> Dict[int, dict]:
    """Load club_registry.json and return as {tm_id: club_dict}."""
    global _club_registry_cache
    if _club_registry_cache is not None:
        return _club_registry_cache

    registry_path = BASE / "data" / "club_registry.json"
    if not registry_path.exists():
        _club_registry_cache = {}
        return _club_registry_cache

    with open(registry_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # Registry stores clubs as a list under 'clubs' key
    clubs_list = raw.get("clubs", []) if isinstance(raw, dict) else raw
    _club_registry_cache = {}
    for club in clubs_list:
        tm_id = club.get("tm_id")
        if tm_id:
            _club_registry_cache[int(tm_id)] = club

    return _club_registry_cache


def normalize_club(name: str, club_tm_id: int = None) -> str:
    """Normalize TM club name to canonical form.

    Priority: 1) CLUB_NAME_NORMALIZE dict, 2) club_registry lookup, 3) raw name.
    All results pass through the dict a second time to catch registry names with suffixes.
    """
    if name in CLUB_NAME_NORMALIZE:
        return CLUB_NAME_NORMALIZE[name]
    if club_tm_id:
        registry = load_club_registry()
        reg_club = registry.get(club_tm_id)
        if reg_club:
            reg_name = reg_club.get("name", name)
            return CLUB_NAME_NORMALIZE.get(reg_name, reg_name)
    return name


# ── Role classification ──────────────────────────────────────────────

def classify_role(role_str: str) -> str:
    """Classify a TM role string into a dashboard category.

    Specialist roles (Reha-, Individual-, Technik-, Konditions-, Performance-)
    are coaching_staff, NOT head_coach. The previous keyword chain promoted them
    to head_coach because "trainer" matched first. See AUDIT 2026-04-29 D1.

    Order of checks matters:
      1. Specialist keywords → coaching_staff (catches Performance Director too)
      2. Academy/youth keywords → academy (U19-Trainer is NOT a head coach)
      3. Generic trainer/coach/manager → head_coach
    """
    r = (role_str or "").lower()

    # Medical staff — must be checked BEFORE specialist (else "Physiotherapeut" wandert
    # via "physio" → coaching_staff). Live-Audit 2026-04-30: Simeon Unger (RB Leipzig
    # Physio) saß bei 69 als Coaching Staff — gehört auf medical (role_weight 2).
    MEDICAL_KEYWORDS = [
        "physio", "arzt", "medizin", "mannschaftsarzt", "teamarzt",
        "doktor", "rehabilitation", "therapeut",
        "osteopath", "chiropraktor", "ernährung",
    ]
    if any(x in r for x in MEDICAL_KEYWORDS):
        return "medical"

    # Specialist/performance roles always coaching_staff (covers "Performance Director"
    # even though it lacks trainer/coach/manager).
    # NB: "reha" (alone) bleibt specialist weil "Rehatrainer" ein Trainer-Spezialist ist.
    # "Reha-Therapeut" / "Rehabilitations-Trainer" werden über medical-Liste gefangen.
    SPECIALIST_KEYWORDS = [
        "co-", "co_", "co ", "assistant", "torwart", "goalkeep",
        "athletik", "athletic", "fitness", "kondition",
        "reha", "individual", "technik", "performance",
        "skill", "mental", "kraft",
    ]
    if any(x in r for x in SPECIALIST_KEYWORDS):
        return "coaching_staff"

    # Team-manager / Mannschaftsleiter / Sportkoordinator → coaching_staff
    # (Trainerstab-nah, NICHT head_coach via generic "manager" keyword).
    # SCORING_FEEDBACK 2026-05-13 A1b: Bornemann-SD-Network promoted Teammanager
    # too high because "manager" matched the generic head_coach branch below.
    TEAMMANAGER_KEYWORDS = [
        "teammanager", "team-manager", "team manager",
        "mannschaftsleiter", "mannschaftsleitung",
        "teammanagement", "team-management",
        "sportkoordinator",
    ]
    if any(x in r for x in TEAMMANAGER_KEYWORDS):
        return "coaching_staff"

    # Academy/youth check BEFORE head_coach default — "U19-Trainer" is academy
    if any(x in r for x in ["nachwuchs", "nlz", "jugend", "u23", "u19", "u17", "u16", "u15"]):
        return "academy"

    if any(x in r for x in ["trainer", "coach", "manager"]):
        return "head_coach"
    if any(x in r for x in ["sportdirektor", "sportvorstand", "sportgeschäftsführer",
                              "technischer direktor"]):
        return "sporting_director"
    if "scout" in r or "kaderplaner" in r:
        return "scouting"
    if any(x in r for x in ["analyst", "video"]):
        return "analyst"
    if any(x in r for x in ["nachwuchs", "nlz", "jugend", "u19", "u17", "u16", "u15"]):
        return "academy"

    # Executive — OPERATIONAL tier (primary trainer-hire-deciders, day-to-day-Ansprechpartner für Berater)
    # GF Sport, Sport-Vorstand, Director of Football — die ENTSCHEIDEN die Trainerwechsel.
    # 2026-05-15 Live-Audit (Blessin): GF Sport muss höher als AR/Präsident sein.
    EXECUTIVE_OPERATIONAL_KEYWORDS = [
        "vorstand sport", "vorstand fußball", "vorstand profifußball",
        "geschäftsführer sport", "geschäftsführer fußball",
        "geschäftsführer profifußball",
        "sportvorstand", "sportgeschäftsführer",
        "sportlicher leiter", "leiter sport", "leiter lizenz",
        "head of football", "director of football",
        "ceo", "managing director", "executive director",
    ]
    if any(x in r for x in EXECUTIVE_OPERATIONAL_KEYWORDS):
        return "executive"

    # Executive — GOVERNANCE tier (Präsident, AR-Vorsitz, stellv. AR-Vorsitz)
    # Vote-of-confidence / Abnick-Rolle, nicht primärer Hire-Driver.
    EXECUTIVE_GOVERNANCE_KEYWORDS = [
        "präsident", "vize-präsident", "vize präsident",
        "präsidium",
        "präsidiumsmitglied",
        "vorstandsvorsitz", "vorsitzende",
        "aufsichtsratsvorsitz",  # AR-chair + stellv.
    ]
    if any(x in r for x in EXECUTIVE_GOVERNANCE_KEYWORDS):
        return "executive_governance"

    # 2026-05-15 Live-Audit (Blessin): Aufsichtsratsmitglied (ohne -vorsitz) ist
    # KEIN Hire-Decider. Niedrigste Tier → executive_secondary.
    if "aufsichtsrat" in r:
        return "executive_secondary"
    # Plain "Geschäftsführer" / "Vorstandsmitglied" without commercial qualifier →
    # club CEO/MD = hire-and-fire authority. But "Geschäftsführer Marketing/Finanzen"
    # is NOT trainer-hire-relevant → executive_secondary (LOW score).
    # SCORING_FEEDBACK 2026-05-13 A1a (Blessin-Live-Test):
    # Marketing-/Finanz-Vorstand zu hoch im Network — nur Vorstandsvorsitzender
    # + Vorstand Sport sind hire-relevant.
    EXEC_NEGATIVE_KEYWORDS = [
        "marketing", "finanzen", "finanz-", "kaufmännisch", "vertrieb",
        "kommunikation", "personal", "merchandising", "it-",
    ]
    if "geschäftsführer" in r:
        if any(neg in r for neg in EXEC_NEGATIVE_KEYWORDS):
            return "executive_secondary"
        return "executive"
    if "vorstandsmitglied" in r:
        if any(neg in r for neg in EXEC_NEGATIVE_KEYWORDS):
            return "executive_secondary"
        return "executive"
    # Plain "vorstand <X>" — if a commercial qualifier follows, executive_secondary.
    # Pure "vorstand" without qualifier is ambiguous → executive_secondary (safe default).
    if "vorstand" in r:
        if any(neg in r for neg in EXEC_NEGATIVE_KEYWORDS):
            return "executive_secondary"
        # bare "vorstand" / "vorstand kommunikation" etc. already caught above;
        # remaining: e.g. "Vorstand" without qualifier → executive_secondary (cautious)
        return "executive_secondary"
    if any(x in r for x in ["präsident", "vize",
                              "aufsichtsrat", "generalsekretär"]):
        return "management"
    return "other_staff"


def classify_staff_section(section: str) -> str:
    """Classify a staff section from the staff files.

    Order of checks matters: SD/Executive must be checked BEFORE generic
    "geschäfts"/"vorstand" → management, otherwise "Sportvorstand",
    "Geschäftsführer Sport" etc. all collapse into management and we lose
    the decision-maker signal in Networks + DM-Logic (B1 audit 2026-05).
    """
    s = (section or "").lower()
    if "trainer" in s:
        return "coaching_staff"
    # Team-Management / Mannschaftsleiter / Sportkoordinator → Trainerstab-nah.
    # SCORING_FEEDBACK 2026-05-13 A1b: Teammanager landed in management/scouting
    # and ranked too high in SD-Networks.
    if any(x in s for x in ["teammanager", "mannschaftsleit", "teammanagement", "sportkoordinator"]):
        return "coaching_staff"
    # Sporting Director tier — check BEFORE management / scouting fall-through
    SD_KEYWORDS = [
        "sportdirektor", "sportvorstand",
        "geschäftsführer sport", "sportgeschäftsführer",
        "sportlicher leiter", "technischer direktor",
    ]
    if any(x in s for x in SD_KEYWORDS):
        return "sporting_director"
    # Scouting-tier leadership (Sport-Koordinator / Kader-Planer / Head of Scouting)
    if any(x in s for x in ["sportkoordinator", "leiter sport", "kaderplaner", "head of scouting"]):
        return "scouting"
    # Executive tier (board/president/supervisory board/CEO)
    EXEC_KEYWORDS = [
        "vorstandsvorsitz", "vorstandsvorsitzender",
        "präsident", "aufsichtsrat",
        "ceo", "managing director",
    ]
    if any(x in s for x in EXEC_KEYWORDS):
        return "executive"
    # Plain "vorstand" without sport-qualifier → executive (vorstand sport is caught above)
    if "vorstand" in s and "sport" not in s:
        return "executive"
    if "scout" in s or "kaderplan" in s:
        return "scouting"
    if "jugend" in s or "nachwuchs" in s or "nlz" in s:
        return "academy"
    if "medizin" in s or "arzt" in s or "physio" in s:
        return "medical"
    if "geschäfts" in s or "vorstand" in s:
        return "management"
    return "other_staff"


# ── Season parsing ───────────────────────────────────────────────────

def parse_season_from_date(date_str: str) -> Optional[int]:
    """Parse TM date format to a season year.

    "23/24 (19.03.2024)" → 2023, "98/99 (...)" → 1998, "-" → None

    Century cutoff: TM uses 2-digit years for seasons. Anything ≤ 50 maps to
    20xx (covers 2000-2050), > 50 maps to 19xx (1951-1999). Previous threshold
    of 80 caused "75/76" → 2075 instead of 1975 (DB-Audit P2).
    """
    if not date_str or date_str.strip() == "-":
        return None

    m = re.match(r"(\d{2})/(\d{2})", date_str)
    if m:
        yy = int(m.group(1))
        return (2000 + yy) if yy <= 50 else (1900 + yy)

    m2 = re.search(r"\((\d{2})\.(\d{2})\.(\d{4})\)", date_str)
    if m2:
        month, year = int(m2.group(2)), int(m2.group(3))
        return year if month >= 7 else year - 1

    m3 = re.search(r"(\d{4})", date_str)
    if m3:
        return int(m3.group(1))

    return None


def get_season_range(date_from: str, date_to: str) -> List[int]:
    """Get list of seasons where the person was active (clamped to 2010–2025)."""
    start = parse_season_from_date(date_from)
    end = parse_season_from_date(date_to)

    if start is None:
        return []
    if end is None:
        end = 2025  # still active

    start = max(start, 2010)
    end = min(end, 2025)

    return list(range(start, end + 1)) if start <= end else [start]


def format_season(year: int) -> str:
    """Format season year: 2023 → '23/24'."""
    return f"{year % 100:02d}/{(year + 1) % 100:02d}"


# ── Name validation ──────────────────────────────────────────────────

def validate_staff_tm_id(staff_name: str, staff_tm_id: int,
                         profiles: Dict[int, dict]) -> Optional[int]:
    """Validate a staff tm_id against persons_master profiles.

    TM uses separate ID namespaces for players and trainers. The same numeric ID
    can refer to different people (e.g., 306 = Marek Heinz as player, Dieter Hecking
    as trainer). This function checks if the name at staff_tm_id matches the staff
    member's name. If not, returns None to prevent wrong cross-links.

    Returns:
        The tm_id if valid, or None if the name doesn't match (ID collision).
    """
    if not staff_tm_id or staff_tm_id not in profiles:
        return staff_tm_id  # Not in persons_master — can't validate, keep as-is

    canonical_name = profiles[staff_tm_id].get("name", "")
    if not canonical_name:
        return staff_tm_id

    sim = SequenceMatcher(None, staff_name.lower(), canonical_name.lower()).ratio()
    if sim >= 0.80:
        return staff_tm_id  # Name matches — valid

    # Name mismatch — this is a trainer/player ID collision
    return None


# ── League ranking ───────────────────────────────────────────────────

def league_rank(league_code: str) -> int:
    """Return numeric rank for league sorting (lower = better)."""
    ranks = {
        "BL1": 1, "PL": 1, "SA": 1, "L1": 1, "Liga": 1,
        "BL2": 2, "Eredivisie": 2, "Championship": 2,
        "BEL1": 3, "TUR1": 3, "SUI1": 3,
        "BL3": 4, "SerieB": 4, "Ligue2": 4, "LaLiga2": 4,
        "DEN1": 5, "SWE1": 5, "NOR1": 5,
    }
    return ranks.get(league_code, 10)


# ── Nationality filtering ───────────────────────────────────────────

_DISSOLVED_STATES = {'DDR', 'Jugoslawien', 'Sowjetunion', 'Tschechoslowakei'}

def filter_nationality(nat) -> str:
    """Clean nationality field — filter youth teams and dissolved states.

    TM stores nationality as a list like ["Deutschland", "Deutschland U20", ...].
    This function returns a single clean string.
    """
    if not nat:
        return ""
    if isinstance(nat, str):
        # Already a string — check if it's a comma-separated list
        if "," in nat:
            nat = [n.strip() for n in nat.split(",")]
        else:
            return nat

    if isinstance(nat, list):
        # Filter out youth team associations and dissolved states
        real = [n for n in nat
                if not any(x in n for x in [' U1', ' U2', ' U ', 'Jugend'])
                and n not in _DISSOLVED_STATES]
        if len(real) >= 2:
            return real[1]  # Second entry is usually actual nationality
        if real:
            return real[0]
        return nat[0] if nat else ""

    return str(nat)


# ============================================================
# Central Contact-Role Resolver (Schuhen-Pattern Fix, 2026-05-14)
# ============================================================
#
# Every contact-builder (Lehrgang, Mitspieler, SD, Coach, etc.) MUST route the
# `role` field through this function. Inline string construction has historically
# produced regressions: active players were labelled "Trainer" (Marcel Schuhen),
# coaches were labelled "Mitspieler", etc.
#
# Rule of precedence (highest first):
#   1. spieler-type with position  → use position ("Torwart") + current club
#   2. career_history[0].role      → most recent TM-stated role + current club
#   3. fallback string             → caller-supplied default ("Trainer", "Spieler", ...)

GENERIC_ROLE_BLOCKLIST = {
    "", "Trainer", "Spieler", "Mitspieler", "Lehrgangs-Kollege",
    "Staff", None,
}


def resolve_contact_role(tm_id, profiles: Dict[int, dict],
                         fallback: str = "Trainer") -> str:
    """Return canonical role_display string for a contact tm_id.

    Reads `person_profiles/{tm_id}.json` (via the in-memory `profiles` dict)
    and constructs "{role}, {current_club}". Handles the Schuhen-pattern:
    active players keep their position, not "Trainer".

    Returns `fallback` only if NO usable signal exists in the profile.
    """
    if not tm_id:
        return fallback

    try:
        tm_id_int = int(tm_id)
    except (ValueError, TypeError):
        return fallback

    p = profiles.get(tm_id_int) or profiles.get(str(tm_id))
    if not p:
        return fallback

    p_type = p.get("type", "")
    position = p.get("position", "")
    career = p.get("career_history", []) or []

    if p_type == "spieler" and position:
        role = position
    elif career and career[0].get("role"):
        role = career[0]["role"]
    else:
        role = fallback

    current = p.get("current_club") or {}
    club_name = current.get("name", "") if current else ""
    if club_name:
        club_norm = normalize_club(club_name, current.get("tm_id"))
        return f"{role}, {club_norm}" if club_norm else role
    return role


def is_generic_role(role: str) -> bool:
    """True if `role` is a placeholder string that masks the real TM role.

    Only flags bare placeholders ("Trainer", "Mitspieler", ""). Anything with
    a comma + club appended ("Torwart, SV Darmstadt 98") is considered
    informative even if the prefix is in the blocklist.

    Used by audit_all_networks.py to flag stale contacts that need rebuild.
    """
    if not role:
        return True
    if "," in role:
        return False  # has a club suffix → informative enough
    return role.strip() in GENERIC_ROLE_BLOCKLIST


# ──────────────────────────────────────────────────────────────────────
# Bug-1-Systematik (2026-05-19): zentrale Role-Display-Computation.
#
# Vorher: Role-Display wurde an mind. 4 verschiedenen Stellen gebildet
# (build_coach_network.py:1681, lib/active_staff_index promote, Section 1b
# direct-add, persons_master career_history fallback). Jede Stelle hatte
# eigene Logik → "Trainerstab, Deutschland" für Nagelsmann (statt "Bundes-
# trainer"), "Mitarbeiter, Mainz" für aktive Co-Trainer, etc.
#
# Jetzt: compute_role_display() ist die EINZIGE Funktion. Alle Pfade
# rufen sie auf. Ein Fix wirkt überall.
# ──────────────────────────────────────────────────────────────────────

# Nationalmannschaften: spezifisches Label "Bundestrainer" statt "Cheftrainer"
NATIONAL_TEAMS = {
    "Deutschland", "Österreich", "Schweiz", "Luxemburg", "Liechtenstein",
    "England", "Schottland", "Wales", "Nordirland", "Irland",
    "Frankreich", "Spanien", "Italien", "Niederlande", "Belgien", "Portugal",
    "Polen", "Tschechien", "Dänemark", "Schweden", "Norwegen", "Finnland",
    "Kroatien", "Serbien", "Slowenien", "Slowakei", "Ungarn", "Türkei",
}

# Kategorie → Default-Label (Fallback wenn keine spezifische Section verfügbar)
_CATEGORY_LABEL = {
    "head_coach": "Cheftrainer",
    "coaching_staff": "Co-Trainer",
    "academy": "Trainer NLZ",
    "sporting_director": "Sportdirektor",
    "executive": "Geschäftsführer Sport",
    "executive_governance": "Präsidium",
    "scouting": "Scout",
    "analyst": "Analyst",
    "management": "Management",
    "medical": "Medizinische Abteilung",
    "lehrgang": "Lehrgangs-Kollege",
    "former_teammate": "Mitspieler",
    "player_coached": "Spieler",
    "other_staff": "Mitarbeiter",
}

# Sections die als generischer Container gelten und durch die category
# überschrieben werden sollen (z.B. "Trainerstab" → kategorie-spezifisch)
_GENERIC_SECTIONS = {
    "Trainerstab", "Mitarbeiter", "Staff", "Sonstiges", "",
}


def compute_role_display(category: str, section: str = "", club_name: str = "",
                          career_history: list = None, position: str = "",
                          person_type: str = "") -> str:
    """Single source of truth for "Role, Club" display string on contact rows.

    Priority order:
      1. Active player (type=spieler + position) → "{position}, {club}"
         e.g. "Torwart, SV Darmstadt 98" (Marcel Schuhen)
      2. Head-coach at a national team → "Bundestrainer, {country}"
         e.g. "Bundestrainer, Deutschland" (Nagelsmann)
      3. Head-coach at a club → "Cheftrainer, {club}"
      4. Specific section (Sportdirektor, Sportvorstand etc.) → "{section}, {club}"
      5. Generic section ("Trainerstab", "") → fall back to category label
         (e.g. "Co-Trainer, Mainz" instead of "Trainerstab, Mainz")
      6. Career-history latest role as last resort
      7. Plain category label without club

    Args:
        category: contact category (head_coach, coaching_staff, ...)
        section: TM staff section name ("Trainerstab", "Sportdirektor", ...)
        club_name: current club (already normalized)
        career_history: optional, latest entry's role used as fallback
        position: TM player position ("Torwart") — wins for active players
        person_type: "spieler" / "trainer" — drives priority 1

    Returns: formatted "Role, Club" string. Never None or empty.
    """
    club = (club_name or "").strip()
    cat = category or ""

    # Priority 1: Active player keeps position label (Marcel-Schuhen-Pattern)
    if person_type == "spieler" and position:
        return f"{position}, {club}" if club else position

    # Priority 2+3: head_coach gets specific Bundestrainer/Cheftrainer prefix
    if cat == "head_coach":
        if club in NATIONAL_TEAMS:
            return f"Bundestrainer, {club}"
        if club:
            return f"Cheftrainer, {club}"
        return "Cheftrainer"

    # Priority 4: specific section beats generic category label
    section_clean = (section or "").strip()
    if section_clean and section_clean not in _GENERIC_SECTIONS:
        if club:
            return f"{section_clean}, {club}"
        return section_clean

    # Priority 5: generic section → use category-default label
    cat_label = _CATEGORY_LABEL.get(cat)
    if cat_label:
        if club:
            return f"{cat_label}, {club}"
        return cat_label

    # Priority 6: latest career-history role as last resort
    if career_history:
        latest = career_history[0] if isinstance(career_history, list) else None
        if isinstance(latest, dict) and latest.get("role"):
            role = latest["role"]
            if club:
                return f"{role}, {club}"
            return role

    # Priority 7: bare category fallback (never empty)
    fallback = cat_label or "Mitarbeiter"
    return f"{fallback}, {club}" if club else fallback


# ──────────────────────────────────────────────────────────────────────
# Bug-2-Systematik (2026-05-19): zentrale Mitspieler-Stationen-Berechnung.
#
# Vorher: GS-add-Branch berechnete stations leer ([]). Squad-overlap-Branch
# setzte stations korrekt. Beide Pfade hatten eigene Logik.
#
# Jetzt: compute_shared_playing_stations() ist die einzige Quelle der Wahrheit.
# Beide Pfade nutzen sie. Stations sind konsistent gefüllt.
# ──────────────────────────────────────────────────────────────────────

def compute_shared_playing_stations(coach_playing_career: list,
                                     player_career_history: list) -> list:
    """Return list of normalized club-names where coach and player overlapped
    as players (intersection of both career_history lists by club_tm_id/name).

    Args:
        coach_playing_career: list of {club_tm_id, club_name, ...} from coach
                              profile.playing_career
        player_career_history: list of {club_tm_id, club_name, ...} from
                                persons_master[player_tm_id].career_history

    Returns: ordered list of normalized club names (most-recent first if
             player_career_history is sorted that way). Empty list if no
             overlap or no input.
    """
    if not coach_playing_career or not player_career_history:
        return []

    coach_clubs = set()
    coach_club_ids = set()
    for e in coach_playing_career:
        if not isinstance(e, dict):
            continue
        cn = e.get("club_name") or ""
        cid = e.get("club_tm_id")
        if cn:
            coach_clubs.add(normalize_club(cn, cid))
        if cid:
            try:
                coach_club_ids.add(int(cid))
            except (ValueError, TypeError):
                pass

    shared = []
    seen = set()
    for pe in player_career_history:
        if not isinstance(pe, dict):
            continue
        pe_cn = pe.get("club_name") or ""
        pe_cid = pe.get("club_tm_id")
        pe_norm = normalize_club(pe_cn, pe_cid)
        if not pe_norm:
            continue

        match = False
        if pe_norm in coach_clubs:
            match = True
        elif pe_cid is not None:
            try:
                if int(pe_cid) in coach_club_ids:
                    match = True
            except (ValueError, TypeError):
                pass

        if match and pe_norm not in seen:
            shared.append(pe_norm)
            seen.add(pe_norm)
    return shared


# ──────────────────────────────────────────────────────────────────────
# Bug-3a-Systematik (2026-05-19): zentrale TM-URL-Konstruktion für Trainer.
#
# Vorher: tm_url wurde in build_coach_network override-block manuell zusammen-
# gebaut. Bei Override-Einträgen ohne `trainer_tm_id` wurde die alte Spieler-
# URL beibehalten. Slug-Generierung war primitiv und in der Funktion inline.
#
# Jetzt: build_trainer_url() ist EINE Funktion. resolve_trainer_tm_id() füllt
# fehlende trainer_tm_id automatisch aus persons_master (Spieler→Trainer-
# Profil-Detection per Name+DOB).
# ──────────────────────────────────────────────────────────────────────

def build_trainer_url(name: str, trainer_tm_id) -> str:
    """Construct canonical Transfermarkt trainer-profile URL.

    Slug generation matches TM's URL scheme: lowercase, hyphenated, umlauts
    expanded (ä→ae, ö→oe, ü→ue, ß→ss), apostrophes removed, dots stripped.
    e.g. "Marcel Rapp" + 24235 → ".../marcel-rapp/profil/trainer/24235"
         "Fabián Hürzeler" + 48076 → ".../fabian-huerzeler/profil/trainer/48076"

    Args:
        name: person's display name
        trainer_tm_id: TM trainer-profile ID (int or str)

    Returns: full HTTPS URL string, or empty string if inputs invalid.
    """
    if not name or not trainer_tm_id:
        return ""
    try:
        tid = int(trainer_tm_id)
    except (ValueError, TypeError):
        return ""

    # Umlaut expansion FIRST (slugify strips them via NFD, we want ae/oe/ue/ss)
    s = name.lower()
    s = (s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
           .replace("ß", "ss"))
    # Remove apostrophes, dots, then NFD-strip remaining diacritics
    s = s.replace("'", "").replace(".", "")
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    # Replace non-letter/digit with hyphen, collapse, trim
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    s = re.sub(r"-+", "-", s)
    return f"https://www.transfermarkt.de/{s}/profil/trainer/{tid}"


def resolve_trainer_tm_id(spieler_tm_id, person_name: str,
                            persons_master: dict) -> int:
    """Find separate trainer-profile tm_id for a person known by spieler_tm_id.

    TM uses different IDs for spieler/trainer profiles of the same person
    (Dual-ID quirk). If persons_master contains a `trainer`-typed entry with
    the same name as the spieler entry, return its tm_id.

    Used by override-loader and contact-resolution to systematically replace
    stale spieler-URLs with active trainer-URLs without per-person curation.

    Args:
        spieler_tm_id: the contact's current (likely stale) tm_id
        person_name: the contact's full name (for cross-id lookup)
        persons_master: data/persons_master.json `persons` dict

    Returns: trainer tm_id (int) if a distinct match is found, else 0.
    """
    if not person_name or not persons_master:
        return 0
    norm_name = (person_name or "").strip().lower()
    if not norm_name:
        return 0

    try:
        spi_id = int(spieler_tm_id) if spieler_tm_id is not None else None
    except (ValueError, TypeError):
        spi_id = None

    candidates = []
    for tm_id, v in persons_master.items():
        if not isinstance(v, dict):
            continue
        if v.get("type") != "trainer":
            continue
        if (v.get("name") or "").strip().lower() != norm_name:
            continue
        try:
            cid = int(tm_id)
        except (ValueError, TypeError):
            continue
        if spi_id is not None and cid == spi_id:
            continue  # same id → not a distinct trainer profile
        candidates.append(cid)

    if len(candidates) == 1:
        return candidates[0]
    # Ambiguous: multiple trainer profiles with same name → do NOT auto-resolve
    return 0
