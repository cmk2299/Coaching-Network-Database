#!/usr/bin/env python3
"""
scaffold_workflow_assets.py — Sprint I (Berater-CRM-Workflow)

Idempotent: verifies that workflow.js + workflow.css exist in output/assets/.
The actual asset files are checked in to the repo. This script is the
first step in run_crm_workflow.sh and prints a status summary so the
log shows whether the surface assets are in place before the dashboard
template gets patched.

Exit code: 0 if both files present, 1 otherwise.
"""

from pathlib import Path
import sys

BASE = Path(__file__).resolve().parent.parent
ASSETS = BASE / "output" / "assets"
EXPECTED = {
    "workflow.js":  "Berater-CRM-Workflow vanilla JS (Sprint I)",
    "workflow.css": "Berater-CRM-Workflow styling (Sprint I)",
}


def main() -> int:
    missing = []
    for fname, desc in EXPECTED.items():
        path = ASSETS / fname
        if path.exists() and path.stat().st_size > 0:
            print(f"  ok  {fname:14s} {path.stat().st_size:>6d} bytes  — {desc}")
        else:
            print(f"  ✗   {fname:14s} MISSING — {desc}")
            missing.append(fname)
    if missing:
        print("")
        print(f"  → {len(missing)} asset(s) missing under {ASSETS}/.")
        print("    Restore from git or re-run scaffold (see directives/berater_crm_workflow.md).")
        return 1
    print("")
    print("  → CRM-Workflow assets ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
