# Bundesliga 2024/25 - Sporting Directors Coverage

## ✅ Complete Coverage: 18/18 Sporting Directors

| # | Club | Sporting Director | Role | Career Stations |
|---|------|-------------------|------|-----------------|
| 1 | FC Bayern München | Max Eberl | Sportvorstand | 4 |
| 2 | Borussia Dortmund | Lars Ricken | Geschäftsführer Sport | 3 |
| 3 | RB Leipzig | Marcel Schäfer | Geschäftsführer Sport | 3 |
| 4 | Bayer 04 Leverkusen | Simon Rolfes | Geschäftsführer Sport | 3 |
| 5 | VfB Stuttgart | Christian Gentner | Sportdirektor | 2 |
| 6 | Eintracht Frankfurt | Markus Krösche | Sportvorstand | 5 |
| 7 | VfL Wolfsburg | Peter Christiansen | Geschäftsführer Sport | 6 |
| 8 | SC Freiburg | Jochen Saier | Sportvorstand | 4 |
| 9 | TSG Hoffenheim | Andreas Schicker | Geschäftsführer Sport | 5 |
| 10 | 1. FC Union Berlin | Horst Heldt | Geschäftsführer Profifußball | 7 |
| 11 | Werder Bremen | Clemens Fritz | Geschäftsführer Profifußball | 4 |
| 12 | Borussia M'gladbach | Markus Aretz | Geschäftsführer Sport & Kommunikation | 3 |
| 13 | 1. FSV Mainz 05 | Niko Bungert | Sportdirektor | 5 |
| 14 | FC Augsburg | Benjamin Weber | Sportdirektor | 7 |
| 15 | 1. FC Heidenheim | Holger Sanwald | Vorstandsvorsitzender | 4 |
| 16 | FC St. Pauli | Andreas Bornemann | Geschäftsführer Sport | 7 |
| 17 | VfL Bochum | Markus Brunnschneider | Direktor Profifußball | 8 |
| 18 | 1. FC Köln | Thomas Kessler | Geschäftsführer Sport | 3 |

## 📊 Coverage Statistics

### Data Completeness
- **Total SDs Scraped:** 18/18 (100%)
- **Total Career Stations:** 83
- **Average Stations per SD:** 4.6
- **Data Source:** Transfermarkt staff pages + profile scraping

### Career History Breakdown
- **Most Experienced:** Markus Brunnschneider (8 stations)
- **Notable SDs:**
  - Andreas Bornemann (7 stations) - St. Pauli
  - Benjamin Weber (7 stations) - Augsburg
  - Horst Heldt (7 stations) - Union Berlin
  - Peter Christiansen (6 stations) - Wolfsburg
  - Markus Krösche (5 stations) - Frankfurt

### Role Distribution
- **Geschäftsführer Sport:** 9 SDs (Bayern, Dortmund, Leipzig, Leverkusen, Wolfsburg, Hoffenheim, Gladbach, St. Pauli, Köln)
- **Sportvorstand:** 3 SDs (Bayern, Frankfurt, Freiburg)
- **Sportdirektor:** 4 SDs (Stuttgart, Mainz, Augsburg)
- **Geschäftsführer Profifußball:** 2 SDs (Union Berlin, Werder Bremen)
- **Vorstandsvorsitzender:** 1 SD (Heidenheim - chairman also handles sporting duties)
- **Direktor Profifußball:** 1 SD (Bochum)

## 🎯 Intelligence Value for projectFIVE

### Core Requirement Fulfilled
**"Welcher Sportdirektor hat welchen Trainer schonmal zusammengearbeitet?"**

This dataset enables mapping SD-Coach relationships by tracking:
1. **SD Career History:** All clubs and periods where each SD worked
2. **Coach Career History:** All clubs and periods where each coach worked  
3. **Overlap Analysis:** Identify when SD and coach were at same club during same period

### Example Insights
- **Max Eberl @ Bayern (2024-present):** Vincent Kompany hired 2024
- **Max Eberl @ RB Leipzig (2022-2023):** Marco Rose coached there
- **Max Eberl @ Gladbach (2008-2022):** Multiple coaches including Marco Rose, Adi Hütter
- **Andreas Bornemann @ St. Pauli (2024):** Alexander Blessin hired 2024

## 📂 Data Structure

Each SD profile includes:
```json
{
  "name": "Max Eberl",
  "current_club": "Bayern München",
  "current_role": "Sportvorstand",
  "url": "https://www.transfermarkt.de/max-eberl/profil/trainer/6343",
  "career_history": [
    {
      "club": "Bayern München",
      "role": "Sportvorstand",
      "start_year": 2023,
      "start_period": "23/24 (01.03.2024)",
      "end_period": "vsl. 30.06.2027",
      "club_url": "..."
    }
  ],
  "total_stations": 4
}
```

## 🔄 Next Steps

### Phase 1: SD-Coach Relationship Mapping ✅ READY
With both coaches and SDs scraped, we can now:
1. Create overlap analysis function
2. Map which SDs hired which coaches
3. Identify repeated SD-Coach partnerships
4. Build "connection strength" scoring

### Phase 2: Assistant Coaches (Next)
- Scrape Co-Trainer for all 18 Bundesliga clubs
- Add to coach network data
- Enable "who worked together as assistant" intelligence

### Phase 3: Dashboard Integration
- Add SD tab to coach profiles
- Show "Hired by" relationships
- Display SD career timeline
- Cross-reference SD networks with coach networks

## 📝 Technical Notes

### Scraping Methodology
1. **Step 1:** Fetch club staff page (`/mitarbeiter/verein/{club_id}`)
2. **Step 2:** Parse inline-table elements to find SD by role keywords
3. **Step 3:** Extract SD profile URL
4. **Step 4:** Scrape full SD profile with career stations table
5. **Rate Limiting:** 5 seconds between requests

### Role Keywords Used
- Sportdirektor
- Sportvorstand  
- Sportchef
- Geschäftsführer Sport
- Geschäftsführer Profifußball
- Direktor Profifußball
- Technischer Direktor
- Vorstandsvorsitzender (for clubs where chairman handles sporting)

### Data Quality
- All 18 clubs covered
- Career histories complete with start/end years
- Role descriptions preserved from source
- TM profile URLs included for verification

---

**Scraped:** 2026-02-08  
**Script:** `execution/scrape_sporting_directors.py`  
**Output:** `data/sporting_directors_bundesliga.json`
