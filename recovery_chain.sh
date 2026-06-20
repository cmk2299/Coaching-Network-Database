#!/bin/bash
# recovery_chain.sh — auto-recover from the 2026-05-19 worktree-collision data wipe.
#
# Steps (in order):
#   0. Wait for reparse PID 9932 to exit
#   1. Revert CACHE_DAYS to 30 in scrape_person_profiles.py
#   2. Run fix_dual_id_tm_urls.py (rewrite tm_urls at source)
#   3. Merge persons_master.json from patched profiles
#   4. Re-scrape staff files (force, --staff-only)
#   5. Rebuild all coach networks + dashboards
#   6. Regenerate club pages
#   7. Deploy to Vercel
#   8. Smoke-test 3 known-fragile dashboards
#   9. ntfy notification on success / failure
#
# Logs everything to logs/recovery_chain_<timestamp>.log
set -euo pipefail

BASE="/Users/cmk/Documents/CMK Digital/Football Coaches DB"
cd "$BASE"

TS=$(date +%Y%m%d_%H%M%S)
LOG="logs/recovery_chain_${TS}.log"
mkdir -p logs
exec > >(tee -a "$LOG") 2>&1

REPARSE_PID=9932

log() { echo "[$(date +%H:%M:%S)] $*"; }

notify() {
  local msg="$1"
  local prio="${2:-default}"
  curl -s -X POST -H "Priority: $prio" -d "$msg" "https://ntfy.sh/cmk-coachdb" >/dev/null || true
}

fail() {
  log "✗ FAILED at: $1"
  notify "Coach-DB Recovery FAILED at: $1" "urgent"
  exit 1
}

log "=== Recovery Chain Started ==="
log "Watching reparse PID $REPARSE_PID"

# --- Step 0: wait for reparse ---
while kill -0 "$REPARSE_PID" 2>/dev/null; do
  PROFILES=$(ls data/person_profiles/ 2>/dev/null | wc -l | tr -d ' ')
  log "  reparse alive — $PROFILES profiles on disk"
  sleep 300
done
log "✓ Reparse PID $REPARSE_PID has exited"

# Sanity: at least 70k profiles expected
PROFILES=$(ls data/person_profiles/ 2>/dev/null | wc -l | tr -d ' ')
log "  Profiles after reparse: $PROFILES"
if [ "$PROFILES" -lt 70000 ]; then
  fail "Profile count $PROFILES too low (expected ~82k)"
fi

# --- Step 1: revert CACHE_DAYS ---
log "Step 1: revert CACHE_DAYS to 30"
python3 -c "
from pathlib import Path
p = Path('execution/scrape_person_profiles.py')
text = p.read_text()
import re
new = re.sub(r'CACHE_DAYS\s*=\s*9999.*', 'CACHE_DAYS = 30', text)
if new == text:
    print('  (already reverted or pattern miss — skipping)')
else:
    p.write_text(new)
    print('  ✓ CACHE_DAYS reset to 30')
" || fail "Step 1: revert CACHE_DAYS"

# --- Step 2: Dual-ID URL patch ---
log "Step 2: Dual-ID tm_url patch"
python3 execution/fix_dual_id_tm_urls.py || fail "Step 2: fix_dual_id_tm_urls"

# --- Step 3: merge persons_master ---
log "Step 3: rebuild persons_master.json"
python3 execution/scrape_person_profiles.py --merge-only || fail "Step 3: merge-only"
MASTER_SIZE=$(stat -f %z data/persons_master.json)
log "  persons_master.json: $MASTER_SIZE bytes"

# --- Step 4: re-scrape staff (live) ---
log "Step 4: re-scrape staff (live, expect 30-60min)"
caffeinate -s python3 execution/scrape_squads.py --staff-only --force \
  || fail "Step 4: scrape_squads --staff-only"
STAFF_COUNT=$(ls data/staff/ 2>/dev/null | wc -l | tr -d ' ')
log "  Staff files: $STAFF_COUNT"
if [ "$STAFF_COUNT" -lt 500 ]; then
  log "  WARN: staff count $STAFF_COUNT is below expected ~900-1050"
fi

# --- Step 5: rebuild networks + dashboards ---
log "Step 5: rebuild all networks + dashboards"
caffeinate -s python3 execution/generate_all_bl_coaches.py \
  --leagues BL1 BL2 BL3 \
  --include-historical --include-decision-makers --include-nlz \
  || fail "Step 5: generate_all_bl_coaches"

NET_COUNT=$(ls data/networks/ 2>/dev/null | wc -l | tr -d ' ')
DASH_COUNT=$(ls output/dashboards/*_network.html 2>/dev/null | wc -l | tr -d ' ')
log "  Networks: $NET_COUNT, Dashboards: $DASH_COUNT"

# --- Step 6: club pages ---
log "Step 6: club pages"
python3 execution/generate_club_pages.py || fail "Step 6: generate_club_pages"

# --- Step 7: deploy ---
log "Step 7: Vercel deploy"
cd output
DEPLOY_URL=$(npx vercel deploy --prod --yes --scope cmk2299s-projects 2>&1 | tail -1)
cd "$BASE"
log "  Deploy URL: $DEPLOY_URL"

# --- Step 8: smoke tests ---
log "Step 8: smoke-test dashboards"
SMOKE_FAIL=0
for slug in "fabian-hurzeler_network" "adi-hutter_network" "mattia-croci-torti_network" "alexander_blessin_network"; do
  CODE=$(curl -o /dev/null -s -w "%{http_code}" "https://coach-network-explorer.vercel.app/dashboards/${slug}.html")
  if [ "$CODE" = "200" ]; then
    log "  ✓ /${slug}.html → $CODE"
  else
    log "  ✗ /${slug}.html → $CODE"
    SMOKE_FAIL=$((SMOKE_FAIL+1))
  fi
done

if [ "$SMOKE_FAIL" -gt 0 ]; then
  log "  $SMOKE_FAIL smoke tests failed"
  notify "Coach-DB Recovery FINISHED with $SMOKE_FAIL smoke failures" "high"
  exit 2
fi

log "=== Recovery Chain Completed ✓ ==="
notify "Coach-DB Recovery COMPLETE: $NET_COUNT networks, $DASH_COUNT dashboards, deploy live"
