"""Rumour prototype: page parser and outcome/attribution helpers."""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "execution"))

import build_rumour_edges as E  # noqa: E402
import scrape_player_rumours as R  # noqa: E402


def _row(club, club_id, source, reply, prob, thread_id):
    return f"""<tr><td></td>
      <td><a title="{club}" href="/x/geruechte/verein/{club_id}">{club}</a></td>
      <td>{source}</td>
      <td><a href="https://www.transfermarkt.de/t/thread/forum/154/thread_id/{thread_id}/post_id/9">{reply}</a></td>
      <td>{prob}</td></tr>"""


PAGE = f"""<html><head><title>Max Muster - Gerüchte | Transfermarkt</title></head><body>
<div class="box"><h2>Gerüchte</h2><table class="items"><tbody>
{_row("FC Bayern München", 27, "13.09.2026", "06.10.2026", "31 %", 111)}
</tbody></table></div>
<div class="box"><h2>Transfermarkt Videos</h2><table class="items"><tbody><tr><td>x</td></tr></tbody></table></div>
<div class="box"><h2>Gerüchtearchiv</h2><table class="items"><tbody>
{_row("Real Madrid", 418, "25.02.2026", "12.03.2026", "-", 222)}
</tbody></table></div></body></html>"""


def test_parses_open_and_archived_rumours():
    parsed = R.parse_rumour_page(PAGE)
    assert parsed["name"] == "Max Muster"
    open_rumour, archived = parsed["rumours"]
    assert open_rumour == {
        "club": "FC Bayern München", "club_tm_id": 27, "status": "open",
        "last_source_date": "2026-09-13", "last_reply_date": "2026-10-06",
        "probability": 31, "thread_id": 111,
        "thread_url": "https://www.transfermarkt.de/t/thread/forum/154/thread_id/111",
    }
    assert (archived["club_tm_id"], archived["status"], archived["probability"]) == (418, "archived", None)


def test_error_page_yields_nothing():
    parsed = R.parse_rumour_page("<html><head><title>Error | Transfermarkt</title></head></html>")
    assert parsed == {"name": None, "rumours": []}


def test_role_type_separates_decision_makers_from_support_staff():
    assert E.role_type("Trainer") == "head_coach"
    assert E.role_type("Sportdirektor") == "sport_lead"
    assert E.role_type("Manager") == "sport_lead"
    for support in ("Teammanager", "Performance Manager", "Manager Marketing/Sponsoring", "Co-Trainer"):
        assert E.role_type(support) is None


def test_parse_tm_date_and_season():
    assert E.parse_tm_date("23/24 (04.07.2023)") == date(2023, 7, 4)
    assert E.parse_tm_date("-") is None
    assert E.season_of(date(2026, 6, 30)) == 2025
    assert E.season_of(date(2026, 7, 1)) == 2026


class _Squads:
    def __init__(self, data):
        self.data = data

    def players(self, club_id, season):
        return self.data.get((club_id, season))


def _rumour(status="archived", day="2024-08-10", club=27):
    return {"status": status, "last_source_date": day, "club_tm_id": club}


def test_outcome():
    covered = _Squads({(27, 2024): {1, 2}, (27, 2025): {3}})
    assert E.outcome(_rumour(), 9, None, covered, 2026) == "not_happened"
    assert E.outcome(_rumour(), 3, None, covered, 2026) == "happened"        # joined a season later
    assert E.outcome(_rumour(), 9, 27, covered, 2026) == "happened"          # plays there now
    assert E.outcome(_rumour(status="open"), 9, None, covered, 2026) == "unknown"
    assert E.outcome(_rumour(club=99), 9, None, covered, 2026) == "unknown"  # no squad coverage
