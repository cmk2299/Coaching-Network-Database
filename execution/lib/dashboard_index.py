"""Central dashboard slug index — used by both regenerate_dashboards.py
and generate_dashboard.py to ensure consistent slug resolution
between Coach-Networks ({slug}_network.html) and SD-Networks
({slug}_sd_network.html) and NLZ-Networks ({slug}_nlz_network.html).

Slug rule must match `slugify()` in lib.normalization so hyphenated/
special-char names (Marie-Louise Eta, O'Brien, Uwe Hölzl) resolve to
the correct {slug}_network.html file on disk.

Single source of truth — eliminates Slug-Drift between regenerator and
single-coach builder (Bug-Context P1 Cluster C, Audit Dim 3 / D4).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Set

from .normalization import slugify

BASE = Path(__file__).parent.parent.parent  # execution/lib/ → project root
NETWORKS_DIR = BASE / "data" / "networks"
DASHBOARD_DIR = BASE / "output" / "dashboards"
PERSONS_MASTER = BASE / "data" / "persons_master.json"
DECISION_MAKERS = BASE / "data" / "decision_makers.json"


def _load_dm_ids() -> Set[int]:
    """Load tm_ids of decision-makers (used to disambiguate SD-suffix)."""
    if not DECISION_MAKERS.exists():
        return set()
    try:
        data = json.load(open(DECISION_MAKERS))
        return {int(d["tm_id"]) for d in data.get("decision_makers", []) if d.get("tm_id")}
    except (json.JSONDecodeError, KeyError, ValueError, OSError):
        return set()


_PERSONS_CACHE: Dict[str, dict] | None = None


def _load_persons() -> Dict[str, dict]:
    """Lazily load persons_master {tm_id_str: person_dict}, memoized.

    Perf (2026-06-29): persons_master is ~300MB. It's only needed as a FALLBACK
    when a network file can't be read (the normal path takes slug from the network
    JSON itself), so eager-loading it in build_dashboard_index AND
    build_dashboard_variants wasted ~600MB and minutes (and OOM-killed when both
    ran in one process). Now it loads at most once, and only if the fallback path
    is actually hit."""
    global _PERSONS_CACHE
    if _PERSONS_CACHE is not None:
        return _PERSONS_CACHE
    if not PERSONS_MASTER.exists():
        _PERSONS_CACHE = {}
        return _PERSONS_CACHE
    try:
        _PERSONS_CACHE = json.load(open(PERSONS_MASTER)).get("persons", {})
    except (json.JSONDecodeError, OSError):
        _PERSONS_CACHE = {}
    return _PERSONS_CACHE


_SCAN_CACHE: "list[tuple[int, str]] | None" = None


def _scan_networks() -> "list[tuple[int, str]]":
    """Scan data/networks once → [(tm_id, slug), ...], memoized. Both
    build_dashboard_index and build_dashboard_variants need the same (tm_id, slug)
    list; without this they each json.load all ~3,300 network files (2× the I/O)."""
    global _SCAN_CACHE
    if _SCAN_CACHE is not None:
        return _SCAN_CACHE
    out: "list[tuple[int, str]]" = []
    for net_file in sorted(NETWORKS_DIR.glob("*.json")):
        try:
            tm_id = int(net_file.stem)
        except ValueError:
            continue
        try:
            net = json.load(open(net_file))
            slug = net.get("slug") or slugify(net.get("center", ""))
        except (json.JSONDecodeError, OSError):
            p = _load_persons().get(str(tm_id)) or {}
            slug = slugify(p.get("name", ""))
        if slug:
            out.append((tm_id, slug))
    _SCAN_CACHE = out
    return out


def build_dashboard_index() -> Dict[int, str]:
    """Returns map: tm_id -> dashboard-slug (without _network.html suffix).

    Slug carries `_sd` suffix for SD-typed centers (decision_makers or
    persons_master.type == "sporting_director") and `_nlz` for NLZ coaches.

    Resolution priority (file-existence based for backwards-compat):
      1. DM with sd_dash file → "{slug}_sd"  (SD wins for dual-role)
      2. coach_dash file exists → "{slug}"
      3. sd_dash file exists → "{slug}_sd"
      4. nlz_dash file exists → "{slug}_nlz"
      5. fallback → "{slug}"  (file may appear later, e.g. mid-batch)
    """
    dm_ids = _load_dm_ids()

    index: Dict[int, str] = {}
    for tm_id, slug in _scan_networks():
        coach_dash = DASHBOARD_DIR / f"{slug}_network.html"
        sd_dash = DASHBOARD_DIR / f"{slug}_sd_network.html"
        nlz_dash = DASHBOARD_DIR / f"{slug}_nlz_network.html"

        if tm_id in dm_ids and sd_dash.exists():
            index[tm_id] = f"{slug}_sd"
        elif coach_dash.exists():
            index[tm_id] = slug
        elif sd_dash.exists():
            index[tm_id] = f"{slug}_sd"
        elif nlz_dash.exists():
            index[tm_id] = f"{slug}_nlz"
        else:
            index[tm_id] = slug
    return index


def build_dashboard_variants() -> Dict[int, Dict[str, str]]:
    """Returns map: tm_id -> {kind: slug-with-suffix} for ALL variants that exist.

    kinds: "coach" | "sd" | "nlz"

    Used for Cross-Drilldown (Sprint G Phase 5): when a person has multiple
    dashboards (e.g. Sebastian Hoeneß has both head_coach and NLZ-era networks),
    the template surfaces all variants as cross-links in the dashboard header.
    """
    variants: Dict[int, Dict[str, str]] = {}
    for tm_id, slug in _scan_networks():
        kinds: Dict[str, str] = {}
        if (DASHBOARD_DIR / f"{slug}_network.html").exists():
            kinds["coach"] = slug
        if (DASHBOARD_DIR / f"{slug}_sd_network.html").exists():
            kinds["sd"] = f"{slug}_sd"
        if (DASHBOARD_DIR / f"{slug}_nlz_network.html").exists():
            kinds["nlz"] = f"{slug}_nlz"
        if len(kinds) >= 2:  # Only register if there's actually a cross-link
            variants[tm_id] = kinds
    return variants
