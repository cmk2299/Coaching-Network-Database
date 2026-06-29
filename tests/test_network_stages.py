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
