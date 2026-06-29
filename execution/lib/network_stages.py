"""Extracted, individually-testable stages of build_coach_network.build_network().

Part of the 2026-06 decomposition of the 2,941-line build_network() monolith
into named pure stages. Each function here is verified byte-identical against a
golden network snapshot before landing (see /tmp/golden_harness.py).

### Public API (stable; called by build_coach_network.py + tested in tests/test_network_stages.py)

Stage pipeline order (the order they run in build_network):
  • parse_coach_stations(career)                             → coach_stations dict
  • add_current_staff_colleagues(...)                        → Section 1
  • add_staff_at_career_stations(...)                        → Section 1b
  • add_shared_career_stations(...)                          → Section 2 (inverted-index sweep)
  • add_former_teammates_from_squads(...)                    → Section 2b
  • add_gemeinsame_spiele_teammates(...)                     → Section 2c (real TM match counts)
  • add_players_coached(...)                                 → Section 3 (squad-overlap + post-career role)
  • resolve_post_career_roles(contacts_map, …)               → "Karriereende" → real role
  • enrich_cross_references(contacts_map)                    → triangular relationships
  • drop_low_value_categories(contacts_map)                  → strip scouting/medical
  • normalize_contact_urls(contacts_list)                    → PATTERN 27
  • remove_connection_self_loops(contacts_list)              → PATTERN 26b
  • sanitize_id_integrity(contacts_list, profiles_ns, …)    → namespace-collision guard
  • dedupe_same_profile_contacts(contacts_list)              → LX2 same-URL merger
  • scoring_finalizer(contacts_list)                         → fill strength + canonical sort

Helpers (used by stages or by callers):
  • compute_playing_career_window(career, profile)           → set of valid seasons
  • current_career_first(career)                             → first non-future entry
  • is_future_career_entry(entry)                            → PATTERN 15
  • refine_executive_tier(section_cat, profile, classify)    → finer executive class
  • CAT_ORDER                                                → canonical category sort dict
  • CURRENT_SEASON, MAX_STAFF_SEASON_GAP                     → temporal-overlap constants

Design contract: every stage has injected dependencies (load_squad,
normalize_club, etc.) instead of importing from lib.normalization directly.
This keeps the lib import graph shallow and stages testable with simple stubs.
"""
import json
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


import re as _re


def compute_playing_career_window(career, profile):
    """Estimate the season window in which the coach was an active player, used
    by Section 2b to pull former teammates from squad files. Returns a set of
    seasons (ints). Empty if the window doesn't overlap squad data start (2010).

    Heuristic chain (each step is a fallback for the prior one):
      • playing_end = start of coaching career (first career_history entry); else
      • playing_end = DOB-year + 35 (typical retirement); else 2010.
      • playing_start = DOB-year + 18 (rookie age); else playing_end - 15.
    Conservative: subtract 2 from playing_end to skip the typical
    retirement-to-first-coach gap (avoids false matches like Blessin@Hoffenheim
    ~2004 matching 2010+ players who were never his teammates).
    """
    # End of playing career
    coaching_start = None
    if career:
        for entry in reversed(career):
            m = _re.search(r"(\d{2})/(\d{2})", entry.get("date_from", ""))
            if m:
                y = int(m.group(1))
                coaching_start = 2000 + y if y < 90 else 1900 + y
                break
    if not coaching_start and profile.get("dob"):
        try:
            coaching_start = int(profile["dob"][:4]) + 35
        except (ValueError, TypeError):
            coaching_start = 2010
    if not coaching_start:
        coaching_start = 2010

    # Start of playing career
    playing_end = coaching_start
    dob = profile.get("dob", "")
    try:
        playing_start = int(dob[:4]) + 18 if dob else playing_end - 15
    except (ValueError, TypeError):
        playing_start = playing_end - 15

    playing_end_conservative = max(playing_end - 2, playing_start)
    return set(range(max(playing_start, 2010), playing_end_conservative + 1))


def add_players_coached(coach_tm_id, coach_stations, contacts_map,
                          load_squad, load_players_used, get_profile_ns,
                          profiles_ns, name_matches, normalize_club,
                          filter_nationality, filter_default_image,
                          normalize_dob, format_season):
    """Section 3: discover players the coach actually coached, by sweeping
    squad files of every club where the coach held a coaching role (trainer /
    coach / manager). Filter to "top players" via real TM appearance data
    (≥20 games) when available, else a 2-season squad-overlap proxy.

    For each top player: either upgrade an existing contact to player_coached
    (and enrich with real stats) or create a new one.  Crucial collision
    guard on current_club (TM namespace ID-reuse: bare pid can resolve to a
    completely different person; require name_matches against the spieler
    profile before trusting any current_club value).

    POST-CAREER ROLE enrichment (2026-06-04): for a player_coached contact
    whose current_club is Karriereende/Vereinslos, look up the
    name+DOB-verified TRAINER profile and surface their CURRENT football role
    (the value the scout actually wants). Both gates required because TM
    reuses numeric ids across spieler/trainer namespaces for different people.

    Returns (players_coached_total, top_players_count, has_real_data) for
    caller logging. Mutates contacts_map in place.
    """
    players_coached = defaultdict(lambda: {"seasons": set(), "stations": set()})
    for club_id, info in coach_stations.items():
        coaching_roles = [r for r in info["roles"] if any(
            x in r.lower() for x in ["trainer", "coach", "manager"])]
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

    real_players_used = load_players_used(coach_tm_id)
    has_real_data = len(real_players_used) > 0
    MIN_REAL_APPEARANCES = 20

    if has_real_data:
        top_players = {pid: info for pid, info in players_coached.items()
                       if (r := real_players_used.get(pid)) and r["appearances"] >= MIN_REAL_APPEARANCES}
        if len(top_players) < 10:
            for pid, info in players_coached.items():
                if pid not in top_players and len(info["seasons"]) >= 2:
                    top_players[pid] = info
    else:
        top_players = {pid: info for pid, info in players_coached.items()
                       if len(info["seasons"]) >= 2}
        if len(top_players) < 10:
            top_players = dict(sorted(players_coached.items(),
                                       key=lambda x: len(x[1]["seasons"]),
                                       reverse=True)[:30])

    for pid, pinfo in top_players.items():
        real = real_players_used.get(pid)
        if pid in contacts_map:
            contacts_map[pid]["category"] = "player_coached"
            if real:
                contacts_map[pid]["appearances"] = real["appearances"]
                contacts_map[pid]["goals"] = real["goals"]
                contacts_map[pid]["assists"] = real["assists"]
                contacts_map[pid]["minutes"] = real["minutes"]
            continue

        player_data = pinfo.get("data", {})
        station_names = sorted(pinfo["stations"])
        seasons = sorted(pinfo["seasons"])
        n_seasons = len(seasons)

        if real:
            est_games = real["appearances"]
            total_minutes = real["minutes"]
        else:
            est_games = n_seasons * 22
            total_minutes = 0

        if n_seasons == 1:
            note = f"{', '.join(station_names)} ({format_season(seasons[0])})"
        else:
            note = (f"{', '.join(station_names)} "
                    f"({format_season(seasons[0])}–{format_season(seasons[-1])})")

        # current_club: bare pid can collide with an unrelated person of the
        # same id (TM namespace ID-reuse: trainer Udo Knierim 18100 vs
        # spieler Per Nilsson 18100). Require name_matches before trusting.
        sp_profile_for_cc = get_profile_ns("spieler", pid) or {}
        if name_matches(sp_profile_for_cc.get("name"), player_data.get("name", "")):
            cc_raw = sp_profile_for_cc.get("current_club")
            if isinstance(cc_raw, dict) and cc_raw.get("name"):
                current_club_val = normalize_club(cc_raw.get("name", ""), cc_raw.get("tm_id"))
            elif isinstance(cc_raw, str):
                current_club_val = cc_raw
            else:
                current_club_val = None
        else:
            current_club_val = None

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
            "dob": normalize_dob(player_data.get("dob", "") or ""),
            "image_url": filter_default_image(player_data.get("image_url")),
            "current_club": current_club_val,
        }

        # POST-CAREER ROLE enrichment for retired players.
        try:
            cc = contacts_map[pid].get("current_club")
            ccn = cc.get("name") if isinstance(cc, dict) else cc
            sp = get_profile_ns("spieler", pid) or {}
            if not name_matches(sp.get("name"), player_data.get("name", "")):
                sp = {}
            sp_dob = (sp.get("dob") or "").strip()
            sp_name = (sp.get("name") or "").strip().lower()
            if ccn in ("Karriereende", "Vereinslos", None) and sp_dob and sp_name:
                match = None
                for k, v in (profiles_ns or {}).items():
                    if not k.startswith("trainer_"):
                        continue
                    if (v.get("name") or "").strip().lower() != sp_name:
                        continue
                    if (v.get("dob") or "").strip() != sp_dob:
                        continue  # DOB gate → same person only
                    match = v
                    break
                tr_career = (match or {}).get("career_history") or []
                if tr_career:
                    cur = tr_career[0]
                    role = (cur.get("role") or "").strip()
                    club = normalize_club(cur.get("club_name", ""), cur.get("club_tm_id"))
                    if role and club:
                        contacts_map[pid]["role"] = f"{role} ({club})"
                        contacts_map[pid]["post_career_role"] = True
                        if (cur.get("date_to") or "").strip() in ("-", "", "heute"):
                            contacts_map[pid]["current_club"] = club
        except Exception:
            pass

    return len(players_coached), len(top_players), has_real_data


def add_gemeinsame_spiele_teammates(coach_tm_id, gs_path, playing_career,
                                     contacts_map, profiles,
                                     compute_shared_playing_stations):
    """Section 2c: enrich/add contacts from the per-coach GemeinsameSpiele JSON
    (`data/gemeinsame_spiele/{coach_tm_id}.json`) — real TM match-count data
    that complements the squad-overlap inference of Section 2b.

    For each teammate record:
      • If already in contacts_map: enrich with shared_matches / shared_minutes /
        teams_together_count, mark _gs_verified for former_teammates, fill empty
        stations via compute_shared_playing_stations, and (Fix C/A8) push match
        count down to shared_stations when there's exactly one known overlap.
      • Else: create a NEW former_teammate contact ONLY if shared_matches ≥ 5
        (lowered 10→5 2026-05-10 to catch e.g. Bobic with 7 shared matches).

    Returns (gs_enriched, gs_added) for caller logging; (0, 0) if gs_path
    missing or malformed. Mutates contacts_map in place.
    """
    if not gs_path.exists():
        return 0, 0
    try:
        gs_data = json.load(open(gs_path, encoding="utf-8"))
    except Exception as e:
        print(f"  GemeinsameSpiele: error loading {gs_path}: {e}")
        return 0, 0

    gs_added = gs_enriched = 0
    for tm in gs_data.get("teammates", []):
        pid = tm.get("tm_id")
        if not pid or pid == coach_tm_id:
            continue
        shared_matches = tm.get("shared_matches", 0)
        if pid in contacts_map:
            existing = contacts_map[pid]
            existing["shared_matches"] = shared_matches
            existing["shared_minutes"] = tm.get("total_minutes", 0)
            existing["teams_together_count"] = tm.get("teams_together", 0)
            if existing.get("category") == "former_teammate":
                existing["_gs_verified"] = True
            # Bug-2-Systematik: backfill empty stations from playing_career ∩ career_history.
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
            # Fix C (A8) — push match-count down when exactly one known overlap-station.
            sst = existing.get("shared_stations") or []
            if len(sst) == 1 and not sst[0].get("matches"):
                sst[0]["matches"] = shared_matches
            gs_enriched += 1
        else:
            if shared_matches < 5:
                continue
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
    return gs_enriched, gs_added


def add_former_teammates_from_squads(coach_tm_id, profile, career, contacts_map,
                                      load_squad, normalize_club,
                                      filter_nationality, filter_default_image):
    """Section 2b: discover the coach's former PLAYING teammates by sweeping
    squad files of every club the coach played for, within the valid playing
    window (compute_playing_career_window). Each squad-mate becomes a contact
    with category=former_teammate (or upgrades to relationship_type='both' if
    already present from career-overlap path).

    Fix C (A8) preserved: each contact gets a per-club shared_stations record
    accumulating club/seasons/matches.

    Returns (playing_stations_count, valid_seasons, teammates_added) for caller
    logging. Mutates contacts_map in place. Returns (0, set(), 0) if the coach
    has no playing_career.
    """
    playing_career = profile.get("playing_career", [])
    if not playing_career:
        return 0, set(), 0

    valid_seasons = compute_playing_career_window(career, profile)

    playing_stations = {}
    for entry in playing_career:
        club_id = entry.get("club_tm_id")
        if club_id:
            playing_stations[club_id] = normalize_club(
                entry.get("club_name", ""), club_id)

    teammates_added = 0
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
                    existing["_latest_season"] = max(
                        existing.get("_latest_season", 0), season)
                    if existing.get("relationship_type") != "playing":
                        existing["relationship_type"] = "both"
                    # Fix C (A8) — accumulate shared_stations per club/season
                    shared_st = existing.setdefault("shared_stations", [])
                    st_rec = next(
                        (s for s in shared_st if s.get("club") == club_name), None)
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
                        "shared_stations": [
                            {"club": club_name, "seasons": [season], "matches": 0}],
                    }
                    teammates_added += 1
    return len(playing_stations), valid_seasons, teammates_added


def add_shared_career_stations(coach_tm_id, coach_club_seasons, profile_index,
                                 profiles, contacts_map, get_season_range,
                                 classify_role, compute_role_display, format_season,
                                 filter_nationality, normalize_dob,
                                 filter_default_image):
    """Section 2: find other people who shared a (club, season) with the coach
    via the inverted profile_index. For each, compute shared stations, build a
    "Club (yy/yy-zz/zz); …" note, classify role via TM career_history, and
    either upgrade an existing contact or create a new one.

    "Sonstiges" section contacts (stadium speakers, mascots) are NOT category-
    upgraded — they stay other_staff regardless of TM career classification.

    Returns (candidate_count, coaches_matched) for caller-side logging.
    Pure side-effects on contacts_map.
    """
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

        station_names = sorted(shared_stations.keys())  # deterministic order
        total_seasons = sum(len(s) for s in shared_stations.values())
        all_shared_seasons = set().union(*shared_stations.values())
        latest_shared = max(all_shared_seasons) if all_shared_seasons else 2015

        station_details = []
        for sname, seasons in shared_stations.items():
            s_sorted = sorted(seasons)
            if len(s_sorted) == 1:
                station_details.append(f"{sname} ({format_season(s_sorted[0])})")
            else:
                station_details.append(
                    f"{sname} ({format_season(s_sorted[0])}–{format_season(s_sorted[-1])})")
        note = "; ".join(station_details)

        # SYSTEMIC FIX (2026-05-22): use compute_role_display() instead of raw
        # latest_role string. Fixes TRAINER_NOT_CHEFTRAINER (285 contacts):
        # TM stores generic "Trainer" title even for head coaches; category is
        # already "head_coach" via classify_role() → compute_role_display maps it
        # to "Cheftrainer, Club". Also normalizes executive/SD display.
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
            # Upgrade other_staff → real category ONLY when NOT a "Sonstiges"
            # contact (stadium speakers, mascots, etc. stay other_staff).
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
                "dob": normalize_dob(other.get("dob", "") or ""),
                "image_url": filter_default_image(other.get("image_url")),
                "current_club": other_current.get("name") if other_current else None,
                "license": other.get("license"),
            }
    return len(candidate_ids), coaches_matched


CURRENT_SEASON = 2025  # 2025/26 — bump at season rollover
MAX_STAFF_SEASON_GAP = 1  # staff file is current snapshot; allow 1-season grace


def add_staff_at_career_stations(coach_tm_id, coach_stations, current_club_id,
                                   contacts_map, profiles, load_staff,
                                   normalize_club, validate_staff_tm_id,
                                   classify_staff_section, compute_role_display):
    """Section 1b: add staff from ALL the coach's career-station clubs (not just
    the current one), picking up foreign-club staff via scrape_foreign_staff.

    Critical temporal-overlap guard: staff files are CURRENT snapshots, so they
    only validly represent colleagues if the coach's tenure overlaps with the
    current season (±1). Skips stations the coach left too long ago, otherwise
    foreign-club staff that joined years later would be falsely linked.

    Skips the coach themselves and the current_club_id (already handled by
    add_current_staff_colleagues). For tm_ids already in contacts_map, only
    appends the new station to existing stations[]. Pure side-effects.
    """
    for club_id, info in coach_stations.items():
        if club_id == current_club_id:
            continue
        coach_latest_season = max(info["seasons"]) if info["seasons"] else 0
        if coach_latest_season < CURRENT_SEASON - MAX_STAFF_SEASON_GAP:
            continue  # Stale: staff file post-dates coach's tenure
        staff = load_staff(club_id)
        if not staff:
            continue
        club_name = normalize_club(info["name"], info.get("tm_id"))
        for s in staff.get("staff", []):
            if s["tm_id"] == coach_tm_id:
                continue
            if s["tm_id"] not in contacts_map:
                validated_id = validate_staff_tm_id(s["name"], s["tm_id"], profiles)
                sec = s.get("section", "")
                cat = classify_staff_section(sec)
                contacts_map[s["tm_id"]] = {
                    "name": s["name"],
                    "stations": [club_name],
                    "category": cat,
                    "role": compute_role_display(category=cat, section=sec,
                                                 club_name=club_name),
                    "tm_url": s.get("tm_url", "") if validated_id else None,
                    "tm_id": validated_id or s["tm_id"],
                    "_validated_tm_id": validated_id,
                    "_staff_section": sec,
                    "seasons_together": 1,
                    "_latest_season": max(info["seasons"]) if info["seasons"] else 2020,
                }
            elif club_name not in contacts_map[s["tm_id"]]["stations"]:
                contacts_map[s["tm_id"]]["stations"].append(club_name)


def add_current_staff_colleagues(coach_tm_id, profile, contacts_map, profiles,
                                  load_staff, normalize_club, validate_staff_tm_id,
                                  classify_staff_section, classify_role,
                                  compute_role_display):
    """Section 1: add the coach's current-club staff colleagues to contacts_map.

    Reads profile.current_club.tm_id, calls injected load_staff(club_id), iterates
    the returned staff, classifies each into a category, and writes into contacts_map.
    Skips the coach themselves. Pure side-effects on contacts_map (which must be
    a mutable dict — typically the build_network's working dict).

    All dependencies are injected so this lib stays decoupled from lib.normalization
    and build_coach_network's local helpers; the caller wires the canonical ones.
    """
    current_club = profile.get("current_club") or {}
    current_club_id = current_club.get("tm_id")
    if not current_club_id:
        return
    staff = load_staff(current_club_id)
    if not staff:
        return
    club_name = normalize_club(
        staff.get("club_name", current_club.get("name", "")), current_club_id)
    for s in staff.get("staff", []):
        if s["tm_id"] == coach_tm_id:
            continue
        validated_id = validate_staff_tm_id(s["name"], s["tm_id"], profiles)
        section_cat = classify_staff_section(s.get("section", ""))
        refined_cat = refine_executive_tier(
            section_cat,
            profiles.get(int(s["tm_id"]), {}) if profiles else {},
            classify_role,
        )
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
            "tm_id": validated_id or s["tm_id"],
            "_validated_tm_id": validated_id,
            "_staff_section": s.get("section", ""),
            "seasons_together": 1,
            "_latest_season": 2025,  # current staff = recent
        }


def refine_executive_tier(section_cat: str, person_profile: dict, classify_role):
    """Refine a section-based "executive" classification into a finer tier
    using the person's current TM job title (career_history entry with date_to
    empty or '-'). Returns one of: "executive" (default sport-GF/Vorstand),
    "executive_governance" (Präsident / Aufsichtsrats-Vorsitz),
    "executive_secondary" (AR-Mitglied / Marketing).

    `classify_role` is injected so the lib stays decoupled from
    lib.normalization import chain; passing None or a non-callable returns
    section_cat unchanged.
    """
    if section_cat != "executive" or not person_profile:
        return section_cat
    title = ""
    for ce in (person_profile.get("career_history") or []):
        if str(ce.get("date_to", "")).strip() in ("-", ""):
            title = ce.get("role", "") or ""
            break
    if not title or not callable(classify_role):
        return section_cat
    title_cat = classify_role(title)
    if title_cat in ("executive_secondary", "executive_governance"):
        return title_cat
    return section_cat


def is_future_career_entry(entry: dict) -> bool:
    """Return True if entry's date_from is a future season (26/27 or later).
    PATTERN 15 (2026-05-23): TM pre-enters next-season contracts before they
    start; these corrupt center_role and contact career_history if not filtered."""
    m = _re.match(r"(\d{2})/(\d{2})", entry.get("date_from", ""))
    if not m:
        return False
    return (2000 + int(m.group(1))) > 2025


def current_career_first(career):
    """Return the FIRST career entry that isn't a future-season pre-entry,
    falling back to career[0] when every entry is future. Pure helper used at
    two call sites (center role + contact career_history enrichment)."""
    if not career:
        return None
    current = [e for e in career if not is_future_career_entry(e)]
    return current[0] if current else career[0]


def sanitize_id_integrity(contacts_list, profiles_ns, name_matches):
    """Single chokepoint guarding against TM namespace id-reuse: if a contact's
    _tm_id resolves (in EITHER namespace) only to a DIFFERENT person, every
    field enriched from that wrong profile is bogus. Strips role/current_club/
    career_history and reverts false promotions back to teammate/player base.

    Dependencies injected to keep lib/ import-light:
      profiles_ns: dict[str, dict]  — {kind}_{tm_id} keys, value=profile
      name_matches(a, b) -> bool    — diacritic-insensitive, surname-anchored

    Returns count sanitized.
    """
    san = 0
    for c in contacts_list:
        tid = c.get("_tm_id")
        if not tid:
            continue
        sp = profiles_ns.get(f"spieler_{tid}")
        tr = profiles_ns.get(f"trainer_{tid}")
        names = [p.get("name") for p in (sp, tr) if p]
        if not names:
            continue
        if any(name_matches(n, c.get("name", "")) for n in names):
            continue
        cat = c.get("category")
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
            base_cat = "player_coached" if cat == "player_coached" else "former_teammate"
            c["category"] = base_cat
            c["pro_status"] = "player"
            if not str(c.get("role", "")).lower().startswith(("mitspieler", "spieler")):
                c["role"] = "Mitspieler" if base_cat == "former_teammate" else "Spieler"
        else:
            if c.get("role") and "(" in str(c.get("role")):
                c["role"] = str(c["role"]).split("(")[0].strip() or "Unbekannt"
        san += 1
    return san


def dedupe_same_profile_contacts(contacts_list):
    """Merge contacts that enter via different _tm_id values but BOTH resolve
    to the same TM profile URL (Hans-Jörg Honold: staff id 10853 + academy id
    24762, both pointing at /trainer/10853). Keep the higher-relevance contact,
    union stations. Returns (new_list, dropped_count)."""
    by_url = {}
    dedup_drop = set()
    for c in contacts_list:
        m = _re.search(r"/(spieler|trainer)/(\d+)", c.get("tm_url") or "")
        if not m:
            continue
        key = (m.group(1), m.group(2))
        prev = by_url.get(key)
        if prev is None:
            by_url[key] = c
            continue
        rank = lambda x: ((x.get("relevance_score") or 0), len(x.get("stations") or []))
        better, worse = (c, prev) if rank(c) > rank(prev) else (prev, c)
        su = better.setdefault("stations", [])
        for s in worse.get("stations", []) or []:
            if s not in su:
                su.append(s)
        dedup_drop.add(id(worse))
        by_url[key] = better
    if dedup_drop:
        return [c for c in contacts_list if id(c) not in dedup_drop], len(dedup_drop)
    return contacts_list, 0


CAT_ORDER = {"head_coach": 0, "sporting_director": 1, "executive": 2,
             "executive_governance": 3, "coaching_staff": 4, "lehrgang": 5,
             "scouting": 6, "management": 7, "executive_secondary": 8,
             "academy": 9, "player_coached": 10, "former_teammate": 11,
             "analyst": 12, "other_staff": 13, "medical": 14}


def _safe_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def scoring_finalizer(contacts_list):
    """Single chokepoint after ALL contacts exist (incl. Phase-6 DM-Enrichment
    additions: coach_hired / co_decision_maker, which are appended after the
    main strength loop + sort). Guarantees two invariants validated by
    execution/scoring_audit.py:
      1. Every contact has strength (1-5, derived from seasons_together).
      2. contacts_list is ordered by (-relevance_score, category, name, tm_id).
    Mutates and sorts contacts_list in place; returns it for convenience."""
    for c in contacts_list:
        if c.get("strength") is None:
            st = c.get("seasons_together", 1) or 1
            c["strength"] = min(5, max(1, (st + 1) // 2))
    contacts_list.sort(key=lambda c: (
        -(c.get("relevance_score") or 0),
        CAT_ORDER.get(c.get("category", ""), 99),
        (c.get("name") or "").lower(),
        _safe_int(c.get("tm_id")),
    ))
    return contacts_list


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
