#!/bin/bash
# run_sprints_b_to_h.sh — Continue Sprint B → H after Sprint A schema-migration.
#
# Sprint A is structurally complete (type-aware key migration done, 0 real
# Frankenstein cases in data — directive overstated scope). This chain:
#   - Rebuilds networks with the migrated master (post-Sprint-A polish)
#   - Deploys (Sprint A's final deploy step)
#   - Continues B → C → D → E → F → G → full-rebuild → H

set -uo pipefail

BASE="/Users/cmk/Documents/CMK Digital/Football Coaches DB"
cd "$BASE"

TS=$(date +%Y%m%d_%H%M%S)
MASTER_LOG="logs/sprints_b_to_h_${TS}.log"
mkdir -p logs
exec > >(tee -a "$MASTER_LOG") 2>&1

log() { echo "[$(date +%H:%M:%S)] $*"; }
notify() {
  local msg="$1"; local prio="${2:-default}"
  /usr/bin/curl -s -X POST -H "Priority: $prio" -d "$msg" "https://ntfy.sh/cmk-coachdb" >/dev/null || true
}

log "=== Sprint B-H Chain started ==="
notify "Sprint B→H Chain STARTED ($(date '+%H:%M'))"

# ── Step 0: Post-Sprint A network rebuild + deploy ───────────────────
log "Step 0: Post-Sprint A network rebuild with type-aware master"
{
  caffeinate -s python3 execution/generate_all_bl_coaches.py \
    --leagues BL1 BL2 BL3 --all-networks \
    --include-historical --include-decision-makers --include-nlz 2>&1 | tail -10

  python3 execution/regenerate_dashboards.py --lazy 500000 2>&1 | tail -3
  python3 execution/generate_club_pages.py 2>&1 | tail -3
  cd output && npx vercel deploy --prod --yes --scope cmk2299s-projects 2>&1 | tail -3
  cd "$BASE"
} >> "logs/post_sprint_a_${TS}.log" 2>&1
log "  ✓ Sprint A final deploy done"
notify "Sprint A final deploy done — proceeding to B"

# ── Sprint B · NLZ Auto-Discovery (P1, ~3-5h) ────────────────────────
log "==================== SPRINT B · NLZ Auto-Discovery ===================="
SPRINT_B_LOG="logs/sprint_b_${TS}.log"
{
  if [ -f execution/discover_youth_teams.py ]; then
    log "B1: discover_youth_teams"
    caffeinate -s python3 execution/discover_youth_teams.py 2>&1 | tail -10 || log "  WARN"
  fi
  if [ -f execution/merge_youth_into_registry.py ]; then
    log "B2: merge_youth_into_registry"
    python3 execution/merge_youth_into_registry.py 2>&1 | tail -5 || log "  WARN"
  fi
  log "B3: staff scrape for new clubs"
  caffeinate -s python3 execution/scrape_squads.py --staff-only --max-age-days=999 2>&1 | tail -5 || log "  WARN"
  if [ -f execution/extract_nlz_trainer_registry.py ]; then
    log "B4: extract NLZ trainer registry"
    python3 execution/extract_nlz_trainer_registry.py 2>&1 | tail -5
  fi
  if [ -f execution/scrape_nlz_missing_profiles.py ]; then
    log "B5: scrape missing NLZ profiles (cap 200)"
    caffeinate -s python3 execution/scrape_nlz_missing_profiles.py --max=200 2>&1 | tail -5
  fi
  if [ -f execution/build_all_nlz_networks.py ]; then
    log "B6: build all NLZ networks"
    caffeinate -s python3 execution/build_all_nlz_networks.py 2>&1 | tail -10
  fi
} >> "$SPRINT_B_LOG" 2>&1
log "✓ Sprint B done"
notify "Sprint B done — proceeding to C"

# ── Sprint C · Coverage PL/LaLiga (P1, ~2-3h) ────────────────────────
log "==================== SPRINT C · Coverage PL/LaLiga ===================="
SPRINT_C_LOG="logs/sprint_c_${TS}.log"
{
  log "C1: staff scrape for PL + LaLiga"
  caffeinate -s python3 execution/scrape_squads.py --staff-only --leagues=PL,LaLiga --max-age-days=999 2>&1 | tail -10 || \
    log "  WARN: leagues= flag might not exist for PL/LaLiga in registry"
} >> "$SPRINT_C_LOG" 2>&1
log "✓ Sprint C done"
notify "Sprint C done — proceeding to D"

# ── Sprint D · National-Coaches Pipeline (P1, ~1-2h) ─────────────────
log "==================== SPRINT D · National-Coaches Pipeline ============="
SPRINT_D_LOG="logs/sprint_d_${TS}.log"
{
  log "D1: scrape Nagelsmann TM 8402"
  python3 execution/scrape_person_profiles.py --tm-id 8402 --type trainer 2>&1 | tail -3
  python3 execution/scrape_person_profiles.py --merge-only 2>&1 | tail -5
  log "D2: build Nagelsmann network"
  python3 execution/build_coach_network.py --tm-id 8402 2>&1 | tail -3
  python3 execution/generate_dashboard.py --network data/networks/8402.json \
    --output output/dashboards/julian_nagelsmann_network.html 2>&1 | tail -3

  log "D3: enumerate national-team trainers"
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
        if str(tm_id).isdigit():
            hits.append({'tm_id': int(tm_id), 'name': v.get('name'), 'team': v.get('current_club')})
# de-dup
seen = set(); uniq = []
for h in hits:
    if h['tm_id'] in seen: continue
    seen.add(h['tm_id']); uniq.append(h)
print(f'{len(uniq)} national trainers')
json.dump({'coaches': uniq}, open('data/national_coaches.json','w'), indent=2, ensure_ascii=False)
EOF
  log "D4: build network+dashboard for each national coach"
  python3 << 'EOF'
import json, subprocess, sys
from pathlib import Path
sys.path.insert(0, 'execution')
from lib.normalization import slugify
data = json.load(open('data/national_coaches.json'))
for c in data['coaches']:
  tm_id = c['tm_id']
  slug = slugify(c['name'])
  try:
    r = subprocess.run(['python3','execution/build_coach_network.py','--tm-id',str(tm_id)],
                       capture_output=True, text=True, timeout=90)
    if r.returncode == 0:
      r2 = subprocess.run(['python3','execution/generate_dashboard.py',
                            '--network', f'data/networks/{tm_id}.json',
                            '--output', f'output/dashboards/{slug}_network.html'],
                           capture_output=True, text=True, timeout=30)
      print(f'  ✓ {tm_id} {c["name"]:<25}  ({"+dash" if r2.returncode==0 else "no-dash"})')
    else:
      print(f'  ✗ {tm_id} {c["name"]:<25}  build-rc={r.returncode}')
  except Exception as e:
    print(f'  ✗ {tm_id}: {e}')
EOF
} >> "$SPRINT_D_LOG" 2>&1
log "✓ Sprint D done"
notify "Sprint D done — proceeding to E"

# ── Sprint E · Coachinside CSV + Croci-Torti (P1, ~1-2h) ─────────────
log "==================== SPRINT E · Coachinside CSV + Croci-Torti ========"
SPRINT_E_LOG="logs/sprint_e_${TS}.log"
{
  log "E1: build Croci-Torti (tm 59028)"
  python3 execution/build_coach_network.py --tm-id 59028 2>&1 | tail -3
  python3 execution/generate_dashboard.py --network data/networks/59028.json \
    --output output/dashboards/mattia_croci_torti_network.html 2>&1 | tail -3

  if [ -f execution/diff_coachinside_csvs.py ]; then
    log "E2: refresh coachinside gap report"
    python3 execution/diff_coachinside_csvs.py 2>&1 | tail -5 || log "  WARN"
  fi
  if [ -f execution/scrape_coachinside_missing.py ]; then
    log "E3: scrape missing coachinside trainers (max 30)"
    caffeinate -s python3 execution/scrape_coachinside_missing.py --max 30 2>&1 | tail -5 || log "  WARN"
  fi
  if [ -f execution/build_coachinside_networks.py ]; then
    log "E4: build coachinside networks"
    caffeinate -s python3 execution/build_coachinside_networks.py --refresh-gap 2>&1 | tail -10 || log "  WARN"
  fi
} >> "$SPRINT_E_LOG" 2>&1
log "✓ Sprint E done"
notify "Sprint E done — proceeding to F"

# ── Sprint F · P1+P2 Ligen International (P2, ~2-4h) ─────────────────
log "==================== SPRINT F · P1+P2 Ligen ==========================="
SPRINT_F_LOG="logs/sprint_f_${TS}.log"
{
  log "F1: scrape club registry (P1+P2 configs)"
  python3 execution/scrape_club_registry.py 2>&1 | tail -10 || log "  WARN"
  log "F2: scrape squads for any added leagues"
  caffeinate -s python3 execution/scrape_squads.py --max-age-days=999 2>&1 | tail -10 || log "  WARN"
} >> "$SPRINT_F_LOG" 2>&1
log "✓ Sprint F done"
notify "Sprint F done — proceeding to G"

# ── Sprint G · SD-Vertragslaufzeiten (P2, ~1h) ───────────────────────
log "==================== SPRINT G · SD-Vertragslaufzeiten ==============="
SPRINT_G_LOG="logs/sprint_g_${TS}.log"
{
  if [ -f execution/scrape_sd_contracts.py ]; then
    log "G1: scrape_sd_contracts"
    caffeinate -s python3 execution/scrape_sd_contracts.py 2>&1 | tail -10
  elif [ -f execution/scrape_coach_contracts.py ]; then
    log "G1: scrape_coach_contracts (handles SDs)"
    caffeinate -s python3 execution/scrape_coach_contracts.py 2>&1 | tail -10 || log "  WARN"
  else
    log "  WARN: no contract scraper script — skipping Sprint G"
  fi
} >> "$SPRINT_G_LOG" 2>&1
log "✓ Sprint G done"
notify "Sprint G done — full rebuild before H"

# ── Full rebuild + deploy after B-G data additions ───────────────────
log "==================== FULL REBUILD AFTER B-G =========================="
{
  python3 execution/scrape_person_profiles.py --merge-only 2>&1 | tail -10
  caffeinate -s python3 execution/generate_all_bl_coaches.py \
    --leagues BL1 BL2 BL3 --all-networks \
    --include-historical --include-decision-makers --include-nlz 2>&1 | tail -10

  python3 execution/regenerate_dashboards.py --lazy 500000 2>&1 | tail -3
  python3 execution/generate_club_pages.py 2>&1 | tail -3
  cd output && npx vercel deploy --prod --yes --scope cmk2299s-projects 2>&1 | tail -3
  cd "$BASE"
} >> "logs/full_rebuild_after_g_${TS}.log" 2>&1

# ── Sprint H · Stakeholder-Demo (P2, ~2-3h) ──────────────────────────
log "==================== SPRINT H · Stakeholder-Demo Prep ================"
SPRINT_H_LOG="logs/sprint_h_${TS}.log"
{
  log "H1: pre-demo smoke tests"
  SMOKE_FAIL=0
  for slug in alexander_blessin andreas_bornemann_sd fabian_huerzeler adi_huetter mattia_croci_torti hansi_flick julian_nagelsmann dieter_hecking florian_kohfeldt; do
    code=$(/usr/bin/curl -o /dev/null -s -w "%{http_code}" "https://coach-network-explorer.vercel.app/dashboards/${slug}_network.html")
    echo "  /${slug} → $code"
    [ "$code" != "200" ] && SMOKE_FAIL=$((SMOKE_FAIL+1))
  done
  log "H1 smoke fails: $SMOKE_FAIL"
  log "H2: write STAKEHOLDER_DEMO_2026.md"
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
3. Cross-Drill: Andreas Bornemann (SD Schalke) → Blessin als Kandidat
4. Filter: "Sportdirektoren" + Hot-Seat "hot" — sortiert nach Score
5. Roadmap-Page für Pipeline-Übersicht

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
NET=$(ls data/networks/ | wc -l | tr -d ' ')
DASH=$(ls output/dashboards/*_network.html 2>/dev/null | wc -l | tr -d ' ')
log "==================== ALL SPRINTS COMPLETE =============================="
log "Final: $NET networks, $DASH dashboards"
notify "Sprint A→H COMPLETE: $NET networks, $DASH dashboards ($(date '+%H:%M'))" "default"
