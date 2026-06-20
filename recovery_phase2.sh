#!/bin/bash
# recovery_phase2.sh — re-scrape squads + GS + playing-careers (Phase 2 of recovery).
#
# data/squads/ (3,324 lost) and data/gemeinsame_spiele/ (308 lost) need full TM scrape.
# Runs squad + GS in parallel (different TM endpoints), then rebuild affected networks.
#
# Steps:
#   0. Targeted build: Flick (tm 67), since he isn't in BL staff (Barcelona)
#   1. Squad scrape (live, ~6-8h) — restores data/squads/*.json + rebuild persons_index
#   2. GS scrape in parallel (~3-4h) — restores data/gemeinsame_spiele/{tm}.json
#   3. Wait both
#   4. Rebuild persons_master (merge-only)
#   5. Full network + dashboard rebuild (BL/SD/NLZ) — incorporates Mitspieler + GS
#   6. Deploy
#   7. ntfy
set -euo pipefail

BASE="/Users/cmk/Documents/CMK Digital/Football Coaches DB"
cd "$BASE"

TS=$(date +%Y%m%d_%H%M%S)
LOG="logs/phase2_${TS}.log"
mkdir -p logs
exec > >(tee -a "$LOG") 2>&1

log() { echo "[$(date +%H:%M:%S)] $*"; }
notify() {
  local msg="$1"
  local prio="${2:-default}"
  /usr/bin/curl -s -X POST -H "Priority: $prio" -d "$msg" "https://ntfy.sh/cmk-coachdb" >/dev/null || true
}
fail() { log "✗ FAILED at: $1"; notify "Coach-DB Phase2 FAILED: $1" "urgent"; exit 1; }

log "=== Phase 2 started ==="

# --- Step 0: Flick targeted build ---
log "Step 0: Flick targeted build (tm 67)"
if [ ! -f "data/networks/67.json" ]; then
  python3 execution/build_coach_network.py --tm-id 67 2>&1 | tail -3 || fail "Flick network build"
  python3 execution/generate_dashboard.py \
    --network data/networks/67.json \
    --output output/dashboards/hansi_flick_network.html 2>&1 | tail -3 \
    || fail "Flick dashboard"
fi
log "  ✓ Flick built"

# --- Step 1+2: squad + GS scrapes in parallel ---
log "Step 1: launch squad scrape (live, ~6-8h)"
caffeinate -s python3 execution/scrape_squads.py > "logs/phase2_squads_${TS}.log" 2>&1 &
SQUAD_PID=$!
log "  Squad PID: $SQUAD_PID"

log "Step 2: launch GS scrape (live, ~3-4h)"
caffeinate -s python3 execution/scrape_gemeinsame_spiele.py > "logs/phase2_gs_${TS}.log" 2>&1 &
GS_PID=$!
log "  GS PID: $GS_PID"

log "Step 3: wait for both scrapes"
SQUAD_RC=0
GS_RC=0
wait $SQUAD_PID || SQUAD_RC=$?
log "  Squad scrape exited rc=$SQUAD_RC"
wait $GS_PID || GS_RC=$?
log "  GS scrape exited rc=$GS_RC"

SQUAD_COUNT=$(ls data/squads/*.json 2>/dev/null | wc -l | tr -d ' ')
GS_COUNT=$(ls data/gemeinsame_spiele/*.json 2>/dev/null | wc -l | tr -d ' ')
log "  Squads: $SQUAD_COUNT  GS: $GS_COUNT"

if [ "$SQUAD_COUNT" -lt 2000 ]; then
  log "  WARN: squad count $SQUAD_COUNT below expected ~3,000"
fi
if [ "$GS_COUNT" -lt 200 ]; then
  log "  WARN: GS count $GS_COUNT below expected ~300"
fi

# --- Step 4: merge ---
log "Step 4: rebuild persons_master"
python3 execution/scrape_person_profiles.py --merge-only 2>&1 | tail -5 \
  || fail "Step 4: merge-only"

# --- Step 5: rebuild networks ---
log "Step 5: rebuild networks (BL + SD + NLZ) with Mitspieler + GS enrichment"
caffeinate -s python3 execution/generate_all_bl_coaches.py \
  --leagues BL1 BL2 BL3 \
  --include-historical \
  --include-decision-makers \
  --include-nlz 2>&1 | tail -20 \
  || fail "Step 5: generate_all"

# Re-include Hürzeler + Croci-Torti + Flick (non-BL)
for tm in 48076 59028 67; do
  python3 execution/build_coach_network.py --tm-id $tm 2>&1 | tail -2 || true
  slug=$(python3 -c "
import json, sys; sys.path.insert(0, 'execution')
from lib.normalization import slugify
m = json.load(open('data/persons_master.json'))['persons']
print(slugify(m.get('$tm', {}).get('name', 'unknown')))
")
  python3 execution/generate_dashboard.py \
    --network data/networks/$tm.json \
    --output output/dashboards/${slug}_network.html 2>&1 | tail -2 || true
done

log "Step 6: regenerate index + clubs"
python3 execution/generate_all_bl_coaches.py \
  --leagues BL1 BL2 BL3 --all-networks --include-historical \
  --include-decision-makers --include-nlz --skip-networks 2>&1 | tail -5 \
  || fail "Step 6a: index"
python3 execution/generate_club_pages.py 2>&1 | tail -5 || fail "Step 6b: clubs"

log "Step 7: Vercel deploy"
cd output
DEPLOY_URL=$(npx vercel deploy --prod --yes --scope cmk2299s-projects 2>&1 | tail -1)
cd "$BASE"
log "  Deploy URL: $DEPLOY_URL"

log "Step 8: smoke tests"
for slug in alexander_blessin_network fabian_huerzeler_network adi_huetter_network mattia_croci_torti_network hansi_flick_network dieter_hecking_network florian_kohfeldt_network vincent_kompany_network; do
  CODE=$(/usr/bin/curl -o /dev/null -s -w "%{http_code}" "https://coach-network-explorer.vercel.app/dashboards/${slug}.html")
  if [ "$CODE" = "200" ]; then
    log "  ✓ /${slug}.html → $CODE"
  else
    log "  ✗ /${slug}.html → $CODE"
  fi
done

NET_COUNT=$(ls data/networks/ | wc -l | tr -d ' ')
DASH_COUNT=$(ls output/dashboards/*_network.html 2>/dev/null | wc -l | tr -d ' ')
log "=== Phase 2 DONE ($NET_COUNT networks, $DASH_COUNT dashboards, $SQUAD_COUNT squads, $GS_COUNT GS) ==="
notify "Coach-DB Phase 2 COMPLETE: $NET_COUNT networks, $DASH_COUNT dashboards, $SQUAD_COUNT squads, $GS_COUNT GS"
