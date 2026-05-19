#!/usr/bin/env python3
"""Extract aktive SDs aus staff/{club_tm_id}.json für BL1/BL2/BL3.

Staff entries have:
  - role: classified ("sporting_director", "executive", "head_coach", etc.)
  - section: TM grouping ("Vorstand", "Management", "Trainerstab", ...)

We pick the FIRST entry per club where role=="sporting_director", or fall
back to executive entries in Vorstand if no SD exists (e.g. Sportvorstand).

Output: data/sd_registry.json
  {
    "_meta": {extracted_at, season, total_clubs, total_sds, no_sd_clubs},
    "sds": [
      {tm_id, name, club_tm_id, club_name, league, role, section, tm_title}
    ]
  }
"""
import json
from pathlib import Path
from datetime import datetime, timezone

BASE = Path(__file__).parent.parent


def get_tm_title(tm_id: int, persons: dict) -> str:
    """Get actual TM job title from person profile (e.g. 'Sportdirektor')."""
    p = persons.get(str(tm_id), {})
    return p.get("role", "") or ""


def main():
    registry = json.load(open(BASE / "data/club_registry.json"))["clubs"]
    persons = json.load(open(BASE / "data/persons_master.json")).get("persons", {})
    season = "2025/2026"
    bl_clubs = [c for c in registry if any(
        l in ("BL1", "BL2", "BL3")
        for l in c.get("leagues", {}).get(season, [])
    )]

    sds = []
    no_sd = []
    for c in bl_clubs:
        staff_file = BASE / f"data/staff/{c['tm_id']}.json"
        if not staff_file.exists():
            no_sd.append(c["name"])
            continue
        s = json.load(open(staff_file))
        # Strategy: first sporting_director, else first executive in Vorstand/Management
        sd_entry = None
        for entry in s.get("staff", []):
            if entry.get("role") == "sporting_director":
                sd_entry = entry
                break
        if not sd_entry:
            # Fallback: executive in Vorstand/Management with Sport/Fußball-Title
            for entry in s.get("staff", []):
                if entry.get("role") != "executive":
                    continue
                if entry.get("section") not in ("Vorstand", "Management"):
                    continue
                tm_title = get_tm_title(entry.get("tm_id"), persons).lower()
                if any(kw in tm_title for kw in ["sport", "fußball", "football"]):
                    sd_entry = entry
                    break
        if not sd_entry:
            no_sd.append(c["name"])
            continue

        sds.append({
            "tm_id": sd_entry["tm_id"],
            "name": sd_entry["name"],
            "club_tm_id": c["tm_id"],
            "club_name": c["name"],
            "league": next((l for l in c.get("leagues", {}).get(season, [])
                            if l in ("BL1", "BL2", "BL3")), None),
            "role": sd_entry.get("role", ""),
            "section": sd_entry.get("section", ""),
            "tm_title": get_tm_title(sd_entry["tm_id"], persons),
        })

    out = BASE / "data/sd_registry.json"
    json.dump({
        "_meta": {
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "season": season,
            "total_clubs": len(bl_clubs),
            "total_sds": len(sds),
            "no_sd_clubs": no_sd,
        },
        "sds": sds,
    }, open(out, "w"), ensure_ascii=False, indent=2)
    print(f"✓ {len(sds)} SDs extracted to {out}")
    if no_sd:
        print(f"⚠ {len(no_sd)} clubs ohne SD: {no_sd[:8]}")


if __name__ == "__main__":
    main()
