#!/usr/bin/env python3
"""Phase A2: Migrate persons_master to type-aware key schema.

Old schema: persons_master["persons"]["104"] = { ...one person... }
            (last scrape wins, Frankenstein profiles)

New schema: persons_master["persons"]["spieler_104"]  = { Bobic ... }
            persons_master["persons"]["trainer_104"]  = { Junghans ... }
            persons_master["persons"]["104"]          = LegacyAlias → newer-of-two
                                                         (backward compat for non-aware readers)

Sources of truth (priority order):
  1. data/person_profiles/{type}_{id}.json  (if exists, NEW format)
  2. data/person_profiles/{id}.json         (LEGACY format, type read from JSON .type field)
  3. tmp/cache/profiles/{type}_{id}.html    (re-parse if profile JSON missing)

Behaviour:
  - All single-namespace IDs migrate "<id>" → "<type>_<id>" and keep "<id>" alias.
  - Dual-namespace IDs get BOTH "<type>_<id>" entries + "<id>" alias points to
    whichever was last modified (newer of two).
  - Person-profile JSONs are renamed: `<id>.json` → `<type>_<id>.json` (old kept as backup).

Run:
  python3 execution/migrate_persons_master.py --dry-run     # preview only
  python3 execution/migrate_persons_master.py --execute     # do it
"""
import argparse
import json
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent.parent
MASTER = BASE / "data" / "persons_master.json"
PROFILES = BASE / "data" / "person_profiles"
COLLISIONS = BASE / "data" / "namespace_collisions.json"
BACKUP = BASE / "data" / "persons_master.before-namespace-fix.json"


def load_profile_json(tm_id: int):
    """Return list of (type, profile_dict) pairs for this tm_id from disk."""
    out = []
    # New format
    for kind in ("spieler", "trainer"):
        p = PROFILES / f"{kind}_{tm_id}.json"
        if p.exists():
            try:
                data = json.load(open(p))
                out.append((kind, data, p))
            except Exception:
                pass
    # Legacy format (only if no new-format files exist)
    if not out:
        p = PROFILES / f"{tm_id}.json"
        if p.exists():
            try:
                data = json.load(open(p))
                kind = data.get("type") or "unknown"
                if kind in ("spieler", "trainer"):
                    out.append((kind, data, p))
            except Exception:
                pass
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--no-rename", action="store_true",
                    help="Skip renaming person_profiles/{id}.json files")
    args = ap.parse_args()

    if not args.dry_run and not args.execute:
        sys.exit("Specify --dry-run or --execute")

    if not MASTER.exists():
        sys.exit(f"ERR: {MASTER} not found")

    if not COLLISIONS.exists():
        sys.exit(f"ERR: {COLLISIONS} not found — run detect_namespace_collisions.py first")

    print("Loading master…")
    master_doc = json.load(open(MASTER))
    persons = master_doc.get("persons", {})
    print(f"  {len(persons):,} entries")

    print("Loading collisions…")
    coll_doc = json.load(open(COLLISIONS))
    dual_namespace_ids = {r["tm_id"] for r in coll_doc.get("dual_namespace", [])}
    print(f"  {len(dual_namespace_ids):,} dual-namespace IDs to handle")

    # Backup
    if args.execute and not BACKUP.exists():
        print(f"\nBacking up master → {BACKUP}")
        shutil.copy(MASTER, BACKUP)

    # ── Walk all entries ───────────────────────────────────────────────
    new_persons: dict[str, dict] = {}
    legacy_aliases: dict[str, str] = {}  # old_key → new_key (for "<id>" → "<type>_<id>")
    stats = defaultdict(int)

    for key, entry in persons.items():
        if not key.isdigit():
            new_persons[key] = entry
            stats["non_numeric"] += 1
            continue

        tm_id = int(key)
        is_dual = tm_id in dual_namespace_ids
        profiles_on_disk = load_profile_json(tm_id)

        if is_dual:
            stats["dual"] += 1
            # Want BOTH typed entries. Pull from on-disk profiles if available;
            # fall back to existing master entry for whichever type matches.
            disk_by_type = {t: prof for t, prof, _ in profiles_on_disk}
            stored_type = entry.get("type")
            for kind in ("spieler", "trainer"):
                target_key = f"{kind}_{tm_id}"
                if kind in disk_by_type:
                    new_persons[target_key] = disk_by_type[kind]
                    stats[f"dual_from_disk_{kind}"] += 1
                elif stored_type == kind:
                    new_persons[target_key] = entry
                    stats[f"dual_from_master_{kind}"] += 1
                else:
                    # neither disk nor master has this type — leave a stub
                    new_persons[target_key] = {
                        "tm_id": tm_id,
                        "type": kind,
                        "name": None,
                        "_stub": "needs_rescrape",
                    }
                    stats[f"dual_stub_{kind}"] += 1
            # Legacy alias: point "<id>" to whichever new key was most recently
            # updated. Heuristic: prefer the type stored in current master.
            legacy_aliases[key] = f"{stored_type}_{tm_id}" if stored_type else f"trainer_{tm_id}"
        else:
            stats["single"] += 1
            # Single namespace: migrate "<id>" → "<type>_<id>"
            kind = entry.get("type")
            if kind in ("spieler", "trainer"):
                target_key = f"{kind}_{tm_id}"
                new_persons[target_key] = entry
                legacy_aliases[key] = target_key
                stats[f"single_{kind}"] += 1
            else:
                # No type info → keep as-is under numeric key (will be reader-fallback)
                new_persons[key] = entry
                stats["single_no_type"] += 1

    print("\nMigration stats:")
    for k, v in sorted(stats.items()):
        print(f"  {k}: {v:,}")

    # Apply legacy aliases
    for old_key, target_key in legacy_aliases.items():
        if target_key in new_persons and old_key not in new_persons:
            new_persons[old_key] = new_persons[target_key]

    if args.dry_run:
        # Sample
        sample = list(legacy_aliases.items())[:8]
        print(f"\nDRY-RUN — sample alias mappings:")
        for old, new in sample:
            print(f"  {old:>10} → {new}")
        print(f"\nTotal new keys (with legacy aliases): {len(new_persons):,}")
        print("\nRe-run with --execute to apply.")
        return

    # Update master + meta
    master_doc["persons"] = new_persons
    meta = master_doc.get("meta", {})
    meta["namespace_migration_at"] = datetime.now().isoformat()
    meta["total_persons"] = len(new_persons)
    meta["dual_namespace_handled"] = len(dual_namespace_ids)
    master_doc["meta"] = meta

    print(f"\nWriting new master ({len(new_persons):,} entries)…")
    with open(MASTER, "w") as f:
        json.dump(master_doc, f, ensure_ascii=False, indent=2)
    print(f"✓ {MASTER}")

    # Rename profile files (optional)
    if args.no_rename:
        print("\nSkipping profile-file renames (--no-rename).")
    else:
        print("\nRenaming person_profiles/{id}.json → {type}_{id}.json…")
        rename_count = 0
        skip_count = 0
        for p in PROFILES.glob("[0-9]*.json"):
            tm_id_str = p.stem
            if not tm_id_str.isdigit():
                continue
            try:
                data = json.load(open(p))
            except Exception:
                skip_count += 1
                continue
            kind = data.get("type")
            if kind not in ("spieler", "trainer"):
                skip_count += 1
                continue
            target = PROFILES / f"{kind}_{tm_id_str}.json"
            if target.exists():
                skip_count += 1
                continue
            try:
                p.rename(target)
                rename_count += 1
            except Exception as e:
                print(f"  ✗ rename failed for {p.name}: {e}")
                skip_count += 1
        print(f"  Renamed: {rename_count:,}")
        print(f"  Skipped: {skip_count:,}")

    print("\n✓ Migration complete.")
    print(f"  Backup: {BACKUP}")
    print(f"  Master: {MASTER} ({MASTER.stat().st_size / 1_048_576:.1f} MB)")
    print("\nNext steps: Phase A3 (reader updates) + A4 (rescrape) + A5 (validate)")


if __name__ == "__main__":
    main()
