"""Unit tests for execution/lib/scoring.py — pure relevance-scoring components."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "execution"))
from lib import scoring as S  # noqa: E402


class TestRelationship:
    def test_caps_at_40(self):
        assert S.score_relationship(10, 10, True) == 40

    def test_stations_cap_30_seasons_cap_15(self):
        # 3 stations*15=45→cap30; 6 seasons*3=18→cap15; no lehrgang → 45→cap40
        assert S.score_relationship(3, 6, False) == 40

    def test_small(self):
        # 1 station=15, 1 season=3, no lehrgang = 18
        assert S.score_relationship(1, 1, False) == 18

    def test_lehrgang_bonus(self):
        assert S.score_relationship(0, 0, True) == 5


class TestRoleWeights:
    def test_coach_center_sd_top(self):
        assert S.role_weights(False)["sporting_director"] == 35
        assert S.role_weights(False)["head_coach"] == 25

    def test_sd_center_hc_top(self):
        assert S.role_weights(True)["head_coach"] == 35
        assert S.role_weights(True)["sporting_director"] == 22


class TestLeague:
    def test_bl1_hc_full(self):
        # BL1=20, coach-center head_coach mod 1.0 → 20
        assert S.score_league("FC Bayern", {"FC Bayern": "BL1"}, "head_coach",
                              False, 0, False) == 20

    def test_low_role_discounted(self):
        # BL1=20, other_staff mod 0.15 → int(3.0)=3
        assert S.score_league("X", {"X": "BL1"}, "other_staff", False, 0, False) == 3

    def test_unknown_club_zero(self):
        assert S.score_league("Nowhere", {}, "head_coach", False, 0, False) == 0

    def test_national_team_fallback(self):
        assert S.score_league("Deutschland", {}, "head_coach", False, 0, False) == 20

    def test_promoted_teammate_full_mod(self):
        # former_teammate w/ role_score>=25 → mod 1.0 on BL1
        assert S.score_league("X", {"X": "BL1"}, "former_teammate", False, 30, False) == 20


class TestRecency:
    def test_recent_full(self):
        # latest 2025, now 2025 → years_ago 0 → 15; head_coach mod 1.0
        assert S.score_recency(2025, "head_coach", False, 0, False) == 15

    def test_old_zero(self):
        assert S.score_recency(2010, "head_coach", False, 0, False) == 0

    def test_mid_discounted_role(self):
        # years_ago 2 → raw 12; other_staff mod 0.25 → int(3.0)=3
        assert S.score_recency(2023, "other_staff", False, 0, False) == 3


class TestCategoryFloor:
    def test_no_evidence_zero(self):
        assert S.category_floor("sporting_director", False, False) == 0

    def test_sd_floor_coach_center(self):
        assert S.category_floor("sporting_director", False, True) == 60

    def test_hc_floor_sd_center(self):
        assert S.category_floor("head_coach", True, True) == 65

    def test_unknown_cat_zero(self):
        assert S.category_floor("other_staff", False, True) == 0


class TestGsBonus:
    def test_none(self):
        assert S.gs_bonus(False, 0) == 0

    def test_verified_only(self):
        assert S.gs_bonus(True, 10) == 5

    def test_tiers_cap_15(self):
        assert S.gs_bonus(True, 150) == 15  # 5+5+5


class TestMultiStation:
    def test_excluded_categories_unchanged(self):
        assert S.apply_multi_station_multiplier(50, "former_teammate", ["A", "B", "C"]) == 50

    def test_two_real_stations_110(self):
        assert S.apply_multi_station_multiplier(50, "head_coach", ["FC A", "FC B"]) == 55

    def test_single_station_unchanged(self):
        assert S.apply_multi_station_multiplier(50, "head_coach", ["FC A"]) == 50

    def test_five_plus_caps_140(self):
        st = ["FC A", "FC B", "FC C", "FC D", "FC E", "FC F"]
        assert S.apply_multi_station_multiplier(50, "head_coach", st) == 70  # 50*1.40


class TestIsStillActivePlayer:
    def test_typed_player(self):
        assert S.is_still_active_player({"type": "player"}, []) is True

    def test_career_only_player_roles(self):
        career = [{"role": "Spieler"}]  # not a coaching/mgmt role
        assert S.is_still_active_player({}, career) is True

    def test_career_with_coaching_role(self):
        career = [{"role": "Cheftrainer"}]
        assert S.is_still_active_player({}, career) is False

    def test_empty_profile_empty_career(self):
        assert S.is_still_active_player({}, []) is False


class TestDetermineTodayRole:
    def test_staff_index_wins(self):
        assert S.determine_today_role({"category": "sporting_director"},
                                      [{"role": "Cheftrainer", "date_to": "-"}]) == ("sporting_director", True)

    def test_current_career_role(self):
        # no staff info; career[0] still active (no date_to) and an active football role
        assert S.determine_today_role(None, [{"role": "Cheftrainer", "date_to": "-"}]) == ("head_coach", True)

    def test_past_role_becomes_ex(self):
        career = [{"role": "Spieler", "date_to": "2020"}, {"role": "Co-Trainer", "date_to": "2022"}]
        role, active = S.determine_today_role(None, career)
        assert role == "ex_coaching_staff" and active is False

    def test_no_football_role(self):
        assert S.determine_today_role(None, [{"role": "Spieler", "date_to": "2020"}]) == ("none", False)

    def test_empty(self):
        assert S.determine_today_role(None, []) == ("none", False)


def _noop_future(e):
    return False


class TestScoreFormerTeammate:
    def test_still_player_scores_zero_base(self):
        c = {"name": "X", "category": "former_teammate"}
        rs, cat = S.score_former_teammate(c, {}, [], True, "none", False,
            S.role_weights(False), profiles={}, spieler_tm_id=1,
            is_future_career_entry=_noop_future)
        assert rs == 0 and cat == "former_teammate"

    def test_no_career_scores_three(self):
        c = {"name": "X", "category": "former_teammate"}
        rs, cat = S.score_former_teammate(c, {}, [], False, "none", False,
            S.role_weights(False), profiles={}, spieler_tm_id=1,
            is_future_career_entry=_noop_future)
        assert rs == 3 and cat == "former_teammate"

    def test_sd_promotion_upgrades_category(self):
        c = {"name": "Di Leone", "category": "former_teammate"}
        career = [{"role": "Sportdirektor", "club": "FC X", "date_to": "-"}]
        prof = {"current_club": {"name": "FC X"}, "type": "trainer"}
        rs, cat = S.score_former_teammate(c, prof, career, False, "none", False,
            S.role_weights(False), profiles={}, spieler_tm_id=1,
            is_future_career_entry=_noop_future)
        assert cat == "sporting_director"
        assert c["category"] == "sporting_director" and c["pro_status"] == "sd"
        assert c.get("_teammate_promoted") is True
        # coach-centered weight for SD is 35, +8 promotion bonus
        assert rs == S.role_weights(False)["sporting_director"] + 8

    def test_today_active_pro_bonus(self):
        c = {"name": "X", "category": "former_teammate"}
        rs, _ = S.score_former_teammate(c, {}, [], False, "head_coach", True,
            S.role_weights(False), profiles={}, spieler_tm_id=1,
            is_future_career_entry=_noop_future)
        assert rs == 3 + 10  # no-career base 3 + active-DM today bonus 10

    def test_geschaeftsfuehrer_becomes_executive(self):
        c = {"name": "X", "category": "former_teammate"}
        career = [{"role": "Geschäftsführer", "club": "FC X", "date_to": "-"}]
        rs, cat = S.score_former_teammate(c, {"current_club": "FC X"}, career, False,
            "none", False, S.role_weights(False), profiles={}, spieler_tm_id=1,
            is_future_career_entry=_noop_future)
        assert cat == "executive" and c["category"] == "executive"
