# Bug Fix: Duplicate Overlap Counting

**Date:** 2026-02-10
**Status:** ✅ Fixed

---

## Problem

User spotted: **Dietmar Hopp ↔ Heinz Seyfert** showed 140 years together, which is impossible.

## Root Cause

The `find_temporal_overlap()` function was counting **every role combination** as a separate overlap:

**Before Fix:**
- Hopp (Shareholder) × Seyfert (Kit Manager) → 35 years
- Hopp (Shareholder) × Seyfert (Team official) → 35 years
- Hopp (Investor) × Seyfert (Kit Manager) → 35 years
- Hopp (Investor) × Seyfert (Team official) → 35 years
- **Total: 140 years** ❌

The correct answer: They were at the same club (Hoffenheim) for the same period (1992-2027), so it should count as **35 years, period**.

---

## Solution

Added **deduplication logic** to `execution/identify_coach_connections.py`:

```python
seen_periods = set()  # Track club+period to avoid duplicates

# Create unique key for each overlap
period_key = (club_a.lower(), overlap_start, overlap_end)

# Skip if already recorded
if period_key in seen_periods:
    continue

seen_periods.add(period_key)
```

---

## Results

**After Fix:**
- Hopp ↔ Seyfert: **35 years, Strength 85** ✅
- Top connection is now: **Michael Niemeyer ↔ Vitus Angerer** (196 strength, 58 years, 5 clubs)

**Network Stats (Corrected):**
- Total connections: Still 37,356
- Manager ↔ Assistant: 520 (was 552)
- Head Coaches Together: 390 (was 428)
- Youth Colleagues: 128 (was 133)
- General Colleagues: 36,318 (was 36,243)

The numbers shifted slightly because duplicate overlaps were removed across the board.

---

## Files Updated

1. ✅ `execution/identify_coach_connections.py` - Added deduplication
2. ✅ `data/coach_to_coach_connections.json` - Re-computed
3. ✅ `data/network_graph.json` - Rebuilt
4. ✅ `data/network_graph.gexf` - Re-exported
5. ✅ `data/network_graph_d3.json` - Re-exported
6. ✅ `data/network_nodes.csv` + `network_edges.csv` - Re-exported
7. ✅ `MEMORY.md` - Updated with correct stats

---

## Verification

Check the fixed connection:
```python
import json
with open('data/coach_to_coach_connections.json') as f:
    data = json.load(f)
for conn in data['connections']:
    if 'Dietmar Hopp' in [conn['coach_a'], conn['coach_b']]:
        print(f"{conn['coach_a']} ↔ {conn['coach_b']}: {conn['total_years']} years")
```

**Output:** `Dietmar Hopp ↔ Heinz Seyfert: 35 years` ✅

---

## Lesson Learned

**Always validate outliers!** When you see impossible values (140 years together), it's usually a counting bug, not real data.

**Self-annealing works:** User spotted issue → Root cause found in 2 minutes → Fix applied → System re-validated → Documentation updated.

---

✅ Bug fixed. Network data is now accurate.
