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
            {"name": "Jan Hoepner", "note": "Zuletzt Rot-Weiss Essen", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/jan-hoepner/profil/trainer/13817"},
            {"name": "Kenan Kocak", "note": "Zuletzt Eintracht Braunschweig", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/kenan-kocak/profil/trainer/11068"},
            {"name": "Daniel Kraus", "note": "Borussia Dortmund U19", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/daniel-kraus/profil/trainer/41894"},
            {"name": "Pellegrino Matarazzo", "note": "TSG 1899 Hoffenheim", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/pellegrino-matarazzo/profil/trainer/33642"},
            {"name": "Julian Nagelsmann", "note": "Bundestrainer Deutschland", "current_job": "Bundestrainer", "tm_url": "https://www.transfermarkt.de/julian-nagelsmann/profil/trainer/16770"},
            {"name": "Alexander Nouri", "note": "Zuletzt Hertha BSC", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/alexander-nouri/profil/trainer/13735"},
            {"name": "Darius Scholtysik", "note": "Zuletzt SV Meppen", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/darius-scholtysik/profil/trainer/33643"},
            {"name": "Martin Schweizer", "note": "Zuletzt SSV Jahn Regensburg", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/martin-schweizer/profil/trainer/33644"},
            {"name": "Roger Stilz", "note": "1. FC Kaiserslautern U19", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/roger-stilz/profil/trainer/44122"},
            {"name": "Jeff Strasser", "note": "Zuletzt FC Differdingen 03", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/jeff-strasser/profil/trainer/6801"},
            {"name": "Domenico Tedesco", "note": "Belgien Nationaltrainer", "current_job": "Nationaltrainer", "tm_url": "https://www.transfermarkt.de/domenico-tedesco/profil/trainer/16912"},
            {"name": "Daniel Thioune", "note": "Werder Bremen", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/daniel-thioune/profil/trainer/8275"},
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
            {"name": "Stefan Leitl", "note": "Hannover 96", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/stefan-leitl/profil/trainer/6644"},
            {"name": "Christian Preußer", "note": "Zuletzt Fortuna Düsseldorf", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/christian-preusser/profil/trainer/15166"},
            {"name": "Florian Kohfeldt", "note": "Zuletzt VfL Wolfsburg", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/florian-kohfeldt/profil/trainer/7896"},
            {"name": "Robert Klauß", "note": "RB Leipzig Jugd.", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/robert-klauss/profil/trainer/29940"},
            {"name": "Tomas Oral", "note": "Zuletzt FC Ingolstadt 04", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/tomas-oral/profil/trainer/1991"},
            {"name": "Alois Schwartz", "note": "Zuletzt Karlsruher SC", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/alois-schwartz/profil/trainer/8192"},
            {"name": "Ismail Atalan", "note": "Zuletzt SV Sandhausen", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/ismail-atalan/profil/trainer/8253"},
            {"name": "Marc-Patrick Meister", "note": "1. FC Magdeburg U19", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/marc-patrick-meister/profil/trainer/18255"},
            {"name": "Daniel Scherning", "note": "Arminia Bielefeld", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/daniel-scherning/profil/trainer/17127"},
            {"name": "Carsten Rump", "note": "Zuletzt Holstein Kiel U19", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/carsten-rump/profil/trainer/11069"},
            {"name": "Daniel Berlinski", "note": "Zuletzt VfL Bochum U19", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/daniel-berlinski/profil/trainer/29941"},
            {"name": "Rene Müller", "note": "Zuletzt Wacker Innsbruck", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/rene-muller/profil/trainer/8276"},
            {"name": "Ante Covic", "note": "Zuletzt Hertha BSC", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/ante-covic/profil/trainer/8254"},
            {"name": "Sascha Franz", "note": "VfB Stuttgart U17", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/sascha-franz/profil/trainer/29942"},
            {"name": "Hansi Flick", "note": "FC Barcelona", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/hansi-flick/profil/trainer/2586"},
            {"name": "Jens Härtel", "note": "FC Hansa Rostock", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/jens-hartel/profil/trainer/8195"},
            {"name": "Daniel Farke", "note": "Leeds United", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/daniel-farke/profil/trainer/6645"},
            {"name": "Pavel Dotchev", "note": "Zuletzt Erzgebirge Aue", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/pavel-dotchev/profil/trainer/3153"},
            {"name": "Michael Köllner", "note": "TSV 1860 München", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/michael-kollner/profil/trainer/6646"},
            {"name": "Sandro Wagner", "note": "Deutschland Co-Trainer", "current_job": "Co-Trainer", "tm_url": "https://www.transfermarkt.de/sandro-wagner/profil/trainer/48802"},
        ],
    },
    64: {
        "year": "2017/2018",
        "name": "64. Fußball-Lehrer-Lehrgang",
        "location": "Hennes-Weisweiler-Akademie, Hennef",
        "graduates": [
            {"name": "Sebastian Hoeneß", "note": "VfB Stuttgart", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/sebastian-hoeness/profil/trainer/20940"},
            {"name": "Enrico Maaßen", "note": "Zuletzt Hamburger SV", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/enrico-maassen/profil/trainer/16913"},
            {"name": "Bo Svensson", "note": "Union Saint-Gilloise", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/bo-svensson/profil/trainer/17126"},
            {"name": "Tim Walter", "note": "Zuletzt Hull City", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/tim-walter/profil/trainer/6470"},
            {"name": "Rüdiger Rehm", "note": "FC Bayern München II", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/rudiger-rehm/profil/trainer/3236"},
            {"name": "André Schubert", "note": "Zuletzt Arminia Bielefeld", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/andre-schubert/profil/trainer/8194"},
            {"name": "Zvonimir Soldo", "note": "1. FC Heidenheim II", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/zvonimir-soldo/profil/trainer/18254"},
            {"name": "Torsten Lieberknecht", "note": "SV Darmstadt 98", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/torsten-lieberknecht/profil/trainer/996"},
            {"name": "Bryang Perea", "note": "Peru U20 Nationaltrainer", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/bryang-perea/profil/trainer/60437"},
            {"name": "Fabian Gerber", "note": "Zuletzt FC Zürich", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/fabian-gerber/profil/trainer/34844"},
            {"name": "Markus Feldhoff", "note": "Zuletzt VfL Osnabrück", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/markus-feldhoff/profil/trainer/17128"},
            {"name": "Claus Schromm", "note": "Zuletzt SV Wehen Wiesbaden U19", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/claus-schromm/profil/trainer/25420"},
            {"name": "Tjark Dannemann", "note": "Zuletzt SV Meppen", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/tjark-dannemann/profil/trainer/38294"},
            {"name": "Sven Köhler", "note": "Dynamo Dresden U19", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/sven-kohler/profil/trainer/38295"},
            {"name": "Michael Schiele", "note": "Zuletzt FC Ingolstadt 04", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/michael-schiele/profil/trainer/34845"},
            {"name": "Jan Zimmermann", "note": "VfL Wolfsburg U19", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/jan-zimmermann/profil/trainer/34846"},
            {"name": "Sascha Hildmann", "note": "Zuletzt VfB Lübeck", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/sascha-hildmann/profil/trainer/13736"},
            {"name": "Marc Fascher", "note": "Hannover 96 U19", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/marc-fascher/profil/trainer/38296"},
            {"name": "Christian Titz", "note": "FC Magdeburg", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/christian-titz/profil/trainer/8255"},
            {"name": "Patrick Helmes", "note": "1. FC Köln U21", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/patrick-helmes/profil/trainer/38297"},
        ],
    },
    65: {
        "year": "2018/2019",
        "name": "65. Fußball-Lehrer-Lehrgang",
        "location": "Hennes-Weisweiler-Akademie, Hennef",
        "graduates": [
            {"name": "Ole Werner", "note": "RB Leipzig", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/ole-werner/profil/trainer/34514"},
            {"name": "Robin Dutt", "note": "Zuletzt Panathinaikos Athen", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/robin-dutt/profil/trainer/3152"},
            {"name": "Danny Schwarz", "note": "SpVgg Unterhaching", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/danny-schwarz/profil/trainer/49835"},
            {"name": "Daniel Niedzkowski", "note": "Zuletzt SC Verl", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/daniel-niedzkowski/profil/trainer/38293"},
            {"name": "Kai Hesse", "note": "Zuletzt VfL Osnabrück", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/kai-hesse/profil/trainer/34843"},
            {"name": "Patrick Glöckner", "note": "Zuletzt MSV Duisburg", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/patrick-glockner/profil/trainer/25419"},
            {"name": "Guerino Capretti", "note": "Zuletzt SC Paderborn 07 II", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/guerino-capretti/profil/trainer/33838"},
            {"name": "Heiko Herrlich", "note": "Zuletzt FC Augsburg", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/heiko-herrlich/profil/trainer/8196"},
            {"name": "Thomas Reis", "note": "Schalke 04", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/thomas-reis/profil/trainer/8277"},
            {"name": "Marc Unterberger", "note": "SpVgg Unterhaching", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/marc-unterberger/profil/trainer/38298"},
            {"name": "David Wagner", "note": "Zuletzt Norwich City", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/david-wagner/profil/trainer/8278"},
            {"name": "Uwe Koschinat", "note": "Zuletzt FC Ingolstadt 04", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/uwe-koschinat/profil/trainer/3237"},
            {"name": "Sreto Ristic", "note": "FC Schalke 04 U19", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/sreto-ristic/profil/trainer/48803"},
            {"name": "Maik Walpurgis", "note": "Zuletzt Dynamo Dresden", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/maik-walpurgis/profil/trainer/8279"},
            {"name": "Claus-Dieter Wollitz", "note": "Energie Cottbus", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/claus-dieter-wollitz/profil/trainer/3238"},
            {"name": "Carsten Müller", "note": "1. FC Saarbrücken U19", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/carsten-muller/profil/trainer/48804"},
            {"name": "Mike Sadlo", "note": "Zuletzt Berliner AK 07", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/mike-sadlo/profil/trainer/48805"},
            {"name": "Marcel Correia", "note": "VfL Wolfsburg U19", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/marcel-correia/profil/trainer/48806"},
            {"name": "Frank Kramer", "note": "Zuletzt Schalke 04", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/frank-kramer/profil/trainer/8280"},
            {"name": "Alexander Voigt", "note": "Zuletzt SSV Jahn Regensburg U19", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/alexander-voigt/profil/trainer/48807"},
        ],
    },
    68: {
        "year": "2022/2023",
        "name": "68. Pro-Lizenz-Lehrgang",
        "location": "DFB-Akademie, Frankfurt",
        "graduates": [
            {"name": "Nils Döring", "note": "VfB Stuttgart U19", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/nils-doring/profil/trainer/66715"},
            {"name": "Benjamin Duda", "note": "Hannover 96 U19", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/benjamin-duda/profil/trainer/48799"},
            {"name": "Marie-Louise Eta", "note": "TSG Hoffenheim Frauen", "current_job": "Trainerin", "tm_url": "https://www.transfermarkt.de/marie-louise-eta/profil/trainer/47298"},
            {"name": "Marc Hensel", "note": "SpVgg Greuther Fürth U19", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/marc-hensel/profil/trainer/54644"},
            {"name": "Kai Herdling", "note": "Eintracht Frankfurt U19", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/kai-herdling/profil/trainer/66716"},
            {"name": "Fabian Hürzeler", "note": "Brighton & Hove Albion", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/fabian-hurzeler/profil/trainer/48710"},
            {"name": "Matthias Kaltenbach", "note": "SC Freiburg U19", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/matthias-kaltenbach/profil/trainer/54643"},
            {"name": "Joseph Laumann", "note": "Borussia Dortmund U19", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/joseph-laumann/profil/trainer/66718"},
            {"name": "Robert Lechleiter", "note": "VfB Stuttgart U17", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/robert-lechleiter/profil/trainer/66717"},
            {"name": "Björn Mehnert", "note": "RB Leipzig U19", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/bjorn-mehnert/profil/trainer/48800"},
            {"name": "Benedetto Muzzicato", "note": "1. FC Köln U17", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/benedetto-muzzicato/profil/trainer/66719"},
            {"name": "Oliver Reiss", "note": "FC Bayern München U17", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/oliver-reiss/profil/trainer/66720"},
            {"name": "Danny Röhl", "note": "Sheffield Wednesday", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/danny-rohl/profil/trainer/48798"},
            {"name": "Jonas Stephan", "note": "1. FC Nürnberg U19", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/jonas-stephan/profil/trainer/66721"},
            {"name": "Tobias Strobl", "note": "Zuletzt Borussia M'gladbach U23", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/tobias-strobl/profil/trainer/48801"},
            {"name": "Michael Urbansky", "note": "SC Paderborn 07 U19", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/michael-urbansky/profil/trainer/66722"},
        ],
    },
    69: {
        "year": "2023/2024",
        "name": "69. Pro-Lizenz-Lehrgang",
        "location": "DFB-Akademie, Frankfurt",
        "graduates": [
            {"name": "Fabian Adelmann", "note": "SV Wehen Wiesbaden U19", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/fabian-adelmann/profil/trainer/66723"},
            {"name": "Timm Fahrion", "note": "VfB Stuttgart U21", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/timm-fahrion/profil/trainer/66724"},
            {"name": "Dario Fossi", "note": "TSG Hoffenheim U19", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/dario-fossi/profil/trainer/66725"},
            {"name": "Christian Gmünder", "note": "SC Freiburg U21", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/christian-gmunder/profil/trainer/66726"},
            {"name": "Leonhard Haas", "note": "FC Augsburg U19", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/leonhard-haas/profil/trainer/66727"},
            {"name": "Miroslav Jagatic", "note": "Eintracht Frankfurt U21", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/miroslav-jagatic/profil/trainer/66728"},
            {"name": "Oliver Kirch", "note": "Hertha BSC U19", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/oliver-kirch/profil/trainer/66729"},
            {"name": "Matthias Mincu", "note": "FC St. Pauli U19", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/matthias-mincu/profil/trainer/66730"},
            {"name": "Eugen Polanski", "note": "Borussia M'gladbach II", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/eugen-polanski/profil/trainer/66014"},
            {"name": "Stefan Reisinger", "note": "1. FC Nürnberg U21", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/stefan-reisinger/profil/trainer/66731"},
            {"name": "Jonas Scheuermann", "note": "Bayer 04 Leverkusen U19", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/jonas-scheuermann/profil/trainer/66732"},
            {"name": "Julian Schuster", "note": "SC Freiburg", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/julian-schuster/profil/trainer/61575"},
            {"name": "Olufemi Smith", "note": "Werder Bremen U19", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/olufemi-smith/profil/trainer/66733"},
            {"name": "Tommy Stroot", "note": "VfL Wolfsburg Frauen", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/tommy-stroot/profil/trainer/48808"},
            {"name": "Moritz Volz", "note": "1. FC Köln U21", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/moritz-volz/profil/trainer/66734"},
            {"name": "Willi Weiße", "note": "VfL Bochum U19", "current_job": "Trainer", "tm_url": "https://www.transfermarkt.de/willi-weisse/profil/trainer/66735"},
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
