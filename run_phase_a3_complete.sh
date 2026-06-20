#!/bin/bash
# run_phase_a3_complete.sh — Finish what Sprint A3+B+D should have done.
#
# After the Phase A3 reader fix (preload_all_profiles now namespace-aware),
# all existing networks need rebuilding (they were built with empty profiles
# dict and are degraded). Plus the silently-failed Sprint B/D need re-run.
#
# Steps:
#   1. Full network + dashboard rebuild with corrected profile loader
#   2. NLZ networks (553 trainers via build_all_nlz_networks.py)
#   3. National-coach networks (32 trainers)
#   4. Final dashboard regen
#   5. Deploy
#   6. Smoke (follow redirects)

set -uo pipefail

BASE="/Users/cmk/Documents/CMK Digital/Football Coaches DB"
cd "$BASE"

TS=$(date +%Y%m%d_%H%M%S)
LOG="logs/phase_a3_${TS}.log"
mkdir -p logs
exec > >(tee -a "$LOG") 2>&1

log() { echo "[$(date +%H:%M:%S)] $*"; }
notify() {
  local msg="$1"; local prio="${2:-default}"
  /usr/bin/curl -s -X POST -H "Priority: $prio" -d "$msg" "https://ntfy.sh/cmk-coachdb" >/dev/null || true
}

log "=== Phase A3 completion chain started ==="
notify "Phase A3 fix-and-finish STARTED ($(date '+%H:%M'))"

# ── Step 1: Full network rebuild with corrected profile loader ───────
log "Step 1: full network rebuild — all existing 660 networks were degraded"
caffeinate -s python3 execution/generate_all_bl_coaches.py \
  --leagues BL1 BL2 BL3 --all-networks \
  --include-historical --include-decision-makers --include-nlz 2>&1 | tail -10

NET=$(ls data/networks/ | wc -l | tr -d ' ')
log "  Networks after rebuild: $NET"

# ── Step 2: NLZ networks (553 trainers) ──────────────────────────────
log "Step 2: build all NLZ networks (553 trainers)"
caffeinate -s python3 execution/build_all_nlz_networks.py 2>&1 | tail -15 || log "  WARN: NLZ builder errors"

NLZ_DASH=$(ls output/dashboards/*_nlz_network.html 2>/dev/null | wc -l | tr -d ' ')
log "  NLZ dashboards: $NLZ_DASH"

# ── Step 3: National-coach networks ──────────────────────────────────
log "Step 3: National-coach networks"
python3 << 'EOF'
import json, subprocess, sys
from pathlib import Path
sys.path.insert(0, 'execution')
from lib.normalization import slugify

# Identify national-team trainers from master
try:
    from lib.normalization import NATIONAL_TEAMS
except ImportError:
    NATIONAL_TEAMS = {"Deutschland","Österreich","Schweiz","Frankreich","Italien",
                      "Spanien","England","Niederlande","Belgien","Portugal",
                      "Polen","Türkei","Schweden","Norwegen","Dänemark"}

m = json.load(open('data/persons_master.json'))['persons']
hits = []
seen = set()
for k, v in m.items():
    if v.get('type') != 'trainer':
        continue
    tm = v.get('tm_id')
    if not tm or tm in seen:
        continue
    club = (v.get('current_club') or '').strip()
    # match if club name STARTS with a national team name
    if any(club == n or club.startswith(f"{n} ") or club.startswith(f"{n} (") for n in NATIONAL_TEAMS):
        seen.add(tm)
        hits.append({'tm_id': int(tm), 'name': v.get('name'), 'team': club})

print(f"Found {len(hits)} national-team trainers")
json.dump({'coaches': hits},
          open('data/national_coaches.json', 'w'),
          indent=2, ensure_ascii=False)

for c in hits:
    tm_id = c['tm_id']
    slug = slugify(c['name'])
    try:
        r = subprocess.run(['python3', 'execution/build_coach_network.py', '--tm-id', str(tm_id)],
                          capture_output=True, text=True, timeout=120)
        if r.returncode == 0:
            r2 = subprocess.run(['python3', 'execution/generate_dashboard.py',
                                '--network', f'data/networks/{tm_id}.json',
                                '--output', f'output/dashboards/{slug}_network.html'],
                               capture_output=True, text=True, timeout=30)
            mark = '✓+dash' if r2.returncode == 0 else '✓ (no-dash)'
        else:
            mark = f'✗ rc={r.returncode}'
        print(f'  {mark:>10}  {tm_id:>6}  {c["name"]:<28}  @ {c["team"]}')
    except subprocess.TimeoutExpired:
        print(f'    TIMEOUT  {tm_id}  {c["name"]}')
    except Exception as e:
        print(f'    ERR  {tm_id}  {e}')
EOF

# ── Step 4: Regen dashboards from canonical sources ──────────────────
log "Step 4: regen all dashboards (canonical source)"
python3 execution/regenerate_dashboards.py --lazy 500000 2>&1 | tail -5

# ── Step 5: Club pages + index re-regen ──────────────────────────────
log "Step 5: club pages + index"
python3 execution/generate_all_bl_coaches.py --leagues BL1 BL2 BL3 \
  --all-networks --include-historical --include-decision-makers --include-nlz \
  --skip-networks 2>&1 | tail -3
python3 execution/generate_club_pages.py 2>&1 | tail -3

# ── Step 6: Deploy ───────────────────────────────────────────────────
log "Step 6: Vercel deploy"
cd output
DEPLOY_OUT=$(npx vercel deploy --prod --yes --scope cmk2299s-projects 2>&1)
DEPLOY_URL=$(echo "$DEPLOY_OUT" | grep -oE "https://coach-network-explorer-[a-z0-9]+-cmk2299s-projects.vercel.app" | head -1)
cd "$BASE"
log "  Deploy: $DEPLOY_URL"
sleep 25

# ── Step 7: Smoke (with redirect-follow) ─────────────────────────────
log "Step 7: smoke (with -L)"
SMOKE_FAIL=0
for slug in alexander_blessin andreas_bornemann_sd fabian_huerzeler adi_huetter mattia_croci_torti hansi_flick julian_nagelsmann dieter_hecking florian_kohfeldt vincent_kompany; do
  code=$(/usr/bin/curl -o /dev/null -sL -w "%{http_code}" "https://coach-network-explorer.vercel.app/dashboards/${slug}_network.html")
  echo "  /${slug} → $code"
  [ "$code" != "200" ] && SMOKE_FAIL=$((SMOKE_FAIL+1))
done
log "Smoke fails: $SMOKE_FAIL"

NET=$(ls data/networks/ | wc -l | tr -d ' ')
DASH=$(ls output/dashboards/*_network.html 2>/dev/null | wc -l | tr -d ' ')
log "=== Phase A3 DONE: $NET networks, $DASH dashboards, $SMOKE_FAIL smoke-fail ==="
notify "Phase A3 fix-and-finish DONE: $NET networks · $DASH dashboards · $SMOKE_FAIL smoke-fail ($(date '+%H:%M'))" "default"
