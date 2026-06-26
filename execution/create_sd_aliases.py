#!/usr/bin/env python3
"""Erstelle Alias-Files für SD-Networks ohne _sd_ Suffix.

Hintergrund: SD-Networks werden als `{slug}_sd_network.html` generiert
(Suffix vermeidet Slug-Kollisionen mit Trainern gleichen Namens).
ABER: Cross-Drilldown aus Coach-Dashboards verlinkt teilweise auf
`{slug}_network.html` (ohne SD-Suffix), weil das build_dashboard_index
nicht zwischen Coach- und SD-Type unterscheidet.

Quick-Fix: Pro SD-Network einen Copy als `{slug}_network.html` ablegen,
sodass beide URLs funktionieren. Drilldown-JSONs analog.

Wenn ein File mit dem Alias-Namen bereits existiert (echter Coach mit
gleichem Namen), wird NICHT überschrieben — Console-Warning.

Usage:
  python3 execution/create_sd_aliases.py             # alle Aliases erzeugen
  python3 execution/create_sd_aliases.py --dry-run   # nur listen
  python3 execution/create_sd_aliases.py --remove    # alle Aliases entfernen
"""
import argparse
import shutil
from pathlib import Path

BASE = Path(__file__).parent.parent
DASH = BASE / "output" / "dashboards"


def find_sd_files() -> list[Path]:
    return sorted(DASH.glob("*_sd_network.html"))


def alias_path(sd_path: Path) -> Path:
    return sd_path.parent / sd_path.name.replace("_sd_network", "_network")


def alias_drilldown_path(sd_path: Path) -> Path:
    drill = sd_path.parent / sd_path.name.replace(
        "_sd_network.html", "_sd_network_drilldown.json"
    )
    if not drill.exists():
        return None
    return drill.parent / drill.name.replace("_sd_network_", "_network_")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--remove", action="store_true",
                        help="entferne alle alias files (idempotent cleanup)")
    args = parser.parse_args()

    sd_files = find_sd_files()
    print("\n=== SD-Alias-Generation ===")
    print(f"Found {len(sd_files)} SD-Network HTMLs in {DASH}")

    created = 0
    skipped_collision = 0
    removed = 0

    for sd in sd_files:
        alias = alias_path(sd)
        sd_drill = sd.parent / sd.name.replace(".html", "_drilldown.json")
        alias_drill = (
            sd_drill.parent / sd_drill.name.replace("_sd_network_", "_network_")
            if sd_drill.exists() else None
        )

        if args.remove:
            for f in (alias, alias_drill):
                if f and f.exists() and f.read_text(errors="ignore")[:200] == \
                        sd.read_text(errors="ignore")[:200]:
                    # nur entfernen, wenn Inhalt mit SD-Original matched (Sicherheit)
                    f.unlink()
                    removed += 1
            continue

        if alias.exists():
            # Check: ist's ein echter Coach (Inhalt anders) oder schon Alias?
            if alias.read_text(errors="ignore")[:500] != sd.read_text(errors="ignore")[:500]:
                print(f"  ⚠ COLLISION: {alias.name} existiert als echter Coach, "
                      f"alias übersprungen")
                skipped_collision += 1
                continue

        if args.dry_run:
            print(f"  would copy: {sd.name} → {alias.name}")
            if alias_drill and not alias_drill.exists():
                print("             + drilldown alias")
            created += 1
            continue

        shutil.copy(sd, alias)
        if alias_drill and not alias_drill.exists() and sd_drill.exists():
            shutil.copy(sd_drill, alias_drill)
        created += 1

    if args.remove:
        print(f"\n  ✓ Removed {removed} alias files")
    else:
        verb = "would create" if args.dry_run else "created"
        print(f"\n  ✓ {verb} {created} aliases, {skipped_collision} collisions skipped")
        if not args.dry_run:
            print("\nNext: cd output && npx vercel deploy --prod --yes "
                  "--scope cmk2299s-projects")


if __name__ == "__main__":
    main()
