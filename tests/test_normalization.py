"""Unit tests for execution/lib/normalization.py — the shared single-source-of-truth
helpers. These lock in behaviour as a regression net (CI runs them on push).

Run: python3 -m pytest tests/ -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "execution"))
from lib import normalization as N  # noqa: E402


# ── slugify (umlaut-safe; naive regex once produced "r_sler" → 404 orphans) ──
class TestSlugify:
    def test_umlaut_club(self):
        assert N.slugify("Borussia Mönchengladbach") == "borussia_moenchengladbach"

    def test_umlaut_name(self):
        assert N.slugify("Marco Rösler") == "marco_roesler"

    def test_no_umlaut_leak(self):
        # never emit an underscore where an umlaut was folded to a letter
        assert "_sler" not in N.slugify("Rösler")

    def test_spaces_to_underscore(self):
        assert N.slugify("Jan Gernlein") == "jan_gernlein"


# ── normalize_club ──────────────────────────────────────────────────────────
class TestNormalizeClub:
    def test_heidenheim_year_suffix_stripped(self):
        assert N.normalize_club("1.FC Heidenheim 1846") == "1.FC Heidenheim"

    def test_gladbach_abbreviated(self):
        assert N.normalize_club("Borussia Mönchengladbach") == "Borussia M'gladbach"

    def test_idempotent(self):
        once = N.normalize_club("1.FC Heidenheim 1846")
        assert N.normalize_club(once) == once

    def test_empty(self):
        assert N.normalize_club("") == ""


# ── classify_role ───────────────────────────────────────────────────────────
class TestClassifyRole:
    def test_sporting_director(self):
        assert N.classify_role("Sportdirektor") == "sporting_director"

    def test_head_coach(self):
        assert N.classify_role("Cheftrainer") == "head_coach"

    def test_co_trainer_is_staff(self):
        assert N.classify_role("Co-Trainer") == "coaching_staff"

    def test_aufsichtsrat_is_governance_tier(self):
        # regression: Aufsichtsratsmitglied must be recognised as management/governance,
        # not silently dropped (Temporal-Overlap fix 2026-04-07)
        assert N.classify_role("Aufsichtsratsmitglied") == "executive_secondary"


# ── seasons ─────────────────────────────────────────────────────────────────
class TestSeasons:
    def test_format_season(self):
        assert N.format_season(2025) == "25/26"

    def test_format_season_decade_boundary(self):
        assert N.format_season(2009) == "09/10"

    def test_parse_season_summer(self):
        assert N.parse_season_from_date("01.07.2025") == 2025

    def test_get_season_range_inclusive(self):
        assert N.get_season_range("01.07.2020", "30.06.2022") == [2020, 2021, 2022]


# ── league_rank (BL1 < BL2 < BL3) ───────────────────────────────────────────
class TestLeagueRank:
    def test_order(self):
        assert N.league_rank("BL1") < N.league_rank("BL2") < N.league_rank("BL3")

    def test_bl1_is_one(self):
        assert N.league_rank("BL1") == 1


# ── filter_nationality (drop U-team / dissolved-state leak) ──────────────────
class TestFilterNationality:
    def test_drops_u_team(self):
        assert N.filter_nationality(["Deutschland", "Deutschland U21"]) == "Deutschland"

    def test_ddr_filtered_to_germany(self):
        assert N.filter_nationality(["DDR", "Deutschland"]) == "Deutschland"

    def test_single_value_passthrough(self):
        assert N.filter_nationality(["Kroatien"]) == "Kroatien"


# ── build_trainer_url ───────────────────────────────────────────────────────
class TestBuildTrainerUrl:
    def test_basic(self):
        assert N.build_trainer_url("Marcel Rapp", 24235) == \
            "https://www.transfermarkt.de/marcel-rapp/profil/trainer/24235"

    def test_umlaut_name(self):
        url = N.build_trainer_url("Adi Hütter", 5018)
        assert "/profil/trainer/5018" in url and " " not in url
