# 🧪 SELF-TEST PROTOCOL - Football Coaches Intelligence
## Testing alle 5 Core Requirements + UX

**Date**: 2026-02-07
**Tester**: Claude (self-test)
**Environment**: Production (Streamlit Cloud)

---

## ✅ TEST PLAN

### **TEST 1: Homepage / Entry Point**

**Goal**: Verify user can find and select a coach

**Steps**:
1. Navigate to https://coaching-network-database-fzgpvzwzxexyfjst9szyee.streamlit.app/
2. Check header: "⚽ Football Coaches Database" visible
3. Check Quick Access buttons work (Blessin, Hjulmand, Kompany, Werner)
4. Check Bundesliga Overview grid shows all 18 clubs
5. Check Direct Search field accepts input

**Expected**:
- ✅ Clean homepage
- ✅ Clear navigation options
- ✅ Quick access for common coaches
- ✅ Search field responsive

**Status**: ⏳ PENDING MANUAL TEST

---

### **TEST 2: Coach Search**

**Goal**: Verify search functionality

**Steps**:
1. Enter "Alexander Blessin" in search field
2. Click "🔍 Search Coach" button
3. Verify loading indicator appears
4. Verify profile loads within 3 seconds (preloaded)

**Expected**:
- ✅ Search accepts input
- ✅ Loading state visible
- ✅ Fast load (< 3s for preloaded coaches)
- ✅ Profile displays correctly

**Status**: ⏳ PENDING MANUAL TEST

---

### **TEST 3: Coach Profile Header** (Requirement #2)

**Goal**: Verify all profile information displays

**Test Data**: Alexander Blessin

**Expected Output**:
```
✅ Photo: Blessin headshot visible
✅ Name: "Alexander Blessin"
✅ Current Role: "Trainer @ FC St. Pauli"
✅ Nationality: "🌍 Deutschland"
✅ Age: "🎂 Age 52" (or similar)
✅ License: "📜 UEFA-Pro-Lizenz"
✅ Agent: "🤝 FDF" (clickable link)

Metrics Row:
✅ Total Games: 303
✅ Career PPG: 1.60 (Above Average)
✅ Stations: 7
✅ Teammates: 346 (Large Network)

Preload Indicator:
✅ "⚡ Preloaded Data (updated Xh ago)"
```

**Status**: ⏳ PENDING MANUAL TEST

---

### **TEST 4: Key Insights** (Contextual Info)

**Goal**: Verify insights provide value

**Expected for Blessin**:
```
💡 Key Insights & Highlights

📈 Career Progression: Started at RB Leipzig U17, now at FC St. Pauli (7 stations)
🎯 Most recent: Hired by Andreas Bornemann at FC St. Pauli  ← MUST be correct!
🔗 Teammate Network: 159 now coaches, 0 directors
⭐ Performance: 1.60 PPG (Above league average of ~1.45)
```

**Critical Check**:
- ❌ "Most recent" must NOT say "Johannes Spors at Genua" (old bug)
- ✅ Must say "Andreas Bornemann at FC St. Pauli" (current)

**Status**: ⏳ PENDING MANUAL TEST

---

### **TEST 5: Decision Makers Tab** (Requirement #3 - part 1)

**Goal**: Verify hiring manager intelligence

**Expected**:
```
Tab: 🎯 Decision Makers (should be first tab)

Header:
"Decision Makers Timeline"
"Who hired this coach? When and where? This is the intelligence edge."

Timeline (sorted newest first):
┌─────────────────────────────────────┐
│ 📅 2024-present                     │
│ 🔵 FC St. Pauli • Trainer           │
│                                     │
│ 🎯 Hired by: Andreas Bornemann      │
│    Role: Sportdirektor              │
│    Notes: Hired Blessin to replace  │
│           Hürzeler after promotion  │
│           to Bundesliga             │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ 📅 2022                             │
│ 🔵 Genua CFC • Trainer              │
│                                     │
│ 🎯 Hired by: Johannes Spors         │
│    Role: Sportdirektor              │
│    Notes: Hired Blessin at Genua    │
│           2022, previously worked   │
│           together indirectly       │
│           through RB network        │
└─────────────────────────────────────┘

Hiring Patterns:
"No repeat hiring patterns detected. Each hiring manager hired this coach once."
```

**Critical Checks**:
- ✅ NO metric cards (removed)
- ✅ Timeline sorted newest → oldest
- ✅ Club logos visible
- ✅ All hiring manager names present
- ✅ Notes provide context

**Status**: ⏳ PENDING MANUAL TEST

---

### **TEST 6: Complete Network Tab** (Requirement #3 - part 2)

**Goal**: Verify network connections display

**Expected Structure**:
```
Categories (in order):
1. 🎯 Hiring Managers (2)
   - Andreas Bornemann
   - Johannes Spors

2. Former Teammates (filtered to coaches/directors)
   - [List of teammates who are now coaches]

3. Coaching Companions
   - [Co-trainers, assistants, etc.]
```

**Critical Checks**:
- ✅ Hiring Managers appear first (top priority)
- ✅ Table searchable
- ✅ Can filter by category
- ✅ Not overwhelming (reasonable default limit)

**Status**: ⏳ PENDING MANUAL TEST

---

### **TEST 7: Career Overview Tab**

**Goal**: Verify career history displays

**Expected**:
```
Table with columns:
- Club
- Role
- Period
- Games
- Wins
- Draws
- Losses
- PPG
- Win %
```

**Critical Checks**:
- ✅ All 7 stations visible
- ✅ Data accurate (matches Transfermarkt)
- ✅ Sorted by period (newest first)

**Status**: ⏳ PENDING MANUAL TEST

---

### **TEST 8: Performance Tab - Players Coached** (Requirement #5)

**Goal**: CRITICAL - Verify players with 20+ games, 70+ mins display

**Expected**:
```
Section: "⚽ Players Coached Successfully"
Caption: "Players with 20+ games and 70+ average minutes (core requirement from projectFIVE)"

Success Message: "✅ X players with 20+ games and 70+ avg minutes"

Table:
┌─────────────────────────────────────────────────────────────┐
│ Player      | Nat | Pos | G  | ⚽ | 🅰️ | Min/G | 🔗        │
├─────────────────────────────────────────────────────────────┤
│ Jackson     | AUS | DM  | 32 | 5 | 3  | 82    | View      │
│ Irvine      |     |     |    |   |    |       |           │
│ Morgan      | FRA | AM  | 28 | 8 | 6  | 85    | View      │
│ Guilavogui  |     |     |    |   |    |       |           │
│ ...         |     |     |    |   |    |       |           │
└─────────────────────────────────────────────────────────────┘
```

**Critical Checks**:
- ✅ Section exists (NOT "No players coached data available")
- ✅ Filter working (only players with 20+ games AND 70+ mins)
- ✅ Table formatted correctly
- ✅ Profile links work

**Status**: ⏳ PENDING MANUAL TEST

---

### **TEST 9: Performance Tab - Teammates** (Requirement #4)

**Goal**: Verify former teammates display

**Expected**:
```
Section: "👥 Teammates from Playing Career"

Stats Row:
- Total Teammates: 346
- Shared Matches: X,XXX
- Shared Minutes: X,XXX,XXX
- Now Coaches/Directors: X

Table (default 25, expandable):
- Name
- Current Role (if coach/director)
- Current Club
- Shared Matches
- Period
```

**Critical Checks**:
- ✅ All teammates listed
- ✅ Filter to coaches/directors works
- ✅ Expand button shows more
- ✅ Data accurate

**Status**: ⏳ PENDING MANUAL TEST

---

### **TEST 10: Bundesliga Overview** (Requirement #1)

**Goal**: Verify "all coaches at club XY" works

**Expected**:
```
Grid of 18 Bundesliga clubs:
┌─────────────────────────────────────┐
│ 🔵 1. FC Heidenheim                 │
│ 👤 Frank Schmidt                    │
│ [View Profile]                      │
└─────────────────────────────────────┘

... (repeat for all 18 clubs)
```

**Critical Checks**:
- ✅ All 18 clubs present
- ✅ Correct current coaches
- ✅ Club logos visible
- ✅ Click → loads coach profile

**Status**: ⏳ PENDING MANUAL TEST

---

## 🐛 KNOWN ISSUES TO VERIFY ARE FIXED

### **Issue 1: Decision Makers Not Loading**
**Status**: ✅ SHOULD BE FIXED (commit ec28bf0)
**Test**: Load Blessin → Check Decision Makers tab shows 2 hiring managers
**Expected**: Timeline with Bornemann + Spors

### **Issue 2: "Most Recent" Shows Wrong SD**
**Status**: ✅ SHOULD BE FIXED (commit 7da562c)
**Test**: Check Key Insights → "Most recent" line
**Expected**: "Andreas Bornemann at FC St. Pauli" (NOT Genua)

### **Issue 3: Players Section Missing**
**Status**: ✅ SHOULD BE FIXED (commit 90c3d0c)
**Test**: Performance tab → "Players Coached Successfully" section exists
**Expected**: Table with filtered players

### **Issue 4: Header Overlap**
**Status**: ✅ SHOULD BE FIXED (commit 1cab6ac)
**Test**: Homepage header not cut off at top
**Expected**: Full header visible with proper spacing

### **Issue 5: Leverkusen Logo Missing**
**Status**: ✅ SHOULD BE FIXED (earlier commit)
**Test**: Bundesliga overview → Bayer Leverkusen has logo
**Expected**: Logo visible

---

## 📊 REGRESSION TESTS

### **Performance**
- [ ] Preloaded coaches load < 3 seconds
- [ ] Search response < 5 seconds
- [ ] Tab switching instant (< 500ms)

### **Data Quality**
- [ ] No "N/A" displayed to user (except acceptable cases)
- [ ] No empty sections (either data or helpful message)
- [ ] All links work (Transfermarkt, agent profiles)

### **UX**
- [ ] No console errors visible
- [ ] No broken images
- [ ] Tables sortable/searchable
- [ ] Mobile responsive (if applicable)

---

## ✅ FINAL CHECKLIST - Core Requirements

Based on projectFIVE requirements:

### **1. Who are all coaches at club XY?**
- [ ] Bundesliga overview shows all 18 clubs
- [ ] Each club shows current coach name
- [ ] Click loads coach profile

### **2. Who is coach XY?**
- [ ] Profile photo visible
- [ ] Age, nationality, license, current club all present
- [ ] Career history complete
- [ ] All data from Transfermarkt profile page

### **3. What other coaches/staff has he worked with?**
- [ ] Decision Makers tab shows hiring managers
- [ ] Complete Network tab shows all connections
- [ ] Teammates who are now coaches/directors identified

### **4. Former teammates (if player)?**
- [ ] Performance tab has "Teammates from Playing Career"
- [ ] All teammates from Transfermarkt listed
- [ ] Current roles shown
- [ ] Data from Transfermarkt teammates page

### **5. Which players worked successfully (20+ games, 70+ mins)?**
- [ ] Performance tab has "Players Coached Successfully"
- [ ] Filter working correctly (20+ AND 70+)
- [ ] Table shows all required columns
- [ ] Data from Transfermarkt "Players used" page

---

## 🚀 TEST EXECUTION

**Manual Test Required**:
User should go through each test above and mark ✅ or ❌

**Time Estimate**: 15-20 minutes for full test

**Priority Tests** (if short on time):
1. ✅ TEST 5 (Decision Makers - was broken)
2. ✅ TEST 4 (Most recent SD - was broken)
3. ✅ TEST 8 (Players section - was removed)

---

## 📝 RESULTS

**To be filled after manual testing**:

Passed: __/10 tests
Failed: __/10 tests

Critical Issues Found:
-
-
-

Minor Issues Found:
-
-

Overall Status: ⏳ PENDING
