#!/usr/bin/env python3
"""Extract aller NLZ-Trainer pro Tier aus Sub-Verein-Staff.

Output: data/nlz_trainer_registry.json
"""
import json
import re
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

BASE = Path(__file__).parent.parent
SEASON = "2025/2026"

TIER_PATTERNS = [
    ("U10-13", re.compile(r"\bU\s?(10|11|12|13)\b", re.I)),
    ("U14-17", re.compile(r"\bU\s?(14|15|16|17)\b", re.I)),
    ("U19",    re.compile(r"\bU\s?(18|19)\b", re.I)),
    ("U23",    re.compile(r"\b(U\s?(20|21|23)|II|Reserve|Amateure?|2\.\s*Mannschaft)\b", re.I)),
]
ROLE_KEEP = {"head_coach", "assistant_coach", "goalkeeper_coach", "co_trainer"}


def detect_tier(club_name: str):
    for tier, pat in TIER_PATTERNS:
        if pat.search(club_name):
            return tier
    return None


def main():
    reg = json.load(open(BASE / "data/club_registry.json"))["clubs"]
    nlz_clubs = [c for c in reg if c.get("parent_tm_id") or c.get("is_nlz")]
    print(f"Loaded {len(nlz_clubs)} NLZ sub-clubs from registry")

    trainers = []
    seen = set()
    tier_counter = defaultdict(int)
    for c in nlz_clubs:
        tier = detect_tier(c.get("name", ""))
        if not tier:
            continue
        path = BASE / f"data/staff/{c['tm_id']}.json"
        if not path.exists():
            continue
        try:
            sd = json.load(open(path))
        except Exception:
            continue
        for entry in sd.get("staff", []):
            tm_id = entry.get("tm_id")
            if not tm_id or tm_id in seen:
                continue
            section = (entry.get("section") or "").strip()
            role = (entry.get("role") or "").strip().lower()
            if section != "Trainerstab":
                continue
            # Accept any Trainerstab entry (broader than just head_coach since
            # NLZ teams often only list 1-2 staff per team).
            if role not in ROLE_KEEP and "trainer" not in role and "coach" not in role:
                continue
            seen.add(tm_id)
            # Look up parent club name
            parent_id = c.get("parent_tm_id")
            parent_name = c.get("parent_club") or c.get("parent_name") or ""
            if not parent_name and parent_id:
                for pc in reg:
                    if pc.get("tm_id") == parent_id:
                        parent_name = pc.get("name", "")
                        break
            trainers.append({
                "tm_id": int(tm_id),
                "name": entry.get("name", ""),
                "club_tm_id": c["tm_id"],
                "club_name": c.get("name", ""),
                "parent_club": parent_name,
                "parent_tm_id": parent_id,
                "tier": tier,
                "role": role,
                "section": section,
                "age_group_label": tier.replace("-", "–"),
            })
            tier_counter[tier] += 1

    out = BASE / "data/nlz_trainer_registry.json"
    json.dump({
        "_meta": {
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "season": SEASON,
            "total_nlz_clubs": len(nlz_clubs),
            "total_trainers": len(trainers),
            "tiers": dict(tier_counter),
        },
        "trainers": trainers,
    }, open(out, "w"), ensure_ascii=False, indent=2)
    print(f"✓ {len(trainers)} NLZ-Trainers extracted ({dict(tier_counter)})")


if __name__ == "__main__":
    main()
