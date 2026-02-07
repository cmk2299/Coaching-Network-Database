#!/usr/bin/env python3
"""
Cache Verification Script
Ensures preloaded caches are complete before deployment

Run this before committing cache files to GitHub:
    python execution/verify_caches.py

Returns exit code 1 if any caches are invalid (stub data)
"""

import json
import sys
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent.parent
PRELOAD_DIR = BASE_DIR / "tmp" / "preloaded"

# Minimum file sizes (in KB)
MIN_CACHE_SIZE_KB = 50  # Stub data is < 1KB, real caches are 150-250KB

def verify_cache_file(filepath: Path) -> tuple[bool, str]:
    """
    Verify a single cache file is complete.
    Returns (is_valid, message)
    """
    # Check file exists
    if not filepath.exists():
        return False, "File does not exist"

    # Check file size
    size_bytes = filepath.stat().st_size
    size_kb = size_bytes / 1024

    if size_kb < MIN_CACHE_SIZE_KB:
        return False, f"File too small ({size_kb:.1f} KB < {MIN_CACHE_SIZE_KB} KB) - likely stub data"

    # Check JSON structure
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return False, f"Invalid JSON: {e}"

    # Check required keys
    required_keys = ["coach_name", "profile", "decision_makers", "_preloaded_at"]
    missing = [k for k in required_keys if k not in data]

    if missing:
        return False, f"Missing keys: {', '.join(missing)}"

    # Check decision_makers structure
    dm = data.get("decision_makers")
    if not dm or not isinstance(dm, dict):
        return False, "decision_makers is missing or invalid"

    if "total" not in dm:
        return False, "decision_makers missing 'total' key"

    # Check decision_makers has data (if enriched)
    total = dm.get("total", 0)
    hiring_managers = len(dm.get("hiring_managers", []))
    sports_directors = len(dm.get("sports_directors", []))

    # Not all coaches have decision makers, so just verify structure
    # Don't fail if total=0, but warn
    if total == 0:
        return True, f"⚠️  Valid but no decision makers ({size_kb:.0f} KB)"

    # Success
    return True, f"✅ Valid ({size_kb:.0f} KB, {total} decision makers: {hiring_managers} HM, {sports_directors} SD)"

def main():
    """Verify all preloaded caches."""
    print("="*70)
    print("CACHE VERIFICATION")
    print("="*70)
    print()

    if not PRELOAD_DIR.exists():
        print(f"❌ ERROR: Preload directory not found: {PRELOAD_DIR}")
        return 1

    cache_files = sorted(PRELOAD_DIR.glob("*.json"))

    if not cache_files:
        print(f"⚠️  WARNING: No cache files found in {PRELOAD_DIR}")
        return 1

    print(f"Found {len(cache_files)} cache file(s):")
    print()

    invalid_count = 0

    for filepath in cache_files:
        is_valid, message = verify_cache_file(filepath)

        status = "✅" if is_valid else "❌"
        print(f"{status} {filepath.name:30s} {message}")

        if not is_valid:
            invalid_count += 1

    print()
    print("="*70)

    if invalid_count > 0:
        print(f"❌ FAILED: {invalid_count} invalid cache file(s)")
        print()
        print("DO NOT COMMIT these files to GitHub!")
        print("Run the preload script to regenerate:")
        print("  python execution/preload_coach_data.py --coach <name> --force")
        print()
        return 1
    else:
        print(f"✅ SUCCESS: All {len(cache_files)} cache files are valid")
        print()
        print("Safe to commit to GitHub:")
        print("  git add tmp/preloaded/*.json")
        print("  git commit -m 'Update preloaded caches'")
        print("  git push")
        print()
        return 0

if __name__ == "__main__":
    sys.exit(main())
