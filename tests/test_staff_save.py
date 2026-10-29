"""Staff files must survive TM block pages (soft blocks parse to zero staff)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "execution"))

import scrape_squads as S  # noqa: E402


def _rec(staff):
    return {"club_tm_id": 79, "club_name": "VfB Stuttgart", "staff": staff, "staff_count": len(staff)}


def test_empty_parse_keeps_existing_staff(tmp_path):
    path = tmp_path / "79.json"
    good = [{"tm_id": 20940, "name": "Sebastian Hoeneß", "role": "head_coach"}]
    assert S.save_staff(path, _rec(good))
    assert not S.save_staff(path, _rec([]))
    assert json.load(open(path))["staff"] == good


def test_empty_parse_written_when_no_file(tmp_path):
    path = tmp_path / "79.json"
    assert S.save_staff(path, _rec([]))
    assert json.load(open(path))["staff"] == []


def test_new_staff_replaces_old(tmp_path):
    path = tmp_path / "79.json"
    S.save_staff(path, _rec([{"tm_id": 1, "name": "Alt", "role": "head_coach"}]))
    new = [{"tm_id": 2, "name": "Neu", "role": "head_coach"}]
    assert S.save_staff(path, _rec(new))
    assert json.load(open(path))["staff"] == new


def test_block_page_is_detected():
    blocked = open(Path(S.CACHE_DIR) / "staff_79.html", errors="ignore").read() if (Path(S.CACHE_DIR) / "staff_79.html").exists() else "<html><body>Access denied</body></html>"
    assert S.looks_like_block(blocked)
