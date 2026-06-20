#!/usr/bin/env bash
# ───────────────────────────────────────────────────────────────────────────
# Validate relationship LOGIC + SCORING across data/networks/*.json in rotating
# random samples. Each round samples a different subset (fresh seed) so repeated
# runs broaden coverage. Exits non-zero if any round finds an issue.
#
#   bash run_audit_loop.sh [SAMPLE_SIZE] [ROUNDS]
#     SAMPLE_SIZE  networks per round   (default 400; use 0 = full each round)
#     ROUNDS       number of rounds     (default 5)
#
# Workflow: run it → if a check fails, the JSON reports under /tmp/audit_loop_*
# list the offending networks. Fix the ROOT CAUSE (lib/ helper or builder), then
# re-run. logic_audit = relationship correctness, scoring_audit = score/strength/
# ordering invariants.
# ───────────────────────────────────────────────────────────────────────────
set -uo pipefail
cd "$(dirname "$0")"

SAMPLE="${1:-400}"
ROUNDS="${2:-5}"
PY=python3
fail_total=0

if [ "$SAMPLE" -eq 0 ]; then SARG=""; LABEL="full"; else LABEL="sample=$SAMPLE"; fi

for r in $(seq 1 "$ROUNDS"); do
  seed=$RANDOM
  [ "$SAMPLE" -eq 0 ] && SARG="" || SARG="--sample $SAMPLE --seed $seed"
  echo "══════════════════════════════════════════════════════════════"
  echo "  ROUND $r/$ROUNDS · $LABEL · seed=$seed"
  echo "══════════════════════════════════════════════════════════════"

  $PY execution/logic_audit.py   $SARG --json "/tmp/audit_loop_logic_$r.json"   2>/dev/null \
      | sed -n '/LOGIC AUDIT RESULTS/,$p'
  lrc=${PIPESTATUS[0]}

  $PY execution/scoring_audit.py $SARG --json "/tmp/audit_loop_scoring_$r.json" 2>/dev/null \
      | sed -n '/SCORING AUDIT RESULTS/,$p'
  src=${PIPESTATUS[0]}

  if [ "$lrc" -ne 0 ] || [ "$src" -ne 0 ]; then
    echo "  ⚠ ROUND $r had findings (logic=$lrc scoring=$src) — see /tmp/audit_loop_*_$r.json"
    fail_total=$((fail_total+1))
  else
    echo "  ✓ ROUND $r clean"
  fi
  echo
done

echo "══════════════════════════════════════════════════════════════"
if [ "$fail_total" -eq 0 ]; then
  echo "  ✓✓ ALL $ROUNDS ROUNDS CLEAN ($LABEL)"
  exit 0
else
  echo "  ✗ $fail_total/$ROUNDS rounds had findings — fix root cause, re-run."
  exit 1
fi
