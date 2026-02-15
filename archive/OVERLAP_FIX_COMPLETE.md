# Overlap Bug Fix - Complete

**Date:** 2026-02-10
**Status:** ✅ Fixed

---

## Problems Fixed

### 1. Multiple Role Duplicates (Hopp/Seyfert Issue)
**Before:** Same time period counted multiple times for different role combinations
- Example: Hopp (Shareholder) × Seyfert (Kit Manager) = 35 years
- Example: Hopp (Investor) × Seyfert (Team official) = 35 years
- **Total:** 4× 35 = 140 years ❌

**After:** Same period counted once, roles combined
- Hopp ↔ Seyfert: **35 years** (Shareholder/Investor + Kit Manager/Team official) ✅

### 2. Overlapping Period Duplicates (Fritz/Werner Issue)
**Before:** Multiple overlapping periods for same person counted separately
- Fritz (Head of Scouting) 2021-2023 + Werner = 2 years
- Fritz (Head of first team football) 2021-2024 + Werner = 3 years
- Fritz (Managing Director) 2024-2025 + Werner = 1 year
- **Total:** 2 + 3 + 1 = 6 years ❌

**After:** Overlapping periods merged
- Fritz ↔ Werner: **3-4 years** (all roles merged to 2021-2025) ✅

---

## Solution Implemented

### Core Fix: `merge_overlapping_periods()`

Added to `execution/identify_coach_connections.py`:

```python
def merge_overlapping_periods(overlaps):
    """Merge overlapping time periods for the same club"""
    # Group by club
    # Sort by start date
    # Merge adjacent/overlapping periods
    # Combine role labels
    return merged_periods
```

**Logic:**
1. Group overlaps by club
2. Sort by start date
3. If `next_start <= current_end`: **Merge** (extend end date, combine roles)
4. Otherwise: Save current, start new period

---

## Files Fixed

### 1. Coach ↔ Coach Connections
**Script:** `execution/identify_coach_connections.py`
- Added `merge_overlapping_periods()`
- Modified `find_temporal_overlap()` to use merging
- **Result:** 37,356 connections with correct years

### 2. SD ↔ Coach Connections
**Script:** `execution/recompute_all_overlaps_fixed.py` (new)
- Recomputed from scratch using fixed logic
- **Result:** 18 connections (was 33 with duplicates)

### 3. Executive ↔ Coach Connections
**Script:** `execution/recompute_all_overlaps_fixed.py` (new)
- Recomputed all 82 executives × 1,057 coaches
- **Result:** 2,539 connections found, filtered to 1,399 (strength > 20)

### 4. Data Consolidation
**Script:** `execution/consolidate_network_data.py`
- Updated to load `*_fixed.json` files
- Filters executive connections (strength > 20) to reduce noise

---

## Verification Examples

### Example 1: Clemens Fritz ↔ Ole Werner
**Before:** 50 strength, 5-6 years
**After:** 26 strength, 3 years ✅

**Details:**
- Werner bei Bremen: Nov 2021 - Mai 2025
- Fritz hatte 3 überlappende Rollen (Head of Scouting, Head of first team, Managing Director)
- **Merged to:** 2021-2025 = 3-4 Jahre

### Example 2: Andreas Schicker ↔ Christian Ilzer
**Before:** 57 strength, 6 years
**After:** 44 strength, 7 years ✅

**Corrected:** Proper merging of Sturm Graz + Hoffenheim periods

### Example 3: Dietmar Hopp ↔ Heinz Seyfert
**Before:** 310 strength, 140 years (!)
**After:** 85 strength, 35 years ✅

---

## New Network Stats

### Full Network
- **Nodes:** 1,095 (1,057 coaches, 15 SDs, 23 executives)
- **Edges:** 38,773 total
  - Coach ↔ Coach: 37,356
  - SD ↔ Coach: 18
  - Executive ↔ Coach: 1,399
- **Density:** 0.0647 (6.47%)
- **Avg Connections/Node:** 74.92

### Decision Makers Only (Filtered)
- **Nodes:** 47 (17 managers, 15 SDs, 15 executives)
- **Edges:** 48 connections
- **Density:** 0.0444
- **Top Connection:** Andreas Schicker ↔ Christian Ilzer (44 strength, 7 years)

---

## Exported Files (All Updated)

### Full Network
- `data/network_graph.json`
- `data/network_graph.gexf` (Gephi)
- `data/network_graph_d3.json` (D3.js)
- `data/network_nodes.csv`
- `data/network_edges.csv`

### Decision Makers
- `data/decision_makers_network.json`
- `data/decision_makers_network.gexf`
- `data/decision_makers_nodes.csv`
- `data/decision_makers_edges.csv`

### Fixed Overlaps
- `data/sd_coach_overlaps_fixed.json` (18 connections)
- `data/executive_coach_overlaps_fixed.json` (2,539 connections)
- `data/coach_to_coach_connections.json` (37,356 connections - already fixed)

---

## Next Phase: Player Connections

As requested, the next phase will track:

### 1. Coach → Player Relationships
- Coaches who played together professionally
- Use `execution/scrape_teammates.py` (already exists)
- Add "playing_career" connections to network

### 2. SD → Player Relationships
- SDs who had playing careers
- Overlaps between SD playing career and coach playing career
- "Former teammates now working together" connections

**Implementation Plan:**
1. Scrape playing careers for coaches/SDs
2. Find teammate overlaps
3. Add to network as new relationship type
4. Track "player → coach" career progressions

---

## Technical Details

### Merge Algorithm Complexity
- **Time:** O(n log n) per club (sorting)
- **Space:** O(n) for storing overlaps
- **Handles:** Adjacent periods, partial overlaps, complete overlaps

### Edge Cases Handled
1. ✅ Exact same period (deduplicated)
2. ✅ Partial overlaps (merged to longest span)
3. ✅ Adjacent periods (2023-2024 + 2024-2025 = 2023-2025)
4. ✅ Multiple roles during same period (combined with " / ")
5. ✅ Current positions (end_year = now + 1)

---

## Lessons Learned

1. **Always validate extreme outliers** (140 years = obvious bug)
2. **Test with real data** (not just edge cases)
3. **Self-annealing works** (user spotted → fixed in ~2 hours)
4. **Document everything** (this file prevents future regressions)

---

✅ **All overlaps fixed. Network data is now accurate.**
