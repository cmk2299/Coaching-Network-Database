"""Pure relevance-scoring components extracted from build_coach_network.build_network()
(decomposition 2026-06-21). The former_teammate post-career promotion logic stays in
build_network (it mutates contacts); everything here is side-effect-free and unit-tested.

Final score = relationship + role + league + recency + gs_bonus, then multi-station
multiplier, then max(.,category_floor), capped at 100. (role_score itself is computed
in build_network because the former_teammate path has side effects.)
"""
from .normalization import is_pseudo_club

# ── Role weights (Dimension 2) — coach-centered vs SD/Exec-centered networks ──
ROLE_WEIGHTS_SD_CENTER = {
    "head_coach": 35,
    "coaching_staff": 22,
    "sporting_director": 22,
    "executive": 22,
    "executive_governance": 14,
    "executive_secondary": 9,
    "scouting": 14,
    "lehrgang": 10,
    "academy": 8,
    "management": 6,
    "analyst": 4,
    "other_staff": 2,
    "medical": 2,
}
ROLE_WEIGHTS_COACH_CENTER = {
    "sporting_director": 35,
    "executive": 32,
    "executive_governance": 20,
    "executive_secondary": 12,
    "head_coach": 25,
    "coaching_staff": 12,
    "lehrgang": 10,
    "scouting": 10,
    "management": 8,
    "academy": 6,
    "analyst": 4,
    "other_staff": 2,
    "medical": 2,
}


def role_weights(is_sd_center: bool) -> dict:
    return ROLE_WEIGHTS_SD_CENTER if is_sd_center else ROLE_WEIGHTS_COACH_CENTER


# ── Dimension 1: Beziehungsstärke (0–40) ──
def score_relationship(shared_station_count: int, seasons_together: int,
                       is_lehrgang: bool) -> int:
    station_pts = min(shared_station_count * 15, 30)
    season_pts = min(seasons_together * 3, 15)
    lehrgang_bonus = 5 if is_lehrgang else 0
    return min(station_pts + season_pts + lehrgang_bonus, 40)


# ── Dimension 3: Liga-Level (0–20, role-weighted) ──
LEAGUE_WEIGHTS = {
    "BL1": 20, "PL": 20, "SA": 18, "L1": 18, "Liga": 18,
    "BL2": 15, "Eredivisie": 15, "Championship": 14,
    "BL3": 10, "SerieB": 10, "Ligue2": 10, "LaLiga2": 10,
    "BEL1": 12, "SUI1": 10, "TUR1": 12, "DEN1": 8, "SWE1": 8, "NOR1": 8,
}
_NATIONAL_TEAMS_MAX = ("Deutschland", "England", "France", "Spain", "Italy")
LEAGUE_MOD_SD_CENTER = {
    "head_coach": 1.0, "coaching_staff": 0.85,
    "sporting_director": 0.75, "executive": 0.75,
    "management": 0.5, "scouting": 0.7,
    "lehrgang": 0.4, "academy": 0.5, "analyst": 0.4,
    "player_coached": 0.4, "former_teammate": 0.25,
    "other_staff": 0.15, "medical": 0.15,
}
LEAGUE_MOD_COACH_CENTER = {
    "sporting_director": 1.0, "head_coach": 1.0, "executive": 1.0,
    "management": 0.7, "coaching_staff": 0.65, "scouting": 0.65,
    "lehrgang": 0.35, "academy": 0.45, "analyst": 0.35,
    "player_coached": 0.4, "former_teammate": 0.25,
    "other_staff": 0.15, "medical": 0.15,
}


def score_league(current_club: str, club_best_league: dict, cat: str,
                 is_sd_center: bool, role_score: int, is_still_player: bool) -> int:
    club_league = club_best_league.get(current_club, "")
    league_raw = LEAGUE_WEIGHTS.get(club_league, 0)
    if not league_raw and current_club in _NATIONAL_TEAMS_MAX:
        league_raw = 20
    mod = (LEAGUE_MOD_SD_CENTER if is_sd_center else LEAGUE_MOD_COACH_CENTER).get(cat, 0.25)
    if cat == "former_teammate" and not is_still_player:
        if role_score >= 25:
            mod = 1.0
        elif role_score >= 10:
            mod = 0.65
    return int(league_raw * mod)


# ── Dimension 4: Rezenz / Recency (0–15, role-weighted) ──
RECENCY_MOD_SD_CENTER = {
    "head_coach": 1.0, "coaching_staff": 0.85,
    "sporting_director": 0.75, "executive": 0.7,
    "management": 0.5, "scouting": 0.75,
    "lehrgang": 0.5, "academy": 0.5, "analyst": 0.5,
    "player_coached": 0.5, "former_teammate": 0.35,
    "other_staff": 0.25, "medical": 0.25,
}
RECENCY_MOD_COACH_CENTER = {
    "sporting_director": 1.0, "head_coach": 1.0, "executive": 0.9,
    "management": 0.7, "coaching_staff": 0.7, "scouting": 0.7,
    "lehrgang": 0.5, "academy": 0.5, "analyst": 0.5,
    "player_coached": 0.5, "former_teammate": 0.35,
    "other_staff": 0.25, "medical": 0.25,
}


def score_recency(latest_season: int, cat: str, is_sd_center: bool,
                  role_score: int, is_still_player: bool, now_year: int = 2025) -> int:
    years_ago = now_year - latest_season
    if years_ago <= 1:
        recency_raw = 15
    elif years_ago <= 3:
        recency_raw = 12
    elif years_ago <= 5:
        recency_raw = 8
    elif years_ago <= 8:
        recency_raw = 4
    else:
        recency_raw = 0
    mod = (RECENCY_MOD_SD_CENTER if is_sd_center else RECENCY_MOD_COACH_CENTER).get(cat, 0.35)
    if cat == "former_teammate" and not is_still_player:
        if role_score >= 25:
            mod = 1.0
        elif role_score >= 10:
            mod = 0.7
    return int(recency_raw * mod)


# ── Category floor (evidence-gated) ──
def category_floor(cat: str, is_sd_center: bool, has_evidence: bool) -> int:
    if not has_evidence:
        return 0
    if is_sd_center:
        return {"head_coach": 65, "coaching_staff": 50, "sporting_director": 50,
                "executive": 50, "executive_governance": 38}.get(cat, 0)
    return {"sporting_director": 60, "executive": 58, "executive_governance": 45,
            "head_coach": 50}.get(cat, 0)


# ── GemeinsameSpiele bonus (0–15) ──
def gs_bonus(gs_verified: bool, shared_matches: int) -> int:
    b = 0
    if gs_verified:
        b += 5
    if shared_matches >= 50:
        b += 5
    if shared_matches >= 100:
        b += 5
    return min(b, 15)


# ── Multi-station multiplier (depth signal; excludes player/teammate/lehrgang) ──
MULTI_STATION_MULT = {1: 1.0, 2: 1.10, 3: 1.20, 4: 1.30, 5: 1.40}


def apply_multi_station_multiplier(total: int, cat: str, stations) -> int:
    if cat in ("player_coached", "former_teammate", "lehrgang"):
        return total
    real_stations = [s for s in (stations or []) if not is_pseudo_club(s)]
    if len(real_stations) >= 2:
        mult = MULTI_STATION_MULT.get(len(real_stations), 1.40)
        return int(round(total * mult))
    return total
