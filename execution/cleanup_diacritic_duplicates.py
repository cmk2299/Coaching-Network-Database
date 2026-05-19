#!/usr/bin/env python3
"""
Cleanup stale dashboard files with raw diacritics in their names.

Background: pre-2026-04-29 the slugify rule wasn't consistent. We had three
flavors floating around for the same coach:
  meikel_schönweitz_network.html      (preserved umlaut)
  meikel_schnweitz_network.html       (umlaut stripped, no transliteration)
  meikel_sch_nweitz_network.html      (umlaut → underscore)

The new canonical slug (lib/normalization.slugify) transliterates ä→ae, ö→oe,
ü→ue, ß→ss, é→e, etc. → meikel_schoenweitz_network.html

Strategy:
  For each dashboard file whose name contains non-ASCII chars, compute the
  canonical slug from the file's `const NETWORK = {center: "..."}`. If that
  canonical file already exists, the diacritic version is stale → move to
  /tmp/stale_dashboards/.

Usage:
  python execution/cleanup_diacritic_duplicates.py --dry-run
  python execution/cleanup_diacritic_duplicates.py            # actually move
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.normalization import slugify  # noqa: E402

BASE = Path(__file__).parent.parent
DASHBOARD_DIR = BASE / "output" / "dashboards"
STALE_DIR = BASE / "tmp" / "stale_dashboards"


def extract_center(html_path: Path) -> str:
    """Extract NETWORK.center from a dashboard HTML."""
    try:
        txt = html_path.read_text(encoding="utf-8")
    except OSError:
        return ""
    m = re.search(r'const NETWORK = (\{.*?\});\s*\n', txt, re.DOTALL)
    if not m:
        return ""
    try:
        net = json.loads(m.group(1))
        return net.get("center", "")
    except json.JSONDecodeError:
        return ""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="report only, don't move files")
    args = parser.parse_args()

    if not args.dry_run:
        STALE_DIR.mkdir(parents=True, exist_ok=True)

    # All HTML files in dashboards/
    all_files = sorted(DASHBOARD_DIR.glob("*.html"))

    # Identify files whose stem contains non-ASCII (diacritics, umlauts)
    diacritic_files = [f for f in all_files if any(ord(c) > 127 for c in f.stem)]
    print(f"Total dashboards: {len(all_files)}")
    print(f"With diacritics in filename: {len(diacritic_files)}")

    moved = 0
    kept_orphaned = []  # diacritic file with no canonical replacement
    suspect_dupes = []  # file_stem → canonical_slug (different)

    for f in diacritic_files:
        center = extract_center(f)
        if not center:
            kept_orphaned.append((f.name, "no NETWORK.center extractable"))
            continue
        canonical_slug = slugify(center)
        canonical_html = DASHBOARD_DIR / f"{canonical_slug}_network.html"
        # Build companion paths to move together
        companions = [f]
        dd = f.with_name(f.stem + "_drilldown.json")
        if dd.exists():
            companions.append(dd)

        if canonical_html.exists() and canonical_html != f:
            # Stale: canonical version already on disk
            suspect_dupes.append((f.name, canonical_html.name))
            for c in companions:
                target = STALE_DIR / c.name
                if args.dry_run:
                    print(f"  [DRY] would move: {c.name} → tmp/stale_dashboards/")
                else:
                    shutil.move(str(c), str(target))
                    print(f"  moved: {c.name} → tmp/stale_dashboards/")
            moved += 1
        else:
            kept_orphaned.append((f.name, f"no canonical {canonical_slug}_network.html"))

    print()
    print(f"Stale → moved: {moved}")
    print(f"Orphaned (kept, no canonical exists): {len(kept_orphaned)}")
    if kept_orphaned[:10]:
        print("  Sample of orphaned:")
        for nm, reason in kept_orphaned[:10]:
            print(f"    {nm}: {reason}")

    if args.dry_run:
        print("\nDry-run only. Re-run without --dry-run to actually move.")


if __name__ == "__main__":
    main()
