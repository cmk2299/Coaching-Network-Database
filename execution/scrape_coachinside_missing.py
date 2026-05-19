#!/usr/bin/env python3
"""
scrape_coachinside_missing.py

For every coach in the MISSING list of data/coachinside_gap_report.json,
search Transfermarkt's Schnellsuche, validate candidates against CSV
metadata (last name, first name/initial, age ±2, country, current club),
and trigger scrape_person_profiles.py --tm-id <id> --type trainer
for the unique winner.

Architecture: Layer 3 (Execution).

Usage:
  python3 execution/scrape_coachinside_missing.py
  python3 execution/scrape_coachinside_missing.py --dry-run
  python3 execution/scrape_coachinside_missing.py --max 5
  python3 execution/scrape_coachinside_missing.py --filter csv_source=vereinslos

Outputs:
  - data/coachinside_scrape_report.json   (scraped/unmatched/errors lists)
  - logs/coachinside_unmatched.json       (full candidate dumps for manual review)
  - tmp/cache/search/{slug}.html          (cached Schnellsuche pages, 30d TTL)
  - data/person_profiles/{tm_id}.json     (via scrape_person_profiles.py)

TM quirks handled (see scrape_person_profiles.py):
  - 3s rate-limit delay between requests, identical UA + headers
  - HTML cache (30d) so re-runs are free
  - Schnellsuche groups results by entity (Spieler / Trainer / Verein) — we only
    parse the Trainer table, identified by its <h2>/<table> sibling pair
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

# ── Paths ────────────────────────────────────────────────────────────
BASE = Path(__file__).parent.parent
DATA = BASE / "data"
LOGS = BASE / "logs"
CACHE_DIR = BASE / "tmp" / "cache" / "search"
GAP_REPORT = DATA / "coachinside_gap_report.json"
SCRAPE_REPORT = DATA / "coachinside_scrape_report.json"
UNMATCHED_LOG = LOGS / "coachinside_unmatched.json"
PERSON_SCRAPER = BASE / "execution" / "scrape_person_profiles.py"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
LOGS.mkdir(parents=True, exist_ok=True)

# ── HTTP config (mirrors scrape_person_profiles.py) ──────────────────
TM_BASE = "https://www.transfermarkt.de"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}
REQUEST_DELAY = 3
CACHE_DAYS = 30

# ── Country normalization ────────────────────────────────────────────
# CSVs use German country labels. TM nationality flags do too — but allow
# common variants for resilience.
COUNTRY_ALIASES = {
    "deutschland": {"deutschland", "germany", "ger", "de"},
    "oesterreich": {"oesterreich", "österreich", "austria", "aut"},
    "schweiz":     {"schweiz", "switzerland", "sui", "che"},
    "niederlande": {"niederlande", "netherlands", "ned", "nl", "holland"},
    "belgien":     {"belgien", "belgium", "bel"},
    "tuerkei":     {"tuerkei", "türkei", "turkey", "tur"},
    "italien":     {"italien", "italy", "ita"},
    "spanien":     {"spanien", "spain", "esp"},
    "portugal":    {"portugal", "por", "prt"},
    "frankreich":  {"frankreich", "france", "fra"},
    "england":     {"england", "eng", "uk"},
    "kroatien":    {"kroatien", "croatia", "cro", "hrv"},
    "polen":       {"polen", "poland", "pol"},
    "daenemark":   {"daenemark", "dänemark", "denmark", "den"},
    "schweden":    {"schweden", "sweden", "swe"},
    "norwegen":    {"norwegen", "norway", "nor"},
}

# ── Diacritic-fold + slug helpers (local copy — lib/normalization.py is heavier) ─
_EXTRA = {
    "ß": "ss", "Ø": "o", "ø": "o", "Æ": "ae", "æ": "ae",
    "Œ": "oe", "œ": "oe", "Ł": "l", "ł": "l", "Đ": "d", "đ": "d",
    "İ": "i", "ı": "i",
}


def _fold(s: str) -> str:
    if not s:
        return ""
    out = []
    for ch in s:
        out.append(_EXTRA.get(ch, ch))
    nfkd = unicodedata.normalize("NFKD", "".join(out))
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def norm(s: str) -> str:
    s = _fold(s or "").lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def country_match(csv_country: str, tm_nat: list[str] | str | None) -> bool:
    """Returns True if csv_country matches at least one of the TM nationality
    entries. Empty CSV country → always True (no filter)."""
    if not csv_country:
        return True
    if not tm_nat:
        return False
    if isinstance(tm_nat, str):
        tm_nat = [tm_nat]
    csv_norm = norm(csv_country).replace(" ", "")
    aliases = COUNTRY_ALIASES.get(csv_norm, {csv_norm})
    for n in tm_nat:
        n_norm = norm(n).replace(" ", "")
        if n_norm in aliases or csv_norm in n_norm or n_norm in csv_norm:
            return True
    return False


def club_fuzzy_match(csv_club: str, tm_club: str | None) -> bool:
    """Lenient club match: token-overlap >= 1 significant token."""
    if not csv_club or csv_club.lower() == "ohne aktuelles team":
        return True  # vereinslos → no club to match
    if not tm_club:
        return False
    a = set(norm(csv_club).split()) - {"fc", "sv", "tsv", "vfl", "vfb",
                                        "borussia", "1", "1.", "der", "die",
                                        "und", "fussball", "fußball"}
    b = set(norm(tm_club).split())
    return bool(a & b) or bool(set(norm(csv_club).split()) & b)


# ── Fetch with cache (mirrors scrape_person_profiles.py) ─────────────
def fetch(url: str, cache_key: str) -> Optional[str]:
    cache_path = CACHE_DIR / f"{cache_key}.html"
    if cache_path.exists():
        age_h = (datetime.now().timestamp() - cache_path.stat().st_mtime) / 3600
        if age_h < CACHE_DAYS * 24:
            return cache_path.read_text(encoding="utf-8")
    time.sleep(REQUEST_DELAY)
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        html = r.text
        # naive captcha sniff
        low = html.lower()
        if "captcha" in low or "are you a human" in low:
            print(f"    WARN: possible captcha on {url}", file=sys.stderr)
        cache_path.write_text(html, encoding="utf-8")
        return html
    except Exception as e:
        print(f"    ERROR fetching {url}: {e}", file=sys.stderr)
        return None


# ── Schnellsuche parsing ─────────────────────────────────────────────
@dataclass
class Candidate:
    tm_id: int
    name: str
    current_club: Optional[str] = None
    nationality: list[str] = field(default_factory=list)
    dob: Optional[str] = None  # YYYY-MM-DD if extractable
    age: Optional[int] = None
    raw_row_text: str = ""

    def to_dict(self) -> dict:
        return {
            "tm_id": self.tm_id,
            "name": self.name,
            "current_club": self.current_club,
            "nationality": self.nationality,
            "dob": self.dob,
            "age": self.age,
        }


def parse_search_trainers(html: str) -> list[Candidate]:
    """Extract Trainer-section candidates from a Schnellsuche result page.

    TM groups results: Spieler → Trainer → Schiedsrichter → Verein. The
    Trainer section is a <table class="items"> directly under or near a
    heading containing 'Trainer'.
    """
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[Candidate] = []

    # Find the Trainer heading; then take the next <table class="items">.
    trainer_table = None
    for h in soup.find_all(["h2", "h3"]):
        if "trainer" in h.get_text(strip=True).lower():
            tbl = h.find_next("table", class_="items")
            if tbl:
                trainer_table = tbl
                break
    # Fallback: any items table whose row links go to /trainer/{id}
    if trainer_table is None:
        for tbl in soup.find_all("table", class_="items"):
            if tbl.find("a", href=re.compile(r"/profil/trainer/\d+")):
                trainer_table = tbl
                break
    if trainer_table is None:
        return candidates

    for tr in trainer_table.find_all("tr"):
        if not tr.find("td"):
            continue
        # Trainer link
        link = tr.find("a", href=re.compile(r"/profil/trainer/(\d+)"))
        if not link:
            continue
        m = re.search(r"/profil/trainer/(\d+)", link["href"])
        if not m:
            continue
        tm_id = int(m.group(1))
        name = link.get("title") or link.get_text(strip=True)

        # Current club (link to /verein/{id} in same row)
        club_link = tr.find("a", href=re.compile(r"/verein/\d+"))
        current_club = club_link.get("title") if club_link else None
        if not current_club and club_link:
            current_club = club_link.get_text(strip=True)

        # Nationality flags
        nats = []
        for img in tr.find_all("img", class_="flaggenrahmen"):
            t = img.get("title", "").strip()
            if t and t not in nats:
                nats.append(t)

        # Age — TM Schnellsuche shows an "Alter" column. We pull all numeric
        # cells and the first plausible 16–90 number is the age.
        age = None
        for td in tr.find_all("td"):
            txt = td.get_text(strip=True)
            if txt.isdigit():
                v = int(txt)
                if 16 <= v <= 90:
                    age = v
                    break

        candidates.append(Candidate(
            tm_id=tm_id,
            name=name,
            current_club=current_club,
            nationality=nats,
            age=age,
            raw_row_text=tr.get_text(" ", strip=True)[:200],
        ))

    return candidates


# ── Validation ───────────────────────────────────────────────────────
def lastname(full: str) -> str:
    parts = norm(full).split()
    return parts[-1] if parts else ""


def firstname(full: str) -> str:
    parts = norm(full).split()
    return parts[0] if parts else ""


def validate(c: Candidate, csv_row: dict) -> tuple[bool, str]:
    """Return (is_match, reason). Strictness:
      - last name must match exactly (after fold/lower)
      - first name match OR first-letter initial OR substring containment
      - if csv age set: TM age within ±2 (when TM age available)
      - if csv country set: at least one nationality in alias group
      - if csv team set + not 'Ohne aktuelles Team': fuzzy club overlap
    """
    csv_full = csv_row["full_name"]
    csv_ln = lastname(csv_full)
    csv_fn = firstname(csv_full)
    cand_ln = lastname(c.name)
    cand_fn = firstname(c.name)

    if csv_ln != cand_ln:
        return False, f"lastname-mismatch ({csv_ln} vs {cand_ln})"

    fn_ok = (
        csv_fn == cand_fn
        or (csv_fn and cand_fn and csv_fn[0] == cand_fn[0])
        or (csv_fn and cand_fn and (csv_fn in cand_fn or cand_fn in csv_fn))
    )
    if not fn_ok:
        return False, f"firstname-mismatch ({csv_fn} vs {cand_fn})"

    csv_age = csv_row.get("age") or 0
    if csv_age and c.age and abs(csv_age - c.age) > 2:
        return False, f"age-mismatch ({csv_age} vs {c.age})"

    if csv_row.get("country") and not country_match(csv_row["country"], c.nationality):
        return False, f"country-mismatch ({csv_row['country']} vs {c.nationality})"

    if csv_row.get("team") and not club_fuzzy_match(csv_row["team"], c.current_club):
        return False, f"club-mismatch ({csv_row['team']} vs {c.current_club})"

    return True, "ok"


# ── Subprocess: invoke scrape_person_profiles.py ─────────────────────
def run_person_scraper(tm_id: int) -> tuple[bool, str]:
    """Calls scrape_person_profiles.py --tm-id N --type=trainer.
    Returns (success, stderr_tail)."""
    try:
        r = subprocess.run(
            ["python3", str(PERSON_SCRAPER), "--tm-id", str(tm_id), "--type=trainer"],
            cwd=BASE, capture_output=True, text=True, timeout=120,
        )
        if r.returncode != 0:
            return False, r.stderr[-500:]
        # Scraper writes data/person_profiles/{tm_id}.json
        prof = DATA / "person_profiles" / f"{tm_id}.json"
        if not prof.exists():
            return False, "profile file missing after scrape"
        return True, ""
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT"
    except Exception as e:
        return False, f"EXC {e!r}"


# ── Main flow ────────────────────────────────────────────────────────
def load_gap_report() -> dict:
    if not GAP_REPORT.exists():
        print(f"[err] {GAP_REPORT} not found — run diff_coachinside_csvs.py first",
              file=sys.stderr)
        sys.exit(1)
    return json.loads(GAP_REPORT.read_text(encoding="utf-8"))


def parse_filter(f: str | None) -> dict:
    """--filter csv_source=vereinslos → {'csv_source': 'vereinslos'}"""
    if not f:
        return {}
    out = {}
    for part in f.split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="Show what would be scraped without fetching")
    ap.add_argument("--max", type=int, default=0, help="Cap N rows (0=all)")
    ap.add_argument("--filter", type=str, default=None,
                    help="csv_source=vereinslos|active_headcoaches|trainerstab_dach")
    args = ap.parse_args()

    gap = load_gap_report()
    missing = gap.get("missing", [])
    flt = parse_filter(args.filter)

    if "csv_source" in flt:
        target = flt["csv_source"]
        missing = [m for m in missing if m.get("file") == target]

    if args.max > 0:
        missing = missing[:args.max]

    print(f"== Coachinside MISSING scraper ==")
    print(f"  Targets: {len(missing)}  (filter={flt or 'none'})")
    if args.dry_run:
        print("  DRY RUN")
    print()

    scraped: list[dict] = []
    unmatched: list[dict] = []
    errors: list[dict] = []

    for i, row in enumerate(missing, 1):
        # Carry firstname/surname forward (gap-report only has full_name)
        fn_parts = row["full_name"].split(" ", 1)
        csv_row = {
            "firstname": fn_parts[0] if fn_parts else "",
            "surname": fn_parts[1] if len(fn_parts) > 1 else "",
            "full_name": row["full_name"],
            "country": row.get("country") or "",
            "age": row.get("age") or 0,
            "team": row.get("team") or "",
            "league": row.get("league") or "",
            "csv_source": row.get("file") or "",
            "coach_type_name": row.get("coach_type") or "",
        }

        print(f"  [{i}/{len(missing)}] {csv_row['full_name']} "
              f"({csv_row['country']}, {csv_row['age']}, {csv_row['team'] or '—'})")

        if args.dry_run:
            continue

        # 1. fetch Schnellsuche
        query = csv_row["full_name"]
        url = f"{TM_BASE}/schnellsuche/ergebnis/schnellsuche?query={quote_plus(query)}"
        cache_key = re.sub(r"[^a-z0-9]+", "_", _fold(query.lower())).strip("_")[:80] or "q"
        html = fetch(url, cache_key)
        if not html:
            errors.append({"row": csv_row, "error": "fetch-failed"})
            continue

        # 2. parse Trainer candidates
        cands = parse_search_trainers(html)
        if not cands:
            unmatched.append({
                "row": csv_row,
                "reason": "no-trainer-candidates",
                "candidates": [],
            })
            print(f"    → no Trainer candidates")
            continue

        # 3. validate
        accepted = []
        rejected = []
        for c in cands:
            ok, why = validate(c, csv_row)
            if ok:
                accepted.append(c)
            else:
                rejected.append({"cand": c.to_dict(), "why": why})

        if len(accepted) == 0:
            unmatched.append({
                "row": csv_row,
                "reason": "all-candidates-rejected",
                "candidates": [c.to_dict() for c in cands],
                "rejections": rejected,
            })
            print(f"    → 0 accepted of {len(cands)}: rejected reasons "
                  f"{ {r['why'] for r in rejected[:3]} }")
            continue

        if len(accepted) > 1:
            unmatched.append({
                "row": csv_row,
                "reason": "ambiguous-multiple-matches",
                "candidates": [c.to_dict() for c in accepted],
            })
            print(f"    → {len(accepted)} candidates accepted; ambiguous, manual review")
            continue

        winner = accepted[0]
        print(f"    → match: TM:{winner.tm_id}  {winner.name}  ({winner.current_club or '—'})")

        # 4. scrape via subprocess
        ok, tail = run_person_scraper(winner.tm_id)
        rec = {
            "row": csv_row,
            "tm_id": winner.tm_id,
            "matched_name": winner.name,
            "matched_club": winner.current_club,
            "matched_age": winner.age,
            "matched_nationality": winner.nationality,
        }
        if ok:
            scraped.append(rec)
            print(f"    ✓ scraped TM:{winner.tm_id}")
        else:
            errors.append({**rec, "error": tail})
            print(f"    ✗ scrape failed: {tail[:200]}")

        # Save partial state every iteration → safe interrupts
        _write_report(scraped, unmatched, errors)

    _write_report(scraped, unmatched, errors)
    UNMATCHED_LOG.write_text(json.dumps(unmatched, indent=2, ensure_ascii=False),
                              encoding="utf-8")

    # NB: persons_master.json is rebuilt by scrape_person_profiles.py only when
    # called WITHOUT --tm-id (single-profile mode skips the merge). Caller
    # should run `scrape_person_profiles.py --merge-only` afterwards if a fresh
    # master is required. run_coachinside_coverage.sh handles this implicitly
    # via the diff-rerun + the build_coach_network pipeline.

    print()
    print(f"== DONE ==")
    print(f"  Scraped:   {len(scraped)}")
    print(f"  Unmatched: {len(unmatched)}")
    print(f"  Errors:    {len(errors)}")
    print(f"  Report:    {SCRAPE_REPORT}")
    print(f"  Unmatched: {UNMATCHED_LOG}")
    return 0


def _write_report(scraped, unmatched, errors) -> None:
    SCRAPE_REPORT.write_text(json.dumps({
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "stats": {
            "scraped": len(scraped),
            "unmatched": len(unmatched),
            "errors": len(errors),
        },
        "scraped": scraped,
        "unmatched": [{
            "full_name": u["row"]["full_name"],
            "csv_source": u["row"]["csv_source"],
            "reason": u["reason"],
            "candidate_count": len(u.get("candidates", [])),
        } for u in unmatched],
        "errors": [{
            "full_name": e.get("row", {}).get("full_name"),
            "tm_id": e.get("tm_id"),
            "error": e.get("error", "")[:300],
        } for e in errors],
    }, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
