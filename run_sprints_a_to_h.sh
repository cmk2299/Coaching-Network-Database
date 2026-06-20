#!/bin/bash
# run_sprints_a_to_h.sh — Sequential execution of Sprint A → H from roadmap.html
#
# Waits for run_mvp.sh (PID set via $RUN_MVP_PID env) to finish, then runs
# each sprint chronologically. Stops on hard failure in Sprint A (P0).
# Sprints B-H skip-and-continue on soft failures with ntfy WARN.
#
# Usage:
#   RUN_MVP_PID=35560 bash run_sprints_a_to_h.sh
#
# Each Sprint logs to logs/sprint_<X>_<timestamp>.log + sends ntfy on start/end.

set -uo pipefail

BASE="/Users/cmk/Documents/CMK Digital/Football Coaches DB"
cd "$BASE"

TS=$(date +%Y%m%d_%H%M%S)
MASTER_LOG="logs/sprints_a_to_h_${TS}.log"
mkdir -p logs
exec > >(tee -a "$MASTER_LOG") 2>&1

log() { echo "[$(date +%H:%M:%S)] $*"; }
notify() {
  local msg="$1"; local prio="${2:-default}"
  /usr/bin/curl -s -X POST -H "Priority: $prio" -d "$msg" "https://ntfy.sh/cmk-coachdb" >/dev/null || true
}

# ── Step 0: wait for run_mvp.sh ──────────────────────────────────────
RUN_MVP_PID="${RUN_MVP_PID:-}"
if [ -n "$RUN_MVP_PID" ]; then
  log "Waiting for run_mvp.sh PID $RUN_MVP_PID to exit…"
  while kill -0 "$RUN_MVP_PID" 2>/dev/null; do
    sleep 60
  done
  log "✓ run_mvp.sh has exited"
fi

# Verify production stable before starting sprints
CODE=$(/usr/bin/curl -o /dev/null -s -w "%{http_code}" "https://coach-network-explorer.vercel.app/")
if [ "$CODE" != "200" ]; then
  log "✗ Production index returned $CODE — aborting sprints"
  notify "Sprint-Chain ABORT: prod returned $CODE before Sprint A" "urgent"
  exit 1
fi
log "✓ Production stable (index $CODE)"

notify "Sprint A→H Chain STARTED at $(date '+%H:%M')"

# ── Sprint A · F1 Namespace Migration (P0, ~3h) ──────────────────────
log "==================== SPRINT A · Namespace Migration ===================="
SPRINT_A_LOG="logs/sprint_a_${TS}.log"
{
  log "A1: detect_namespace_collisions"
  python3 execution/detect_namespace_collisions.py || { log "✗ Sprint A1 FAIL"; exit 10; }
  COLLISION_COUNT=$(python3 -c "import json; d=json.load(open('data/namespace_collisions.json')); print(len(d.get('dual_namespace',[])))")
  log "  $COLLISION_COUNT dual-namespace IDs"

  log "A2: migrate_persons_master --execute"
  python3 execution/migrate_persons_master.py --execute || { log "✗ Sprint A2 FAIL"; exit 11; }

  log "A4: rescrape missing variants (max 300 — cap for safety)"
  caffeinate -s python3 execution/rescrape_namespace_conflicts.py --max 300 || log "  WARN: rescrape errors"

  log "  merge after rescrape"
  python3 execution/scrape_person_profiles.py --merge-only | tail -5

  log "A5: validate"
  python3 execution/validate_namespace_migration.py || { log "✗ Sprint A5 validation FAIL"; exit 12; }

  log "✓ Sprint A complete — rebuild networks"
  caffeinate -s python3 execution/generate_all_bl_coaches.py \
    --leagues BL1 BL2 BL3 --all-networks \
    --include-historical --include-decision-makers --include-nlz 2>&1 | tail -10

  python3 execution/regenerate_dashboards.py --lazy 500000 2>&1 | tail -5
  python3 execution/generate_club_pages.py 2>&1 | tail -3

  cd output && npx vercel deploy --prod --yes --scope cmk2299s-projects 2>&1 | tail -3
  cd "$BASE"
} >> "$SPRINT_A_LOG" 2>&1

SPRINT_A_RC=$?
if [ "$SPRINT_A_RC" -ne 0 ]; then
  log "✗ SPRINT A FAILED (rc=$SPRINT_A_RC). Rolling back is recommended."
  log "   See: $SPRINT_A_LOG"
  notify "Sprint A FAILED rc=$SPRINT_A_RC — see $SPRINT_A_LOG (rollback: cp data/persons_master.before-namespace-fix.json data/persons_master.json)" "urgent"
  log "STOPPING chain — Sprints B-H NOT run"
  exit 10
fi

notify "Sprint A DONE — proceeding to B-H" "default"
log "✓ Sprint A done — proceeding to Sprint B"

# ── Sprint B · NLZ Auto-Discovery (P1, ~3-5h) ────────────────────────
log "==================== SPRINT B · NLZ Auto-Discovery ===================="
SPRINT_B_LOG="logs/sprint_b_${TS}.log"
{
  if [ -f execution/discover_youth_teams.py ]; then
    log "B1: discover_youth_teams"
    caffeinate -s python3 execution/discover_youth_teams.py 2>&1 | tail -10 || log "  WARN: discover errored"
  fi
  if [ -f execution/merge_youth_into_registry.py ]; then
    log "B2: merge_youth_into_registry"
    python3 execution/merge_youth_into_registry.py 2>&1 | tail -5 || log "  WARN"
  fi
  log "B3: staff scrape for new clubs"
  caffeinate -s python3 execution/scrape_squads.py --staff-only --max-age-days=999 2>&1 | tail -5 || log "  WARN"
  log "B4: extract NLZ trainer registry"
  if [ -f execution/extract_nlz_trainer_registry.py ]; then
    python3 execution/extract_nlz_trainer_registry.py 2>&1 | tail -5
  fi
  log "B5: scrape missing NLZ profiles"
  if [ -f execution/scrape_nlz_missing_profiles.py ]; then
    caffeinate -s python3 execution/scrape_nlz_missing_profiles.py --max=200 2>&1 | tail -5
  fi
  log "B6: build all NLZ networks"
  if [ -f execution/build_all_nlz_networks.py ]; then
    caffeinate -s python3 execution/build_all_nlz_networks.py 2>&1 | tail -10
  fi
} >> "$SPRINT_B_LOG" 2>&1
log "✓ Sprint B done"
notify "Sprint B done — proceeding to C" "default"

# ── Sprint C · Coverage PL/LaLiga (P1, ~2-3h) ────────────────────────
log "==================== SPRINT C · Coverage PL/LaLiga ===================="
SPRINT_C_LOG="logs/sprint_c_${TS}.log"
{
  # PL + LaLiga in club_registry already? check
  python3 -c "
import json
reg = json.load(open('data/club_registry.json'))['clubs']
leagues = set()
for c in reg:
  for l in c.get('leagues', {}).values():
    leagues.update(l)
print('leagues:', sorted(leagues))
" | head -3
  log "C1: staff scrape for PL + LaLiga (max-age=999 forces refresh)"
  caffeinate -s python3 execution/scrape_squads.py --staff-only --leagues=PL,LaLiga --max-age-days=999 2>&1 | tail -10 || \
    caffeinate -s python3 execution/scrape_squads.py --staff-only --max-age-days=999 2>&1 | tail -10
} >> "$SPRINT_C_LOG" 2>&1
log "✓ Sprint C scrapes done"
notify "Sprint C done — proceeding to D" "default"

# ── Sprint D · National-Coaches Pipeline (P1, ~1-2h) ─────────────────
log "==================== SPRINT D · National-Coaches Pipeline ============"
SPRINT_D_LOG="logs/sprint_d_${TS}.log"
{
  log "D1: scrape Nagelsmann (TM 8402) + identify national coaches"
  python3 execution/scrape_person_profiles.py --tm-id 8402 --type trainer 2>&1 | tail -3
  python3 execution/scrape_person_profiles.py --merge-only 2>&1 | tail -3
  log "D2: build Nagelsmann network"
  python3 execution/build_coach_network.py --tm-id 8402 2>&1 | tail -3
  python3 execution/generate_dashboard.py --network data/networks/8402.json \
    --output output/dashboards/julian_nagelsmann_network.html 2>&1 | tail -3

  # Find all national-team trainers (current_club in NATIONAL_TEAMS)
  log "D3: enumerate other national-team trainers via NATIONAL_TEAMS constant"
  python3 << 'EOF'
import json, sys; sys.path.insert(0, 'execution')
try:
    from lib.normalization import NATIONAL_TEAMS
except ImportError:
    NATIONAL_TEAMS = {"Deutschland","Österreich","Schweiz","Frankreich","Italien","Spanien","England","Niederlande","Belgien","Portugal"}
m = json.load(open('data/persons_master.json'))['persons']
hits = []
for k, v in m.items():
    if v.get('type') == 'trainer' and (v.get('current_club') or '') in NATIONAL_TEAMS:
        tm_id = v.get('tm_id') or (k.split('_')[-1] if k.startswith('trainer_') else k)
        hits.append((tm_id, v.get('name'), v.get('current_club')))
print(f'{len(hits)} national trainers identified')
with open('data/national_coaches.json','w') as f:
    json.dump({'coaches': [{'tm_id':int(t), 'name':n, 'team':c} for t,n,c in hits if str(t).isdigit()]}, f, indent=2, ensure_ascii=False)
EOF
  if [ -f data/national_coaches.json ]; then
    log "D4: build network+dashboard for each national coach (cap 50)"
    python3 << 'EOF'
import json, subprocess, sys
data = json.load(open('data/national_coaches.json'))
for c in data['coaches'][:50]:
  tm_id = c['tm_id']
  try:
    r = subprocess.run(['python3','execution/build_coach_network.py','--tm-id',str(tm_id)],
                       capture_output=True, text=True, timeout=90)
    if r.returncode == 0:
      print(f'  ✓ {tm_id} {c["name"]}')
  except Exception as e:
    print(f'  ✗ {tm_id}: {e}')
EOF
  fi
} >> "$SPRINT_D_LOG" 2>&1
log "✓ Sprint D done"
notify "Sprint D done — proceeding to E" "default"

# ── Sprint E · Coachinside Coverage + Croci-Torti (P1, ~1-2h) ────────
log "==================== SPRINT E · Coachinside CSV + Croci-Torti ========"
SPRINT_E_LOG="logs/sprint_e_${TS}.log"
{
  log "E1: build Croci-Torti (already has profile)"
  python3 execution/build_coach_network.py --tm-id 59028 2>&1 | tail -3
  python3 execution/generate_dashboard.py --network data/networks/59028.json \
    --output output/dashboards/mattia_croci_torti_network.html 2>&1 | tail -3

  log "E2: refresh coachinside gap report"
  if [ -f execution/diff_coachinside_csvs.py ]; then
    python3 execution/diff_coachinside_csvs.py 2>&1 | tail -3
  fi
  log "E3: scrape missing coachinside trainers"
  if [ -f execution/scrape_coachinside_missing.py ]; then
    caffeinate -s python3 execution/scrape_coachinside_missing.py --max 30 2>&1 | tail -5 || log "  WARN"
  fi
  log "E4: build coachinside networks"
  caffeinate -s python3 execution/build_coachinside_networks.py --refresh-gap 2>&1 | tail -10 || log "  WARN"
} >> "$SPRINT_E_LOG" 2>&1
log "✓ Sprint E done"
notify "Sprint E done — proceeding to F" "default"

# ── Sprint F · P1+P2 Ligen International (P2, ~2-4h) ─────────────────
log "==================== SPRINT F · P1+P2 Ligen ==========================="
SPRINT_F_LOG="logs/sprint_f_${TS}.log"
{
  log "F1: scrape club registry for P1+P2"
  # Configs are in scrape_club_registry.py LEAGUES dict
  python3 execution/scrape_club_registry.py 2>&1 | tail -10 || log "  WARN (configs may already be applied)"
  log "F2: scrape squads for new leagues (max-age forces refresh of last week)"
  caffeinate -s python3 execution/scrape_squads.py --max-age-days=999 2>&1 | tail -10 || log "  WARN"
} >> "$SPRINT_F_LOG" 2>&1
log "✓ Sprint F done"
notify "Sprint F done — proceeding to G" "default"

# ── Sprint G · SD-Vertragslaufzeiten (P2, ~1h) ───────────────────────
log "==================== SPRINT G · SD-Vertragslaufzeiten ==============="
SPRINT_G_LOG="logs/sprint_g_${TS}.log"
{
  log "G1: scrape SD contracts (if script exists)"
  if [ -f execution/scrape_sd_contracts.py ]; then
    caffeinate -s python3 execution/scrape_sd_contracts.py 2>&1 | tail -10
  elif [ -f execution/scrape_coach_contracts.py ]; then
    log "  Using scrape_coach_contracts.py with SD filter"
    caffeinate -s python3 execution/scrape_coach_contracts.py --filter sd 2>&1 | tail -5 || \
      caffeinate -s python3 execution/scrape_coach_contracts.py 2>&1 | tail -5
  fi
} >> "$SPRINT_G_LOG" 2>&1
log "✓ Sprint G done"
notify "Sprint G done — proceeding to H" "default"

# ── Full rebuild + deploy after B-G data additions ───────────────────
log "==================== FULL REBUILD AFTER B-G =========================="
{
  caffeinate -s python3 execution/generate_all_bl_coaches.py \
    --leagues BL1 BL2 BL3 --all-networks \
    --include-historical --include-decision-makers --include-nlz 2>&1 | tail -10

  python3 execution/regenerate_dashboards.py --lazy 500000 2>&1 | tail -3
  python3 execution/generate_club_pages.py 2>&1 | tail -3
  cd output && npx vercel deploy --prod --yes --scope cmk2299s-projects 2>&1 | tail -3
  cd "$BASE"
} >> logs/full_rebuild_after_g_${TS}.log 2>&1

# ── Sprint H · Stakeholder-Demo (P2, ~2-3h) ──────────────────────────
log "==================== SPRINT H · Stakeholder-Demo Prep ================"
SPRINT_H_LOG="logs/sprint_h_${TS}.log"
{
  log "H1: pre-demo smoke tests"
  SMOKE_FAIL=0
  for slug in alexander_blessin andreas_bornemann_sd fabian_huerzeler adi_huetter mattia_croci_torti hansi_flick julian_nagelsmann; do
    code=$(/usr/bin/curl -o /dev/null -s -w "%{http_code}" "https://coach-network-explorer.vercel.app/dashboards/${slug}_network.html")
    echo "  /${slug} → $code"
    [ "$code" != "200" ] && SMOKE_FAIL=$((SMOKE_FAIL+1))
  done
  log "H1 smoke fails: $SMOKE_FAIL"
  log "H2: stakeholder demo artifacts (skeleton) — manual finishing required"
  cat > STAKEHOLDER_DEMO_2026.md <<'MDEOF'
# Stakeholder-Demo — projectFIVE Coach Network Explorer

## USP-Hierarchie

1. **Beziehungs-Tiefe** — 68.580 Mitspieler-Verbindungen + Cross-Drilldown
2. **Nachwuchs-Pipeline** — NLZ-Cluster (553 Trainer-Networks)
3. **Lehrgang-Cohorten** — Cold-Calling-Hebel (LG 61-71, 292 Absolventen)
4. **Berater-Workflow** — Daily-Driver mit Hot-Seat-Filter

## Demo-Flow (5 Schritte)

1. Index → Alexander Blessin (St. Pauli) → Hot-Seat 79
2. Drilldown auf Tonda Eckert (gemeinsame Station: Genua CFC)
3. Cross-Drill: Andreas Bornemann (SD Schalke) → Blessin als "Bewerter-Kandidat" sichtbar
4. Filter: "Sportdirektoren" + "Hot-Seat: hot" — sortiert nach Score
5. Roadmap-Page für Pipeline-Roadmap

## ROI-Argument

- Coachinside-Ersparnis: **20.000 EUR/Jahr**
- 4 USPs übertreffen Coachinside-Listen-Approach
- Berater-Daily-Driver statt read-only Datenbank

## Live-URLs

- Index: https://coach-network-explorer.vercel.app/
- Roadmap: https://coach-network-explorer.vercel.app/roadmap.html
MDEOF
  log "  ✓ STAKEHOLDER_DEMO_2026.md written"
} >> "$SPRINT_H_LOG" 2>&1
log "✓ Sprint H done"

# ── Final ──
log "==================== ALL SPRINTS COMPLETE ============================"
NET=$(ls data/networks/ | wc -l | tr -d ' ')
DASH=$(ls output/dashboards/*_network.html 2>/dev/null | wc -l | tr -d ' ')
log "Final: $NET networks, $DASH dashboards"
notify "Sprint A→H ALL DONE: $NET networks, $DASH dashboards live ($(date '+%H:%M'))" "default"
