# 🌙 Overnight Scraping - Ready to Start

**Created:** 12. Februar 2026, 23:30 Uhr
**Status:** ✅ READY TO LAUNCH

---

## 📋 Was läuft overnight:

### **Phase 1: Squad Pages (15 Minuten)**
- Scrape alle Bundesliga Kader-Seiten 2015-2026
- 18 Clubs × 11 Seasons = 198 Seiten
- Extrahiere ~3,000 unique player URLs
- **Output:** `data/bundesliga_players_2015_2026/players_master_urls.json`

### **Phase 2: Player Profiles (5-6 Stunden)**
- Scrape alle 3,000 Spieler-Profile
- Extract complete career history
- Filter auf 2015+ mit timestamps
- **Output:** `data/bundesliga_players_2015_2026/profiles/` (3,000 JSON files)

---

## 🚀 Wie starten:

### **Option 1: Automatic (Empfohlen)**
```bash
cd "/Users/cmk/Documents/Football Coaches DB"
./run_overnight_player_scraping.sh
```

Das Script:
- Läuft beide Phasen automatisch
- Verhindert Sleep mit `caffeinate`
- Loggt alles nach `logs/`
- Erstellt Summary am Ende

### **Option 2: Manual (Phase by Phase)**
```bash
# Phase 1
caffeinate -i python3 execution/scrape_bundesliga_squads_2015_2026.py

# Phase 2 (nach Phase 1)
caffeinate -i python3 execution/scrape_player_profiles_with_timestamps.py
```

---

## 📊 Was du bekommst:

### **Player Profile Structure:**
```json
{
  "player_id": "8198",
  "name": "Thomas Müller",
  "url": "https://www.transfermarkt.de/...",
  "nationality": "Deutschland",
  "dob": "13.09.1989",
  "age": 37,
  "position": "Attacking Midfield",
  "height": "1,85 m",
  "foot": "right",
  "career_history": [
    {
      "season": "2015/16",
      "club": "Bayern München",
      "club_id": "27",
      "games": 31,
      "goals": 8,
      "assists": 12
    },
    {
      "season": "2016/17",
      "club": "Bayern München",
      "club_id": "27",
      "games": 29,
      "goals": 5,
      "assists": 13
    },
    ...
  ]
}
```

### **Data Files:**
```
data/bundesliga_players_2015_2026/
├── players_master_urls.json       # All player URLs (~3,000)
├── profiles/                       # Individual profiles
│   ├── thomas_muller_8198.json
│   ├── robert_lewandowski_38253.json
│   └── ... (3,000 files)
├── scraping_summary.json           # Success/fail stats
└── progress_checkpoint.json        # Resume point if interrupted
```

---

## ⏱️ Timeline:

| Time | Phase | Activity |
|------|-------|----------|
| 23:30 | Start | Launch script |
| 23:30-23:45 | Phase 1 | Squad pages (15 min) |
| 23:45-06:00 | Phase 2 | Player profiles (6h) |
| 06:00 | Complete | Summary generated |

**Expected Completion:** ~06:00-07:00 Uhr morgens

---

## 📈 Expected Results:

**Minimum Success:**
- ✅ 2,500+ player profiles
- ✅ 90%+ with career timestamps
- ✅ All 18 Bundesliga clubs covered

**Full Success:**
- ✅ 3,000+ player profiles
- ✅ 95%+ with career timestamps
- ✅ Complete 2015-2026 coverage

---

## 🔍 Monitoring:

### **Check Progress (während es läuft):**
```bash
# Phase 1 log
tail -f logs/overnight_phase1_squads.log

# Phase 2 log
tail -f logs/overnight_phase2_profiles.log

# Progress checkpoint
cat data/bundesliga_players_2015_2026/progress_checkpoint.json
```

### **Morning Check:**
```bash
# Summary
cat data/bundesliga_players_2015_2026/scraping_summary.json

# Count profiles
ls data/bundesliga_players_2015_2026/profiles/ | wc -l
```

---

## ⚠️ Wichtig:

### **Vor dem Start:**
1. ✅ Laptop an Strom anschließen
2. ✅ WLAN stabil (Ethernet besser)
3. ✅ Genug Speicherplatz (~20MB benötigt)

### **Während des Laufs:**
- ❌ **NICHT** Laptop schließen (caffeinate verhindert Sleep)
- ❌ **NICHT** WLAN trennen
- ❌ **NICHT** Script abbrechen (Ctrl+C)
- ✅ **OK** Laptop offen lassen (Display kann dimmen)

### **Bei Unterbrechung:**
- Script speichert Progress alle 100 Players
- Kann fortgesetzt werden (gleichen Command erneut starten)
- Überspringt bereits gespeicherte Profile

---

## 🎯 Next Steps:

**Jetzt:**
```bash
cd "/Users/cmk/Documents/Football Coaches DB"
./run_overnight_player_scraping.sh
```

**Morgen (nach Completion):**
1. Check Summary: `cat data/bundesliga_players_2015_2026/scraping_summary.json`
2. Validate Data: `python3 execution/validate_player_profiles.py`
3. Integrate into Network: `python3 execution/integrate_players_into_network.py`

---

## 📊 Current Status:

**Coach Re-Scraping:**
- Status: Running in background
- Progress: ~50% (estimated)
- ETA: ~00:00 Uhr

**Player Scraping:**
- Status: ✅ Ready to start
- Scripts: Built and tested
- Waiting for: Your command!

---

**Ready to start?**

Run:
```bash
cd "/Users/cmk/Documents/Football Coaches DB"
./run_overnight_player_scraping.sh
```

**Or wait for coach re-scraping to finish first (~30 min)**

---

**Files created:**
- ✅ `execution/scrape_bundesliga_squads_2015_2026.py`
- ✅ `execution/scrape_player_profiles_with_timestamps.py`
- ✅ `run_overnight_player_scraping.sh`
- ✅ `OVERNIGHT_PLAYER_SCRAPING_PLAN.md`
- ✅ `OVERNIGHT_SCRAPING_READY.md` (this file)

**Status:** 🟢 READY TO LAUNCH
