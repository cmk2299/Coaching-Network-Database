import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "execution"))
from lib.logging_setup import get_logger, write_run_summary  # noqa: E402


def test_get_logger_idempotent():
    a = get_logger("test_unit_logger")
    b = get_logger("test_unit_logger")
    assert a is b
    assert len(a.handlers) >= 1  # not duplicated on second call


def test_write_run_summary_returns_record():
    rec = write_run_summary("test_unit_run", ok=5, failed=1)
    assert rec["run"] == "test_unit_run"
    assert rec["ok"] == 5 and rec["failed"] == 1
    assert "ts" in rec and rec["ts"].endswith("+00:00")
