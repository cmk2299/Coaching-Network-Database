"""Unit tests for execution/validate_coach_overrides.py."""
import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "execution" / "validate_coach_overrides.py"


def _load():
    spec = importlib.util.spec_from_file_location("vco", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestValidate:
    def test_clean_data_no_issues(self):
        v = _load().validate({
            "sacked": [{"club_tm_id": 1, "club": "X", "tm_id": 99, "name": "A"}],
            "appointed": [{"club_tm_id": 2, "club": "Y", "tm_id": 100, "name": "B",
                           "replaces_tm_id": 99}],
            "sd": [{"club_tm_id": 3, "club": "Z", "tm_id": 101, "name": "C"}],
        })
        assert v == []

    def test_missing_required(self):
        v = _load().validate({"sacked": [{"club_tm_id": 1, "club": "X"}]})
        assert any("missing required" in m for m in v)
        # Both tm_id and name are required
        assert sum("missing required" in m for m in v) == 2

    def test_zero_tm_id_rejected(self):
        v = _load().validate({"sacked": [
            {"club_tm_id": 1, "club": "X", "tm_id": 0, "name": "A"}]})
        assert any("tm_id" in m and "0" in m for m in v)

    def test_string_tm_id_rejected(self):
        v = _load().validate({"sacked": [
            {"club_tm_id": "1", "club": "X", "tm_id": 99, "name": "A"}]})
        assert any("club_tm_id" in m for m in v)

    def test_replaces_tm_id_null_allowed(self):
        v = _load().validate({"appointed": [
            {"club_tm_id": 1, "club": "X", "tm_id": 99, "name": "A",
             "replaces_tm_id": None}]})
        assert v == []

    def test_replaces_tm_id_zero_rejected(self):
        v = _load().validate({"appointed": [
            {"club_tm_id": 1, "club": "X", "tm_id": 99, "name": "A",
             "replaces_tm_id": 0}]})
        assert any("replaces_tm_id" in m for m in v)

    def test_duplicate_appointed_for_same_club(self):
        v = _load().validate({"appointed": [
            {"club_tm_id": 1, "club": "X", "tm_id": 99, "name": "A"},
            {"club_tm_id": 1, "club": "X", "tm_id": 100, "name": "B"},
        ]})
        assert any("club_tm_id=1" in m and "2 entries" in m for m in v)

    def test_real_overrides_file_is_valid(self):
        """The committed data/coach_overrides.json should always validate."""
        mod = _load()
        import json
        if not mod.OVERRIDES.exists():
            return  # nothing to check
        data = json.load(open(mod.OVERRIDES))
        v = mod.validate(data)
        assert v == [], f"data/coach_overrides.json has issues: {v}"
