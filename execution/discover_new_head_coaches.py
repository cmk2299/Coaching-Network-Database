#!/usr/bin/env python3
"""
discover_new_head_coaches.py — Auto-build profile + network for newly-detected head coaches.

After a staff scrape (run_mvp.sh Step 1), TM may now reflect a new head coach at
a BL1/BL2/BL3 club (e.g., Union Berlin hires a new HC mid-season). This script:

  1. Scans all BL1/BL2/BL3 club staff files.
  2. Extracts every contact with role="head_coach" (and SD-tier roles via flag).
  3. For each NEW head coach (no network on disk yet):
     a. Scrape their profile via scrape_person_profiles.py if missing.
     b. Build their network via build_coach_network.py.
  4. Emit a summary report.

Architecture: Layer 3 (Execution). Called from run_mvp.sh between Step 1 (staff
scrape) and Step 2 (network rebuild) so the daily refresh self-heals coverage
when a coach changes club.

Usage:
  python3 execution/discover_new_head_coaches.py            # discover + build
  python3 execution/discover_new_head_coaches.py --dry-run  # only report
  python3 execution/discover_new_head_coaches.py --leagues=BL1,BL2,BL3
  python3 execution/discover_new_head_coaches.py --include-sd   # also SD-tier

Outputs:
  - stdout: human-readable summary
  - data/new_coach_discovery.json (audit trail)
"""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
STAFF_DIR = DATA / "staff"
NETWORKS_DIR = DATA / "networks"
PROFILES_DIR = DATA / "person_profiles"
CLUB_REGISTRY = DATA / "club_registry.json"
REPORT_PATH = DATA / "new_coach_discovery.json"

HEAD_COACH_ROLE = "head_coach"
SD_ROLES = {"sporting_director", "executive", "management"}


def has_network(tm_id: int) -> bool:
    return (NETWORKS_DIR / f"{tm_id}.json").exists()


def has_profile(tm_id: int) -> bool:
    """Check whether ANY profile file exists (trainer_X or spieler_X)."""
    return any((PROFILES_DIR / f"{prefix}{tm_id}.json").exists()
               for prefix in ("trainer_", "spieler_", ""))


def bl_club_ids(leagues: list[str], current_season: str = "2025/2026") -> set[int]:
    """Return club_tm_ids that are CURRENTLY in any of the requested leagues
    (i.e. league membership in `current_season`). Historical clubs are excluded —
    we only want clubs whose staff file reflects an active BL HC.
    """
    reg = json.load(open(CLUB_REGISTRY))
    clubs = reg.get("clubs", []) if isinstance(reg, dict) else reg
    ids = set()
    target = set(leagues)
    for c in clubs:
        if not isinstance(c, dict):
            continue
        current_lgs = set(c.get("leagues", {}).get(current_season, []))
        if current_lgs & target:
            ids.add(c.get("tm_id"))
    return ids - {None}


def scan_staff_for_coaches(club_tm_ids: set[int],
                            include_sd: bool = False,
                            include_youth: bool = False) -> list[dict]:
    """Return list of {tm_id, name, club_tm_id, club_name, role, section} entries
    for FIRST-TEAM head coaches (and optionally SD-tier) found in BL staff files.

    By default, section='Jugend' entries are EXCLUDED — youth/NLZ head coaches
    are handled by the separate NLZ pipeline (nlz_trainer_registry.json), not
    the BL coach network pipeline. Pass include_youth=True to include them.
    """
    targets = {HEAD_COACH_ROLE} | (SD_ROLES if include_sd else set())
    SKIP_SECTIONS = set() if include_youth else {"Jugend"}
    coaches = []
    for cid in club_tm_ids:
        sf_path = STAFF_DIR / f"{cid}.json"
        if not sf_path.exists():
            continue
        try:
            sf = json.load(open(sf_path))
        except (ValueError, json.JSONDecodeError):
            continue
        for p in sf.get("staff", []):
            if p.get("section", "") in SKIP_SECTIONS:
                continue
            if p.get("role") in targets:
                tm_id = p.get("tm_id")
                if not tm_id:
                    continue
                coaches.append({
                    "tm_id": tm_id,
                    "name": p.get("name", "?"),
                    "club_tm_id": cid,
                    "club_name": sf.get("club_name", "?"),
                    "role": p.get("role"),
                    "section": p.get("section", ""),
                })
    return coaches


def detect_missing(coaches: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """Split into (missing_profile, missing_network_only, complete)."""
    missing_profile = []
    missing_network = []
    complete = []
    for c in coaches:
        tid = c["tm_id"]
        if not has_profile(tid):
            missing_profile.append(c)
        elif not has_network(tid):
            missing_network.append(c)
        else:
            complete.append(c)
    return missing_profile, missing_network, complete


def scrape_profile(tm_id: int, role: str) -> bool:
    """Trigger scrape_person_profiles.py for a single trainer tm_id."""
    # role here is our internal classification — TM URL uses 'trainer' for HCs/SDs.
    person_type = "trainer"
    cmd = ["python3", "execution/scrape_person_profiles.py",
            f"--tm-id={tm_id}", f"--type={person_type}"]
    print(f"    + scrape: tm_id={tm_id}")
    try:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=60)
        return "Saved" in r.stdout
    except subprocess.TimeoutExpired:
        print(f"    ✗ scrape TIMEOUT for {tm_id}")
        return False


def build_network(tm_id: int) -> bool:
    """Trigger build_coach_network.py for a single tm_id."""
    cmd = ["python3", "execution/build_coach_network.py", f"--tm-id={tm_id}"]
    print(f"    + build:  tm_id={tm_id}")
    try:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=300)
        return "Saved:" in r.stdout
    except subprocess.TimeoutExpired:
        print(f"    ✗ build TIMEOUT for {tm_id}")
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--leagues", default="BL1,BL2,BL3",
                     help="Comma-separated leagues (default: BL1,BL2,BL3)")
    ap.add_argument("--include-sd", action="store_true",
                     help="Also discover sporting directors / executives")
    ap.add_argument("--include-youth", action="store_true",
                     help="Include section='Jugend' HCs (NLZ pipeline handles these by default)")
    ap.add_argument("--dry-run", action="store_true",
                     help="Report what would be done, don't scrape/build")
    args = ap.parse_args()

    leagues = [s.strip() for s in args.leagues.split(",") if s.strip()]
    print(f"=== discover_new_head_coaches ({','.join(leagues)}) ===")

    club_ids = bl_club_ids(leagues)
    print(f"  Clubs in target leagues: {len(club_ids)}")

    coaches = scan_staff_for_coaches(club_ids, include_sd=args.include_sd)
    dedup = {c["tm_id"]: c for c in coaches}
    coaches = list(dedup.values())
    print(f"  Unique head coaches{' + SDs' if args.include_sd else ''}: {len(coaches)}")

    missing_profile, missing_network, complete = detect_missing(coaches)
    print(f"    Complete (have profile + network): {len(complete)}")
    print(f"    Missing network only:              {len(missing_network)}")
    print(f"    Missing profile (need TM scrape):  {len(missing_profile)}")

    if args.dry_run:
        print(f"\n[DRY-RUN] would scrape+build {len(missing_profile)} new + build {len(missing_network)} existing")
        for c in missing_profile + missing_network:
            print(f"    {c['tm_id']:>7}  {c['name']:30s} @ {c['club_name']} ({c['role']})")
        return

    scraped_ok = []
    scraped_fail = []
    built_ok = []
    built_fail = []

    # Step 1: scrape missing profiles
    if missing_profile:
        print(f"\n--- Step 1: Scraping {len(missing_profile)} missing profiles ---")
        for c in missing_profile:
            if scrape_profile(c["tm_id"], c["role"]):
                scraped_ok.append(c)
            else:
                scraped_fail.append(c)

    # Step 2: build networks for everyone whose profile now exists
    to_build = missing_network + scraped_ok
    if to_build:
        print(f"\n--- Step 2: Building {len(to_build)} networks ---")
        for c in to_build:
            if build_network(c["tm_id"]):
                built_ok.append(c)
            else:
                built_fail.append(c)

    # Write report
    report = {
        "ran_at": datetime.utcnow().isoformat() + "Z",
        "leagues": leagues,
        "include_sd": args.include_sd,
        "clubs_scanned": len(club_ids),
        "coaches_found": len(coaches),
        "complete_before": len(complete),
        "scraped": [{"tm_id": c["tm_id"], "name": c["name"], "club": c["club_name"]} for c in scraped_ok],
        "scrape_failed": [{"tm_id": c["tm_id"], "name": c["name"]} for c in scraped_fail],
        "built": [{"tm_id": c["tm_id"], "name": c["name"], "club": c["club_name"]} for c in built_ok],
        "build_failed": [{"tm_id": c["tm_id"], "name": c["name"]} for c in built_fail],
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print("\n=== Summary ===")
    print(f"  Scraped: {len(scraped_ok)} ok, {len(scraped_fail)} failed")
    print(f"  Built:   {len(built_ok)} ok, {len(built_fail)} failed")
    print(f"  Report → {REPORT_PATH}")

    if built_ok:
        print("\nNew networks added:")
        for c in built_ok:
            print(f"  + {c['name']} (tm_id={c['tm_id']}) — {c['club_name']}")


if __name__ == "__main__":
    main()
