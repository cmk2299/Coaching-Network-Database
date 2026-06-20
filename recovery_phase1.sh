#!/bin/bash
# recovery_phase1.sh — rebuild networks + dashboards + deploy.
#
# Pre-conditions verified (2026-05-20):
#   ✓ data/person_profiles/  : 82,189 files
#   ✓ data/staff/            : 999 files
#   ✓ data/persons_master    : 27 MB (trainer-only)
#   ✓ Dual-ID overwrites restored (Blessin et al.)
#   ✓ generate_dashboard.py mkdir-parent fix applied
#
# What still needs Phase 2 (not blocking deploy):
#   - data/squads/, data/gemeinsame_spiele/, data/coach_playing_careers/
#
# Steps:
#   1. Active BL1+BL2+BL3 head-coach networks + dashboards (incl. historical)
#   2. SD networks (build_all_sd_networks.py)
#   3. NLZ networks (build_all_nlz_networks.py)
#   4. Regenerate index with --all-networks + --include-historical
#      --include-decision-makers --include-nlz
#   5. Club pages
#   6. Vercel deploy
#   7. Smoke-test Blessin/Hürzeler/Hütter/Croci-Torti
set -euo pipefail

BASE="/Users/cmk/Documents/CMK Digital/Football Coaches DB"
cd "$BASE"
TS=$(date +%Y%m%d_%H%M%S)
LOG="logs/phase1_${TS}.log"
mkdir -p logs
exec > >(tee -a "$LOG") 2>&1

log() { echo "[$(date +%H:%M:%S)] $*"; }
notify() {
  local msg="$1"; local prio="${2:-default}"
  curl -s -X POST -H "Priority: $prio" -d "$msg" "https://ntfy.sh/cmk-coachdb" >/dev/null || true
}
fail() { log "✗ FAILED at: $1"; notify "Phase1 FAIL: $1" "urgent"; exit 1; }

log "=== Phase 1 started ==="

log "Step 1: active BL coaches + historical"
caffeinate -s python3 execution/generate_all_bl_coaches.py \
  --leagues BL1 BL2 BL3 \
  --include-historical --skip-index \
  || fail "Step 1"

NET1=$(ls data/networks/ | wc -l | tr -d ' ')
log "  networks after Step 1: $NET1"

log "Step 2: SD networks"
caffeinate -s python3 execution/build_all_sd_networks.py || fail "Step 2"
NET2=$(ls data/networks/ | wc -l | tr -d ' ')
log "  networks after Step 2: $NET2"

log "Step 3: NLZ networks"
caffeinate -s python3 execution/build_all_nlz_networks.py || fail "Step 3"
NET3=$(ls data/networks/ | wc -l | tr -d ' ')
log "  networks after Step 3: $NET3"

log "Step 4: regenerate index with all sections"
python3 execution/generate_all_bl_coaches.py \
  --leagues BL1 BL2 BL3 \
  --all-networks --include-historical \
  --include-decision-makers --include-nlz \
  --skip-networks \
  || fail "Step 4"

DASH=$(ls output/dashboards/*_network.html 2>/dev/null | wc -l | tr -d ' ')
log "  dashboards on disk: $DASH"

log "Step 5: club pages"
python3 execution/generate_club_pages.py || fail "Step 5"

log "Step 6: Vercel deploy"
cd output
DEPLOY_OUT=$(npx vercel deploy --prod --yes --scope cmk2299s-projects 2>&1)
DEPLOY_URL=$(echo "$DEPLOY_OUT" | grep -oE 'https://[a-z0-9-]+\.vercel\.app' | head -1)
cd "$BASE"
log "  Deploy URL: $DEPLOY_URL"
[ -n "$DEPLOY_URL" ] || fail "Step 6 (no URL extracted)"

log "Step 7: smoke tests"
SMOKE_FAIL=0
sleep 5  # give vercel a moment to propagate
for slug in "alexander_blessin_network" "fabian_huerzeler_network" "adi_huetter_network" "mattia_croci_torti_network"; do
  CODE=$(curl -o /dev/null -s -w "%{http_code}" "https://coach-network-explorer.vercel.app/dashboards/${slug}.html")
  if [ "$CODE" = "200" ]; then
    log "  ✓ /${slug}.html → $CODE"
  else
    log "  ✗ /${slug}.html → $CODE"
    SMOKE_FAIL=$((SMOKE_FAIL+1))
  fi
done

log "=== Phase 1 DONE ($NET3 networks, $DASH dashboards) ==="
if [ "$SMOKE_FAIL" -gt 0 ]; then
  notify "Phase1 DONE w/ $SMOKE_FAIL smoke fails — $DASH dashboards live" "high"
  exit 2
fi
notify "Phase1 SUCCESS: $DASH dashboards live, all smokes 200"
