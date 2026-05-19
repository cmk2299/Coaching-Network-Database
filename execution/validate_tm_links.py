#!/usr/bin/env python3
"""
Validate TM links across network JSONs.

Goal: catch the Marcel Klos / Johannes Spors class of bugs — contacts whose
`tm_url` points at a different person than their `tm_id` field claims.

Checks per contact entry:
  1. URL pattern matches /transfermarkt\.[a-z]+/.+/profil/(spieler|trainer)/\d+/?
  2. tm_id embedded in the URL == contact.tm_id  (mismatch == wrong link)
  3. Contact has tm_id but is missing tm_url

Output: data/tm_link_issues.json
  {
    "scanned_networks": N,
    "total_contacts": N,
    "summary": {"mismatched": N, "broken": N, "missing": N, "ok": N},
    "mismatched": [...],
    "broken": [...],
    "missing": [...]
  }

Spot-check pass: cross-references Marcel Klos + Johannes Spors against
data/persons_master.json regardless of sample selection.

Usage:
  python execution/validate_tm_links.py                # scan 50 random networks
  python execution/validate_tm_links.py --all          # scan all
  python execution/validate_tm_links.py --sample=100   # scan 100 random
  python execution/validate_tm_links.py --dry-run      # don't write output file
"""

import argparse
import json
import random
import re
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
DATA = BASE / "data"
NETWORKS = DATA / "networks"
OUT = DATA / "tm_link_issues.json"

# Accept transfermarkt.de / .com / .co.uk etc., OR path-only URLs (/<slug>/profil/<kind>/<id>),
# with or without https://, with or without trailing slash
URL_PATTERN = re.compile(
    r"(?:(?:https?://)?(?:www\.)?transfermarkt\.[a-z.]+)?/[^/]+/profil/(spieler|trainer|berater)/(\d+)/?",
    re.IGNORECASE,
)


def extract_url_info(url: str):
    """Return (kind, tm_id_int) or None if URL doesn't match TM profile pattern."""
    if not url or not isinstance(url, str):
        return None
    m = URL_PATTERN.search(url)
    if not m:
        return None
    return m.group(1).lower(), int(m.group(2))


def iter_contacts(network: dict):
    """Yield (contact_dict) for any field that looks like a contact list."""
    # Standard top-level "contacts" key
    for c in network.get("contacts", []) or []:
        if isinstance(c, dict):
            yield c
    # Some networks may also nest contacts under stations (only if dicts)
    for st in network.get("stations", []) or []:
        if not isinstance(st, dict):
            continue
        for c in st.get("contacts", []) or []:
            if isinstance(c, dict):
                yield c


def validate_network(net_path: Path):
    """Return list of issue dicts for this network."""
    try:
        net = json.load(open(net_path))
    except Exception as e:
        return [{
            "issue_type": "parse_error",
            "network": net_path.name,
            "error": str(e),
        }], 0

    issues = []
    contact_count = 0
    center_name = net.get("center") or net.get("coach", {}).get("name", "?")

    for c in iter_contacts(net):
        contact_count += 1
        name = c.get("name", "?")
        tm_id = c.get("tm_id")
        tm_url = c.get("tm_url")

        # Case 3: tm_id present but tm_url missing
        if tm_id and not tm_url:
            issues.append({
                "issue_type": "missing",
                "network": net_path.name,
                "center": center_name,
                "contact": name,
                "tm_id": tm_id,
            })
            continue

        # No tm_id and no tm_url → not an issue (e.g., unknown lehrgang grad)
        if not tm_url:
            continue

        info = extract_url_info(tm_url)
        if info is None:
            issues.append({
                "issue_type": "broken",
                "network": net_path.name,
                "center": center_name,
                "contact": name,
                "tm_id": tm_id,
                "tm_url": tm_url,
            })
            continue

        kind, url_tm_id = info
        # Case 1: tm_id in URL doesn't match contact.tm_id
        if tm_id and url_tm_id != tm_id:
            issues.append({
                "issue_type": "mismatched",
                "network": net_path.name,
                "center": center_name,
                "contact": name,
                "contact_tm_id": tm_id,
                "url_tm_id": url_tm_id,
                "url_kind": kind,
                "tm_url": tm_url,
            })
    return issues, contact_count


SLUG_PATTERN = re.compile(r"/([^/]+)/profil/", re.IGNORECASE)


def extract_slug(url: str):
    if not url:
        return None
    m = SLUG_PATTERN.search(url)
    return m.group(1).lower() if m else None


def name_to_slug(name: str) -> str:
    """Rough slugify for comparison: lowercase, remove diacritics, hyphens."""
    import unicodedata
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def spot_check_persons_master(targets: list[str]):
    """Look up specific names in persons_master and report URL/ID and URL/slug consistency."""
    pm_path = DATA / "persons_master.json"
    if not pm_path.exists():
        return []
    pm = json.load(open(pm_path)).get("persons", {})
    out = []
    for tid, p in pm.items():
        nm = p.get("name", "")
        if any(t in nm for t in targets):
            url = p.get("tm_url") or p.get("url")
            info = extract_url_info(url) if url else None
            url_slug = extract_slug(url) if url else None
            expected_slug = name_to_slug(nm)
            id_ok = info is not None and str(info[1]) == str(tid)
            # Slug mismatch flag: URL slug doesn't share any token with the expected slug
            slug_ok = False
            if url_slug and expected_slug:
                url_tokens = set(url_slug.split("-"))
                exp_tokens = set(expected_slug.split("-"))
                slug_ok = bool(url_tokens & exp_tokens)
            row = {
                "name": nm,
                "tm_id_master": tid,
                "tm_url": url,
                "url_kind": info[0] if info else None,
                "url_tm_id": info[1] if info else None,
                "url_slug": url_slug,
                "expected_slug": expected_slug,
                "type": p.get("type"),
                "id_consistent": id_ok,
                "slug_consistent": slug_ok,
            }
            out.append(row)
    return out


def main():
    ap = argparse.ArgumentParser(description="Validate tm_url integrity across network JSONs")
    ap.add_argument("--all", action="store_true", help="Scan all networks (default 50 random)")
    ap.add_argument("--sample", type=int, default=50, help="Random sample size (default 50)")
    ap.add_argument("--seed", type=int, default=42, help="RNG seed for reproducibility")
    ap.add_argument("--dry-run", action="store_true", help="Don't write output file")
    args = ap.parse_args()

    if not NETWORKS.exists():
        print(f"ERROR: {NETWORKS} not found", file=sys.stderr)
        sys.exit(1)

    files = sorted(NETWORKS.glob("*.json"))
    if not args.all:
        random.seed(args.seed)
        if len(files) > args.sample:
            files = random.sample(files, args.sample)

    print(f"Scanning {len(files)} network files...")

    all_issues = {"mismatched": [], "broken": [], "missing": [], "parse_error": []}
    total_contacts = 0
    for f in files:
        issues, n = validate_network(f)
        total_contacts += n
        for iss in issues:
            t = iss.get("issue_type", "parse_error")
            all_issues.setdefault(t, []).append(iss)

    summary = {k: len(v) for k, v in all_issues.items()}
    ok_count = total_contacts - sum(summary.values())
    summary["ok"] = ok_count

    spot = spot_check_persons_master(["Marcel Klos", "Johannes Spors"])

    result = {
        "scanned_networks": len(files),
        "total_contacts": total_contacts,
        "summary": summary,
        "spot_check_klos_spors": spot,
        **all_issues,
    }

    if not args.dry_run:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"Wrote {OUT}")

    print("\n=== Summary ===")
    print(f"Networks scanned: {len(files)}")
    print(f"Total contacts:   {total_contacts}")
    for k in ("mismatched", "broken", "missing", "parse_error", "ok"):
        print(f"  {k:12} {summary.get(k, 0):>6}")

    if spot:
        print("\n=== Spot-check Klos / Spors (persons_master) ===")
        for r in spot:
            id_tag = "ID-OK" if r["id_consistent"] else "ID-BAD"
            slug_tag = "SLUG-OK" if r["slug_consistent"] else "SLUG-BAD"
            print(f"  [{id_tag} | {slug_tag}] {r['name']:30} | master_id={r['tm_id_master']:>8} | url_id={r['url_tm_id']} | url_slug={r['url_slug']} (expected: {r['expected_slug']})")

    # Sample print
    if all_issues["mismatched"]:
        print("\n=== Sample MISMATCHED (URL points at wrong person) ===")
        for iss in all_issues["mismatched"][:10]:
            print(f"  {iss['contact']:30} | net={iss['network']:>12} | "
                  f"contact_id={iss['contact_tm_id']:>8} ≠ url_id={iss['url_tm_id']}")

    if all_issues["broken"]:
        print("\n=== Sample BROKEN (URL pattern fail) ===")
        for iss in all_issues["broken"][:5]:
            print(f"  {iss['contact']:30} | net={iss['network']:>12} | url={iss['tm_url']}")


if __name__ == "__main__":
    main()
