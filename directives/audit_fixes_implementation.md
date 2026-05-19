# Directive: Audit Fixes Implementation (for Claude Code)

## Context
Browser audit completed 23.03.2026. MVP is live with 36 dashboards.
This directive contains all remaining fixes from `directives/audit_fixes.md` + newly discovered issues from the Chrome-based audit.

**After all fixes:** Run `python execution/generate_all_bl_coaches.py` then `cd output && npx vercel deploy --prod --yes --scope cmk2299s-projects`

---

## Fix 1: Nationality in center_info (P0)

### Problem
`build_coach_network.py` line ~585-587 uses `nationality[0]` for center_info, which is often the Verbandsgebiet (work country), not the real nationality. The index page already has the correct logic (prefer second entry for dual nationals).

Example: Kovac profile has `["Deutschland", "Kroatien"]` → dashboard shows "Deutschland", should show "Kroatien".

### File
`execution/build_coach_network.py`, lines 585-587

### Current Code
```python
nationality = profile.get("nationality", "")
if isinstance(nationality, list):
    nationality = nationality[0] if nationality else ""
```

### Replace With
```python
nationality = profile.get("nationality", "")
if isinstance(nationality, list):
    real = [n for n in nationality if not any(x in n for x in [' U', 'DDR'])]
    if len(real) >= 2:
        nationality = real[1]  # Real nationality (second after Verbandsgebiet)
    elif real:
        nationality = real[0]
    else:
        nationality = nationality[0] if nationality else ""
```

### Also fix contact nationality (~line 430 area)
Same pattern: wherever contact nationality is resolved from a list, apply the same logic. Search for `nationality[0]` in the file and apply the same resolution everywhere.

### Test
```bash
python execution/build_coach_network.py --tm-id 97
# Check: data/networks/97.json → center_info.nationality should be "Kroatien", not "Deutschland"
python execution/build_coach_network.py --tm-id 55100
# Check: data/networks/55100.json → center_info.nationality should be "Österreich" (not "Deutschland" or "Jugoslawien (SFR)")
```

---

## Fix 2: Missing Flags in Index (P0)

### Problem
Titz and Muslic have no flag emoji in the index page. Root cause: the nationality resolution returns strings not in `COUNTRY_FLAGS` dict.

- **Titz** (tm_id 11489): nationality = `["Deutschland", "Vereinigte Staaten"]` → resolves to "Vereinigte Staaten", but dict has "USA"
- **Muslic** (tm_id 55100): nationality = `["Deutschland", "Jugoslawien (SFR)", "Österreich"]` → resolves to "Jugoslawien (SFR)", which is not in dict

### File
`execution/generate_all_bl_coaches.py`, COUNTRY_FLAGS dict (~line 109-121)

### Fix
Add missing entries to `COUNTRY_FLAGS`:
```python
"Vereinigte Staaten": "🇺🇸",
"Jugoslawien (SFR)": "",  # Dissolved state — no flag, should be filtered out by resolution logic
"Bosnien und Herzegowina": "🇧🇦",  # Alternative TM spelling
"Côte d'Ivoire": "🇨🇮",
"Korea, Süd": "🇰🇷",
"Ghana": "🇬🇭",
"Japan": "🇯🇵",
"Kamerun": "🇨🇲",
"Nigeria": "🇳🇬",
"Senegal": "🇸🇳",
"Mali": "🇲🇱",
"Marokko": "🇲🇦",
"Tunesien": "🇹🇳",
"Algerien": "🇩🇿",
"Kosovo": "🇽🇰",
"Montenegro": "🇲🇪",
"Albanien": "🇦🇱",
"Slowakei": "🇸🇰",
"Slowenien": "🇸🇮",
"Bulgarien": "🇧🇬",
"Ukraine": "🇺🇦",
```

### Additional fix: Muslic nationality resolution
For Muslic the current logic picks `nationality[1]` = "Jugoslawien (SFR)" which is a dissolved country. Better: also filter out dissolved states in the resolution logic.

In both `build_coach_network.py` AND `generate_all_bl_coaches.py`, update the filter:
```python
real = [n for n in nationality if not any(x in n for x in [' U', 'DDR', 'Jugoslawien', 'Sowjetunion', 'Tschechoslowakei'])]
```
This way Muslic resolves from `["Deutschland", "Jugoslawien (SFR)", "Österreich"]` → filter → `["Deutschland", "Österreich"]` → "Österreich" (his current citizenship — Jugoslawien (SFR) is his historical birth country, now Bosnia, but TM lists Österreich as actual nationality).

### Test
After batch regeneration, check index.html for flags next to Titz (🇺🇸) and Muslic (🇦🇹).

---

## Fix 3: "Zurück zum Index" Link in Dashboards (P0)

### Problem
Dashboards have no link back to the index page. Users must use browser back.

### File
`blessin_network_v3.html` (dashboard template in project root)

### Fix
Find the header/logo area (search for "p5 Network Explorer" or the logo text). Wrap it in a link:

```html
<a href="../index.html" style="text-decoration:none;color:inherit;display:flex;align-items:center;gap:8px;">
  <span style="color:var(--text-dim);font-size:13px;">&larr;</span>
  <span>p5 Network Explorer</span>
</a>
```

The `../index.html` path is correct because dashboards live in `output/dashboards/`.

### Test
Open any dashboard → click logo → should navigate to index page.

---

## Fix 4: Font Stack Unification (P1)

### Problem
Index uses Space Grotesk + IBM Plex Sans. Dashboard uses DM Sans + JetBrains Mono. Two different design systems.

### Decision
Use **IBM Plex Sans** for body text everywhere. Keep **Space Grotesk** for headings, **JetBrains Mono** for stats/mono.

### File
`blessin_network_v3.html` (dashboard template)

### Fix
1. Replace Google Fonts link: swap `DM+Sans` for `IBM+Plex+Sans:wght@400;500;600;700`
2. Replace all `font-family:'DM Sans'` with `font-family:'IBM Plex Sans'`
3. Keep JetBrains Mono for stats — that's consistent with the terminal aesthetic

### Test
Visual comparison: dashboard body text should match index page text.

---

## Fix 5: Red Accent Unification (P1)

### Problem
Index: `#c8102e`, Dashboard: `#e63946` — two different reds.

### Decision
Use `#c8102e` everywhere (darker, more professional, Bundesliga-adjacent).

### File
`blessin_network_v3.html` (dashboard template)

### Fix
Find `--red: #e63946` (or similar CSS variable) and replace with `--red: #c8102e`.
Also search for any hardcoded `#e63946` values and replace.

### Test
Dashboard accent color should match index page accent.

---

## Fix 6: 404 Page (P1)

### Problem
No custom 404 page — Vercel shows generic error.

### File
Create new: `output/404.html`

### Content
```html
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<title>404 — Coach Network Explorer</title>
<style>
  body { background:#08090c; color:#d4d4d8; font-family:'IBM Plex Sans',system-ui,sans-serif;
         display:flex; align-items:center; justify-content:center; min-height:100vh; text-align:center; }
  h1 { font-family:'Space Grotesk',sans-serif; font-size:48px; color:#c8102e; }
  a { color:#c8102e; }
</style>
</head>
<body>
<div>
  <h1>404</h1>
  <p>Seite nicht gefunden.</p>
  <p><a href="/">Zurück zur Übersicht</a></p>
</div>
</body>
</html>
```

Vercel auto-detects `404.html` in the deploy root.

---

## Execution Order

1. Fix 1: Nationality center_info (`build_coach_network.py`)
2. Fix 2: COUNTRY_FLAGS + dissolved-state filter (`generate_all_bl_coaches.py` + `build_coach_network.py`)
3. Fix 3: "Zurück zum Index" link (`blessin_network_v3.html`)
4. Fix 4: Font stack (`blessin_network_v3.html`)
5. Fix 5: Red accent (`blessin_network_v3.html`)
6. Fix 6: 404 page (new file `output/404.html`)
7. **Batch rebuild:** `python execution/generate_all_bl_coaches.py`
8. **Deploy:** `cd output && npx vercel deploy --prod --yes --scope cmk2299s-projects`

### Verification after deploy
- [ ] Kovac dashboard: nationality shows "Kroatien"
- [ ] Muslic dashboard: nationality shows "Österreich"
- [ ] Index: Titz has 🇺🇸 flag, Muslic has 🇦🇹 flag
- [ ] Any dashboard: click logo → navigates to index
- [ ] Dashboard fonts match index (IBM Plex Sans body)
- [ ] Dashboard red accent matches index (#c8102e)
- [ ] Visit invalid URL → custom 404 page

---

## Learnings
(Update as you go)
