# Directive: Audit Fixes

## Quelle
Basiert auf dem vollständigen Audit vom 21.03.2026 (`output/AUDIT_REPORT.md`).
Priorisierung: P0 = vor Stakeholder-Präsentation, P1 = diese Woche, P2 = Sprint 2-3.

---

## P0 — Club-Name-Normalisierung (KRITISCH)

### Problem
Gleiche Clubs erscheinen unter verschiedenen Namen als separate Stationen:
- "Borussia Dortmund" vs. "Bor. Dortmund"
- "Fortuna Düsseldorf" vs. "F. Düsseldorf"
- "1.FC Heidenheim 1846" vs. "1.FC Heidenheim"
- Weitere Varianten wahrscheinlich bei ~30-50% der Dashboards

Ursache: `career_history` in `person_profiles/` hat TM-Kurzform ("Bor. Dortmund"), `staff/` Dateien haben TM-Langform ("Borussia Dortmund"). `build_network()` verwendet den rohen `club_name` String statt über `club_tm_id` aufzulösen.

### Fix

**Schritt 1:** Club-Name-Lookup aus `club_registry.json` bauen.

In `build_coach_network.py`, neue Hilfsfunktion:
```python
def get_canonical_club_name(club_tm_id: int) -> str:
    """Return the canonical club name from club_registry, or empty string."""
    registry = load_club_registry()
    club = registry.get(club_tm_id)
    if club:
        return club.get("name", "")
    return ""
```

**Schritt 2:** In `build_network()` alle `club_name` durch kanonischen Namen ersetzen.

Betrifft 3 Stellen:
1. **Coach-Stationen parsen** (~Zeile 324): `coach_stations[club_id]["name"]` → `get_canonical_club_name(club_id) or entry.get("club_name", "")`
2. **Shared-Career-Stations** (~Zeile 384): `coach_club_seasons` Lookup verwendet bereits `club_name` aus Schritt 1
3. **Player-Kontakte** (~Zeile 477): `station_names` kommen aus `coach_stations[club_id]["name"]` → bereits normalisiert

**Schritt 3:** Auch die `note`-Strings werden automatisch korrekt, weil sie auf `station_names` basieren.

**Schritt 4:** Staff-Kontakte (Zeile 342): `club_name = get_canonical_club_name(current_club_id) or staff.get("club_name", "")`

### Testen
```bash
# Einzeltest: Kovac (hatte "Bor. Dortmund" + "Borussia Dortmund" Duplikat)
python execution/build_coach_network.py --tm-id 97
# Prüfen: data/networks/97.json → "stations" Array darf kein Duplikat mehr haben

# Einzeltest: Anfang (hatte "F. Düsseldorf" + "Fortuna Düsseldorf")
python execution/build_coach_network.py --tm-id 7498
# Prüfen: Stationen-Anzahl sollte von 13 auf 12 sinken

# Dann Batch:
python execution/generate_all_bl_coaches.py
```

### Erwartet
- Kovac: 10 → 9 Stationen
- Anfang: 13 → 12 Stationen
- Keine doppelten Filter-Chips mehr in Dashboards
- Index-Stationen-Zahlen korrekter

---

## P0 — "Zurück zum Index" Link in Dashboards

### Problem
Dashboards haben keinen Link zurück zur Index-Seite. User muss Browser-Back nutzen.

### Fix
In `blessin_network_v3.html` (Dashboard-Template), im Header-Bereich einen Link ergänzen.

Suche die Logo/Header-Stelle im Template (ungefähr Zeile 140-150):
```html
<!-- Irgendwo beim Logo "p5 Network Explorer" -->
```

Ergänze einen Link:
```html
<a href="../index.html" style="text-decoration:none;color:inherit;display:flex;align-items:center;gap:8px;">
  <span style="color:var(--text-dim);font-size:13px;">&larr;</span>
  <span>p5 Network Explorer</span>
</a>
```

Der Logo-Text wird zum klickbaren Zurück-Link. `../index.html` weil Dashboards in `dashboards/` Unterordner liegen.

### Testen
Dashboard öffnen → auf Logo klicken → muss auf Index-Seite landen.

---

## P1 — Font-Stack vereinheitlichen

### Problem
Index nutzt Space Grotesk + IBM Plex Sans, Dashboard nutzt DM Sans + JetBrains Mono. Zwei verschiedene Design-Systeme.

### Fix
Entscheidung treffen:
- **Option A:** IBM Plex Sans überall (nüchterner, corporate) — dann Dashboard-Template auf IBM Plex Sans umstellen
- **Option B:** DM Sans überall (weicher, moderner) — dann Index auf DM Sans umstellen

**Empfehlung:** IBM Plex Sans passt besser zum Data-Terminal-Aesthetic. Space Grotesk (Headings) + IBM Plex Sans (Body) + JetBrains Mono (Stats) als einheitlicher Stack.

### Umsetzung
Im Dashboard-Template alle `font-family:'DM Sans'` ersetzen durch `font-family:'IBM Plex Sans'`.
Google Fonts Link im Template anpassen.

---

## P1 — Rot-Akzent vereinheitlichen

### Problem
Index: `#c8102e`, Dashboard: `#e63946` — zwei verschiedene Rottöne.

### Fix
Einen wählen. `#c8102e` ist dunkler/seriöser (Bundesliga-nah), `#e63946` ist heller/signal-stärker.

**Empfehlung:** `#c8102e` überall (passt besser zum professionellen Kontext).

Im Dashboard-Template: `--red: #e63946` ändern zu `--red: #c8102e`.

---

## P1 — Nationalitäts-Logik vereinheitlichen

### Problem
Index zeigt `nationality[1]` (echte Herkunft), Dashboard `center_info` zeigt `nationality[0]` (Verbandsgebiet).
Beispiel Kovac: Index zeigt "Kroatien" (korrekt), Dashboard zeigt "Deutschland" (Verbandsgebiet).

### Fix
In `build_coach_network.py`, Zeile ~539:
```python
# Aktuell:
nationality = profile.get("nationality", "")
if isinstance(nationality, list):
    nationality = nationality[0] if nationality else ""

# Ändern zu (gleiche Logik wie Index):
nationality = profile.get("nationality", "")
if isinstance(nationality, list):
    real = [n for n in nationality if not any(x in n for x in [' U', 'DDR'])]
    if len(real) >= 2:
        nationality = real[1]  # Echte Nationalität
    elif real:
        nationality = real[0]
    else:
        nationality = nationality[0] if nationality else ""
```

Gleiche Änderung für Kontakt-Nationalitäten (~Zeile 430):
```python
nationality=other.get("nationality")
# Wenn Liste, gleiche Auflösung anwenden
```

---

## P1 — 404-Seite

### Problem
Tippfehler in URLs zeigen generische Vercel-404-Seite.

### Fix
Neue Datei `output/404.html` erstellen:
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

Vercel erkennt `404.html` automatisch.

---

## P2 — Tabellen-Sortierung im Index

### Problem
Index-Tabelle kann nicht sortiert werden (nach Kontakten, Stationen, Name).

### Fix
In `generate_index_page()`: Spaltenköpfe klickbar machen mit JS Sort-Funktion.

```javascript
function sortTable(col, type) {
  const sections = ['bl1', 'bl2'];
  sections.forEach(id => {
    const section = document.getElementById(id);
    const rows = [...section.querySelectorAll('.row')];
    rows.sort((a, b) => {
      let va = a.children[col].textContent.trim();
      let vb = b.children[col].textContent.trim();
      if (type === 'num') { va = parseInt(va) || 0; vb = parseInt(vb) || 0; return vb - va; }
      return va.localeCompare(vb, 'de');
    });
    const hdr = section.querySelector('.table-hdr');
    rows.forEach(r => section.appendChild(r));
  });
}
```

Spaltenköpfe bekommen `onclick="sortTable(3, 'num')"` (Kontakte) und `onclick="sortTable(4, 'num')"` (Stationen).

---

## P2 — Accessibility Basics

### Problem
Keine `aria-labels`, `alt`-Texte, `lang`-Attribut, Skip-Navigation.

### Fixes (im Dashboard-Template)
1. `<html lang="de">` setzen
2. `<canvas aria-label="Netzwerk-Visualisierung" role="img">`
3. Portraits: `alt="{coach_name}"` statt leeres alt
4. Filter-Chips: `role="button" aria-pressed="true/false"`
5. Skip-Link: `<a href="#main" class="skip-nav">Zum Inhalt</a>` (visuell versteckt)

### Fixes (in Index)
1. Bilder: `alt="{coach_name}"` hinzufügen (aktuell `alt=""`)
2. Tabellenköpfe: `role="columnheader"` für Screen-Reader

---

## P2 — Open Graph Tags

### Problem
Kein Vorschaubild bei Link-Sharing (Slack, WhatsApp, etc.)

### Fix
In Index und Dashboard-Templates:
```html
<meta property="og:title" content="Coach Network Explorer — BL1 & BL2">
<meta property="og:description" content="Interaktive Trainer-Netzwerke der Bundesliga">
<meta property="og:type" content="website">
<meta property="og:url" content="https://coach-network-explorer.vercel.app">
```

Optional: Screenshot als og:image hosten (z.B. auf Vercel Blob oder statisch).

---

## Umsetzungs-Reihenfolge

1. Club-Name-Normalisierung (`build_coach_network.py`) → Batch-Regenerierung
2. "Zurück zum Index" (Dashboard-Template)
3. Rot-Akzent + Fonts vereinheitlichen (Template + Index)
4. Nationalitäts-Logik (build_coach_network.py)
5. 404-Seite (neue Datei)
6. Redeploy: `python execution/generate_all_bl_coaches.py && cd output && npx vercel deploy --prod --yes`
7. P2-Items nach Bedarf

## Learnings
(Update as you go)
