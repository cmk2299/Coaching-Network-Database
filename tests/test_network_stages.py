"""Unit tests for execution/lib/network_stages.py — extracted build_network() stages."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "execution"))
from lib.network_stages import (  # noqa: E402
    enrich_cross_references,
    normalize_contact_urls,
    remove_connection_self_loops,
)


class TestEnrichCrossReferences:
    def test_shared_station_links_coach(self):
        contacts = {
            1: {"name": "Alpha", "category": "head_coach", "stations": ["FC X", "FC Y"]},
            2: {"name": "Beta", "category": "coaching_staff", "stations": ["FC Y"]},
        }
        n = enrich_cross_references(contacts)
        assert n == 2  # Alpha↔Beta share FC Y, both coach-type
        assert contacts[1]["coaches_worked_with"] == [{"name": "Beta", "shared": ["FC Y"]}]
        assert contacts[2]["coaches_worked_with"] == [{"name": "Alpha", "shared": ["FC Y"]}]

    def test_sd_goes_to_sds_bucket(self):
        contacts = {
            1: {"name": "Coach", "category": "head_coach", "stations": ["FC X"]},
            2: {"name": "Boss", "category": "sporting_director", "stations": ["FC X"]},
        }
        enrich_cross_references(contacts)
        assert contacts[1]["sds_worked_with"] == [{"name": "Boss", "shared": ["FC X"]}]
        assert "coaches_worked_with" not in contacts[1]

    def test_no_shared_station_no_link(self):
        contacts = {
            1: {"name": "A", "category": "head_coach", "stations": ["FC X"]},
            2: {"name": "B", "category": "head_coach", "stations": ["FC Z"]},
        }
        assert enrich_cross_references(contacts) == 0
        assert "coaches_worked_with" not in contacts[1]

    def test_shared_station_count_stamped(self):
        contacts = {1: {"name": "A", "category": "head_coach", "stations": ["X", "Y", "Z"]}}
        enrich_cross_references(contacts)
        assert contacts[1]["shared_station_count"] == 3

    def test_coaches_capped_at_10(self):
        contacts = {0: {"name": "Center", "category": "head_coach", "stations": ["X"]}}
        for i in range(1, 16):
            contacts[i] = {"name": f"C{i:02d}", "category": "head_coach", "stations": ["X"]}
        enrich_cross_references(contacts)
        assert len(contacts[0]["coaches_worked_with"]) == 10  # capped

    def test_shared_list_sorted(self):
        contacts = {
            1: {"name": "A", "category": "head_coach", "stations": ["FC Z", "FC A", "FC M"]},
            2: {"name": "B", "category": "head_coach", "stations": ["FC Z", "FC A", "FC M"]},
        }
        enrich_cross_references(contacts)
        assert contacts[1]["coaches_worked_with"][0]["shared"] == ["FC A", "FC M", "FC Z"]


class TestNormalizeContactUrls:
    def test_relative_made_absolute(self):
        cs = [{"tm_url": "/lambertz/profil/spieler/8640"}]
        assert normalize_contact_urls(cs) == 1
        assert cs[0]["tm_url"] == "https://www.transfermarkt.de/lambertz/profil/spieler/8640"

    def test_absolute_untouched(self):
        cs = [{"tm_url": "https://www.transfermarkt.de/x/profil/spieler/1"}]
        assert normalize_contact_urls(cs) == 0

    def test_missing_url_ok(self):
        cs = [{"name": "no url"}]
        assert normalize_contact_urls(cs) == 0


class TestRemoveConnectionSelfLoops:
    def test_self_reference_removed(self):
        cs = [{"name": "Tuchel", "coaches_worked_with": [
            {"name": "Tuchel", "shared": ["X"]}, {"name": "Löw", "shared": ["Y"]}]}]
        assert remove_connection_self_loops(cs) == 1
        assert cs[0]["coaches_worked_with"] == [{"name": "Löw", "shared": ["Y"]}]

    def test_case_insensitive(self):
        cs = [{"name": "Klopp", "sds_worked_with": [{"name": "klopp", "shared": ["X"]}]}]
        assert remove_connection_self_loops(cs) == 1
        assert cs[0]["sds_worked_with"] == []

    def test_no_loop_no_change(self):
        cs = [{"name": "A", "coaches_worked_with": [{"name": "B", "shared": ["X"]}]}]
        assert remove_connection_self_loops(cs) == 0


from lib.network_stages import parse_coach_stations  # noqa: E402


class TestParseCoachStations:
    def test_groups_seasons_and_roles_by_club(self):
        career = [
            {"club_tm_id": 10, "club_name": "FC X", "role": "Cheftrainer",
             "date_from": "01.07.2020", "date_to": "30.06.2021"},
            {"club_tm_id": 10, "club_name": "FC X", "role": "Co-Trainer",
             "date_from": "01.07.2019", "date_to": "30.06.2020"},
        ]
        st = parse_coach_stations(career)
        assert set(st[10]["roles"]) == {"Cheftrainer", "Co-Trainer"}
        assert 2020 in st[10]["seasons"]

    def test_skips_entries_without_club_id(self):
        st = parse_coach_stations([{"club_name": "No ID", "role": "x"}])
        assert len(st) == 0

    def test_skips_pseudo_clubs(self):
        career = [{"club_tm_id": 99, "club_name": "DFB-Lehrgang",
                   "date_from": "01.07.2020", "date_to": "30.06.2021"}]
        # DFB-Lehrgang is a pseudo/virtual bucket → skipped
        from lib.normalization import is_pseudo_club
        if is_pseudo_club("DFB-Lehrgang"):
            assert len(parse_coach_stations(career)) == 0

    def test_missing_key_returns_default(self):
        # defaultdict contract preserved for callers indexing unknown clubs
        st = parse_coach_stations([])
        assert st[123] == {"name": "", "seasons": set(), "roles": set()}


class TestResolvePostCareerRoles:
    def test_resolves_karriereende_to_post_career_role(self):
        contacts = {1: {"name": "X", "category": "former_teammate", "current_club": "Karriereende"}}
        def fake_parse(tid): return {"role": "Co-Trainer", "club": "FC Test"}
        def fake_norm(c): return c
        from lib.network_stages import resolve_post_career_roles
        n = resolve_post_career_roles(contacts, fake_parse, fake_norm)
        assert n == 1
        c = contacts[1]
        assert c["post_career_role"] is True
        assert c["current_club"] == "FC Test"
        assert c["role"] == "Co-Trainer (FC Test)"

    def test_skips_non_retired_player(self):
        contacts = {1: {"name": "X", "category": "former_teammate", "current_club": "FC Bayern"}}
        from lib.network_stages import resolve_post_career_roles
        assert resolve_post_career_roles(contacts, lambda _: {"role": "C"}, lambda c: c) == 0
        assert "post_career_role" not in contacts[1]

    def test_skips_wrong_category(self):
        contacts = {1: {"name": "X", "category": "head_coach", "current_club": "Karriereende"}}
        from lib.network_stages import resolve_post_career_roles
        assert resolve_post_career_roles(contacts, lambda _: {"role": "C"}, lambda c: c) == 0

    def test_clubless_role(self):
        contacts = {1: {"name": "X", "category": "former_teammate", "current_club": ""}}
        def fake_parse(tid): return {"role": "TV-Experte"}
        from lib.network_stages import resolve_post_career_roles
        assert resolve_post_career_roles(contacts, fake_parse, lambda c: c) == 1
        assert contacts[1]["current_club"] == "TV-Experte"
        assert contacts[1]["role"] == "TV-Experte"


class TestScoringFinalizer:
    def test_fills_missing_strength_from_seasons_together(self):
        from lib.network_stages import scoring_finalizer
        cs = [{"name": "A", "relevance_score": 50, "seasons_together": 3}]
        scoring_finalizer(cs)
        assert cs[0]["strength"] == 2  # (3+1)//2 = 2

    def test_strength_capped_at_5(self):
        from lib.network_stages import scoring_finalizer
        cs = [{"name": "A", "relevance_score": 50, "seasons_together": 20}]
        scoring_finalizer(cs)
        assert cs[0]["strength"] == 5

    def test_strength_floor_1(self):
        from lib.network_stages import scoring_finalizer
        cs = [{"name": "A", "relevance_score": 50, "seasons_together": 0}]
        scoring_finalizer(cs)
        assert cs[0]["strength"] == 1

    def test_sorts_desc_by_relevance_score(self):
        from lib.network_stages import scoring_finalizer
        cs = [
            {"name": "Low", "relevance_score": 10, "category": "head_coach"},
            {"name": "Hi",  "relevance_score": 90, "category": "head_coach"},
            {"name": "Mid", "relevance_score": 50, "category": "head_coach"},
        ]
        scoring_finalizer(cs)
        assert [c["name"] for c in cs] == ["Hi", "Mid", "Low"]

    def test_category_tiebreak_on_equal_score(self):
        from lib.network_stages import scoring_finalizer
        cs = [
            {"name": "P", "relevance_score": 50, "category": "player_coached"},
            {"name": "C", "relevance_score": 50, "category": "head_coach"},
        ]
        scoring_finalizer(cs)
        assert cs[0]["category"] == "head_coach"  # head_coach < player_coached in CAT_ORDER


class TestSanitizeIdIntegrity:
    def test_no_profile_match_leaves_contact_alone(self):
        from lib.network_stages import sanitize_id_integrity
        cs = [{"name": "Schäfer", "_tm_id": 999, "category": "head_coach"}]
        # empty profiles_ns = no profile to contradict
        n = sanitize_id_integrity(cs, {}, lambda a, b: a == b)
        assert n == 0
        assert cs[0]["category"] == "head_coach"

    def test_name_match_keeps_contact(self):
        from lib.network_stages import sanitize_id_integrity
        cs = [{"name": "Bode", "_tm_id": 5, "category": "head_coach",
               "current_club": "Werder", "career_history": [{"club": "X"}]}]
        ns = {"trainer_5": {"name": "Bode"}}
        assert sanitize_id_integrity(cs, ns, lambda a, b: a == b) == 0
        assert cs[0]["current_club"] == "Werder"

    def test_mismatch_player_origin_reverts_to_former_teammate(self):
        from lib.network_stages import sanitize_id_integrity
        cs = [{"name": "Bode", "_tm_id": 5, "category": "head_coach",
               "current_club": "US Salernitana", "shared_matches": 50,
               "role": "Head Coach (Salernitana)", "post_career_role": True}]
        # _tm_id 5 belongs to a different person
        ns = {"spieler_5": {"name": "Someone Else"}}
        assert sanitize_id_integrity(cs, ns, lambda a, b: a == b) == 1
        c = cs[0]
        assert c["category"] == "former_teammate"
        assert c["pro_status"] == "player"
        assert c["current_club"] is None
        assert c["career_history"] is None
        assert "post_career_role" not in c
        assert c["role"] == "Mitspieler"

    def test_mismatch_unknown_origin_neutralizes_role_paren(self):
        from lib.network_stages import sanitize_id_integrity
        cs = [{"name": "X", "_tm_id": 7, "category": "head_coach",
               "role": "Cheftrainer (FC Wrong)", "current_club": "FC Wrong"}]
        ns = {"trainer_7": {"name": "Different Person"}}
        assert sanitize_id_integrity(cs, ns, lambda a, b: a == b) == 1
        assert cs[0]["role"] == "Cheftrainer"
        assert cs[0]["current_club"] is None


class TestDedupeSameProfileContacts:
    def test_merges_same_url_keeps_higher_score(self):
        from lib.network_stages import dedupe_same_profile_contacts
        cs = [
            {"name": "Honold", "tm_url": "https://x/trainer/10853",
             "relevance_score": 30, "stations": ["FC A"]},
            {"name": "Honold", "tm_url": "https://x/trainer/10853",
             "relevance_score": 80, "stations": ["FC B", "FC C"]},
        ]
        out, dropped = dedupe_same_profile_contacts(cs)
        assert dropped == 1
        assert len(out) == 1
        assert out[0]["relevance_score"] == 80
        assert set(out[0]["stations"]) == {"FC A", "FC B", "FC C"}

    def test_different_namespace_not_merged(self):
        from lib.network_stages import dedupe_same_profile_contacts
        cs = [
            {"tm_url": "https://x/spieler/5", "relevance_score": 10},
            {"tm_url": "https://x/trainer/5", "relevance_score": 20},
        ]
        out, dropped = dedupe_same_profile_contacts(cs)
        assert dropped == 0
        assert len(out) == 2

    def test_no_url_skipped(self):
        from lib.network_stages import dedupe_same_profile_contacts
        cs = [{"name": "no url"}, {"name": "no url 2"}]
        out, dropped = dedupe_same_profile_contacts(cs)
        assert dropped == 0
        assert len(out) == 2


class TestComputePlayingCareerWindow:
    def test_coaching_start_from_career(self):
        from lib.network_stages import compute_playing_career_window
        # Career first entry (after reversed): date_from 15/16 → coaching_start 2015
        # DOB 1980 → playing_start 1998. Window: [max(1998, 2010), 2015-2] = [2010, 2013]
        career = [{"date_from": "20/21"}, {"date_from": "15/16"}]  # reversed → 15/16 first
        profile = {"dob": "1980-01-01"}
        win = compute_playing_career_window(career, profile)
        assert win == set(range(2010, 2014))  # 2010..2013

    def test_dob_fallback_when_no_career_dates(self):
        from lib.network_stages import compute_playing_career_window
        # No parseable career dates → coaching_start = DOB + 35 = 1980 + 35 = 2015
        # playing_start = DOB + 18 = 1998. Window: [2010, 2013]
        win = compute_playing_career_window([], {"dob": "1980-01-01"})
        assert win == set(range(2010, 2014))

    def test_no_data_uses_2010_default(self):
        from lib.network_stages import compute_playing_career_window
        # No career, no DOB → coaching_start=2010, playing_start=2010-15=1995
        # End conservative=2008 → window empty (< 2010 floor)
        win = compute_playing_career_window([], {})
        assert win == set()

    def test_modern_coach_window_overlaps_squad_era(self):
        from lib.network_stages import compute_playing_career_window
        # Coach started coaching at 2020/21, DOB 1985 → playing 2003..2018(cons)
        # Window starts at max(2003, 2010) = 2010, ends at 2018
        win = compute_playing_career_window(
            [{"date_from": "20/21"}], {"dob": "1985-01-01"})
        assert min(win) == 2010
        assert max(win) == 2018
