#!/usr/bin/env python3
"""
Fix Name Mismatches — Comprehensive repair script

Fixes two categories of mismatches:
1. Lehrgang (coaching_licenses.json): wrong tm_ids for manually entered names
2. Network-level: contacts in network JSONs with tm_ids pointing to wrong person

Strategy:
- For lehrgang entries with confidence < 1.0 and clearly wrong matches: set tm_id to null
- For specific cases where correct tm_id was found: update to correct value
- For near-matches that ARE the same person (abbreviations, accents): keep as-is
- For network contacts: cross-reference against persons_master canonical names,
  fix or remove bad _tm_id values that would create broken cross-links

Usage:
    python fix_name_mismatches.py --dry-run     # Show what would change
    python fix_name_mismatches.py               # Apply fixes
"""

import json
import sys
from pathlib import Path
from difflib import SequenceMatcher

BASE = Path(__file__).parent.parent
DATA = BASE / "data"
NETWORKS_DIR = DATA / "networks"
COACHING_LICENSES = DATA / "coaching_licenses.json"
PERSONS_MASTER = DATA / "persons_master.json"

# ── Known correct mappings ─────────────────────────────────────────────
# These are cases where we found the correct tm_id in persons_master
LEHRGANG_CORRECTIONS = {
    # (cohort_num, name) → correct tm_id
    ("61", "Daniel Wimmer"): 1040498,      # Was 27329 (Michael Wimmer)
}

# These are cases where the name spelling differs but it IS the same person
LEHRGANG_SAME_PERSON = {
    ("67", "Michel Kniat"),       # = Mitch Kniat (tm_id 35168), spelling variant
    ("65", "Christian Fiel"),     # = Cristian Fiél (tm_id 1222), accent variant
    ("66", "Alexander Reifschneider"),  # = Alex Reifschneider (tm_id 71209), abbreviation
    ("61", "Christian Wimmer"),   # = Dr. Christian Wimmer (tm_id 36423), title
    ("65", "Mike Sergio Terranova"),  # = Sergio Terranova — same person, middle name
}

# These entries have wrong tm_ids and we couldn't find the correct one → set to null
# (they coach at clubs outside our scraped leagues)
LEHRGANG_SET_NULL = set()  # Will be populated by scanning confidence < 1.0 entries


def load_persons_master():
    """Load canonical names from persons_master."""
    pm = json.load(open(PERSONS_MASTER))
    return pm["persons"]


def build_name_to_id_index(persons):
    """Build a reverse index: lowercase name → tm_id for fast lookup."""
    idx = {}
    for tid, p in persons.items():
        name = p.get("name", "").strip().lower()
        if name:
            # First match wins (there may be dupes, but for correction this is fine)
            if name not in idx:
                idx[name] = int(tid)
    return idx


def load_dashboard_index():
    """Get set of tm_ids that have their own dashboard (network files are named {tm_id}.json)."""
    dashboard_ids = set()
    for nf in NETWORKS_DIR.glob("*.json"):
        stem = nf.stem
        if stem.isdigit():
            dashboard_ids.add(stem)
    return dashboard_ids


def fix_coaching_licenses(dry_run=False):
    """Fix wrong tm_ids in coaching_licenses.json."""
    licenses = json.load(open(COACHING_LICENSES))
    persons = load_persons_master()

    fixes = []
    cohorts = licenses["courses"][0]["cohorts"]

    for cohort_num, cohort in cohorts.items():
        for grad in cohort["graduates"]:
            name = grad["name"]
            tm_id = grad.get("tm_id")
            matched_name = grad.get("matched_name")
            confidence = grad.get("confidence", 0)

            if tm_id is None:
                continue  # Already unmatched

            key = (cohort_num, name)

            # Case 1: Known correct mapping
            if key in LEHRGANG_CORRECTIONS:
                new_id = LEHRGANG_CORRECTIONS[key]
                new_name = persons.get(str(new_id), {}).get("name", "???")
                fixes.append({
                    "type": "CORRECT_ID",
                    "cohort": cohort_num,
                    "name": name,
                    "old_tm_id": tm_id,
                    "old_matched": matched_name,
                    "new_tm_id": new_id,
                    "new_matched": new_name,
                })
                if not dry_run:
                    grad["tm_id"] = new_id
                    grad["matched_name"] = new_name
                    grad["confidence"] = 1.0
                continue

            # Case 2: Same person (abbreviation/accent)
            if key in LEHRGANG_SAME_PERSON:
                # Keep as-is, just update confidence to 1.0
                fixes.append({
                    "type": "SAME_PERSON",
                    "cohort": cohort_num,
                    "name": name,
                    "tm_id": tm_id,
                    "matched_name": matched_name,
                })
                if not dry_run:
                    grad["confidence"] = 1.0
                continue

            # Case 3: Confidence < 1.0 and name mismatch → wrong person
            if confidence < 1.0 and matched_name and matched_name != name:
                # Verify it's truly wrong by checking similarity
                sim = SequenceMatcher(None, name.lower(), matched_name.lower()).ratio()
                if sim < 0.95:  # Clearly different person
                    fixes.append({
                        "type": "SET_NULL",
                        "cohort": cohort_num,
                        "name": name,
                        "old_tm_id": tm_id,
                        "old_matched": matched_name,
                        "confidence": confidence,
                        "similarity": round(sim, 3),
                    })
                    if not dry_run:
                        grad["tm_id"] = None
                        grad["matched_name"] = None
                        grad["confidence"] = 0.0

    # Update match stats
    if not dry_run:
        for cohort_num, cohort in cohorts.items():
            matched = sum(1 for g in cohort["graduates"] if g.get("tm_id"))
            cohort["matched"] = matched

        total_matched = sum(c["matched"] for c in cohorts.values())
        total_grads = sum(c["total"] for c in cohorts.values())
        licenses["courses"][0]["stats"]["total_matched"] = total_matched
        licenses["courses"][0]["stats"]["match_rate"] = round(total_matched / total_grads, 3) if total_grads else 0

        with open(COACHING_LICENSES, "w") as f:
            json.dump(licenses, f, indent=2, ensure_ascii=False)

    return fixes


def fix_network_mismatches(dry_run=False):
    """Fix wrong _tm_id values in network JSON contacts."""
    persons = load_persons_master()
    name_index = build_name_to_id_index(persons)
    dashboard_ids = load_dashboard_index()

    # Pre-build canonical name lookup: tm_id_str → canonical_name
    canonical_names = {}
    for tid, p in persons.items():
        canonical_names[tid] = p.get("name", "")

    all_fixes = []
    networks_modified = set()

    for nf in sorted(NETWORKS_DIR.glob("*.json")):
        net = json.load(open(nf))
        contacts = net.get("contacts", [])
        modified = False

        for contact in contacts:
            tm_id = contact.get("_tm_id")
            contact_name = contact.get("name", "")

            if not tm_id:
                continue

            tm_id_str = str(tm_id)
            canonical = canonical_names.get(tm_id_str, "")

            if not canonical:
                continue

            # Check if name matches
            sim = SequenceMatcher(None, contact_name.lower(), canonical.lower()).ratio()

            if sim >= 0.85:
                continue  # Good enough match

            # Mismatch found — is this contact linked to a dashboard?
            has_dashboard = tm_id_str in dashboard_ids
            severity = "CRITICAL" if has_dashboard else "minor"

            # Fast lookup for correct tm_id
            correct_id = name_index.get(contact_name.lower())

            fix_info = {
                "network": nf.stem,
                "contact_name": contact_name,
                "wrong_tm_id": tm_id,
                "canonical_at_id": canonical,
                "similarity": round(sim, 3),
                "severity": severity,
                "correct_id_found": correct_id,
                "category": contact.get("category", "?"),
            }
            all_fixes.append(fix_info)

            if not dry_run:
                if correct_id:
                    contact["_tm_id"] = correct_id
                    if contact.get("tm_url"):
                        contact["tm_url"] = f"https://www.transfermarkt.de/-/profil/spieler/{correct_id}"
                else:
                    contact["_tm_id"] = None
                    if contact.get("tm_url"):
                        contact["tm_url"] = None
                modified = True

        if modified and not dry_run:
            with open(nf, "w") as f:
                json.dump(net, f, indent=2, ensure_ascii=False)
            networks_modified.add(nf.stem)

    return all_fixes, networks_modified


def main():
    dry_run = "--dry-run" in sys.argv
    mode = "DRY RUN" if dry_run else "APPLYING FIXES"

    print(f"{'='*60}")
    print(f"  Name Mismatch Fixer — {mode}")
    print(f"{'='*60}\n")

    # ── Step 1: Fix coaching_licenses.json ──────────────────────────────
    print("Step 1: Fixing coaching_licenses.json")
    print("-" * 40)
    lic_fixes = fix_coaching_licenses(dry_run)

    for f in lic_fixes:
        if f["type"] == "CORRECT_ID":
            print(f"  ✓ LG {f['cohort']}: {f['name']} — tm_id {f['old_tm_id']}→{f['new_tm_id']} ({f['old_matched']}→{f['new_matched']})")
        elif f["type"] == "SAME_PERSON":
            print(f"  ≈ LG {f['cohort']}: {f['name']} = {f['matched_name']} (same person, keeping)")
        elif f["type"] == "SET_NULL":
            print(f"  ✗ LG {f['cohort']}: {f['name']} — tm_id {f['old_tm_id']} was {f['old_matched']} (sim={f['similarity']}) → null")

    print(f"\n  Total lehrgang fixes: {len(lic_fixes)} ({sum(1 for f in lic_fixes if f['type']=='SET_NULL')} nulled, "
          f"{sum(1 for f in lic_fixes if f['type']=='CORRECT_ID')} corrected, "
          f"{sum(1 for f in lic_fixes if f['type']=='SAME_PERSON')} confirmed)\n")

    # ── Step 2: Fix network JSONs ──────────────────────────────────────
    print("Step 2: Fixing network JSON contacts")
    print("-" * 40)
    net_fixes, modified_networks = fix_network_mismatches(dry_run)

    critical = [f for f in net_fixes if f["severity"] == "CRITICAL"]
    minor = [f for f in net_fixes if f["severity"] == "minor"]

    if critical:
        print(f"\n  CRITICAL fixes ({len(critical)}):")
        for f in critical:
            action = f"→ {f['correct_id_found']}" if f["correct_id_found"] else "→ null"
            print(f"    [{f['network']}] {f['contact_name']} (was {f['canonical_at_id']}, tm_id={f['wrong_tm_id']}) {action}")

    print(f"\n  Total network fixes: {len(net_fixes)} ({len(critical)} critical, {len(minor)} minor)")
    print(f"  Networks modified: {len(modified_networks)}")

    if net_fixes:
        # Show category breakdown
        from collections import Counter
        cats = Counter(f["category"] for f in net_fixes)
        print(f"  By category: {dict(cats)}")

        fixed_vs_nulled = sum(1 for f in net_fixes if f["correct_id_found"]), sum(1 for f in net_fixes if not f["correct_id_found"])
        print(f"  Corrected: {fixed_vs_nulled[0]}, Nulled: {fixed_vs_nulled[1]}")

    print(f"\n{'='*60}")
    if dry_run:
        print("  DRY RUN complete. Re-run without --dry-run to apply.")
    else:
        print("  All fixes applied.")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
