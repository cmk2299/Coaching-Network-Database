# Next Phase: Player Connection Tracking

**Status:** 📋 Planned
**Priority:** Next after network build complete

---

## Overview

Extend the network to include **playing career connections**:
- Coach ↔ Coach (former teammates)
- SD ↔ Coach (former teammates)
- SD ↔ SD (former teammates)

This adds a crucial dimension: **"They played together → Now they work together"**

---

## Data Sources

### Existing Infrastructure
**Already available:** `execution/scrape_teammates.py`
- Scrapes Transfermarkt player profiles
- Extracts career history with all clubs
- Identifies teammates at each club/season

### Target Data
- **Playing careers** for all 1,057 coaches
- **Playing careers** for all 15 SDs
- **Teammate relationships** across ~20 years of professional football

---

## Implementation Plan

### Phase 1: Scrape Playing Careers (2-3 hours)

**Script:** `execution/scrape_playing_careers_bulk.py` (to create)

```python
def scrape_playing_career(person_name, transfermarkt_url):
    """
    Extract playing career from Transfermarkt player page

    Returns:
    {
        'name': str,
        'playing_career': [
            {
                'club': str,
                'season': str,  # e.g., "2010/11"
                'appearances': int,
                'goals': int
            }
        ]
    }
    """
```

**Target:**
- 1,057 coaches (many were professional players)
- 15 SDs (most were players)
- Total: ~1,000 profiles (not all coaches have playing careers on Transfermarkt)

**Rate Limiting:**
- 4 seconds between requests
- Estimated time: ~1-2 hours for 1,000 profiles

---

### Phase 2: Identify Teammate Overlaps (10 minutes)

**Script:** `execution/identify_teammate_connections.py` (to create)

```python
def find_teammate_overlaps(playing_career_a, playing_career_b):
    """
    Find seasons where two people played at same club

    Returns: [
        {
            'club': 'Bayern Munich',
            'seasons': ['2010/11', '2011/12'],
            'years_together': 2
        }
    ]
    """
```

**Logic:**
- Match clubs (normalized)
- Match seasons
- Count years together
- Calculate relationship strength

**Expected Results:**
- ~500-1,000 teammate connections
- Strong connections: 5+ seasons together
- Recent connections: Post-2010

---

### Phase 3: Add to Network (5 minutes)

**Update:** `execution/build_network_graph.py`

**New Edge Type:** `playing_career_teammates`

```json
{
  "source": "niko_kovac",
  "target": "robert_kovac",
  "relationship_type": "playing_career_teammates",
  "strength": 85,
  "total_years": 12,
  "clubs_together": 3,
  "overlaps": [
    {
      "club": "Bayern Munich",
      "seasons": "2001-2003",
      "years": 2
    },
    {
      "club": "Hertha BSC",
      "seasons": "1996-2001",
      "years": 5
    },
    {
      "club": "Croatia National Team",
      "seasons": "1996-2009",
      "years": 13
    }
  ]
}
```

---

## Use Cases

### 1. "Former Teammates" Network
Filter network to only show:
- Coaches who played together
- Now working at same/different clubs
- Hiring patterns based on playing relationships

**Example:**
- **Niko Kovac ↔ Robert Kovac**
  - Played together: 12 years (Bayern, Hertha, Croatia)
  - Now both coaches in Bundesliga
  - Hiring likelihood: High (family + long playing history)

### 2. SD-Coach Playing Connections
Identify SDs who hire coaches they played with

**Example:**
- **Max Eberl (SD) ↔ Vincent Kompany (Coach)**
  - Did they play together? Check overlaps
  - If yes: Strong connection for hiring decision

### 3. Career Progression Tracking
Visualize: **Player → Assistant Coach → Head Coach → SD**

Track complete career arcs with relationships at each stage

---

## Expected Insights

### Pattern 1: "Teammate → Co-Workers"
- Coaches who played together tend to work together
- Especially strong in youth systems (ex-players become academy coaches)

### Pattern 2: "National Team Bonds"
- National team teammates often reunite at club level
- Example: German national team players → Bundesliga coaching staff

### Pattern 3: "Club Loyalty"
- Ex-players returning to clubs as coaches/SDs
- Long playing career at club = higher chance of coaching there

---

## Technical Considerations

### Data Quality
- **Challenge:** Not all coaches have playing careers on Transfermarkt
- **Solution:** Mark as "no_playing_career" if not found
- **Fallback:** Use Wikipedia/other sources for top coaches

### Matching Accuracy
- **Challenge:** Name variations (Niko vs Nikolaus Kovac)
- **Solution:** Use Transfermarkt ID matching when available
- **Validation:** Check birth year, nationality for disambiguation

### Scale
- **Current Network:** 1,095 nodes, 38,773 edges
- **After Adding Players:** ~1,095 nodes (same), ~39,500 edges (+500-1,000)
- **Density:** Minimal increase (teammates are sparse)

---

## Timeline

**Total Estimated Time:** 3-4 hours

1. **Scraping:** 2 hours (1,000 profiles × 4s + processing)
2. **Analysis:** 30 minutes (identify overlaps)
3. **Integration:** 30 minutes (add to network graph)
4. **Export:** 10 minutes (regenerate all formats)
5. **Validation:** 30 minutes (spot checks, quality assurance)

---

## Dependencies

### Required
- ✅ `execution/scrape_teammates.py` (already exists)
- ✅ `master_coach_profiles.json` (has coach names + URLs)
- ✅ `merge_overlapping_periods()` logic (for season overlaps)

### Optional
- 🔄 Wikipedia scraper for non-Transfermarkt playing careers
- 🔄 Manual validation dataset (top 50 coaches)

---

## Output Files

### New Data Files
- `data/playing_careers.json` - All playing careers
- `data/teammate_connections.json` - Teammate overlaps
- `data/player_to_coach_progressions.json` - Career arcs

### Updated Network Files
- `data/network_graph.json` (with teammate edges)
- `data/network_graph.gexf` (Gephi)
- `data/network_graph_d3.json` (D3.js)
- `data/network_nodes.csv` + `network_edges.csv` (Excel)

### New Analysis
- `data/playing_career_summary.json` - Stats on player→coach paths
- `PLAYING_CAREER_INSIGHTS.md` - Analysis report

---

## Future Extensions (Post-Phase)

### 1. Player Transfer Network
- Which coaches signed players they played with?
- Which SDs recruit former teammates?

### 2. Youth Academy Connections
- Coaches who played in a club's youth system
- Now coaching at the same club

### 3. International Networks
- National team connections
- Cross-country coaching movements

---

**Status:** Ready to implement when requested

**Trigger:** User says "start player connections" or similar
