#!/bin/bash
# run_mvp.sh — One-click daily pipeline: staff refresh → network rebuild → deploy
#
# Reconstructed 2026-05-21 after worktree-collision wipe lost the previous version.
# Specified behaviour (per CLAUDE.md + directives/DIRECTIVE_2026-05-21_evening_deploy.md):
#
#   1. Staff scrape with --max-age-days=1 (only re-fetch stale files)
#   2. Rebuild ALL coach networks (BL1/2/3 + historical + SDs + NLZ)
#   3. Regenerate all dashboards from canonical network JSONs (lazy >500KB)
#   4. Generate club pages
#   5. Vercel production deploy
#   6. ntfy push to cmk-coachdb
#
# Activated by LaunchAgent com.footballdb.daily-refresh @ 06:00 daily.
# Also runnable manually: bash run_mvp.sh
#
# Flags:
#   --skip-staff       skip staff scrape (use existing files)
#   --skip-deploy      build locally, skip Vercel push
#   --max-age-days=N   stale threshold for staff (default 1)

set -euo pipefail

BASE="/Users/cmk/Documents/CMK Digital/Football Coaches DB"
cd "$BASE"

TS=$(date +%Y%m%d_%H%M%S)
LOG="logs/run_mvp_${TS}.log"
mkdir -p logs
exec > >(tee -a "$LOG") 2>&1

SKIP_STAFF=0
SKIP_DEPLOY=0
MAX_AGE=1
for arg in "$@"; do
  case "$arg" in
    --skip-staff)      SKIP_STAFF=1 ;;
    --skip-deploy)     SKIP_DEPLOY=1 ;;
    --max-age-days=*)  MAX_AGE="${arg#--max-age-days=}" ;;
  esac
done

log() { echo "[$(date +%H:%M:%S)] $*"; }
notify() {
  local msg="$1"; local prio="${2:-default}"
  /usr/bin/curl -s -X POST -H "Priority: $prio" -d "$msg" "https://ntfy.sh/cmk-coachdb" >/dev/null || true
}
fail() {
  log "✗ FAILED: $1"
  notify "Coach-DB run_mvp FAILED at: $1 ($(date '+%H:%M'))" "urgent"
  exit 1
}

log "=== run_mvp.sh started ==="
log "  skip_staff=$SKIP_STAFF  skip_deploy=$SKIP_DEPLOY  max_age_days=$MAX_AGE"

# --- Step 1: Staff scrape ---
if [ "$SKIP_STAFF" -eq 0 ]; then
  log "Step 1: staff scrape (max-age=${MAX_AGE}d)"
  caffeinate -s python3 execution/scrape_squads.py --staff-only --max-age-days=${MAX_AGE} 2>&1 | tail -10 \
    || fail "Step 1: staff scrape"
  STAFF_COUNT=$(ls data/staff/*.json 2>/dev/null | wc -l | tr -d ' ')
  log "  Staff files: $STAFF_COUNT"
else
  log "Step 1: skipped (--skip-staff)"
fi

# --- Step 1b: Auto-discover newly-hired head coaches (2026-05-23) ---
# When the staff scrape surfaces a new HC at a BL1/BL2/BL3 club, this script
# auto-scrapes their TM profile and builds their network — so the next step
# (full rebuild) includes them. Without this, new HCs would be invisible
# until manually added.
log "Step 1b: auto-discover new BL head coaches"
caffeinate -s python3 execution/discover_new_head_coaches.py 2>&1 | tail -15 \
  || log "  ⚠ Step 1b had errors (non-fatal, continuing)"

# --- Step 2: Rebuild all coach networks ---
log "Step 2: rebuild all coach networks (BL1/2/3 + historical + SDs + NLZ)"
caffeinate -s python3 execution/generate_all_bl_coaches.py \
  --leagues BL1 BL2 BL3 \
  --all-networks \
  --include-historical \
  --include-decision-makers \
  --include-nlz 2>&1 | tail -15 \
  || fail "Step 2: generate_all_bl_coaches"

NET_COUNT=$(ls data/networks/*.json 2>/dev/null | wc -l | tr -d ' ')
DASH_COUNT=$(ls output/dashboards/*_network.html 2>/dev/null | wc -l | tr -d ' ')
log "  Networks: $NET_COUNT, Dashboards: $DASH_COUNT"

# --- Step 3: Regenerate dashboards from canonical sources ---
# Ensures F2 fix (canonical data/networks/*.json as source, not corrupt HTML).
log "Step 3: regenerate dashboards (lazy >500KB)"
python3 execution/regenerate_dashboards.py --lazy 500000 2>&1 | tail -5 \
  || fail "Step 3: regenerate_dashboards"

# --- Step 4: Club pages ---
log "Step 4: generate club pages"
python3 execution/generate_club_pages.py 2>&1 | tail -5 \
  || fail "Step 4: generate_club_pages"

# --- Step 4b: Quality gate (2026-06-20) — BLOCK deploy on logic/scoring defects ---
# Root-cause guard against the recurring silent-regression class (dual-ID
# Frankensteins, stale stamps, strength/order drift). A bad build must not reach
# the paying client. Override with --skip-gate only for emergencies.
if [ "${SKIP_GATE:-0}" -eq 0 ]; then
  log "Step 4b: quality gate (logic + scoring audit)"
  python3 execution/logic_audit.py   2>&1 | tail -3 || fail "Step 4b: logic_audit found defects — deploy blocked"
  python3 execution/scoring_audit.py 2>&1 | tail -3 || fail "Step 4b: scoring_audit found defects — deploy blocked"
  # Volume gate: block on catastrophic artifact loss (the 2026-05-21 wipe class)
  python3 execution/validate_pipeline.py 2>&1 | tail -8 || fail "Step 4b: pipeline volume regressed — deploy blocked (re-baseline if intentional)"
  log "  ✓ Quality gate passed"
else
  log "Step 4b: quality gate SKIPPED (SKIP_GATE=1)"
fi

# --- Step 5: Deploy ---
if [ "$SKIP_DEPLOY" -eq 0 ]; then
  log "Step 5: Vercel production deploy"
  cd output
  DEPLOY_OUT=$(npx vercel deploy --prod --yes --scope cmk2299s-projects 2>&1)
  DEPLOY_URL=$(echo "$DEPLOY_OUT" | grep -oE "https://coach-network-explorer-[a-z0-9]+-cmk2299s-projects.vercel.app" | head -1)
  cd "$BASE"
  log "  Deploy: $DEPLOY_URL"
  sleep 15

  # Smoke test — HTTP 200 AND content-level sanity (a blank/broken index can
  # still return 200). Assert the index actually lists coaches.
  INDEX_HTML=$(/usr/bin/curl -s -w "\n%{http_code}" "https://coach-network-explorer.vercel.app/")
  CODE=$(printf '%s' "$INDEX_HTML" | tail -1)
  ROWS=$(printf '%s' "$INDEX_HTML" | grep -oc 'class="row-club"' || true)
  if [ "$CODE" != "200" ]; then
    fail "Step 5: production index returned $CODE"
  fi
  if [ "${ROWS:-0}" -lt 50 ]; then
    fail "Step 5: production index only has $ROWS coach rows (<50) — likely a broken build"
  fi
  log "  ✓ Index smoke: 200, $ROWS coach rows"
else
  log "Step 5: skipped (--skip-deploy)"
fi

log "=== run_mvp.sh DONE (networks=$NET_COUNT dashboards=$DASH_COUNT) ==="
notify "Coach-DB run_mvp OK ($(date '+%H:%M')) — $NET_COUNT networks, $DASH_COUNT dashboards live"
