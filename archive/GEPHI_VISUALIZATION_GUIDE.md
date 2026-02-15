# 🎨 Gephi Visualization Guide - Football Coaches Network

## Quick Start (5 Minuten)

### 1. Gephi installieren
- Download: **https://gephi.org/**
- Installiere Gephi (kostenlos, open source)
- Starte Gephi

### 2. Netzwerk öffnen
```
File → Open → Navigiere zu:
/Users/cmk/Documents/Football Coaches DB/data/gephi_coaches_only.gexf
```

**Empfehlung für den Anfang:** `gephi_coaches_only.gexf` (196 nodes - übersichtlich)

### 3. Layout anwenden
Im **Layout** Panel (links unten):
1. Wähle **"ForceAtlas 2"**
2. Einstellungen:
   - ✅ Prevent Overlap
   - ✅ LinLog mode (optional - macht Cluster deutlicher)
   - Gravity: 1.0
   - Scaling: 2.0
3. Klicke **Run** für 30-60 Sekunden
4. Klicke **Stop** wenn es stabil aussieht

### 4. Preview erstellen
1. Klicke auf **Preview** Tab (oben)
2. Preset: "Default Straight"
3. Settings:
   - Show Labels: ✅ (nur für Nodes mit Degree > 20)
   - Font Size: 10-12
   - Edge Thickness: Proportional
4. Klicke **Refresh**

### 5. Export
```
File → Export → SVG/PDF/PNG
```

---

## 🎨 Fancy Visualisierung Einstellungen

### Farben (bereits vorkonfiguriert!)
Die Nodes sind bereits nach Typ eingefärbt:

| Farbe | Node Type |
|-------|-----------|
| 🔴 **Rot** | Head Coach (Trainer) |
| 🔵 **Blau** | Assistant Coach |
| 🟢 **Grün** | Scout |
| 🟡 **Gelb** | Sporting Director |
| 🟣 **Lila** | Executive |
| 🟠 **Orange** | Youth Coach |
| ⚪ **Grau** | Support Staff |

### Node Größe (bereits vorkonfiguriert!)
Größe = Anzahl der Verbindungen
- Kleine Nodes = wenige Connections (< 10)
- Große Nodes = viele Connections (> 100)

### Manuelle Anpassungen (optional)

**Im Appearance Panel (links):**

**Nodes:**
- Color: "Partition" → "type" (schon gesetzt)
- Size: "Ranking" → "connections" (schon gesetzt)
- Label: "Ranking" → "connections" (Top 10% anzeigen)

**Edges:**
- Color: Grau mit 30% Transparenz (schon gesetzt)
- Thickness: "Ranking" → "Weight" (Stärke der Verbindung)

---

## 📊 Verfügbare Netzwerke

### 1. **gephi_coaches_only.gexf** ⚽
- **196 nodes, 1,271 edges**
- Nur Head Coaches + Assistants
- **Perfekt für:** Reine Trainer-Beziehungen
- **Beste Visualisierung:** Klar und übersichtlich

### 2. **gephi_decision_makers.gexf** 👔
- **95 nodes, 304 edges**
- Head Coaches + Sporting Directors + Executives
- **Perfekt für:** Entscheider-Ebene
- **Beste Visualisierung:** Executive Network

### 3. **gephi_technical_staff.gexf** 🔧
- **714 nodes, 16,900 edges**
- Coaches + Scouts + Support Staff
- **Perfekt für:** Komplettes Technical Team
- **Beste Visualisierung:** Mittel-groß, zeigt alle Bereiche

### 4. **gephi_academy.gexf** 🎓
- **46 nodes, 55 edges**
- Youth Coaches + Academy Directors
- **Perfekt für:** Nachwuchs-Netzwerk
- **Beste Visualisierung:** Sehr übersichtlich

### 5. **gephi_full.gexf** 🌐
- **1,095 nodes, 38,359 edges**
- Alle Personen, alle Verbindungen
- **Perfekt für:** Gesamtüberblick
- **Achtung:** Sehr groß, braucht starken Computer

---

## 🎯 Layout-Strategien

### ForceAtlas 2 (Empfohlen)
**Wann:** Standardlayout, zeigt Communities gut
```
Settings:
- Scaling: 2.0
- Gravity: 1.0
- ✅ Prevent Overlap
- ✅ LinLog mode (optional)
```

### Yifan Hu
**Wann:** Für große Netzwerke (full network)
```
Settings:
- Optimal Distance: 200
- ✅ Quadtree
```

### Fruchterman Reingold
**Wann:** Gleichmäßige Verteilung
```
Settings:
- Area: 10000
- Gravity: 10.0
```

### Noverlap
**Wann:** Nach anderem Layout, um Überlappungen zu entfernen
```
Run nach ForceAtlas 2 für 10-20 Sekunden
```

---

## 🔍 Filter & Analysen

### Filter anwenden (rechts)

**1. Topology → Degree Range**
- Zeige nur Nodes mit > 50 Connections
- Findet die wichtigsten Personen

**2. Attributes → Type**
- Filter nach Node Type
- Z.B. nur "head_coach" anzeigen

**3. Attributes → Current Club**
- Zeige nur Personen von einem Club
- Z.B. nur Bayern Munich

### Statistiken berechnen

Im **Statistics** Panel (rechts):

1. **Average Degree** - Durchschnittliche Verbindungen
2. **Network Diameter** - Längster Pfad im Netzwerk
3. **Modularity** - Community Detection (findet Gruppen)
4. **PageRank** - Wichtigste Nodes (wie Google)
5. **Betweenness Centrality** - Broker (verbinden Gruppen)

**Nach Berechnung:**
- Neue Columns in Data Table
- Können für Node Size/Color verwendet werden

---

## 💡 Pro Tips

### 1. Labels nur für wichtige Nodes
```
Appearance → Label Size → Ranking → "connections"
Min: 0, Max: 12
→ Nur große Nodes bekommen Labels
```

### 2. Highlight on Hover
```
Preview → Settings → Show Node Labels: "on hover"
→ Cleaner Look, Labels nur wenn du drüber fährst
```

### 3. Export in hoher Auflösung
```
File → Export → PNG
Einstellungen:
- Width: 4096px
- Height: 4096px
- Transparent Background: ✅ (für Presentations)
```

### 4. Dunkler Hintergrund
```
Preview → Background: #1a1a1a (Dunkelgrau/Schwarz)
→ Sieht moderner aus, Farben stechen hervor
```

### 5. Community Detection
```
Statistics → Modularity → Run
Appearance → Nodes → Partition → "Modularity Class"
→ Färbt Communities automatisch ein
```

---

## 🎬 Workflow für finale Visualisierung

### Schritt 1: Layout
1. ForceAtlas 2 mit Prevent Overlap
2. Run für 60 Sekunden
3. Noverlap für 10 Sekunden (entfernt Überlappungen)

### Schritt 2: Filter
1. Topology → Degree Range → min: 20
2. Zeigt nur relevante Nodes

### Schritt 3: Statistiken
1. Modularity → Run (findet Communities)
2. Optional: Color by Modularity Class

### Schritt 4: Preview
1. Preset: Default Straight
2. Node Labels: Show (font 10)
3. Edge Thickness: Proportional
4. Background: Dark

### Schritt 5: Export
1. SVG für Vektorgrafik (Illustrator, Präsentationen)
2. PNG für Social Media (4096x4096)
3. PDF für Dokumentation

---

## 🐛 Troubleshooting

### "Out of Memory" Error
- Schließe andere Programme
- Gephi Preferences → Memory: Erhöhe auf 4GB+
- Nutze kleineres Netzwerk (coaches_only statt full)

### Nodes überlappen sich
- Layout → Noverlap → Run
- ForceAtlas 2 → Prevent Overlap aktivieren

### Layout explodiert
- Gravity erhöhen (2.0-5.0)
- Scaling verringern (1.0)

### Zu langsam
- Nutze kleineres Netzwerk
- Yifan Hu statt ForceAtlas 2
- Deaktiviere Preview während Layout

---

## 📚 Beispiel-Analysen

### "Wer sind die Broker?"
1. Statistics → Betweenness Centrality → Run
2. Appearance → Size → Ranking → "Betweenness Centrality"
3. Große Nodes = Personen die Gruppen verbinden

### "Welche Communities gibt es?"
1. Statistics → Modularity → Run
2. Appearance → Color → Partition → "Modularity Class"
3. Farben = Communities (z.B. Bayern-Netzwerk, RB-Netzwerk)

### "Niko Kovac's Netzwerk"
1. Data Laboratory → Nodes → Suche "Niko Kovac"
2. Filters → Topology → Neighbors → Depth: 1
3. Zeigt nur Kovac und seine direkten Connections

### "Scouts vs Coaches"
1. Filters → Attributes → Type → "scout"
2. Appearance → Size → Ranking → "connections"
3. Siehe wer am besten vernetzt ist

---

## 🎨 Style-Vorlagen

### Modern Dark
```
Background: #1a1a1a
Node Border: White, 1.5px
Edge Color: #666666, 30% opacity
Labels: White, font 10
```

### Clean White
```
Background: #ffffff
Node Border: #333333, 1px
Edge Color: #cccccc, 50% opacity
Labels: Black, font 12
```

### High Contrast
```
Background: Black
Node Colors: Bright (saturated)
Edge Color: White, 20% opacity
Labels: White, bold
```

---

## 📖 Weitere Ressourcen

- **Gephi Tutorials:** https://gephi.org/users/
- **Gephi Forum:** https://forum-gephi.org/
- **Force Atlas 2 Paper:** Erklärt wie der Algorithmus funktioniert

---

**Erstellt:** Februar 11, 2026
**Netzwerk:** Football Coaches DB
**Nodes:** 1,095 Personen
**Edges:** 38,359 Verbindungen

**Viel Spaß beim Visualisieren! 🎨⚽**
