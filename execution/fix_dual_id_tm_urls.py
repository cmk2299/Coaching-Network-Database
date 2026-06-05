#!/usr/bin/env python3
"""Fix TM-URL Dual-ID Mismatch (Pattern 6 from feedback_systemic_bugs_2026-05-19.md).

Pattern: persons_master.tm_url referenced the WRONG person at the same tm_id
because TM allows /profil/trainer/X and /profil/spieler/X to map to DIFFERENT people.
After scrape, profile.json has correct name + type but tm_url=None.
Master-merge falls back to stale persons_index.json (old spieler-side URL).

Fix: rewrite tm_url at the SOURCE (person_profiles/*.json) using TM-style ASCII slug
derived from profile.name + profile.type + tm_id.

Then run scrape_person_profiles.py --merge-only to rebake persons_master.

Persistent committed location: execution/fix_dual_id_tm_urls.py
"""
import json
import re
import unicodedata
from pathlib import Path

BASE = Path(__file__).parent.parent
PROFILES = BASE / "data/person_profiles"


def tm_slug(name: str) -> str:
    """TM-style ASCII slug: lowercase + strip diacritics + ß→s + non-alphanum→dash."""
    s = (name or "").lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("ß", "s").replace("ø", "o").replace("ł", "l").replace("đ", "d")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def main():
    files = sorted(PROFILES.glob("*.json"))
    print(f"Scanning {len(files)} profile files for tm_url patches...")
    patched = 0
    skipped = 0
    no_name = 0
    for pf in files:
        try:
            p = json.load(open(pf))
        except Exception:
            skipped += 1
            continue
        tm_id = pf.stem
        if not tm_id.isdigit():
            skipped += 1
            continue
        name = p.get("name", "")
        ptype = p.get("type", "")
        if not name or not ptype:
            no_name += 1
            continue
        slug = tm_slug(name)
        if not slug:
            no_name += 1
            continue
        correct_url = f"https://www.transfermarkt.de/{slug}/profil/{ptype}/{tm_id}"
        if p.get("tm_url") != correct_url:
            p["tm_url"] = correct_url
            json.dump(p, open(pf, "w"), ensure_ascii=False, indent=2)
            patched += 1
    print(f"\n✓ Patched: {patched}")
    print(f"  Skipped (no name/type): {no_name}")
    print(f"  Errored: {skipped}")
    print("\nNext: python3 execution/scrape_person_profiles.py --merge-only")


if __name__ == "__main__":
    main()
