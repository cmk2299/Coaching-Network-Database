#!/usr/bin/env python3
"""
Generate Dashboard — Schritt 2 des MVP

Takes a network JSON (from build_coach_network.py) and injects it into
the blessin_network_v3.html dashboard template.

Output: A self-contained HTML file per coach.

Usage:
    python generate_dashboard.py --network data/networks/26099.json
    python generate_dashboard.py --network data/networks/26099.json --output output/blessin.html
"""

import argparse
import json
import re
from pathlib import Path

BASE = Path(__file__).parent.parent
TEMPLATE = BASE / "blessin_network_v3.html"
OUTPUT_DIR = BASE / "output" / "dashboards"
NETWORKS_DIR = BASE / "data" / "networks"

# Dashboard cross-link index: {tm_id: slug}
_dashboard_index = {}


import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent))
from lib.dashboard_index import (  # noqa: E402
    build_dashboard_index as _build_dashboard_index,
    build_dashboard_variants as _build_dashboard_variants,
)

_dashboard_variants = {}


def build_dashboard_index():
    """Populate module-level `_dashboard_index` and `_dashboard_variants`.
    Single source of truth (lib.dashboard_index). Fix P1-C2 Slug-Drift.
    """
    global _dashboard_index, _dashboard_variants
    if _dashboard_index:
        return
    _dashboard_index.update(_build_dashboard_index())
    _dashboard_variants.update(_build_dashboard_variants())


def load_template() -> list[str]:
    """Load the dashboard template and return as list of lines."""
    with open(TEMPLATE, "r", encoding="utf-8") as f:
        return f.readlines()


def load_network(path: Path) -> dict:
    """Load a network JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


STRIP_CONTACT_FIELDS = {'scraped_at', 'player_positions', 'foot', 'birthplace', 'was_player', 'player_tm_id'}

def _strip_contact(c: dict) -> dict:
    """Remove fields the dashboard JS doesn't use."""
    out = {}
    for k, v in c.items():
        if k in STRIP_CONTACT_FIELDS:
            continue
        if v is None or v == '' or v == [] or v == {}:
            continue
        out[k] = v
    return out

def _strip_network(network: dict) -> dict:
    """Strip unused fields from network JSON."""
    out = dict(network)
    if 'contacts' in out:
        out['contacts'] = [_strip_contact(c) for c in out['contacts']]
    return out

def _strip_drilldown(drilldown: dict) -> dict:
    """Strip unused fields from drilldown sub-networks."""
    out = {}
    for key, dd in drilldown.items():
        stripped_dd = dict(dd)
        if 'contacts' in stripped_dd:
            stripped_dd['contacts'] = [_strip_contact(c) for c in stripped_dd['contacts']]
        out[key] = stripped_dd
    return out


def generate_dashboard(network: dict, output_path: Path, drilldown: dict = None,
                       lazy_threshold: int = 500_000):
    """
    Generate a dashboard HTML file from a network JSON.

    Args:
        network: Coach network data (from build_network())
        output_path: Where to save the HTML
        drilldown: Optional drill-down sub-networks {contact_name: sub_network}
        lazy_threshold: Externalize drilldown JSON if larger than this (bytes).
                        Default 500KB. Set to 0 to always inline.

    Lazy-loading for large dashboards:
    - If drilldown JSON > lazy_threshold, save it as external {slug}_drilldown.json
    - Template uses fetch() to load on first drill-down click
    - Small dashboards stay inline for backward compatibility
    """
    build_dashboard_index()
    lines = load_template()
    coach_name = network["center"]

    # Find the data lines (const NETWORK = ... and const DRILLDOWN = ...)
    network_line_idx = None
    drilldown_line_idx = None
    drilldown_url_line_idx = None

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("const NETWORK") and "=" in stripped:
            network_line_idx = i
        elif stripped.startswith("const DRILLDOWN_URL") and "=" in stripped:
            drilldown_url_line_idx = i
        elif stripped.startswith("const DRILLDOWN") and "=" in stripped:
            drilldown_line_idx = i

    if network_line_idx is None:
        print("  ✗ Could not find 'const NETWORK' line in template")
        return False

    # Strip redundant fields to reduce file size
    stripped_network = _strip_network(network)
    stripped_drilldown = _strip_drilldown(drilldown or {})

    # Build NETWORK JSON (minified)
    network_json = json.dumps(stripped_network, ensure_ascii=False, separators=(',', ':'))

    # Build DRILLDOWN JSON
    drilldown_json = json.dumps(stripped_drilldown, ensure_ascii=False, separators=(',', ':'))

    # Decide: inline or external drilldown
    # Drilldown > lazy_threshold is saved as external JSON, loaded on first drill-down click.
    drilldown_size = len(drilldown_json)
    use_external_drilldown = (lazy_threshold > 0 and drilldown_size > lazy_threshold
                              and drilldown_json != '{}')

    # Generate slug from output filename (e.g., "blessin_network.html" -> "blessin_network")
    slug = output_path.stem

    # Replace data lines
    new_network_line = f"const NETWORK = {network_json};\n"

    if use_external_drilldown and drilldown_json != '{}':
        # Save drilldown as external JSON file
        drilldown_path = output_path.parent / f"{slug}_drilldown.json"
        drilldown_path.parent.mkdir(parents=True, exist_ok=True)
        with open(drilldown_path, "w", encoding="utf-8") as f:
            f.write(drilldown_json)

        new_drilldown_line = "const DRILLDOWN = null;\n"
        new_drilldown_url_line = f"const DRILLDOWN_URL = '{slug}_drilldown.json';\n"

        print(f"  → Drilldown saved externally: {drilldown_path} ({drilldown_size / 1_000_000:.1f} MB)")
    else:
        # Keep inline
        new_drilldown_line = f"const DRILLDOWN = {drilldown_json};\n"
        new_drilldown_url_line = "const DRILLDOWN_URL = '';\n"

    lines[network_line_idx] = new_network_line
    if drilldown_line_idx is not None:
        lines[drilldown_line_idx] = new_drilldown_line
    if drilldown_url_line_idx is not None:
        lines[drilldown_url_line_idx] = new_drilldown_url_line

    # Inject DASHBOARD_INDEX (cross-link mapping) + DASHBOARD_VARIANTS (Sprint G Phase 5)
    # Determine CENTER_TM_ID from the network JSON or output filename stem
    center_tm_id = None
    # Try center_tm_id from network metadata first (set by build_coach_network.py for some flows)
    for key in ("center_tm_id", "tm_id"):
        if key in network and isinstance(network[key], int):
            center_tm_id = network[key]
            break
    # Else try to invert _dashboard_index by name → slug match
    if center_tm_id is None:
        target_slug = output_path.stem.replace("_nlz_network", "").replace("_sd_network", "").replace("_network", "")
        for tm_id, idx_slug in _dashboard_index.items():
            base = idx_slug.replace("_sd", "").replace("_nlz", "")
            if base == target_slug:
                center_tm_id = tm_id
                break

    di_json = json.dumps(_dashboard_index, ensure_ascii=False, separators=(',', ':'))
    dv_json = json.dumps(_dashboard_variants, ensure_ascii=False, separators=(',', ':'))
    ctm_json = json.dumps(center_tm_id)

    for i, line in enumerate(lines):
        if '__DASHBOARD_INDEX_PLACEHOLDER__' in line:
            lines[i] = line.replace('__DASHBOARD_INDEX_PLACEHOLDER__', di_json)
        if '__DASHBOARD_VARIANTS_PLACEHOLDER__' in lines[i]:
            lines[i] = lines[i].replace('__DASHBOARD_VARIANTS_PLACEHOLDER__', dv_json)
        if '__CENTER_TM_ID_PLACEHOLDER__' in lines[i]:
            lines[i] = lines[i].replace('__CENTER_TM_ID_PLACEHOLDER__', ctm_json)

    # Replace center-name placeholder with the actual coach name.
    # FIX 2026-05-21 (F2): Previous version used naive `line.replace("Alexander Blessin", coach_name)`
    # which corrupted contact names in embedded NETWORK JSON whenever Blessin
    # appeared as a contact (e.g., Bornemann's SD-network had a coach_hired entry
    # for Blessin → name got replaced with "Andreas Bornemann"). Now uses a
    # unique placeholder marker that cannot appear in real names or data.
    result = []
    for line in lines:
        line = line.replace("__CENTER_NAME_PLACEHOLDER__", coach_name)
        result.append(line)

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.writelines(result)

    print(f"  ✓ Dashboard saved: {output_path}")
    print(f"    Coach: {coach_name}")
    print(f"    Contacts: {network['total_contacts']}")
    print(f"    Drilldown size: {drilldown_size / 1_000_000:.1f} MB ({'external' if use_external_drilldown else 'inline'})")
    return True


def main():
    parser = argparse.ArgumentParser(description="Generate coach network dashboard")
    parser.add_argument("--network", type=str, required=True, help="Path to network JSON")
    parser.add_argument("--output", type=str, help="Output HTML path")
    parser.add_argument("--template", type=str, help="Custom template path")

    args = parser.parse_args()

    if args.template:
        global TEMPLATE
        TEMPLATE = Path(args.template)

    network = load_network(Path(args.network))
    coach_name = network["center"]

    # PATTERN 30 FIX (2026-05-23): use canonical slugify() for diacritic
    # transliteration (é→e, ä→ae, ß→ss). Inline regex below dropped
    # non-ASCII chars entirely → "René Wagner" → "ren_wagner" (broken URL).
    try:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).parent))
        from lib.normalization import slugify
        slug = slugify(coach_name)
    except Exception:
        # Fallback to old behavior (shouldn't trigger)
        slug = re.sub(r'[^a-z0-9]+', '_', coach_name.lower()).strip('_')

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = OUTPUT_DIR / f"{slug}_network.html"

    generate_dashboard(network, output_path)


if __name__ == "__main__":
    main()
