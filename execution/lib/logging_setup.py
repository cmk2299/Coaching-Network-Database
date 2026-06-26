"""Structured logging + machine-parseable run summaries for the pipeline.

Audit 2026-06-20: 0/152 scripts used `logging` — no observability, silent
regressions (GS-parser, player-refresh) left no audit trail. This gives a single
configured logger (ISO timestamp + level + name, to stderr AND logs/<name>.log)
plus `write_run_summary()` which appends one JSON line per run to
logs/runs/<YYYYMMDD>.jsonl — the basis for drift detection (compare counts
across runs).

    from lib.logging_setup import get_logger, write_run_summary
    log = get_logger("staff_scrape")
    log.info("starting")
    ...
    write_run_summary("staff_scrape", scraped=120, skipped=800, failed=2)
"""
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
LOG_DIR = BASE / "logs"
RUN_DIR = LOG_DIR / "runs"


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Return a configured logger (idempotent — safe to call repeatedly)."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(level)
    fmt = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s",
                            "%Y-%m-%dT%H:%M:%S")
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(LOG_DIR / f"{name}.log", encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except OSError:
        pass  # stderr-only if the log dir isn't writable
    logger.propagate = False
    return logger


def write_run_summary(run: str, **fields) -> dict:
    """Append one JSON record (run name, UTC ts, arbitrary counts) to the daily
    run-summary JSONL. Returns the record. Never raises — observability must not
    break the pipeline."""
    rec = {"run": run, "ts": datetime.now(timezone.utc).isoformat(), **fields}
    try:
        RUN_DIR.mkdir(parents=True, exist_ok=True)
        day = datetime.now(timezone.utc).strftime("%Y%m%d")
        with open(RUN_DIR / f"{day}.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return rec
