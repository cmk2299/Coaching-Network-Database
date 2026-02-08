#!/usr/bin/env python3
"""
DFB Pro-Lizenz / Fußball-Lehrer Lehrgang Cohorts Database

This module contains data about DFB coaching license cohorts.
These connections are extremely valuable for understanding coach networks.

Sources:
- https://www.dfb.de/news/
- https://www.kicker.de/
- https://www.bdfl.de/
"""

from typing import Dict, List, Optional

# DFB Fußball-Lehrer / Pro-Lizenz Lehrgänge
# Format: cohort_number -> { year, name, graduates }
LICENSE_COHORTS: Dict[int, Dict] = {
    62: {
        "year": "2015/2016",
        "name": "62. Fußball-Lehrer-Lehrgang",
        "location": "Hennes-Weisweiler-Akademie, Hennef",
        "graduates": [
            {"name": "Marco Antwerpen", "note": "SC Paderborn 07", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/marco-antwerpen/profil/trainer/8346"},
            {"name": "Holger Bachthaler", "note": "Zuletzt SpVgg Greuther Fürth", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/holger-bachthaler/profil/trainer/14530"},
            {"name": "David Bergner", "note": "Zuletzt FC Erzgebirge Aue", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/david-bergner/profil/trainer/8253"},
            {"name": "Alexander Blessin", "note": "FC St. Pauli", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/alexander-blessin/profil/trainer/13852"},
            {"name": "Hannes Drews", "note": "FC Hansa Rostock", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/hannes-drews/profil/trainer/13816"},
            {"name": "Katja Greulich", "note": "DFB Trainerin", "current_job": "Trainerin", "tm_url": "https://www.transfermarkt.de/katja-greulich/profil/trainer/24838"},
            {"name": "Inka Grings", "note": "Frauenfußball-Legende", "current_job": "Trainerin", "tm_url": "https://www.transfermarkt.de/inka-grings/profil/trainer/24876"},
            {"name": "Jan Hoepner", "note": "", "current_job": "Trainer", "tm_url": ""},
            {"name": "Kenan Kocak", "note": "Zuletzt Eintracht Braunschweig", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/kenan-kocak/profil/trainer/11068"},
            {"name": "Daniel Kraus", "note": "Borussia Dortmund U19", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/daniel-kraus/profil/trainer/41894"},
            {"name": "Pellegrino Matarazzo", "note": "TSG 1899 Hoffenheim", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/pellegrino-matarazzo/profil/trainer/33642"},
            {"name": "Julian Nagelsmann", "note": "Bundestrainer Deutschland", "current_job": "Bundestrainer", "tm_url": "https://www.transfermarkt.de/julian-nagelsmann/profil/trainer/16770"},
            {"name": "Alexander Nouri", "note": "Zuletzt Hertha BSC", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/alexander-nouri/profil/trainer/13735"},
            {"name": "Darius Scholtysik", "note": "", "current_job": "Trainer", "tm_url": ""},
            {"name": "Martin Schweizer", "note": "", "current_job": "Trainer", "tm_url": ""},
            {"name": "Roger Stilz", "note": "1. FC Kaiserslautern U19", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/roger-stilz/profil/trainer/44122"},
            {"name": "Jeff Strasser", "note": "Zuletzt FC Differdingen 03", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/jeff-strasser/profil/trainer/6801"},
            {"name": "Domenico Tedesco", "note": "Belgien Nationaltrainer", "current_job": "Nationaltrainer", "tm_url": "https://www.transfermarkt.de/domenico-tedesco/profil/trainer/16912"},
            {"name": "Daniel Thioune", "note": "1. FC Nürnberg", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/daniel-thioune/profil/trainer/8275"},
            {"name": "Patrick Weiser", "note": "FC Wegberg-Beeck", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/patrick-weiser/profil/trainer/51430"},
            {"name": "Nico Willig", "note": "FC Viktoria 1889 Berlin", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/nico-willig/profil/trainer/32890"},
            {"name": "Oliver Zapel", "note": "Zuletzt SV Darmstadt 98", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/oliver-zapel/profil/trainer/17148"},
            {"name": "Mark Zimmermann", "note": "Zuletzt Dynamo Dresden", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/mark-zimmermann/profil/trainer/36970"},
        ],
    },
    63: {
        "year": "2016/2017",
        "name": "63. Fußball-Lehrer-Lehrgang",
        "location": "Hennes-Weisweiler-Akademie, Hennef",
        "graduates": [
            {"name": "Stefan Leitl", "note": ""},
            {"name": "Christian Preußer", "note": ""},
            {"name": "Florian Kohfeldt", "note": ""},
            {"name": "Robert Klauß", "note": "Jahrgangsbester"},
            # TODO: Complete list
        ],
    },
    64: {
        "year": "2017/2018",
        "name": "64. Fußball-Lehrer-Lehrgang",
        "location": "Hennes-Weisweiler-Akademie, Hennef",
        "graduates": [
            {"name": "Sebastian Hoeneß", "note": ""},
            {"name": "Enrico Maaßen", "note": ""},
            {"name": "Bo Svensson", "note": ""},
            # TODO: Complete list
        ],
    },
    65: {
        "year": "2018/2019",
        "name": "65. Fußball-Lehrer-Lehrgang",
        "location": "Hennes-Weisweiler-Akademie, Hennef",
        "graduates": [
            {"name": "Ole Werner", "note": ""},
            # TODO: Complete list
        ],
    },
    68: {
        "year": "2022/2023",
        "name": "68. Pro-Lizenz-Lehrgang",
        "location": "DFB-Akademie, Frankfurt",
        "graduates": [
            {"name": "Nils Döring", "note": ""},
            {"name": "Benjamin Duda", "note": ""},
            {"name": "Marie-Louise Eta", "note": "Erste Trainerin in der Bundesliga"},
            {"name": "Marc Hensel", "note": ""},
            {"name": "Kai Herdling", "note": ""},
            {"name": "Fabian Hürzeler", "note": "Brighton & Hove Albion"},
            {"name": "Matthias Kaltenbach", "note": ""},
            {"name": "Joseph Laumann", "note": ""},
            {"name": "Robert Lechleiter", "note": ""},
            {"name": "Björn Mehnert", "note": ""},
            {"name": "Benedetto Muzzicato", "note": ""},
            {"name": "Oliver Reiss", "note": ""},
            {"name": "Danny Röhl", "note": "Sheffield Wednesday"},
            {"name": "Jonas Stephan", "note": ""},
            {"name": "Tobias Strobl", "note": ""},
            {"name": "Michael Urbansky", "note": ""},
        ],
    },
    69: {
        "year": "2023/2024",
        "name": "69. Pro-Lizenz-Lehrgang",
        "location": "DFB-Akademie, Frankfurt",
        "graduates": [
            {"name": "Fabian Adelmann", "note": ""},
            {"name": "Timm Fahrion", "note": ""},
            {"name": "Dario Fossi", "note": ""},
            {"name": "Christian Gmünder", "note": ""},
            {"name": "Leonhard Haas", "note": ""},
            {"name": "Miroslav Jagatic", "note": ""},
            {"name": "Oliver Kirch", "note": ""},
            {"name": "Matthias Mincu", "note": ""},
            {"name": "Eugen Polanski", "note": "Borussia M'gladbach II"},
            {"name": "Stefan Reisinger", "note": ""},
            {"name": "Jonas Scheuermann", "note": ""},
            {"name": "Julian Schuster", "note": "SC Freiburg"},
            {"name": "Olufemi Smith", "note": ""},
            {"name": "Tommy Stroot", "note": "VfL Wolfsburg Frauen"},
            {"name": "Moritz Volz", "note": ""},
            {"name": "Willi Weiße", "note": ""},
        ],
    },
    70: {
        "year": "2024/2025",
        "name": "70. Pro-Lizenz-Lehrgang",
        "location": "DFB-Akademie, Frankfurt",
        "graduates": [
            {"name": "Marc Unterberger", "note": "SpVgg Unterhaching, alternativer Zulassungsweg"},
            # TODO: Complete when finished
        ],
    },
}

# Mapping of coach names to their cohort
COACH_TO_COHORT: Dict[str, int] = {}
for cohort_num, cohort_data in LICENSE_COHORTS.items():
    for grad in cohort_data.get("graduates", []):
        name = grad["name"]
        COACH_TO_COHORT[name.lower()] = cohort_num


def find_cohort_for_coach(coach_name: str) -> Optional[int]:
    """Find which cohort a coach belongs to."""
    name_lower = coach_name.lower().strip()

    # Direct match
    if name_lower in COACH_TO_COHORT:
        return COACH_TO_COHORT[name_lower]

    # Partial match (last name)
    for full_name, cohort in COACH_TO_COHORT.items():
        if name_lower in full_name or full_name.split()[-1] in name_lower:
            return cohort

    return None


def get_cohort_mates(coach_name: str) -> List[Dict]:
    """Get all coaches from the same license cohort."""
    cohort_num = find_cohort_for_coach(coach_name)
    if not cohort_num:
        return []

    cohort = LICENSE_COHORTS.get(cohort_num, {})
    graduates = cohort.get("graduates", [])

    # Filter out the coach themselves
    name_lower = coach_name.lower()
    mates = []
    for grad in graduates:
        if grad["name"].lower() != name_lower:
            mates.append({
                "name": grad["name"],
                "note": grad.get("note", ""),
                "current_job": grad.get("current_job", ""),
                "tm_url": grad.get("tm_url", ""),
                "cohort": cohort_num,
                "cohort_name": cohort.get("name", ""),
                "year": cohort.get("year", ""),
            })

    return mates


def get_cohort_info(cohort_num: int) -> Optional[Dict]:
    """Get full info about a specific cohort."""
    return LICENSE_COHORTS.get(cohort_num)


if __name__ == "__main__":
    # Test with Blessin
    print("=" * 60)
    print("Testing: Alexander Blessin")
    print("=" * 60)

    cohort = find_cohort_for_coach("Alexander Blessin")
    print(f"Cohort: {cohort}")

    if cohort:
        info = get_cohort_info(cohort)
        print(f"Name: {info['name']}")
        print(f"Year: {info['year']}")
        print(f"Location: {info['location']}")

    print("\nCohort mates:")
    mates = get_cohort_mates("Alexander Blessin")
    for mate in mates:
        note = f" - {mate['note']}" if mate['note'] else ""
        print(f"  - {mate['name']}{note}")
