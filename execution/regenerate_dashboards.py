#!/usr/bin/env python3
"""
Regenerate all dashboards from existing HTML files using the updated template.

Extracts NETWORK and DRILLDOWN JSON from each existing dashboard, then
re-injects into the current blessin_network_v3.html template.

This is useful when the template has visual changes but the data hasn't changed.

Usage:
    python regenerate_dashboards.py
    python regenerate_dashboards.py --dry-run
"""

import json
import re
import sys
import time
from pathlib import Path

BASE = Path(__file__).parent.parent
TEMPLATE = BASE / "blessin_network_v3.html"
DASHBOARD_DIR = BASE / "output" / "dashboards"
NETWORKS_DIR = BASE / "data" / "networks"

# Re-export the canonical slugify so this script stays a single source of truth
sys.path.insert(0, str(Path(__file__).parent))
from lib.dashboard_index import build_dashboard_index  # noqa: E402  central slug index

# TM portrait URLs encode tm_id: .../portrait/header/{tm_id}-{ts}.jpg
_TM_ID_FROM_IMG = re.compile(r"/portrait/header/(\d+)-")


# Lazy-built {coach_name: tm_id} index from data/networks/*.json — used as a second-pass
# fallback when image_url is absent. Only covers people who have their own coach network.
_COACH_NAME_INDEX = None


def _coach_name_index() -> dict:
    global _COACH_NAME_INDEX
    if _COACH_NAME_INDEX is not None:
        return _COACH_NAME_INDEX
    idx = {}
    for nf in NETWORKS_DIR.glob("*.json"):
        try:
            tm_id = int(nf.stem)
        except ValueError:
            continue
        try:
            with open(nf) as f:
                net = json.load(f)
            name = (net.get("center") or "").strip()
            if name:
                # First-write-wins; skip duplicates (rare same-name collision)
                idx.setdefault(name, tm_id)
        except (json.JSONDecodeError, KeyError, OSError):
            pass
    _COACH_NAME_INDEX = idx
    return idx


def backfill_tm_id(network: dict) -> int:
    """Set `_tm_id` on contacts that lack it. Two-pass strategy:
      1. Parse from image_url (TM portrait pattern: /portrait/header/{tm_id}-…jpg)
      2. Name-match against the coach-network index (covers contacts that are themselves
         head coaches with their own dashboard — the path the user actually drills down)
    Returns count of contacts patched. Used to repair legacy networks that were
    serialized before the strip_internal_fields() no-op fix (2026-04-29)."""
    patched = 0
    name_idx = None  # built lazily, only if needed
    for c in network.get("contacts", []):
        if c.get("_tm_id"):
            continue
        # Pass 1: image_url
        img = c.get("image_url") or ""
        m = _TM_ID_FROM_IMG.search(img)
        if m:
            try:
                c["_tm_id"] = int(m.group(1))
                patched += 1
                continue
            except ValueError:
                pass
        # Pass 2: name lookup
        name = (c.get("name") or "").strip()
        if not name:
            continue
        if name_idx is None:
            name_idx = _coach_name_index()
        tm_id = name_idx.get(name)
        if tm_id:
            c["_tm_id"] = tm_id
            patched += 1
    return patched


# NOTE: build_dashboard_index() is now imported from lib.dashboard_index (single
# source of truth shared with generate_dashboard.py). Slug-Drift-Fix P1-C2.


def extract_json_from_line(line: str, var_name: str):
    """Extract JSON value from a 'const VAR = {...};' line."""
    pattern = rf'^const\s+{var_name}\s*=\s*'
    m = re.match(pattern, line.strip())
    if not m:
        return None
    # Everything after 'const VAR = ' and before trailing ';'
    rest = line.strip()[m.end():]
    if rest.endswith(';'):
        rest = rest[:-1]
    try:
        return json.loads(rest)
    except json.JSONDecodeError:
        return None


def extract_data_from_dashboard(html_path: Path) -> tuple:
    """Extract NETWORK and DRILLDOWN data from an existing dashboard HTML."""
    with open(html_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    network = None
    network_url = ''
    drilldown = None
    drilldown_url = ''

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('const NETWORK_URL') and '=' in stripped:
            val = extract_json_from_line(stripped, 'NETWORK_URL')
            if val is not None:
                network_url = val
        elif (stripped.startswith('let NETWORK') or stripped.startswith('const NETWORK')) and '=' in stripped and network is None:
            network = extract_json_from_line(stripped, 'NETWORK')
        elif stripped.startswith('const DRILLDOWN_URL') and '=' in stripped:
            val = extract_json_from_line(stripped, 'DRILLDOWN_URL')
            if val is not None:
                drilldown_url = val
        elif stripped.startswith('const DRILLDOWN') and '=' in stripped and drilldown is None:
            # Skip if it's DRILLDOWN_URL
            if not stripped.startswith('const DRILLDOWN_URL'):
                drilldown = extract_json_from_line(stripped, 'DRILLDOWN')

    # Serve-from-DB: when NETWORK was externalized (let NETWORK = null + URL),
    # reload it from {slug}_network.json so regeneration has the canonical data.
    if network is None or network == {}:
        ext = html_path.parent / (network_url or f"{html_path.stem}_network.json")
        if ext.exists():
            try:
                with open(ext, 'r', encoding='utf-8') as ef:
                    network = json.loads(ef.read())
            except Exception:
                pass

    # If drilldown is empty, try to load from external JSON file.
    # Case 1: DRILLDOWN_URL is set explicitly (DRILLDOWN = null + URL = 'file.json')
    # Case 2: Convention-based — look for {stem}_drilldown.json next to HTML
    if drilldown is None or drilldown == {}:
        # Try explicit URL first
        if drilldown_url:
            external_path = html_path.parent / drilldown_url
        else:
            # Convention: {slug}_drilldown.json next to the HTML
            external_path = html_path.parent / f"{html_path.stem}_drilldown.json"

        if external_path.exists():
            try:
                with open(external_path, 'r', encoding='utf-8') as ef:
                    drilldown = json.loads(ef.read())
            except Exception:
                pass  # Keep drilldown as-is if loading fails

    return network, drilldown, drilldown_url


def regenerate_dashboard(html_path: Path, template_lines: list, dashboard_index: dict,
                         network: dict, drilldown: dict, drilldown_url: str,
                         lazy_threshold: int = 0,
                         dashboard_variants: dict = None,
                         tm_id_lookup: dict = None) -> dict:
    """Regenerate a single dashboard HTML from the updated template.

    Args:
        lazy_threshold: If drilldown JSON bytes > this, save as external file.
                        0 = always inline (no lazy loading).

    Returns:
        dict with 'ok' bool and optional 'externalized' size.
    """
    coach_name = network.get("center", "Unknown")
    result = {'ok': False, 'externalized': 0, 'tm_id_patched': 0, 'tm_id_patched_drill': 0}

    # Backfill _tm_id (legacy networks were stripped before serialization).
    # This restores cross-coach drill-down (Eta → Fischer → …) without a full rebuild.
    result['tm_id_patched'] = backfill_tm_id(network)
    if drilldown:
        for sub in drilldown.values():
            result['tm_id_patched_drill'] += backfill_tm_id(sub)

    # Find replacement lines in template
    network_line_idx = None
    network_url_line_idx = None
    drilldown_line_idx = None
    drilldown_url_line_idx = None
    dashboard_index_line_idx = None

    for i, line in enumerate(template_lines):
        stripped = line.strip()
        if stripped.startswith("const NETWORK_URL") and "=" in stripped:
            network_url_line_idx = i
        elif (stripped.startswith("let NETWORK") or stripped.startswith("const NETWORK")) and "=" in stripped:
            network_line_idx = i
        elif stripped.startswith("const DRILLDOWN_URL") and "=" in stripped:
            drilldown_url_line_idx = i
        elif stripped.startswith("const DRILLDOWN") and "=" in stripped:
            drilldown_line_idx = i
        if '__DASHBOARD_INDEX_PLACEHOLDER__' in line:
            dashboard_index_line_idx = i

    if network_line_idx is None:
        return result

    # Build new lines
    lines = list(template_lines)  # Copy

    network_json = json.dumps(network, ensure_ascii=False, separators=(',', ':'))
    drilldown_json = json.dumps(drilldown or {}, ensure_ascii=False, separators=(',', ':'))

    slug = html_path.stem

    # Serve-from-DB: externalize NETWORK to {slug}_network.json (thin-shell HTML).
    if network_url_line_idx is not None:
        with open(html_path.parent / f"{slug}_network.json", 'w', encoding='utf-8') as f:
            f.write(network_json)
        lines[network_line_idx] = "let NETWORK = null;\n"
        lines[network_url_line_idx] = f"const NETWORK_URL = '{slug}_network.json';\n"
    else:
        lines[network_line_idx] = f"let NETWORK = {network_json};\n"

    # Decide: inline or external drilldown
    use_external = (lazy_threshold > 0 and len(drilldown_json) > lazy_threshold
                    and drilldown_json != '{}')

    if use_external:
        # Save drilldown as external JSON file next to the HTML
        drilldown_path = html_path.parent / f"{slug}_drilldown.json"
        with open(drilldown_path, 'w', encoding='utf-8') as f:
            f.write(drilldown_json)
        result['externalized'] = len(drilldown_json)
        if drilldown_line_idx is not None:
            lines[drilldown_line_idx] = "const DRILLDOWN = null;\n"
        if drilldown_url_line_idx is not None:
            lines[drilldown_url_line_idx] = f"const DRILLDOWN_URL = '{slug}_drilldown.json';\n"
    else:
        if drilldown_line_idx is not None:
            lines[drilldown_line_idx] = f"const DRILLDOWN = {drilldown_json};\n"
        if drilldown_url_line_idx is not None:
            lines[drilldown_url_line_idx] = "const DRILLDOWN_URL = '';\n"

    # Inject dashboard index + variants + center tm_id (Sprint G Phase 5 Cross-Drilldown)
    di_json = json.dumps(dashboard_index, ensure_ascii=False, separators=(',', ':'))
    dv_json = json.dumps(dashboard_variants or {}, ensure_ascii=False, separators=(',', ':'))
    # Resolve center_tm_id by stem → tm_id reverse lookup
    target_stem = html_path.stem
    base_slug = target_stem.replace("_nlz_network", "").replace("_sd_network", "").replace("_network", "")
    center_tm_id = None
    if tm_id_lookup is not None:
        center_tm_id = tm_id_lookup.get(base_slug)
    if center_tm_id is None:
        for tm_id, idx_slug in dashboard_index.items():
            base = idx_slug.replace("_sd", "").replace("_nlz", "")
            if base == base_slug:
                center_tm_id = tm_id
                break
    ctm_json = json.dumps(center_tm_id)

    for i, line in enumerate(lines):
        if '__DASHBOARD_INDEX_PLACEHOLDER__' in line:
            lines[i] = line.replace('__DASHBOARD_INDEX_PLACEHOLDER__', di_json)
        if '__DASHBOARD_VARIANTS_PLACEHOLDER__' in lines[i]:
            lines[i] = lines[i].replace('__DASHBOARD_VARIANTS_PLACEHOLDER__', dv_json)
        if '__CENTER_TM_ID_PLACEHOLDER__' in lines[i]:
            lines[i] = lines[i].replace('__CENTER_TM_ID_PLACEHOLDER__', ctm_json)

    # Replace center-name placeholder with the actual coach name.
    # FIX 2026-05-21 (F2): Same fix as generate_dashboard.py — naive
    # "Alexander Blessin" replace corrupted contact names in embedded JSON.
    # Backward compat: also replace the literal "Alexander Blessin" string
    # in case a template was regenerated before the placeholder migration.
    output_lines = []
    for line in lines:
        line = line.replace("__CENTER_NAME_PLACEHOLDER__", coach_name)
        output_lines.append(line)

    with open(html_path, 'w', encoding='utf-8') as f:
        f.writelines(output_lines)

    result['ok'] = True
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Regenerate dashboards with updated template")
    parser.add_argument("--dry-run", action="store_true", help="Don't write files")
    parser.add_argument("--lazy", type=int, default=0, metavar="BYTES",
                        help="Externalize drilldown JSON larger than BYTES (e.g. 500000 for 500KB). "
                             "0 = always inline (default).")
    parser.add_argument("--changed-only", action="store_true",
                        help="Incremental mode: skip dashboards whose canonical source "
                             "data/networks/{tm_id}.json is older than the dashboard HTML "
                             "AND the template is older than the dashboard. Drastically "
                             "speeds up daily refreshes (typically 5-10 changes vs 4054).")
    args = parser.parse_args()

    if not TEMPLATE.exists():
        print(f"✗ Template not found: {TEMPLATE}")
        sys.exit(1)

    with open(TEMPLATE, 'r', encoding='utf-8') as f:
        template_lines = f.readlines()

    from lib.dashboard_index import build_dashboard_variants
    dashboard_index = build_dashboard_index()
    dashboard_variants = build_dashboard_variants()
    # Reverse lookup: base_slug → tm_id (for center_tm_id resolution)
    tm_id_lookup = {}
    for tm_id, idx_slug in dashboard_index.items():
        base = idx_slug.replace("_sd", "").replace("_nlz", "")
        tm_id_lookup[base] = tm_id
    print(f"Dashboard index: {len(dashboard_index)} coaches · {len(dashboard_variants)} with multiple variants")
    if args.lazy:
        print(f"Lazy loading: externalize drilldown > {args.lazy / 1000:.0f} KB")

    dashboards = sorted(DASHBOARD_DIR.glob("*_network.html"))
    print(f"Found {len(dashboards)} dashboards to regenerate\n")

    success = 0
    failed = 0
    externalized_count = 0
    externalized_bytes = 0
    t0 = time.time()

    # FIX 2026-05-21 (F2 ext): Canonical network source is data/networks/{tm_id}.json,
    # NOT the embedded JSON in the existing dashboard HTML. Previous version
    # read NETWORK from HTML — which propagated any prior corruption (e.g., the
    # "Alexander Blessin" string-replace bug) forward into every regenerate cycle.
    # Now we load from the source-of-truth JSON when available; fall back to HTML
    # extraction only for dashboards without a matching source file.
    NETWORK_DIR = Path("data/networks")
    template_mtime = TEMPLATE.stat().st_mtime
    skipped_clean = 0
    for i, dp in enumerate(dashboards, 1):
        network = drilldown = None
        drilldown_url = ''
        # Try canonical source via reverse lookup
        target_stem = dp.stem
        base_slug = target_stem.replace("_nlz_network", "").replace("_sd_network", "").replace("_network", "")
        canonical_tm_id = tm_id_lookup.get(base_slug)

        # Incremental mode: skip if dashboard is newer than BOTH its canonical
        # network JSON and the template. Dashboards needing regen: canonical
        # data changed OR template changed OR HTML missing.
        if args.changed_only and canonical_tm_id is not None:
            try:
                dp_mtime = dp.stat().st_mtime
                net_path = NETWORK_DIR / f"{canonical_tm_id}.json"
                net_mtime = net_path.stat().st_mtime if net_path.exists() else 0
                if net_mtime <= dp_mtime and template_mtime <= dp_mtime:
                    skipped_clean += 1
                    continue
            except OSError:
                pass  # any stat failure → just process normally
        if canonical_tm_id is not None:
            net_json_path = NETWORK_DIR / f"{canonical_tm_id}.json"
            if net_json_path.exists():
                try:
                    with open(net_json_path, 'r', encoding='utf-8') as nf:
                        network = json.load(nf)
                    # Load matching drilldown JSON if present
                    dd_external = dp.parent / f"{dp.stem}_drilldown.json"
                    if dd_external.exists():
                        with open(dd_external, 'r', encoding='utf-8') as df:
                            drilldown = json.load(df)
                except Exception as e:
                    print(f"  [{i}/{len(dashboards)}] ⚠ canonical-load failed for {dp.name}: {e}")
                    network = None
        # Fallback to old extraction if canonical not found
        if network is None:
            network, drilldown, drilldown_url = extract_data_from_dashboard(dp)
        if network is None:
            print(f"  [{i}/{len(dashboards)}] ✗ {dp.name} — could not extract NETWORK data")
            failed += 1
            continue

        coach = network.get("center", "?")
        contacts = network.get("total_contacts", 0)

        if args.dry_run:
            dd_size = len(json.dumps(drilldown or {}, ensure_ascii=False, separators=(',', ':')))
            ext_marker = " [→ external]" if args.lazy and dd_size > args.lazy else ""
            print(f"  [{i}/{len(dashboards)}] ○ {dp.name} — {coach} ({contacts} contacts){ext_marker} [dry-run]")
            success += 1
            continue

        res = regenerate_dashboard(dp, template_lines, dashboard_index,
                                   network, drilldown, drilldown_url,
                                   lazy_threshold=args.lazy,
                                   dashboard_variants=dashboard_variants,
                                   tm_id_lookup=tm_id_lookup)
        if res['ok']:
            if res['externalized']:
                externalized_count += 1
                externalized_bytes += res['externalized']
                print(f"  [{i}/{len(dashboards)}] ✓ {dp.name} — {coach} ({contacts} contacts) → drilldown externalized ({res['externalized']/1e6:.1f} MB)")
            elif i % 50 == 0 or i == len(dashboards):
                print(f"  [{i}/{len(dashboards)}] ✓ {dp.name} — {coach} ({contacts} contacts)")
            success += 1
        else:
            print(f"  [{i}/{len(dashboards)}] ✗ {dp.name} — template injection failed")
            failed += 1

    elapsed = time.time() - t0
    print(f"\n{'─'*50}")
    print(f"  Regenerated: {success} ✓  Failed: {failed} ✗"
          + (f"  Skipped (clean): {skipped_clean}" if args.changed_only else ""))
    if externalized_count:
        print(f"  Externalized: {externalized_count} drilldowns ({externalized_bytes/1e6:.1f} MB saved from HTML)")
    print(f"  Time: {elapsed:.1f}s ({elapsed/max(1,len(dashboards))*1000:.0f}ms per dashboard)")


if __name__ == "__main__":
    main()
