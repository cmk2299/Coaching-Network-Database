#!/usr/bin/env python3
"""Sync SD-Registry → Decision-Makers JSON.

Stellt sicher dass alle Phase-1-SDs aus sd_registry.json auch in
decision_makers.json als Tier-1 erscheinen.
"""
import json
from pathlib import Path
from datetime import datetime, timezone

BASE = Path(__file__).parent.parent

def main():
    sds = json.load(open(BASE / "data/sd_registry.json"))["sds"]
    dms_file = BASE / "data/decision_makers.json"
    dms_data = json.load(open(dms_file))
    dms = dms_data["decision_makers"]

    existing_ids = {int(d["tm_id"]) for d in dms if d.get("tm_id")}
    added = 0
    for sd in sds:
        tid = int(sd.get("tm_id", 0) or 0)
        if not tid or tid in existing_ids:
            continue
        # Add as Tier 1 DM
        dms.append({
            "tm_id": tid,
            "name": sd["name"],
            "club_tm_id": sd.get("club_tm_id"),
            "club_name": sd.get("club_name", ""),
            "league": sd.get("league"),
            "role": sd.get("role", "Sportdirektor"),
            "section": "Verein",
            "tier": "1",
            "since_text": "",
            "contract_until_text": "",
            "_source": "sd_registry_sync",
        })
        added += 1

    # Update _meta + tiers
    dms_data["_meta"]["total_decision_makers"] = len(dms)
    dms_data["_meta"]["synced_at"] = datetime.now(timezone.utc).isoformat()
    dms_data["_meta"]["synced_from_sd_registry"] = added

    from collections import Counter
    dms_data["tiers"] = dict(Counter(d["tier"] for d in dms))

    json.dump(dms_data, open(dms_file, "w"), ensure_ascii=False, indent=2)
    print(f"Added {added} SDs from sd_registry -> decision_makers ({len(dms)} total)")
    print(f"  Tiers: {dms_data['tiers']}")

if __name__ == "__main__":
    main()
