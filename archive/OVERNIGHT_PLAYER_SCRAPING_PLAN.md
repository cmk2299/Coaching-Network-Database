# Overnight Bundesliga Player Scraping Plan

**Created:** 12. Februar 2026, 23:15 Uhr
**Goal:** Scrape as many Bundesliga players as possible overnight with club timestamps since 2015
**Timeline:** ~8-10 hours (overnight)

---

## 🎯 Scope

**Target:** Alle Bundesliga-Spieler seit 2015 bis 2026

**Data needed:**
- Player name
- Player ID
- Position
- Nationality
- Age/DOB
- **Club history with timestamps (seit 2015)**
  - Club name
  - Start date (DD/MM/YYYY)
  - End date (DD/MM/YYYY)
  - Games played
  - Goals/Assists

---

## 📊 Estimated Volume

### **Bundesliga Seasons 2015-2026:**
- Seasons: 11 (2015/16 bis 2025/26)
- Clubs per season: 18
- Players per club per season: ~25-30
- **Total player-seasons:** 18 × 11 × 27 = 5,346

### **Unique Players (accounting for transfers):**
- Estimated: **2,500-3,000 unique players**
- Many players played for multiple clubs
- Some only 1-2 seasons

---

## ⏱️ Time Estimation

**Per Player:**
- Profile page: 4s delay
- Parse profile: 2s
- **Total:** ~6s per player

**Total Time:**
- 3,000 players × 6s = 18,000s = **300 minutes = 5 hours**
- With overhead: **6-7 hours**

**Feasible overnight:** ✅ Yes!

---

## 🗂️ Data Strategy

### **Step 1: Get Squad Lists (Fast)**
For each season 2015/16 to 2025/26:
- For each of 18 Bundesliga clubs:
  - Scrape squad page: `transfermarkt.de/{club}/kader/verein/{id}/saison_id/{year}`
  - Extract player URLs
  - **Time:** 18 clubs × 11 seasons × 4s = 792s = **13 minutes**

**Output:** List of all unique player URLs (~3,000)

---

### **Step 2: Scrape Player Profiles (Slow)**
For each unique player:
- Fetch profile: `transfermarkt.de/{player}/profil/spieler/{id}`
- Extract:
  - Name, Position, Nationality, DOB
  - **Career History table (KRITISCH!)**
    - All clubs with start/end dates
    - Filter to 2015+
    - Include games, goals, assists

**Output:** 3,000 player profiles with full career history

---

### **Step 3: Filter & Structure**
- Keep only Bundesliga clubs
- Keep only periods 2015+
- Structure data for network integration

---

## 📋 Implementation Plan

### **Script 1: `scrape_bundesliga_squads_2015_2026.py`**

**Purpose:** Get all player URLs from squad pages

```python
# Pseudocode
clubs = get_bundesliga_clubs()  # 18 clubs
seasons = range(2015, 2027)  # 2015-2026

all_players = set()

for season in seasons:
    for club in clubs:
        url = f"transfermarkt.de/{club}/kader/verein/{club_id}/saison_id/{season}"
        players = extract_player_urls(url)
        all_players.update(players)

save_json(all_players, 'data/bundesliga_players_urls_2015_2026.json')
```

**Time:** ~15 minutes
**Output:** ~3,000 player URLs

---

### **Script 2: `scrape_player_profiles_bulk.py`**

**Purpose:** Scrape full profiles with career history

```python
# Pseudocode
player_urls = load_json('data/bundesliga_players_urls_2015_2026.json')

for url in player_urls:
    profile = scrape_player_profile(url)

    # Extract career history
    career = []
    for row in profile.career_table:
        club, start, end, games, goals = parse_row(row)

        # Filter to 2015+
        if year(start) >= 2015:
            career.append({
                'club': club,
                'start_date': start,  # DD/MM/YYYY
                'end_date': end,      # DD/MM/YYYY
                'games': games,
                'goals': goals,
                'assists': assists
            })

    save_player(profile)
    sleep(4)  # Rate limiting
```

**Time:** ~5-6 hours
**Output:** 3,000 player profiles

---

## 🎯 Data Structure

### **Player Profile:**
```json
{
  "player_id": "8198",
  "name": "Thomas Müller",
  "position": "Attacking Midfield",
  "nationality": "Deutschland",
  "dob": "13.09.1989",
  "age": 37,
  "career_history": [
    {
      "club": "Bayern München",
      "club_id": "27",
      "start_date": "01.07.2008",
      "end_date": "present",
      "seasons": ["2015/16", "2016/17", ... "2025/26"],
      "total_games": 450,
      "total_goals": 180,
      "total_assists": 150
    }
  ]
}
```

---

## 🚀 Execution Plan

### **Phase 1: Squad Lists (Now - 23:30)**
- Run `scrape_bundesliga_squads_2015_2026.py`
- Get all player URLs
- **Duration:** 15 minutes

### **Phase 2: Player Profiles (23:30 - 06:00)**
- Run `scrape_player_profiles_bulk.py`
- Scrape overnight
- **Duration:** 6-7 hours

### **Phase 3: Validation (Morning)**
- Check completeness
- Validate timestamps
- Quality report

---

## 💾 Storage

**Estimated size:**
- 3,000 players × 3KB average = **9MB**
- With career data: **15-20MB**

**Location:**
- `data/bundesliga_players_2015_2026/`
  - `profiles/` (3,000 JSON files)
  - `players_master.json` (consolidated)
  - `players_urls.json` (URL list)

---

## ⚠️ Risks & Mitigations

### **Risk 1: Rate Limiting**
- **Mitigation:** 4s delay (conservative)
- **Fallback:** Resume capability (save after each player)

### **Risk 2: HTML Structure Changes**
- **Mitigation:** Robust selectors with fallbacks
- **Fallback:** Log failed players, retry later

### **Risk 3: Time Overrun**
- **Mitigation:** Prioritize recent players (2020+)
- **Fallback:** Can continue next night

### **Risk 4: Computer Sleep**
- **Mitigation:** Disable sleep for duration
- **Command:** `caffeinate -i python3 script.py`

---

## 📊 Success Criteria

**Minimum Success:**
- ✅ 2,000+ player profiles
- ✅ 90%+ have career timestamps
- ✅ All Bundesliga clubs covered 2015+

**Full Success:**
- ✅ 3,000+ player profiles
- ✅ 95%+ have career timestamps
- ✅ Complete coverage 2015-2026

---

## 🎯 Next Steps

1. **Build Squad Scraper** (30 min)
   - Get Bundesliga club list
   - Scrape squad pages
   - Extract player URLs

2. **Build Player Scraper** (1 hour)
   - Parse player profiles
   - Extract career history
   - Filter to 2015+
   - Save with timestamps

3. **Test Scripts** (30 min)
   - Test on 10 players
   - Validate data structure
   - Check timestamps

4. **Start Overnight Job** (23:30)
   - Run with `caffeinate`
   - Monitor initial progress
   - Set alarm for morning check

---

**Timeline:**
- 23:15-23:45: Build scripts
- 23:45-00:00: Test scripts
- 00:00-06:00: Overnight scraping
- 06:00-06:30: Morning validation

**Expected Result by Morning:**
- 2,500-3,000 player profiles ✅
- Complete career timestamps seit 2015 ✅
- Ready for network integration ✅

---

**Status:** Ready to build scripts
**Next:** Create `scrape_bundesliga_squads_2015_2026.py`
