"""Drilldown sub-network cache: each person is built once per run and reused,
without callers sharing objects, optionally shared across processes via a dir.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "execution"))

import build_coach_network as B  # noqa: E402


def _fake_network(tm_id, n_contacts=20):
    return {
        "center": f"P{tm_id}",
        "total_contacts": n_contacts,
        "contacts": [
            {"name": f"C{i}", "_tm_id": 1000 + i, "background_summary": "x",
             "coaches_worked_with": [1], "sds_worked_with": [2]}
            for i in range(n_contacts)
        ],
    }


@pytest.fixture
def calls(monkeypatch):
    made = []

    def fake_build(tm_id, profiles=None, profile_index=None):
        made.append(tm_id)
        return None if tm_id == 404 else _fake_network(tm_id)

    monkeypatch.setattr(B, "build_network", fake_build)
    monkeypatch.setattr(B, "_SUB_NETWORK_CACHE", {})
    monkeypatch.delenv("NETWORK_DRILLDOWN_CACHE", raising=False)
    return made


def _center(*tm_ids):
    return {"contacts": [{"name": f"Person {t}", "_tm_id": t, "category": "coach"}
                         for t in tm_ids]}


def test_person_is_built_once_across_centers(calls):
    profiles = {7: {}, 8: {}}
    first = B.build_drilldown(_center(7, 8), profiles, {})
    second = B.build_drilldown(_center(8, 7), profiles, {})
    assert sorted(calls) == [7, 8]
    assert first["person_7"] == second["person_7"]


def test_cached_result_is_trimmed_and_stripped(calls):
    sub = B.build_drilldown(_center(7), {7: {}}, {})["person_7"]
    again = B.build_drilldown(_center(7), {7: {}}, {})["person_7"]
    for result in (sub, again):
        assert len(result["contacts"]) == 15 and result["total_contacts"] == 15
        assert all(c["has_drilldown"] is False for c in result["contacts"])
        assert all("background_summary" not in c and "coaches_worked_with" not in c
                   and "sds_worked_with" not in c for c in result["contacts"])


def test_callers_do_not_share_objects(calls):
    a = B.build_drilldown(_center(7), {7: {}}, {})["person_7"]
    a["contacts"].clear()
    b = B.build_drilldown(_center(7), {7: {}}, {})["person_7"]
    assert len(b["contacts"]) == 15


def test_failed_build_is_cached_and_skipped(calls):
    for _ in range(2):
        assert B.build_drilldown(_center(404), {404: {}}, {}) == {}
    assert calls == [404]


def test_disk_cache_is_shared_between_processes(calls, monkeypatch, tmp_path):
    monkeypatch.setenv("NETWORK_DRILLDOWN_CACHE", str(tmp_path))
    first = B.build_drilldown(_center(7), {7: {}}, {})
    monkeypatch.setattr(B, "_SUB_NETWORK_CACHE", {})  # simulates another shard process
    second = B.build_drilldown(_center(7), {7: {}}, {})
    assert calls == [7]
    assert first == second
    assert [p.name for p in tmp_path.iterdir()] == ["7_15.json"]
