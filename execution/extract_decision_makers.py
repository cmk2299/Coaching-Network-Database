#!/usr/bin/env python3
"""Extract alle Trainer-Hire-Decision-Maker pro BL-Club (Tier 1/2/3/NLZ).

Reads:  data/club_registry.json + data/staff/{club_tm_id}.json
Output: data/decision_makers.json
"""
import json
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

BASE = Path(__file__).parent.parent

# Title-based tier rules — use the TM job title from persons_master
# (staff entries only have classified role like "sporting_director", not raw title).
TIER_1_TITLE_HINTS = [
    "sportdirektor", "sportvorstand", "sportgeschäftsführer",
    "geschäftsführer sport", "geschäftsführer fußball",
    "sportlicher leiter", "technischer direktor",
    "director of football", "head of football", "head of sport",
]
TIER_2_TITLE_HINTS = [
    "sportkoordinator", "leiter sport", "sportlicher koordinator",
    "kaderplaner", "head of scouting", "leiter scouting",
    "leiter lizenzbereich", "leiter lizenzspielerabteilung",
    "chefscout",
]
# Tier 3 = governance/chairperson only — NOT every Vorstand-member.
TIER_3_TITLE_HINTS = [
    "vorstandsvorsitz", "vorsitzender des vorstands",
    "präsident", "ceo", "aufsichtsratsvorsitz",
]
NLZ_TITLE_HINTS = [
    "nlz-leiter", "nachwuchsleistungszentrum",
    "leiter nlz", "leiter nachwuchs",
    "leiter jugendabteilung", "head of academy", "akademiedirektor",
]


def classify_tier(staff_role: str, staff_section: str, tm_title: str):
    """Classify into Tier 1/2/3/NLZ.

    Strategy:
      1. NLZ via title hints
      2. Tier 1 via title hints (Sportdirektor/Sportvorstand/etc.)
      3. Tier 1 fallback via classified role == "sporting_director"
      4. Tier 1 fallback via classified role == "executive" + section ∈ Vorstand/Management
                                     + title contains sport/fußball/football
      5. Tier 2 via title hints
      6. Tier 3 via title hints (only chairperson-level)
    """
    title_lc = (tm_title or "").lower()
    role = (staff_role or "").lower()
    section = (staff_section or "").lower()

    SPORT_TOKENS = ["sport", "fußball", "football", "sportlich"]
    NEGATIVE_TOKENS = ["marketing", "finanzen", "kaufmännisch", "vertrieb",
                       "kommunikation", "merchandising", "personal", "presse",
                       "medien", "it", "digital"]

    if any(k in title_lc for k in NLZ_TITLE_HINTS):
        return "nlz"
    if any(k in title_lc for k in TIER_1_TITLE_HINTS):
        return "1"
    # Fallback: classified role "sporting_director" — but VALIDATE against title.
    # The staff scraper sometimes mis-tags commercial leaders as sporting_director.
    if role == "sporting_director":
        if title_lc and any(neg in title_lc for neg in NEGATIVE_TOKENS):
            return None  # actually a commercial role, not sport
        if title_lc and not any(t in title_lc for t in SPORT_TOKENS):
            return None  # title doesn't mention sport — likely misclassified
        return "1"
    # Fallback: "executive" with sport qualifier
    if role == "executive" and section in ("vorstand", "management"):
        if any(t in title_lc for t in SPORT_TOKENS) and not any(neg in title_lc for neg in NEGATIVE_TOKENS):
            return "1"
    if any(k in title_lc for k in TIER_2_TITLE_HINTS):
        return "2"
    if any(k in title_lc for k in TIER_3_TITLE_HINTS):
        return "3"
    return None


# Leagues to extract Decision-Maker from. DACH-Fokus (Stakeholder-Mandat):
# deutsche Profiligen + Österreich (ABL/AUT2) + Schweiz (SUI). Staff-Dateien für
# diese Ligen sind bereits gescraped (siehe data/staff/).
DM_LEAGUES = ("BL1", "BL2", "BL3", "ABL", "AUT2", "SUI")


def main():
    registry = json.load(open(BASE / "data/club_registry.json"))["clubs"]
    persons = json.load(open(BASE / "data/persons_master.json"))["persons"]
    season = "2025/2026"
    bl_clubs = [c for c in registry if any(
        l in DM_LEAGUES
        for l in c.get("leagues", {}).get(season, [])
    )]

    dms = []
    for c in bl_clubs:
        staff_file = BASE / f"data/staff/{c['tm_id']}.json"
        if not staff_file.exists():
            continue
        s = json.load(open(staff_file))
        seen_tm_ids = set()
        for entry in s.get("staff", []):
            tm_id = entry.get("tm_id")
            if not tm_id or tm_id in seen_tm_ids:
                continue
            person = persons.get(str(tm_id), {})
            # TM job title lives in career_history[0].role for current station,
            # or fall back to person.role (legacy) / position.
            tm_title = ""
            ch = person.get("career_history") or []
            if ch:
                for entry_ch in ch:
                    if str(entry_ch.get("date_to", "")).strip() in ("-", ""):
                        tm_title = entry_ch.get("role", "") or ""
                        break
                if not tm_title:
                    tm_title = ch[0].get("role", "") or ""
            if not tm_title:
                tm_title = person.get("role") or person.get("position") or ""
            tier = classify_tier(entry.get("role", ""), entry.get("section", ""), tm_title)
            if not tier:
                continue
            seen_tm_ids.add(tm_id)
            dms.append({
                "tm_id": tm_id,
                "name": entry.get("name", ""),
                "club_tm_id": c["tm_id"],
                "club_name": c["name"],
                "league": next((l for l in c.get("leagues", {}).get(season, [])
                                if l in DM_LEAGUES), None),
                "role": entry.get("role", ""),
                "section": entry.get("section", ""),
                "tm_title": tm_title,
                "tier": tier,
                "since_text": entry.get("since_text") or entry.get("appointed", ""),
                "contract_until_text": entry.get("contract_until_text") or "",
            })

    tier_counts = defaultdict(int)
    for d in dms:
        tier_counts[d["tier"]] += 1

    out = BASE / "data/decision_makers.json"
    json.dump({
        "_meta": {
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "season": season,
            "total_clubs": len(bl_clubs),
            "total_decision_makers": len(dms),
        },
        "tiers": dict(tier_counts),
        "decision_makers": dms,
    }, open(out, "w"), ensure_ascii=False, indent=2)
    print(f"✓ {len(dms)} Decision-Makers extracted ({dict(tier_counts)})")


if __name__ == "__main__":
    main()
