# UI Overhaul Plan: Network Explorer → 95/100

**Status:** Geplant
**Aktueller Stand:** ~42/100
**Ziel:** ≥95/100
**Referenzen:** Kumu.io, Neo4j Bloom, LinkedIn Sales Navigator, Apple HIG

---

## Diagnose: Warum 42/100?

| Problem | Impact | Prio |
|---------|--------|------|
| Nodes = abstrakte Dots statt Menschen | Kein emotionaler Bezug, "Daten-Tool statt Kontakt-Tool" | P0 |
| Labels überlappen, schlecht lesbar | Unprofessionell, Information geht verloren | P0 |
| Kein visueller Kontext pro Kontakt | Man sieht Punkte, weiß aber nicht wer/was/warum | P0 |
| Tooltip = primitives Textfeld | Fühlt sich nach Prototype an | P1 |
| Station-Wedges kaum sichtbar | Strukturprinzip geht visuell verloren | P1 |
| Keine Übergangs-Animationen | Abrupte Wechsel, kein Gefühl von Navigation | P1 |
| Radial Lines = visuelles Rauschen | Verbindungen sagen nichts aus | P2 |
| Kein Onboarding | Neuer User versteht Layout nicht | P2 |
| Sidebar-Design = Standard | Kein "wow", kein Branding | P2 |
| Footer-Bereich verschenkt | Könnte Kontext geben | P3 |

---

## Die 10 Maßnahmen

### M1: "People First" — Foto-zentrische Nodes (P0)

**Problem:** Kontakte = farbige Dots. Das Dashboard zeigt Daten, aber keine Menschen.

**Lösung:**
- **ALLE Kontakte mit Bild** bekommen Photo-Nodes (runde Avatare), nicht nur Score >0.35
- Kontakte OHNE Bild bekommen **Initialen-Avatare** (erste Buchstaben von Vor+Nachname) in der Kategoriefarbe — wie LinkedIn/Slack
- Mindest-Noderadius: 14px (aktuell 3px für low-score = unsichtbar)
- Bei Score <30: leicht dimmed (opacity 0.6), aber immer noch erkennbar als Person
- Äußerer Ring um Photo-Nodes: 2px in Kategoriefarbe → sofortige visuelle Kategorisierung

**Technisch:**
```
// Initialen-Avatar
ctx.fillStyle = catColor;
ctx.beginPath(); ctx.arc(x, y, r, 0, PI*2); ctx.fill();
ctx.fillStyle = '#fff';
ctx.font = `600 ${r*0.8}px 'IBM Plex Sans'`;
ctx.fillText(initials, x, y);
```

**Impact:** Von "Daten-Tool" zu "Kontakt-Tool". Sofort erkennbar: das sind echte Menschen.

---

### M2: Smart Label Collision Detection (P0)

**Problem:** Labels überlappen, besonders im mittleren Ring bei vielen Kontakten.

**Lösung:**
- Label-Collision-Grid: Canvas in 60×40px Zellen unterteilen
- Jeder Label berechnet seine Bounding-Box VOR dem Zeichnen
- Wenn Zelle besetzt → Label nicht zeichnen (wird nur bei Hover gezeigt)
- Priorität nach Score: High-Score-Labels gewinnen immer
- Labels für niedrig-priorisierte Kontakte werden nur bei Zoom ≥1.5× gezeigt

**Technisch:**
```
const labelGrid = {};
function canPlaceLabel(x, y, w, h) {
  const key = `${Math.floor(x/60)}_${Math.floor(y/40)}`;
  if (labelGrid[key]) return false;
  labelGrid[key] = true;
  return true;
}
```

**Impact:** Saubere, professionelle Darstellung — keine Überlappungen mehr.

---

### M3: Glassmorphism Hover-Card statt Tooltip (P0)

**Problem:** Tooltip ist ein kleines schwarzes Textfeld. Fühlt sich nach 2015 an.

**Lösung:** Glassmorphism-Card bei Hover/Click:
- Backdrop-Filter: `blur(16px)` + semi-transparenter Hintergrund
- Abgerundete Ecken (12px), sanfter Schatten
- Layout der Card:
  ```
  ┌─────────────────────────────┐
  │ [Photo 48px]  Name          │
  │              Rolle · Club   │
  │              ████░░ Score 73│
  │─────────────────────────────│
  │ 🏟 Station 1, Station 2    │
  │ Seit 2019 · 4 gemeins. St. │
  │─────────────────────────────│
  │ [→ Netzwerk erkunden]       │
  └─────────────────────────────┘
  ```
- Score als Mini-Balken (gefüllt, Kategoriefarbe)
- Smooth Fade-in (150ms transition)
- Positionierung: intelligentes Flipping wenn am Rand

**Technisch:** HTML-Overlay (kein Canvas-Tooltip), positioned absolute über dem Canvas.

**Impact:** Jeder Hover fühlt sich wie eine Premium-App an.

---

### M4: Station-Wedge Redesign mit Gradient-Arcs (P1)

**Problem:** Wedge-Sektoren sind kaum sichtbar (0.02 alpha fill, 0.12 alpha arc).

**Lösung:**
- Wedge-Hintergrund: radialer Gradient vom Center (transparent) zum Rand (leichte Farbe, 0.06 alpha)
- Wedge-Arc am Rand: solide Linie statt dashed (1.5px, 0.25 alpha)
- Station-Label: größer (12px statt 10px), mit kleinem farbigen Dot-Indicator davor
- **Active-Wedge-Highlight:** Wenn ein Kontakt in einer Station gehovered/selected ist → ganzer Wedge leuchtet leicht auf (0.04 → 0.08 alpha)
- Wedge-Separatoren: feine radiale Linien (0.06 alpha) mit Mini-Gap am Center

**Impact:** Man SIEHT die Struktur sofort. Stationen sind nicht nur Labels, sondern räumliche Zonen.

---

### M5: Animated Transitions (P1)

**Problem:** Score-Slider-Änderungen, Filter, Drilldown = abrupte Neuberechnung.

**Lösung:**
- **Filter/Score-Änderung:** Nodes animieren zur neuen Position (300ms ease-out)
  - Speichere `targetX/Y` aus neuem Layout
  - Interpoliere `x += (targetX - x) * 0.15` pro Frame
- **Drilldown:** Zoom-In-Animation auf gewählten Kontakt → Fade → neues Netzwerk erscheint mit Scale-Up von 0.5→1
- **Node-Erscheinen:** Neue Nodes faden ein (opacity 0→1) statt plötzlich da zu sein
- **Score-Slider:** Nodes die rausfallen faden aus, Nodes die reinkommen faden ein

**Technisch:**
```
// In layoutNodes: calculate targets
nodes.forEach(n => { n.targetX = newX; n.targetY = newY; });
// In render: interpolate
nodes.forEach(n => {
  n.x += (n.targetX - n.x) * 0.12;
  n.y += (n.targetY - n.y) * 0.12;
});
```

**Impact:** Von "statischer Datei" zu "lebendiger App". Fundamental für Premium-Gefühl.

---

### M6: Score-Ring Visualisierung pro Node (P1)

**Problem:** Man sieht nicht direkt, welchen Score ein Kontakt hat (nur via Tooltip/Detail).

**Lösung:**
- Jeder Node bekommt einen **Score-Arc** als äußeren Ring:
  - 360° = Score 100, proportional weniger für niedrigere Scores
  - Farbe: Gradient von Grau (low) zu Kategoriefarbe (high)
  - Linienstärke: 2px
  - Start bei 12 Uhr, im Uhrzeigersinn
- Nur sichtbar bei Nodes ≥10px Radius (sonst zu klein)
- Auf Hover: Arc pulsiert kurz (opacity 0.6 → 1 → 0.6)

**Technisch:**
```
const scoreAngle = (score / 100) * Math.PI * 2;
ctx.strokeStyle = catColor;
ctx.lineWidth = 2;
ctx.beginPath();
ctx.arc(x, y, r + 3, -PI/2, -PI/2 + scoreAngle);
ctx.stroke();
```

**Impact:** Relevanz wird sofort sichtbar auf Node-Ebene — kein Tooltip nötig.

---

### M7: Connection Lines → Relationship Arcs (P2)

**Problem:** Radiale Linien (center → node) sagen nichts aus und erzeugen visuelles Rauschen.

**Lösung:**
- Radiale Lines komplett entfernen
- Stattdessen: **Beziehungs-Arcs** zwischen Kontakten die sich kennen:
  - `coaches_worked_with` / `sds_worked_with` = leichte curved Verbindungslinien
  - Nur anzeigen bei Hover auf einen Kontakt (seine Connections leuchten auf)
  - Linienstärke nach `shared_station_count` (1-3px)
  - Kurve berechnen: quadratische Bezier durch Mittelpunkt versetzt
- Auf Hover eines Kontakts:
  - Alle verbundenen Kontakte werden highlighted (opacity boost)
  - Alle nicht-verbundenen werden gedimmt
  - Arc-Lines fade in (200ms)

**Impact:** Echte Netzwerk-Visualisierung statt Sonnensystem. Zeigt WER wen KENNT.

---

### M8: Minimap + Zoom Controls (P2)

**Problem:** Bei Zoom verliert man die Orientierung. Kein visueller Kontext wo man ist.

**Lösung:**
- **Minimap** (120×90px) in der unteren rechten Ecke:
  - Zeigt das gesamte Netzwerk als kleine Punkte
  - Viewport-Rechteck zeigt den aktuell sichtbaren Bereich
  - Klickbar: Klick auf Minimap = navigiert dorthin
  - Nur sichtbar wenn viewScale > 1.2
- **Zoom-Controls** (optional, neben Minimap):
  - `+` / `−` Buttons für Präzisions-Zoom
  - `⟲` Reset-Button

**Technisch:** Separates 120×90 Canvas-Element oder Off-Screen-Rendering.

**Impact:** Navigation wird intuitiv, man verliert nie den Überblick.

---

### M9: Sidebar Redesign — Visual Contact List (P2)

**Problem:** Kontakt-Liste in Sidebar = plain text. Kein visueller Bezug zu den Nodes.

**Lösung:**
- Kontakt-Items bekommen **Mini-Avatare** (24px, Photo oder Initialen)
- Score als farbiger Balken neben dem Namen (nicht nur Dot)
- Hover auf Sidebar-Item = entsprechender Node im Graph highlighted + Verbindungen angezeigt
- **Sticky Group Headers** für Stationen beim Scrollen
- Suchfeld mit Live-Highlighting: Treffer werden im Graph hervorgehoben
- Optional: **Compact/Expanded Toggle** — Compact = nur Foto+Name, Expanded = Foto+Name+Rolle+Score

**Impact:** Sidebar wird zum primären Navigations-Tool, nicht nur Anhängsel.

---

### M10: Polish & Micro-Interactions (P3)

**Einzelmaßnahmen:**

1. **Loading State:** Beim Öffnen → kurze Lade-Animation (Nodes erscheinen Ring für Ring von innen nach außen, 100ms Delay pro Ring)

2. **Center Node Pulse:** Dezenter radialer Pulse (0.5s, alle 4s) der vom Center ausgeht — zeigt "das ist der Mittelpunkt"

3. **Keyboard Navigation:**
   - Tab = nächster Kontakt (nach Score sortiert)
   - Enter = Detail öffnen
   - Esc = Detail schließen / Zoom Reset

4. **Stats-Bar Redesign:** Footer wird zur Stats-Bar:
   ```
   239 Kontakte · 15 Stationen · Score ⌀ 38 · Kern: 13 · [Exportieren ↓]
   ```

5. **Cursor-Feedback:** Custom Cursor über Canvas:
   - Default = Crosshair (dezent)
   - Über Node = Pointer
   - Drag = Grab/Grabbing
   - Über leeren Bereich bei Zoom >1 = Move

6. **Dark/Light Theme Toggle:** (Future) Light-Variante für Druck/Präsentationen

7. **Export-Button:** PNG/SVG-Export des aktuellen Views (Screenshot-Funktion)

---

## Implementierungs-Reihenfolge

### Sprint A: "People First" (größter Impact)
1. M1: Foto-Nodes + Initialen-Avatare
2. M2: Label Collision Detection
3. M3: Glassmorphism Hover-Card

→ **Erwarteter Stand: ~68/100**

### Sprint B: "Lebendig" (Premium-Gefühl)
4. M5: Animated Transitions
5. M4: Station-Wedge Redesign
6. M6: Score-Ring pro Node

→ **Erwarteter Stand: ~82/100**

### Sprint C: "Professionell" (Feinschliff)
7. M7: Relationship Arcs (Hover)
8. M9: Sidebar Redesign
9. M8: Minimap + Zoom Controls

→ **Erwarteter Stand: ~92/100**

### Sprint D: "Poliert" (Letzte 5%)
10. M10: Micro-Interactions + Polish

→ **Erwarteter Stand: ≥95/100**

---

## Technische Hinweise

- **Canvas vs. HTML:** Tooltip/Hover-Card als HTML-Overlay (nicht Canvas) → bessere Textqualität, einfachere Interaktion
- **Smooth Animations:** Verwende `requestAnimationFrame` + Interpolation, nicht CSS Transitions auf Canvas
- **Performance:** Bei >300 Nodes: nur sichtbare Nodes rendern (Frustum Culling basierend auf Viewport)
- **Image Preloading:** Alle Contact-Images beim Init vorladen (batch), Fortschrittsbalken anzeigen
- **Font Loading:** Google Fonts async laden, Fallback-Font setzen um FOUT zu vermeiden
- **Template-Integration:** Alle Änderungen müssen in `generate_dashboard.py` Template + `blessin_network_v3.html` landen
- **Self-Anneal:** Nach jedem Sprint testen (Playwright Screenshots), Bugs fixen, Directive updaten
