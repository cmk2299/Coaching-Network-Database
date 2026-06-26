#!/usr/bin/env python3
"""
Scrape and compile DFB Fußball-Lehrer cohort data.
Sources: DFB.de, Kicker, ran.de, regional FA sites, web search results.

Architecture: Layer 3 (Execution)

Usage:
  python scrape_coaching_licenses.py              # Build coaching_licenses.json
  python scrape_coaching_licenses.py --match-only # Only re-run tm_id matching
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from difflib import SequenceMatcher

# ── Config ──────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_FILE = DATA_DIR / "coaching_licenses.json"

# ── Known cohort data (manually compiled from web search) ──────────
# Sources: DFB.de, Kicker, ran.de, t-online, RevierSport, StN, media-sportservice
KNOWN_COHORTS = {
    "dfb_fussball_lehrer": {
        "course_name": "DFB Fußball-Lehrer-Lehrgang",
        "provider": "DFB",
        "location": "Hennes-Weisweiler-Akademie, Hennef (bis 2021) / DFB-Akademie, Frankfurt (ab 2022)",
        "license_level": "UEFA-Pro-Lizenz",
        "cohorts": {
            "61": {
                "year": "2014/2015",
                "graduates": [
                    "Steffen Baumgart", "Tom Cichon", "Frank Fahrenhorst",
                    "Torsten Frings", "Günther Gorenzel-Simonitsch", "Vahid Hashemian",
                    "Sascha Hildmann", "Benjamin Hoffmann", "Marcus Jahn",
                    "Florian Kohfeldt", "Martin Lanzinger", "Jana Menzel",
                    "Daniel Meyer", "Rüdiger Rehm", "Thomas Reis",
                    "Marco Rose", "Boris Schommers", "Thomas Seeliger",
                    "Holger Seitz", "Erdinc Sözer", "Christian Wimmer",
                    "Daniel Wimmer", "Steffen Winter", "Engin Yanova",
                ],
                "best": "Florian Kohfeldt",
                "source": "kicker.de, stuttgarter-nachrichten.de",
            },
            "62": {
                "year": "2015/2016",
                "graduates": [
                    "Marco Antwerpen", "Holger Bachthaler", "David Bergner",
                    "Alexander Blessin", "Hannes Drews", "Katja Greulich",
                    "Inka Grings", "Jan Hoepner", "Kenan Kocak",
                    "Daniel Kraus", "Pellegrino Matarazzo", "Julian Nagelsmann",
                    "Alexander Nouri", "Darius Scholtysik", "Martin Schweizer",
                    "Roger Stilz", "Jeff Strasser", "Domenico Tedesco",
                    "Daniel Thioune", "Patrick Weiser", "Nico Willig",
                    "Oliver Zapel", "Mark Zimmermann",
                ],
                "best": "Domenico Tedesco",
                "source": "sport1.de, badfv.de, nofv-online.de",
            },
            "63": {
                "year": "2016/2017",
                "graduates": [
                    # Partial — need more research for full list
                    # Known from various sources:
                    "Stefan Leitl",
                    # 63. Lehrgang info is sparse in search results
                ],
                "best": None,
                "source": "dfb.de (148012) — article no longer available",
                "incomplete": True,
            },
            "64": {
                "year": "2017/2018",
                "graduates": [
                    "Francisco Copado", "Markus Daun", "Antonio Di Salvo",
                    "Alexander Frankenberger", "Bartosch Gaul", "Dimitrios Grammozis",
                    "Matthias Heidrich", "Oliver Heine", "Arne Janssen",
                    "Florian Junge", "Robert Klauß", "Thomas Kleine",
                    "Oliver Krause", "Markus Krösche", "Lukas Kwasniok",
                    "Christoph Liebich", "Christian Neidhart", "Ersan Parlatan",
                    "Mike Sadlo", "Timo Schultz", "Daniel Steuernagel",
                    "Ronny Thielemann", "Timo Wenzel", "Marco Wildersinn",
                    "Rainer Zietsch",
                ],
                "best": "Robert Klauß",
                "source": "reviersport.de, media-sportservice.de, dfb.de",
            },
            "65": {
                "year": "2018/2019",
                "graduates": [
                    "Arne Barez", "Daniel Bierofka", "Sebastian Dreier",
                    "Christian Fiel", "Sebastian Geppert", "Ovid Hajou",
                    "Patrick Helmes", "Andreas Hinkel", "Patrick Irmler",
                    "Alexander Kiene", "Oskar Kretzinger", "Georg Martin Leopold",
                    "Theresa Merk", "Patrick Mölzl", "Elard Ostermann",
                    "Roberto Pätzold", "André Pawlak", "Marcel Rapp",
                    "Pit Reimers", "Sven Schuchardt", "Uwe Speidel",
                    "Mike Sergio Terranova", "Marco Vorbeck", "Markus Zschiesche",
                ],
                "best": None,  # DFB stopped naming best graduate
                "source": "t-online.de, fussballdaten.de, kicker.de",
            },
            "66": {
                "year": "2019/2020",
                "graduates": [
                    "Sebastian Bönig", "Tim Borowski", "Heiko Butscher",
                    "Steven Cherundolo", "Onur Cinel", "Lennart Claussen",
                    "Christian Eichner", "Alexander Ende", "Rajko Fijalek",
                    "Conny Frank Fritsch", "Martin Heck", "Matthias Jaissle",
                    "Jens Langeneke", "Enrico Maaßen", "Christoph Metzelder",
                    "Christian Rahn", "Alexander Reifschneider", "Dino Toppmöller",
                    "Thomas Voggenreiter", "Engin Vural", "Ole Werner",
                    "Thomas Wörle", "Imke Wübbenhorst", "Rüdiger Ziehl",
                    "Jan Zimmermann",
                ],
                "best": None,
                "source": "kicker.de, murrhardter-zeitung.de",
            },
            "67": {
                "year": "2020/2021",
                "graduates": [
                    "Hanno Balitsch", "Jens Bauer", "Guerino Capretti",
                    "Sabrina Eckhoff", "Florian Fulland", "Danny Galm",
                    "Miroslav Klose", "Michel Kniat", "Marco Konrad",
                    "Kim Kulig", "Dennis Lamby", "Stephan Lerch",
                    "Andreas Neuendorf", "Robin Peter", "Carsten Rump",
                    "Daniel Scherning", "Manuel Schulitz", "Danny Schwarz",
                    "Tobias Schweinsteiger", "Jochen Seitz", "David Siebers",
                    "Farat Toku", "Lars Voßler", "Michael Wimmer",
                    "Eren Yilmaz",
                ],
                "best": None,
                "source": "dfb.de, ran.de, t-online.de, bdfl.de",
            },
            "68": {
                "year": "2022/2023",
                "graduates": [
                    "Nils Döring", "Benjamin Duda", "Marie-Louise Eta",
                    "Marc Hensel", "Kai Herdling", "Fabian Hürzeler",
                    "Matthias Kaltenbach", "André Meyer", "Michael Patz",
                    "Tobias Rau", "Michael Schiele", "Janos Radoki",
                    "Sebastian Schindzielorz", "Marcel Schuhen", "Vanessa Wiedemann",
                    "Thorsten Zaunmüller",
                ],
                "best": None,
                "source": "dfb.de (250333)",
                "note": "First cohort as 'Pro Lizenz' instead of 'Fußball-Lehrer'",
            },
            "69": {
                "year": "2023/2024",
                "graduates": [
                    # From DFB article 259164
                    "Julian Schuster",
                    # Need to fetch remaining names from the DFB page
                ],
                "best": None,
                "source": "dfb.de (259164)",
                "incomplete": True,
            },
        },
    }
}


def load_persons_master():
    """Load persons_master and build a name→tm_id index for fast matching."""
    master_path = DATA_DIR / "persons_master.json"
    if not master_path.exists():
        print("  ✗ persons_master.json not found")
        return {}, {}
    with open(master_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    persons = data.get("persons", data)

    # Build name index: normalized_name → [(tm_id, original_name, role)]
    name_index = {}
    for tm_id, p in persons.items():
        name = p.get("name", "")
        if not name:
            continue
        norm = normalize_name(name)
        role = ""
        # Try to get role from career or type
        if p.get("type") == "trainer" or "trainer" in str(p.get("tm_url", "")):
            role = "trainer"
        entry = (int(tm_id), name, role)
        name_index.setdefault(norm, []).append(entry)
        # Also index by last name only for fuzzy matching
        parts = norm.split()
        if len(parts) >= 2:
            name_index.setdefault(parts[-1], []).append(entry)

    return persons, name_index


def normalize_name(name: str) -> str:
    """Normalize name for fuzzy matching."""
    name = name.strip().lower()
    # Remove common prefixes/suffixes
    name = re.sub(r'\s+', ' ', name)
    # Normalize umlauts
    replacements = {
        'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss',
        'é': 'e', 'è': 'e', 'ê': 'e', 'á': 'a', 'à': 'a',
        'ó': 'o', 'ò': 'o', 'ú': 'u', 'ù': 'u', 'í': 'i',
        'ì': 'i', 'ç': 'c', 'ñ': 'n', 'ø': 'o', 'å': 'a',
    }
    for k, v in replacements.items():
        name = name.replace(k, v)
    return name


def match_name_to_tm_id(name: str, name_index: dict) -> dict:
    """
    Match a graduate name to a tm_id using the pre-built name index.
    Returns: {"tm_id": int, "confidence": float, "matched_name": str}
    """
    norm_name = normalize_name(name)
    name_parts = norm_name.split()

    # 1. Exact match
    if norm_name in name_index:
        candidates = name_index[norm_name]
        # Prefer trainers
        trainers = [c for c in candidates if c[2] == "trainer"]
        pick = trainers[0] if trainers else candidates[0]
        return {"tm_id": pick[0], "confidence": 1.0, "matched_name": pick[1]}

    # 2. Last-name lookup + first-name fuzzy
    if len(name_parts) >= 2:
        last_name = name_parts[-1]
        first_name = " ".join(name_parts[:-1])
        if last_name in name_index:
            candidates = name_index[last_name]
            best = None
            best_score = 0.0
            for tm_id, orig_name, role in candidates:
                orig_norm = normalize_name(orig_name)
                score = SequenceMatcher(None, norm_name, orig_norm).ratio()
                if role == "trainer":
                    score += 0.05
                if score > best_score:
                    best_score = score
                    best = (tm_id, orig_name)
            if best and best_score >= 0.75:
                return {"tm_id": best[0], "confidence": round(min(best_score, 1.0), 3), "matched_name": best[1]}

    # 3. No match
    return {"tm_id": None, "confidence": 0.0, "matched_name": None}


def build_coaching_licenses():
    """Build the coaching_licenses.json file."""
    print("Building coaching_licenses.json...")
    print("  Loading persons_master...")
    persons, name_index = load_persons_master()
    print(f"  {len(persons)} persons loaded, {len(name_index)} name index entries")

    output = {
        "meta": {
            "generated_at": datetime.now().isoformat(),
            "description": "DFB Fußball-Lehrer / Pro Lizenz cohort data with tm_id matching",
            "sources": [
                "dfb.de", "kicker.de", "sport1.de", "ran.de",
                "t-online.de", "reviersport.de", "media-sportservice.de",
                "stuttgarter-nachrichten.de", "badfv.de", "nofv-online.de",
            ],
        },
        "courses": [],
    }

    for course_id, course_data in KNOWN_COHORTS.items():
        course_entry = {
            "course_id": course_id,
            "name": course_data["course_name"],
            "provider": course_data["provider"],
            "location": course_data["location"],
            "license_level": course_data["license_level"],
            "cohorts": {},
        }

        total_matched = 0
        total_graduates = 0

        for cohort_num, cohort_data in course_data["cohorts"].items():
            graduates_with_ids = []
            for grad_name in cohort_data["graduates"]:
                match = match_name_to_tm_id(grad_name, name_index)
                entry = {
                    "name": grad_name,
                    "tm_id": match["tm_id"],
                    "matched_name": match["matched_name"],
                    "confidence": match["confidence"],
                }
                graduates_with_ids.append(entry)
                if match["tm_id"]:
                    total_matched += 1
                total_graduates += 1

            matched_count = sum(1 for g in graduates_with_ids if g["tm_id"])

            cohort_entry = {
                "year": cohort_data["year"],
                "graduates": graduates_with_ids,
                "total": len(cohort_data["graduates"]),
                "matched": matched_count,
                "best": cohort_data.get("best"),
                "source": cohort_data.get("source", ""),
                "incomplete": cohort_data.get("incomplete", False),
                "note": cohort_data.get("note", ""),
            }
            course_entry["cohorts"][cohort_num] = cohort_entry

            status = "✓" if not cohort_data.get("incomplete") else "⚠"
            print(f"  {status} Lehrgang {cohort_num} ({cohort_data['year']}): "
                  f"{matched_count}/{len(cohort_data['graduates'])} matched")

        course_entry["stats"] = {
            "total_cohorts": len(course_data["cohorts"]),
            "total_graduates": total_graduates,
            "total_matched": total_matched,
            "match_rate": round(total_matched / max(1, total_graduates), 3),
        }
        output["courses"].append(course_entry)

        print(f"\n  Overall: {total_matched}/{total_graduates} matched "
              f"({100*total_matched/max(1,total_graduates):.1f}%)")

    # Save
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n  ✓ Saved: {OUTPUT_FILE}")
    print(f"    Size: {OUTPUT_FILE.stat().st_size / 1024:.1f} KB")

    return output


def main():
    if "--match-only" in sys.argv:
        print("Re-running tm_id matching only...")
    build_coaching_licenses()


if __name__ == "__main__":
    main()
