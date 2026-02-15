# 🚀 Mass Scraping In Progress

**Started:** 2026-02-10
**Status:** Running all 3 phases sequentially
**Expected Duration:** 8-12 hours
**Expected Results:** ~17,000 data points

---

## 📋 Phases

### Phase 1: Bundesliga Staff ⏳
- **Target:** 18 clubs × ~100 staff = ~1,800 profiles
- **Duration:** 3-4 hours
- **Script:** `execution/scrape_club_staff_pages.py`
- **Log:** `/tmp/bundesliga_scrape.log`
- **Output:** `preload/{coach}/profile.json`

### Phase 2: 2. Bundesliga Staff ⏳
- **Target:** 8 clubs × ~50 staff = ~400 profiles
- **Duration:** 1-2 hours
- **Script:** `execution/scrape_2bundesliga_staff.py`
- **Log:** `/tmp/2bundesliga_scrape.log`
- **Output:** `preload/{coach}/profile.json`

### Phase 3: Companions Bulk ⏳
- **Target:** ~2,200 coaches × ~75 connections = ~15,000 connections
- **Duration:** 4-6 hours
- **Script:** `execution/scrape_companions_bulk.py`
- **Log:** `/tmp/companions_scrape.log`
- **Output:** `preload/{coach}/companions.json`

---

## 🔍 How to Monitor

### Check if still running:
```bash
ps aux | grep python | grep scrape
```

### View live logs:
```bash
# Current phase log
tail -f /tmp/bundesliga_scrape.log
tail -f /tmp/2bundesliga_scrape.log
tail -f /tmp/companions_scrape.log
```

### Check progress stats:
```bash
cd "/Users/cmk/Documents/Football Coaches DB"
python3 execution/monitor_scraping_progress.py
```

### Watch progress continuously (refresh every 60s):
```bash
python3 execution/monitor_scraping_progress.py watch 60
```

### Quick profile count:
```bash
ls -1 preload/*/profile.json 2>/dev/null | wc -l
ls -1 preload/*/companions.json 2>/dev/null | wc -l
```

---

## 🛑 How to Stop

### Stop gracefully:
Press `Ctrl+C` in the terminal running the script.

Progress is saved automatically - you can resume later.

### Force stop:
```bash
pkill -f run_mass_scraping
```

---

## ⚠️ If Something Goes Wrong

### Script hangs:
1. Check the current log file for errors
2. Stop the process (Ctrl+C or pkill)
3. Check which phase failed
4. Run that phase individually to debug

### Network errors / Rate limiting:
The scripts have built-in delays (3-5s between requests) and retry logic. If Transfermarkt blocks you:
- Wait 15-30 minutes
- Resume the scraping (scripts skip already-scraped coaches)

### Disk space:
Each profile is ~5-20KB. Total expected: ~50-100MB.
Check available space:
```bash
df -h /Users/cmk/Documents/
```

---

## 📊 Expected Results

After completion:

```
preload/
├── julian_nagelsmann/
│   ├── profile.json
│   └── companions.json
├── thomas_tuchel/
│   ├── profile.json
│   └── companions.json
├── ... (~2,200 coaches)

data/
├── bundesliga_staff_scrape_summary.json
├── 2bundesliga_staff_scrape_summary.json
└── companions_bulk_scrape_summary.json
```

**Metrics:**
- ~2,200 coach profiles
- ~15,000 companion connections
- ~10,000 teammate links
- ~5,000 management links

---

## ✅ When Complete

1. Run final stats:
   ```bash
   python3 execution/monitor_scraping_progress.py
   ```

2. Check summary files:
   ```bash
   cat data/bundesliga_staff_scrape_summary.json
   cat data/2bundesliga_staff_scrape_summary.json
   cat data/companions_bulk_scrape_summary.json
   ```

3. Ready for Spider Web building! 🕸️

---

**Master Script:** `execution/run_mass_scraping.py`
**All logs:** `/tmp/*_scrape.log`
