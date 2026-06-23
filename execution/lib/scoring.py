"""Pure relevance-scoring components extracted from build_coach_network.build_network()
(decomposition 2026-06-21). The former_teammate post-career promotion logic stays in
build_network (it mutates contacts); everything here is side-effect-free and unit-tested.

Final score = relationship + role + league + recency + gs_bonus, then multi-station
multiplier, then max(.,category_floor), capped at 100. (role_score itself is computed
in build_network because the former_teammate path has side effects.)
"""
from .normalization import (
    is_pseudo_club, classify_role, normalize_club, compute_role_display,
    build_trainer_url, resolve_trainer_tm_id,
)

# Role sets for former-teammate "what are they NOW?" detection. NOTE the two sets
# differ deliberately (matches the original inline logic): the player-exit check
# excludes "executive", the today-role check includes it.
_PLAYER_EXIT_ROLES = frozenset({
    "head_coach", "coaching_staff", "sporting_director",
    "scouting", "management", "analyst", "academy",
})
_ACTIVE_FOOTBALL_ROLES = frozenset({
    "head_coach", "coaching_staff", "sporting_director", "executive",
    "scouting", "analyst", "academy", "management",
})


def is_still_active_player(profile: dict, career: list) -> bool:
    """True if a former teammate is still a pure player — profile typed 'player',
    or a career with no coaching/management role anywhere."""
    if (profile or {}).get("type") == "player":
        return True
    if not career:
        return False
    return not any(classify_role(e.get("role", "")) in _PLAYER_EXIT_ROLES for e in career)


def score_former_teammate(c, teammate_profile, teammate_career, is_still_player,
                          today_role, today_active, weights, *,
                          profiles, spieler_tm_id, is_future_career_entry):
    """Compute role_score for a former_teammate AND apply post-career promotion.

    MUTATES ``c`` (category / pro_status / current_club / career_history / role /
    tm_id / tm_url / _teammate_promoted) when the teammate's post-playing career
    classifies them as a decision-maker (HC/SD/Exec) or scout. Returns
    ``(role_score, cat)`` — cat is the possibly-upgraded category, which the caller
    must use for the league/recency/floor dimensions.
    """
    cat = "former_teammate"
    if is_still_player:
        role_score = 0  # Active players without football-business career = low relevance
    elif teammate_career:
        # Q2: Smart "Geschäftsführer" classification
        first_role = teammate_career[0].get("role", "")
        post_role = classify_role(first_role)
        # Plain "Geschäftsführer" / "Vorstandsmitglied" at non-commercial club → executive
        rl = first_role.lower()
        if "geschäftsführer" in rl or "vorstandsmitglied" in rl:
            if not any(x in rl for x in ["marketing", "finanzen", "kaufmännisch", "vertrieb", "kommunikation"]):
                post_role = "executive"

        role_score = weights.get(post_role, 2)

        # Q1: Promote category for Executive/SD/HC/Scout ex-teammates
        if post_role in ("head_coach", "sporting_director", "executive"):
            role_score += 8
            # Category upgrade — appears in Decision-Maker filter
            cat = post_role
            c["category"] = post_role
            c["pro_status"] = {
                "executive": "exec",
                "head_coach": "trainer",
                "sporting_director": "sd",
            }[post_role]
            # PATTERN 23 FIX: refresh role/current_club/career_history so the contact
            # doesn't keep the stale "Mitspieler (Position)" string (Grover Gibson /
            # Di Leone bug). Not relying on later profile-enrichment (may be skipped).
            try:
                _tm_first = teammate_career[0] if teammate_career else {}
                _tm_current_club = ""
                _tp_cc = teammate_profile.get("current_club") or {}
                if isinstance(_tp_cc, dict):
                    _tm_current_club = normalize_club(_tp_cc.get("name", ""), _tp_cc.get("tm_id")) or ""
                elif isinstance(_tp_cc, str):
                    _tm_current_club = normalize_club(_tp_cc) or ""
                if not _tm_current_club:
                    _tm_current_club = normalize_club(_tm_first.get("club", "") or _tm_first.get("club_name", ""),
                                                      _tm_first.get("club_tm_id")) or ""
                if _tm_current_club:
                    c["current_club"] = _tm_current_club
                # PATTERN 15 EXTENSION: filter future entries from copied career_history
                if teammate_career and not c.get("career_history"):
                    _tc_current = [e for e in teammate_career if not is_future_career_entry(e)]
                    _tc_display = _tc_current if _tc_current else teammate_career
                    c["career_history"] = [
                        {"club": normalize_club(e.get("club", "") or e.get("club_name", ""), e.get("club_tm_id")),
                         "role": e.get("role", ""),
                         "from": e.get("date_from", "") or e.get("from", ""),
                         "to":   e.get("date_to", "")   or e.get("to", "")}
                        for e in _tc_display
                    ]
                c["role"] = compute_role_display(
                    category=post_role,
                    section="",
                    club_name=_tm_current_club,
                    career_history=c.get("career_history") or teammate_career,
                    position=c.get("playing_position", "") or "",
                    person_type=teammate_profile.get("type", "") or "",
                )
                c["_teammate_promoted"] = True
                # PATTERN 34: promoted-to-HC → refresh tm_id+tm_url to trainer namespace
                # so dashboard cross-links resolve (was left at /profil/spieler/{id}).
                if post_role == "head_coach":
                    try:
                        trainer_tmid = resolve_trainer_tm_id(
                            spieler_tm_id=spieler_tm_id,
                            person_name=c.get("name", ""),
                            persons_master=profiles or {},
                        )
                        if trainer_tmid:
                            c["tm_id"] = trainer_tmid
                            _new_url = build_trainer_url(c.get("name", ""), trainer_tmid)
                            if _new_url:
                                c["tm_url"] = _new_url
                    except Exception:
                        pass
            except Exception:
                pass
        elif post_role == "scouting":
            # Scout-promotion (Minkwitz-Pattern) — relevant for talent pipeline
            cat = "scouting"
            c["category"] = "scouting"
            c["pro_status"] = "scout"
            try:
                _tp_cc = teammate_profile.get("current_club") or {}
                _tm_current_club = ""
                if isinstance(_tp_cc, dict):
                    _tm_current_club = normalize_club(_tp_cc.get("name", ""), _tp_cc.get("tm_id")) or ""
                elif isinstance(_tp_cc, str):
                    _tm_current_club = normalize_club(_tp_cc) or ""
                if _tm_current_club:
                    c["current_club"] = _tm_current_club
                if teammate_career and not c.get("career_history"):
                    _tc_current = [e for e in teammate_career if not is_future_career_entry(e)]
                    _tc_display = _tc_current if _tc_current else teammate_career
                    c["career_history"] = [
                        {"club": normalize_club(e.get("club", "") or e.get("club_name", ""), e.get("club_tm_id")),
                         "role": e.get("role", ""),
                         "from": e.get("date_from", "") or e.get("from", ""),
                         "to":   e.get("date_to", "")   or e.get("to", "")}
                        for e in _tc_display
                    ]
                c["role"] = compute_role_display(
                    category="scouting",
                    section="",
                    club_name=_tm_current_club,
                    career_history=c.get("career_history") or teammate_career,
                    position=c.get("playing_position", "") or "",
                    person_type=teammate_profile.get("type", "") or "",
                )
                c["_teammate_promoted"] = True
            except Exception:
                pass
    else:
        role_score = 3  # Still active player, less relevant for placements

    # Fix A (A1e) — Today-role bonus, ADDITIVE: active DM +10, active staff/scout +5,
    # ex-trainer +2, none +0.
    _ACTIVE_PRO = {"head_coach", "sporting_director", "executive"}
    _ACTIVE_STAFF = {"coaching_staff", "scouting", "analyst", "academy", "management"}
    if today_active and today_role in _ACTIVE_PRO:
        role_score += 10
    elif today_active and today_role in _ACTIVE_STAFF:
        role_score += 5
    elif today_role.startswith("ex_"):
        role_score += 2
    return role_score, cat


def determine_today_role(staff_info, career: list):
    """Return (today_role, today_active) for a former teammate. Priority:
      1) active-staff-index category (most reliable signal for TODAY)
      2) current career[0] (no/'-' date_to) in an active football role
      3) any past coaching/management role → 'ex_<role>'
      4) else ('none', False)"""
    if staff_info and staff_info.get("category") in _ACTIVE_FOOTBALL_ROLES:
        return staff_info["category"], True
    if career:
        first = career[0]
        first_to = (first.get("date_to") or "").strip()
        first_classified = classify_role(first.get("role", ""))
        if (not first_to or first_to == "-") and first_classified in _ACTIVE_FOOTBALL_ROLES:
            return first_classified, True
        had_role = next((classify_role(e.get("role", "")) for e in career
                         if classify_role(e.get("role", "")) in _ACTIVE_FOOTBALL_ROLES), None)
        if had_role:
            return "ex_" + had_role, False
    return "none", False

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
