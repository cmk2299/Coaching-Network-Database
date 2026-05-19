#!/usr/bin/env python3
"""
Post-patch script: re-classify staff members whose TM role label contains
'Interimstrainer' / 'Interimstrainerin' / 'Interimscheftrainer'.

Root cause: _detect_specific_role() in scrape_squads.py used
    re.search(r'\btrainer\b', t)
which requires a word boundary before 'trainer' — so 'Interimstrainer'
(no boundary between 'interims' and 'trainer') falls through to
'other_staff'. Affects recently appointed interim head coaches.

This script re-parses cached HTML for staff pages and patches any affected
staff/*.json file in-place. It is idempotent.

Usage:
    python3 execution/patch_interims_classifier.py          # dry-run + report
    python3 execution/patch_interims_classifier.py --apply  # write changes
"""

import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

BASE = Path(__file__).parent.parent
STAFF_DIR = BASE / "data" / "staff"
CACHE_DIR = BASE / "tmp" / "cache" / "squads"


def interims_tm_ids(html_path: Path) -> set[int]:
    """Return tm_ids of all staff members whose inline-table label is
    Interimstrainer / Interimstrainerin / Interimscheftrainer."""
    html = html_path.read_text(errors="ignore")
    soup = BeautifulSoup(html, "html.parser")
    interim_ids: set[int] = set()

    for table in soup.find_all("table", class_="inline-table"):
        text = table.get_text(" ", strip=True).lower()
        if "interimstrainer" not in text and "interimscheftrainer" not in text:
            continue
        # find the <a> with id=... and href containing /trainer/ or /profil/
        for a in table.find_all("a", id=True):
            try:
                interim_ids.add(int(a["id"]))
            except (ValueError, KeyError):
                continue
    return interim_ids


def patch_file(path: Path, apply: bool = False) -> list[tuple[str, int, str]]:
    """Returns list of (name, tm_id, old_role) changes made. If apply=False,
    simply reports would-be changes without writing."""
    try:
        data = json.loads(path.read_text())
    except Exception:
        return []

    club_tm_id = data.get("club_tm_id")
    cache_path = CACHE_DIR / f"staff_{club_tm_id}.html"
    if not cache_path.exists():
        return []

    interim_ids = interims_tm_ids(cache_path)
    if not interim_ids:
        return []

    changes: list[tuple[str, int, str]] = []
    for member in data.get("staff", []):
        if member.get("tm_id") not in interim_ids:
            continue
        if member.get("role") == "head_coach":
            continue  # already correct
        changes.append((member.get("name", ""), member.get("tm_id"), member.get("role", "")))
        member["role"] = "head_coach"

    if changes and apply:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return changes


def main():
    apply = "--apply" in sys.argv
    files = sorted(STAFF_DIR.glob("*.json"))
    total_changes = 0
    for f in files:
        changes = patch_file(f, apply=apply)
        if not changes:
            continue
        try:
            club_name = json.loads(f.read_text()).get("club_name", f.stem)
        except Exception:
            club_name = f.stem
        for name, tm_id, old_role in changes:
            print(f"  [{club_name}] {name} (tm_id {tm_id}): {old_role} → head_coach")
            total_changes += 1

    print()
    if apply:
        print(f"APPLIED {total_changes} classifier fix(es) across {len(files)} staff files.")
    else:
        print(f"DRY-RUN: would apply {total_changes} fix(es). Re-run with --apply to write.")


if __name__ == "__main__":
    main()
