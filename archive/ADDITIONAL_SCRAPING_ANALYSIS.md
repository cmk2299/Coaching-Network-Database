# Zusätzliches Scraping - Was können wir noch extrahieren?

**Datum:** 11. Februar 2026
**Status:** Analyse für Datenqualität-Verbesserung

---

## 🎯 Ziel

Die Datenqualität von **6/10 auf 9/10** verbessern durch Hinzufügen fehlender Metadaten.

---

## ❌ Aktuell Fehlende Daten (0% Vollständigkeit)

### 1. **Nationality** - 0%
**Impact:** HOCH (kritisch für internationales Headhunting)

**Was wir brauchen:**
- Land/Länder der Staatsbürgerschaft
- Beispiel: "Deutschland", "Spanien", "Kroatien"

**Aktueller Status:**
- Scraper-Code **existiert bereits** (Zeile 183-184, 215-218)
- Sucht nach "Nationalität" in HTML
- **Funktioniert offenbar nicht** → HTML-Struktur hat sich geändert

**Behebung:**
- HTML-Struktur von Transfermarkt analysieren
- Scraper-Selektoren aktualisieren
- Re-scrape alle 1,059 Profile
- **Aufwand:** 2-3 Stunden

---

### 2. **Age / Date of Birth** - 0%
**Impact:** MITTEL-HOCH (wichtig für Karriere-Phase Analyse)

**Was wir brauchen:**
- Geburtsdatum: z.B. "25. November 1981 (43)"
- Oder nur Alter: z.B. "43 Jahre"

**Aktueller Status:**
- Scraper-Code **existiert bereits** (Zeile 185-189, 219-223)
- Sucht nach "Geburtsdatum", "geb./alter", "Alter"
- **Funktioniert offenbar nicht** → HTML-Struktur hat sich geändert

**Behebung:**
- Gleiches Problem wie Nationality
- Update Scraper-Selektoren
- Re-scrape alle Profile
- **Aufwand:** Zusammen mit Nationality (gleicher Update)

---

### 3. **Birthplace** - 0%
**Impact:** NIEDRIG (interessant, aber nicht kritisch)

**Was wir brauchen:**
- Geburtsort: z.B. "Berlin, Deutschland"

**Aktueller Status:**
- Scraper-Code **existiert bereits** (Zeile 190-191)
- **Funktioniert offenbar nicht**

**Behebung:**
- Teil des gleichen Scraper-Updates
- **Aufwand:** Inkludiert in 2-3h oben

---

### 4. **License** - 1%
**Impact:** MITTEL (wichtig für Qualifikations-Check)

**Was wir brauchen:**
- Trainerlizenz: z.B. "UEFA Pro Licence", "DFB-Fußball-Lehrer"

**Aktueller Status:**
- Scraper-Code **existiert bereits** (Zeile 192-193, 205-210)
- **Fast nie vorhanden** auf Transfermarkt
- Nur 10 von 1,059 Profilen haben Lizenz-Daten

**Problem:**
- Transfermarkt listet Lizenzen selten
- Daten meist nicht öffentlich verfügbar
- Müssten von UEFA/DFB/Verbänden kommen

**Behebung:**
- ⚠️ **Nicht lösbar** nur mit Transfermarkt
- Alternative Quelle nötig (UEFA, DFB, manuelle Eingabe)
- **Aufwand:** Hoch (neue Datenquelle erschließen)

---

## ✅ Bereits Vorhandene Daten (100% Vollständigkeit)

### 5. **Image URL** - 100% ✅
**Was wir haben:**
- Profilbild URL: z.B. "https://img.a.transfermarkt.technology/portrait/header/10463-1657202037.jpg"

**Verwendung:**
- Dashboard zeigt Profilbilder
- Visuelle Identifikation

---

### 6. **Contract Until** - ~80% ✅
**Was wir haben:**
- Vertragsende: z.B. "30/06/2027"

**Verwendung:**
- Availability-Check (Wann ist Coach frei?)
- Transfer-Timing

**Hinweis:**
- Nicht alle Coaches haben aktiven Vertrag (Vereinslose)
- Daher nur ~80% Abdeckung (normal)

---

## 🔍 Zusätzliche Scraping-Möglichkeiten

### 7. **Preferred Formation** - 0% (NEUE IDEE)
**Impact:** HOCH (taktisches Profil)

**Was wir bekommen könnten:**
- Bevorzugte Formation: z.B. "4-3-3", "3-5-2", "4-4-2"

**Quelle:**
- Transfermarkt zeigt "Preferred formation" auf Coach-Profil
- Beispiel: "4-3-3 attacking" (Xabi Alonso)

**Value für Kunden:**
- Taktische Kompatibilität prüfen
- Spielphilosophie erkennen
- Matching mit Kader (passt Formation zu Spielermaterial?)

**Behebung:**
- HTML analysieren
- Neuen Parser hinzufügen
- **Aufwand:** 1-2 Stunden

---

### 8. **Social Media Links** - 0% (NEUE IDEE)
**Impact:** NIEDRIG-MITTEL (zusätzlicher Kontext)

**Was wir bekommen könnten:**
- Instagram: @xabialonso
- Twitter/X: @MisterXabi
- Facebook Page

**Quelle:**
- Transfermarkt hat manchmal Social Media Icons
- Nicht immer vorhanden

**Value für Kunden:**
- Direkter Kontakt
- Öffentliche Kommunikation analysieren
- Reichweite / Popularität messen

**Behebung:**
- HTML analysieren
- Icons/Links parsen
- **Aufwand:** 2 Stunden

---

### 9. **Career Stats Summary** - 0% (NEUE IDEE)
**Impact:** SEHR HOCH (Performance-Metriken)

**Was wir bekommen könnten:**
- **Total Games Coached:** 500+ Spiele
- **Win Rate:** 55% Siege
- **Average PPM (Points per Match):** 1.8
- **Total Trophies:** 5 Titel

**Quelle:**
- Transfermarkt hat diese Daten **aggregate**
- Müssten berechnet werden aus Career History

**Value für Kunden:**
- **Performance-Bewertung** (objektive Metriken)
- **Vergleichbarkeit** zwischen Coaches
- **Success Rate** auf einen Blick

**Behebung:**
- HTML für Statistik-Sektion analysieren
- Oder: Selbst berechnen aus Career History + Spieldaten
- **Aufwand:** 4-6 Stunden (komplex)

---

### 10. **Agent / Berater Information** - ~5% (BEREITS IM CODE)
**Impact:** MITTEL (Geschäftsbeziehungen)

**Was wir bekommen könnten:**
- Agent Name: z.B. "Karlheinz Förster"
- Agent Agency: z.B. "SportsTotal"
- Agent URL: Link zu Berater-Profil

**Quelle:**
- Transfermarkt listet manchmal Berater
- Nicht für alle Coaches vorhanden

**Aktueller Status:**
- Scraper-Code **existiert bereits** (Zeile 194-199)
- **Funktioniert vermutlich**, aber wenig Daten vorhanden

**Value für Kunden:**
- Geschäftsnetzwerk verstehen
- Berater-Empfehlungen (welcher Agent hat gute Coaches?)

**Behebung:**
- Prüfen ob Code funktioniert
- Ggf. Selektoren updaten
- **Aufwand:** 1 Stunde

---

### 11. **Player Career Data** - 63% (BEREITS TEILWEISE VORHANDEN)
**Impact:** HOCH (Verbindungen zu Ex-Mitspielern)

**Was wir haben:**
- 666 Coaches mit Teammate-Daten
- 434 Coach-zu-Coach Verbindungen aus Spielerkarriere

**Was fehlt:**
- 393 Coaches ohne Teammate-Daten

**Quelle:**
- Transfermarkt .de gemeinsameSpiele Seite

**Behebung:**
- Remaining 393 Coaches scrapen
- **Aufwand:** 6-8 Stunden (bereits geplant)

---

### 12. **Club-Level Stats** - 0% (NEUE IDEE)
**Impact:** SEHR HOCH (Erfolgsmetriken pro Club)

**Was wir bekommen könnten:**
```json
{
  "club": "Bayern Munich",
  "period": "2018-2019",
  "games": 65,
  "wins": 42,
  "draws": 11,
  "losses": 12,
  "win_rate": 64.6,
  "ppg": 2.08,
  "trophies": ["Bundesliga", "DFB-Pokal"]
}
```

**Quelle:**
- Transfermarkt hat detaillierte Statistiken pro Station
- Click auf Career History Station → Statistik-Detail-Seite

**Value für Kunden:**
- **Performance pro Club** sehen
- **Trend erkennen** (besser/schlechter über Zeit?)
- **Club-Fit** analysieren (erfolgreich bei großen vs. kleinen Clubs?)

**Behebung:**
- Für jede Career Station zusätzlichen Request
- 1,005 Coaches × 4 Stationen = ~4,000 Requests
- **Aufwand:** 8-12 Stunden (viele Requests + Parsing)

---

## 📊 Priorisierung - Was lohnt sich?

### **Tier 1: MUST-HAVE (Quick Wins)**

| Feature | Impact | Effort | Value/Effort | Status |
|---------|--------|--------|--------------|--------|
| **Nationality** | HOCH | 2h | ⭐⭐⭐⭐⭐ | Fix Scraper |
| **Age/DOB** | HOCH | 2h | ⭐⭐⭐⭐⭐ | Fix Scraper |
| **Birthplace** | NIEDRIG | 0h | ⭐⭐⭐ | Inkludiert |
| **Remaining Teammates** | HOCH | 8h | ⭐⭐⭐⭐ | New Scrape |

**Total Tier 1:** 12 Stunden → **Datenqualität 6/10 → 9/10**

---

### **Tier 2: NICE-TO-HAVE (High Value)**

| Feature | Impact | Effort | Value/Effort | Status |
|---------|--------|--------|--------------|--------|
| **Career Stats Summary** | SEHR HOCH | 6h | ⭐⭐⭐⭐⭐ | New Feature |
| **Preferred Formation** | HOCH | 2h | ⭐⭐⭐⭐ | New Feature |
| **Agent Information** | MITTEL | 1h | ⭐⭐⭐⭐ | Fix Scraper |

**Total Tier 2:** 9 Stunden → **Neue USPs**

---

### **Tier 3: ADVANCED (High Effort, High Value)**

| Feature | Impact | Effort | Value/Effort | Status |
|---------|--------|--------|--------------|--------|
| **Club-Level Stats** | SEHR HOCH | 12h | ⭐⭐⭐⭐ | New Feature |
| **Social Media Links** | NIEDRIG | 2h | ⭐⭐ | New Feature |
| **License (external)** | MITTEL | 20h+ | ⭐ | New Source |

**Total Tier 3:** 34+ Stunden → **Advanced Features**

---

## 🎯 Empfehlung

### **Phase 1: Fix Existing Scrapers (2-3 Stunden)**

**Ziel:** Datenqualität von 6/10 auf 8/10

**Tasks:**
1. ✅ Transfermarkt HTML-Struktur für Nationality analysieren
2. ✅ Transfermarkt HTML-Struktur für Age/DOB analysieren
3. ✅ Scraper-Selektoren in `scrape_transfermarkt.py` updaten
4. ✅ Test-Scrape auf 10 Profilen
5. ✅ Full Re-Scrape aller 1,059 Profile (~70 Minuten bei 4s/coach)
6. ✅ Validierung (sollte 90%+ Nationality, 90%+ Age haben)

**Expected Result:**
```
Nationality: 0% → 90%+
Age/DOB: 0% → 90%+
Birthplace: 0% → 80%+
```

---

### **Phase 2: Complete Teammate Network (8 Stunden)**

**Ziel:** Netzwerk von 63% auf 100%

**Tasks:**
1. ✅ Scrape remaining 393 Coaches (Teammates)
2. ✅ Integrate new connections into network
3. ✅ Validate & export updated network

**Expected Result:**
```
Coaches with Teammates: 666 (63%) → 1,059 (100%)
Teammate Connections: 434 → ~700+
```

---

### **Phase 3: Add Formation & Agent (3 Stunden)**

**Ziel:** Neue taktische Insights

**Tasks:**
1. ✅ Parse "Preferred Formation" from Transfermarkt
2. ✅ Fix Agent parsing (if broken)
3. ✅ Re-scrape profiles with new fields
4. ✅ Add to dashboard display

**Expected Result:**
```
Preferred Formation: 0% → 70%+ (nicht alle haben)
Agent Information: 5% → 20%+
```

---

### **Phase 4: Career Stats (6 Stunden) - OPTIONAL**

**Ziel:** Performance-Metriken

**Tasks:**
1. ✅ Calculate aggregate stats from Career History
2. ✅ Win Rate, PPG, Total Games, Trophies
3. ✅ Add to profiles
4. ✅ Add to dashboard (sortable table)

**Expected Result:**
```
Every coach has:
- Total Games Coached
- Career Win Rate
- Average PPG
- Career Length
```

---

## 📈 Value Proposition nach Scraping

### **Aktuell (Status Quo):**
- Datenqualität: 6/10
- Einzigartigkeit: 10/10 (Network Graph)
- Marktreife: 7/10

### **Nach Phase 1 (3 Stunden):**
- Datenqualität: 8/10 ✅
- Nationality & Age verfügbar
- International einsetzbar

### **Nach Phase 2 (11 Stunden):**
- Datenqualität: 9/10 ✅
- Vollständiges Teammate-Netzwerk
- 700+ Coach-Verbindungen aus Spielerkarriere

### **Nach Phase 3 (14 Stunden):**
- Datenqualität: 9/10 ✅
- **Taktisches Profil** (Formation)
- **Business Network** (Agents)
- **Neue USPs**

### **Nach Phase 4 (20 Stunden):**
- Datenqualität: 10/10 ✅
- **Performance-Metriken** (Win Rate, PPG)
- **Objektive Vergleichbarkeit**
- **Wissenschaftlich fundiert**

---

## 🏆 Finale Datenqualität

### **Mit minimalem Aufwand (3h):**
```
Career History:      95% ✅ (vorhanden)
Current Position:   100% ✅ (vorhanden)
Nationality:         90% ✅ (NEU)
Age/DOB:             90% ✅ (NEU)
Birthplace:          80% ⭐ (NEU)
Network Connections: 100% ✅ (vorhanden)
Image URL:          100% ✅ (vorhanden)
Contract Until:      80% ✅ (vorhanden)
License:              1% ⚠️ (externe Quelle nötig)

OVERALL SCORE: 8/10
```

### **Mit vollem Aufwand (20h):**
```
+ Preferred Formation:  70% ✅ (NEU)
+ Agent Information:    20% ✅ (NEU)
+ Teammate Network:    100% ✅ (von 63%)
+ Career Stats:        100% ✅ (NEU)
  - Total Games
  - Win Rate
  - Average PPG
  - Career Length

OVERALL SCORE: 10/10
```

---

## 💡 Zusammenfassung

### **Was wir zusätzlich scrapen sollten:**

**MUST (3 Stunden):**
1. ✅ Nationality
2. ✅ Age/DOB
3. ✅ Birthplace

**SHOULD (11 Stunden):**
4. ✅ Remaining 393 Teammate Networks

**NICE (17 Stunden):**
5. ✅ Preferred Formation
6. ✅ Agent Information
7. ✅ Career Stats (Win Rate, PPG, Games)

**FUTURE:**
8. ⚠️ Club-Level Stats (detailliert pro Station)
9. ⚠️ Social Media Links
10. ⚠️ License (externe Quelle)

---

**Erstellt:** 11. Februar 2026
**Status:** Bereit für Implementierung
**Nächster Schritt:** Phase 1 (Nationality + Age Scraper Fix)
