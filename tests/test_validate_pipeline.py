"""Unit tests for execution/validate_pipeline.py — the pre-deploy artifact-count
gate that blocks a deploy when key data volumes regress >5%. Was untested even
though it's run on every run_mvp invocation.
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "execution" / "validate_pipeline.py"


def _import_module():
    """Load validate_pipeline as a module so we can test internals directly."""
    spec = importlib.util.spec_from_file_location("validate_pipeline", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(args, baseline=None, tmp_baseline=None):
    """Run the script as a subprocess in --update-baseline-isolated mode by
    pointing BASELINE to a tmp file via monkey-patched module globals."""
    cmd = [sys.executable, str(SCRIPT)] + args
    env = {"PATH": "/usr/bin:/bin"}
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


class TestMetricsShape:
    def test_metrics_has_expected_keys(self):
        m = _import_module().metrics()
        assert {"networks", "person_profiles", "dashboards", "staff_files",
                "persons_master_bytes", "index_exists"} <= set(m.keys())

    def test_all_int(self):
        m = _import_module().metrics()
        for v in m.values():
            assert isinstance(v, int)

    def test_index_exists_is_0_or_1(self):
        m = _import_module().metrics()
        assert m["index_exists"] in (0, 1)


class TestGateLogic:
    def test_baseline_seed_when_missing(self, tmp_path, monkeypatch):
        mod = _import_module()
        fake = tmp_path / ".pipeline_baseline.json"
        monkeypatch.setattr(mod, "BASELINE", fake)
        monkeypatch.setattr(sys, "argv", ["validate_pipeline.py"])
        try:
            mod.main()
        except SystemExit as e:
            assert e.code in (None, 0)
        assert fake.exists()
        seeded = json.load(open(fake))
        assert "networks" in seeded

    # Fake metrics: synthesize values so tests work in any env (CI has no
    # output/index.html so real metrics() would always fail the gate).
    _FAKE_METRICS = {"networks": 100, "person_profiles": 1000, "dashboards": 100,
                     "staff_files": 50, "persons_master_bytes": 1000000,
                     "index_exists": 1}

    def test_regression_above_tolerance_exits_nonzero(self, tmp_path, monkeypatch):
        mod = _import_module()
        fake = tmp_path / ".pipeline_baseline.json"
        monkeypatch.setattr(mod, "metrics", lambda: dict(self._FAKE_METRICS))
        inflated = {k: (v * 10 if isinstance(v, int) and k != "index_exists" else v)
                    for k, v in self._FAKE_METRICS.items()}
        json.dump(inflated, open(fake, "w"))
        monkeypatch.setattr(mod, "BASELINE", fake)
        monkeypatch.setattr(sys, "argv", ["validate_pipeline.py"])
        try:
            mod.main()
            assert False, "expected SystemExit"
        except SystemExit as e:
            assert e.code == 1

    def test_within_tolerance_passes(self, tmp_path, monkeypatch):
        mod = _import_module()
        fake = tmp_path / ".pipeline_baseline.json"
        monkeypatch.setattr(mod, "metrics", lambda: dict(self._FAKE_METRICS))
        json.dump(self._FAKE_METRICS, open(fake, "w"))
        monkeypatch.setattr(mod, "BASELINE", fake)
        monkeypatch.setattr(sys, "argv", ["validate_pipeline.py"])
        try:
            mod.main()
        except SystemExit as e:
            assert e.code in (None, 0)

    def test_update_baseline_overwrites(self, tmp_path, monkeypatch):
        mod = _import_module()
        fake = tmp_path / ".pipeline_baseline.json"
        json.dump({"networks": 1}, open(fake, "w"))
        monkeypatch.setattr(mod, "BASELINE", fake)
        monkeypatch.setattr(sys, "argv", ["validate_pipeline.py", "--update-baseline"])
        try:
            mod.main()
        except SystemExit as e:
            assert e.code in (None, 0)
        rewritten = json.load(open(fake))
        assert rewritten["networks"] > 1  # current state, not the stub
