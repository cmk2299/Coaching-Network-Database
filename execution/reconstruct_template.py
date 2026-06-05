#!/usr/bin/env python3
"""Reconstruct blessin_network_v3.html template from a live-deployed dashboard.

The dashboard template (blessin_network_v3.html) was lost in a worktree-collision
data-loss event. Live production HTML retains the template structure — we strip
the inlined data lines back to placeholders so generate_dashboard.py can re-use it.

Usage:
  python3 execution/reconstruct_template.py \
    --source /tmp/blessin_live.html \
    --output blessin_network_v3.html

What gets rewritten:
  const NETWORK = {...};                   →  const NETWORK = {};
  const DRILLDOWN = {...};                 →  const DRILLDOWN = {};
  const DRILLDOWN_URL = '...';             →  const DRILLDOWN_URL = '';
  const DASHBOARD_INDEX = {...};           →  const DASHBOARD_INDEX = __DASHBOARD_INDEX_PLACEHOLDER__;
  const DASHBOARD_VARIANTS = {...};        →  const DASHBOARD_VARIANTS = __DASHBOARD_VARIANTS_PLACEHOLDER__;
  const CENTER_TM_ID = 26099;              →  const CENTER_TM_ID = __CENTER_TM_ID_PLACEHOLDER__;

What stays:
  - 'Alexander Blessin' references (generate_dashboard.py globally replaces them)
  - All HTML/CSS/JS template structure
"""
import argparse
import re
import sys
from pathlib import Path


def reconstruct(source: Path, output: Path) -> bool:
    if not source.exists():
        print(f"✗ Source not found: {source}")
        return False

    text = source.read_text(encoding="utf-8")
    lines = text.split("\n")

    # Track which replacements happen
    repl = {
        "NETWORK": False,
        "DRILLDOWN": False,
        "DRILLDOWN_URL": False,
        "DASHBOARD_INDEX": False,
        "DASHBOARD_VARIANTS": False,
        "CENTER_TM_ID": False,
    }

    new_lines = []
    for line in lines:
        s = line.lstrip()
        if s.startswith("const NETWORK") and "=" in s:
            new_lines.append("const NETWORK = {};")
            repl["NETWORK"] = True
        elif s.startswith("const DRILLDOWN_URL") and "=" in s:
            new_lines.append("const DRILLDOWN_URL = '';")
            repl["DRILLDOWN_URL"] = True
        elif s.startswith("const DRILLDOWN") and "=" in s:
            new_lines.append("const DRILLDOWN = {};")
            repl["DRILLDOWN"] = True
        elif s.startswith("const DASHBOARD_INDEX") and "=" in s:
            new_lines.append("const DASHBOARD_INDEX = __DASHBOARD_INDEX_PLACEHOLDER__;")
            repl["DASHBOARD_INDEX"] = True
        elif s.startswith("const DASHBOARD_VARIANTS") and "=" in s:
            new_lines.append("const DASHBOARD_VARIANTS = __DASHBOARD_VARIANTS_PLACEHOLDER__;")
            repl["DASHBOARD_VARIANTS"] = True
        elif s.startswith("const CENTER_TM_ID") and "=" in s:
            new_lines.append("const CENTER_TM_ID = __CENTER_TM_ID_PLACEHOLDER__;")
            repl["CENTER_TM_ID"] = True
        else:
            new_lines.append(line)

    missing = [k for k, v in repl.items() if not v]
    if missing:
        print(f"✗ Could not find these data lines: {missing}")
        return False

    output.write_text("\n".join(new_lines), encoding="utf-8")
    print(f"✓ Template reconstructed: {output} ({output.stat().st_size:,} bytes)")
    print(f"  Lines: {len(new_lines)}")
    print(f"  Stripped: NETWORK, DRILLDOWN, DRILLDOWN_URL, DASHBOARD_INDEX, "
          f"DASHBOARD_VARIANTS, CENTER_TM_ID")
    print("  Kept: 'Alexander Blessin' hardcoded refs (generator replaces these)")
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", required=True, help="Live deployed Blessin HTML")
    ap.add_argument("--output", required=True, help="Template output path")
    args = ap.parse_args()

    src = Path(args.source)
    out = Path(args.output)
    ok = reconstruct(src, out)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
