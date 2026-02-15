# Teammate Connections - Phase 6 Complete

## Summary

Successfully completed Phase 6: Adding player connections (teammate relationships) to the Football Coaches Network.

**Date:** February 11, 2026
**Duration:** ~13 hours total (11h scraping + 2h processing)

---

## What Was Built

### 1. Teammates Bulk Scraper
**File:** `execution/scrape_teammates_bulk.py`

- Scraped all teammates for 666 coaches from Transfermarkt.de
- Used existing `scrape_teammates.py` infrastructure
- Pagination support (up to 5 pages per coach)
- Filter: 10+ shared matches minimum

### 2. Teammate Connection Identifier
**File:** `execution/identify_teammate_connections.py`

- Cross-referenced teammates with master coach database
- Identified which teammates are also coaches in our network
- Created bidirectional connections (A ↔ B played together)

### 3. Network Integration
**File:** `execution/integrate_teammate_connections.py`

- Added teammate edges to existing network graph
- Calculated connection strength based on shared matches and teams
- Maintained all existing coach-to-coach connections

### 4. Multi-Format Export
**Updated:** `execution/export_network_formats.py`

- Fixed to handle edges without IDs
- Exported updated network to GEXF, D3.js, and CSV formats

---

## Final Results

### Teammates Scraping
- **666/666** coaches scraped (100%)
- **539 coaches** with teammate data (80.9% success rate)
- **35,275 total teammates** identified
- **Average: 65.4 teammates** per coach
- **Time: 10.9 hours**

### Teammate Connections
- **434 unique connections** identified
- **378 coaches** have teammate connections
- **Average: 2.3 connections** per coach
- **Max: 15 connections** (Thomas Treß)

### Updated Network
- **Nodes: 1,095** (unchanged)
- **Edges: 39,641** (added 868 teammate edges)
  - **38,773** existing edges (coach-coach, SD-coach, executive-coach)
  - **868** new teammate edges
- **Density: 6.47%**

---

## Top 10 Strongest Teammate Connections

Ranked by shared matches:

1. **Thomas Riedel ↔ Philipp Lahm**
   448 matches, 4 teams (Bayern Munich, etc.)

2. **Thomas Riedel ↔ Thomas Müller**
   262 matches, 2 teams

3. **Christian Beckers ↔ Petra Dahl**
   239 matches, 1 team

4. **Daniel Van Buyten ↔ Roman Weidenfeller**
   228 matches, 2 teams

5. **Klaus Augenthaler ↔ Philipp Lahm**
   215 matches, 2 teams

6. **Rainer Falkenhain ↔ Philipp Lahm**
   214 matches, 1 team

7. **Klaus Augenthaler ↔ Thomas Riedel**
   204 matches, 2 teams

8. **Rainer Falkenhain ↔ Thomas Riedel**
   199 matches, 1 team

9. **Thomas Riedel ↔ Mario Gómez**
   187 matches, 3 teams

10. **Daniel Van Buyten ↔ Thomas Müller**
    171 matches, 3 teams

**Notable:** Many Bayern Munich connections dominate the top rankings.

---

## Most Connected Coaches (By Teammates)

**Top 5:**
1. Thomas Treß: 15 connections
2. Philipp Lahm: 14 connections
3. Thomas Riedel: 13 connections
4. Klaus Augenthaler: 11 connections
5. Daniel Van Buyten: 10 connections

---

## Connection Strength Formula

For teammate connections:
```
Strength = (shared_matches / 10) + (teams_together × 5)
```

**Examples:**
- 100 matches, 1 team = 10 + 5 = **15 strength**
- 200 matches, 3 teams = 20 + 15 = **35 strength**
- 448 matches, 4 teams = 44.8 + 20 = **64.8 strength** (Riedel-Lahm)

---

## Data Files

### Input Files
- `data/teammates_bulk.json` (9.5 MB)
  - Raw teammates data for all 666 coaches
  - 35,275 total teammate relationships

### Output Files
- `data/teammate_connections.json` (153 KB)
  - 434 identified connections between coaches

### Network Files (Updated)
- `data/network_graph.json` (19+ MB)
  - Main network with teammate edges added
- `data/network_graph_with_teammates.json` (backup)
- `data/network_graph.gexf` (Gephi format)
- `data/network_graph_d3.json` (D3.js format)
- `data/network_nodes.csv` (1,095 nodes)
- `data/network_edges.csv` (39,641 edges)

### Cache
- `tmp/cache/player_*_teammates.json` (686 files)
  - Individual teammate data per coach
  - Enables fast re-processing without re-scraping

---

## Technical Details

### Scraping Approach
- Used **Transfermarkt.de** (German version) for better data availability
- Rate limiting: 4 seconds between requests
- Pagination: Up to 5 pages per coach (~125 teammates max)
- Filter: Minimum 10 shared matches to reduce noise
- Caching: All results cached to avoid re-scraping

### Challenges Solved

1. **No Direct Player Career Data**
   - Transfermarkt player profiles don't have club-by-club career history
   - Solution: Used teammates page to reconstruct playing connections

2. **JavaScript-Rendered Pages**
   - `.transfermarkt.com` uses JavaScript for teammates
   - Solution: Used `.transfermarkt.de` which has static HTML

3. **Performance**
   - Original estimate: 2-4 hours
   - Actual time: 11 hours (due to pagination)
   - Solution: Accepted longer runtime for complete data

4. **Missing Edge IDs**
   - Export failed due to legacy edges without IDs
   - Solution: Updated export script to generate fallback IDs

---

## Network Insights

### Connection Types Distribution
- **General Colleagues:** 36,224 edges (91.4%)
- **Manager ↔ Assistant:** 560 edges (1.4%)
- **Teammate:** 868 edges (2.2%)
- **Head Coaches Together:** 436 edges (1.1%)
- **Executive ↔ Coach:** 1,399 edges (3.5%)
- **Youth Colleagues:** 136 edges (0.3%)
- **SD ↔ Coach:** 18 edges (0.05%)

### Playing Career Impact
- **80.9%** of coaches have identifiable playing careers
- **70.1%** of those played with other coaches in the network
- Strong clustering around **Bayern Munich** ecosystem

---

## Use Cases

### For Network Analysis
1. **Identify playing career connections** between current coaches
2. **Trace mentorship paths** (player → coach relationships)
3. **Cluster analysis** by shared playing clubs
4. **Strong ties** (high shared matches) vs weak ties

### For Recruitment
1. Find coaches who played with specific star players
2. Identify coaches with Bundesliga playing experience
3. Map playing career prestige (# of matches, teams)

### For Research
1. Does playing career success correlate with coaching success?
2. Do ex-teammates make better coaching partnerships?
3. Club loyalty: Do players return as coaches to their former clubs?

---

## Next Steps (Optional)

### Potential Enhancements
1. **Expand to more coaches**
   - Currently: 666 coaches scraped
   - Could expand to all 1,057 profiles

2. **Add club metadata**
   - Extract which specific clubs they played together at
   - Reconstruct full playing career timeline

3. **Player statistics**
   - Add goals, appearances, positions
   - Weight connections by playing time

4. **Temporal analysis**
   - When did they play together (seasons)
   - Career overlap duration

5. **Decision makers filter**
   - Create teammate network for only managers/SDs
   - Focus on decision-maker playing connections

---

## Files Changed

### New Files
- `execution/scrape_teammates_bulk.py`
- `execution/identify_teammate_connections.py`
- `execution/integrate_teammate_connections.py`
- `data/teammates_bulk.json`
- `data/teammate_connections.json`
- `TEAMMATE_CONNECTIONS_SUMMARY.md` (this file)

### Modified Files
- `execution/export_network_formats.py` (fixed ID handling)
- `data/network_graph.json` (added teammate edges)
- `data/network_graph.gexf` (updated)
- `data/network_graph_d3.json` (updated)
- `data/network_edges.csv` (updated)

### Memory Updated
- `MEMORY.md` should be updated with Phase 6 learnings

---

## Conclusion

✅ **Phase 6: Player Connections - COMPLETE**

Successfully added 868 teammate connections to the Football Coaches Network, providing a new dimension of analysis based on playing career relationships. The network now includes:

- **5 relationship types:** Colleagues, Manager-Assistant, Teammates, SD-Coach, Executive-Coach
- **39,641 total connections** spanning coaching and playing careers
- **1,095 nodes** representing coaches, sporting directors, and executives

The enhanced network enables deeper analysis of:
- How playing careers influence coaching networks
- Mentorship paths from player to coach
- Club ecosystems across playing and coaching dimensions

**Total project time:** 11 hours scraping + 2 hours processing = **13 hours**

🎉 **Mission accomplished!**
