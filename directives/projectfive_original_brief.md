# projectFIVE Original Brief — Henryk's Email

## Context
Email from Henryk (projectFIVE team) to internal automation/AI/data experts, brainstormed before Christmas 2025.

## Core Request
> Create a database where all coaches of the biggest 100/200 football clubs are listed together with all important information about each individual coach.

## Desired Outputs (highest value for agency)

### 1. Club → Coaches
**"Who are all coaches (incl. assistant and youth coaches) at club XY?"**

### 2. Coach Profile
**"Who is coach XY?"** (key profile information)
- Age, nationality, license, current club/team, etc.
- All info from TM Profil page: `transfermarkt.com/{name}/profil/trainer/{id}`

### 3. Coaching Network
**"What other coaches and club staff has he worked with?"**

### 4. Playing Career Connections (if former player)
**"What other coaches & sporting directors has he played together with?"**
- All info from TM sub-page: `transfermarkt.com/{name}/gemeinsameSpiele/spieler/{player_id}`
- NOTE: This is the "Gemeinsame Spiele" (shared games) page — different from squad overlap!

### 5. Players Coached
**"Which players has he/she worked with successfully?"**
- Threshold: more than 20 games with avg. 70mins+ per game
- All info from TM sub-page: `transfermarkt.com/{name}/eingesetzteSpieler/trainer/{id}/...`

## Key TM Pages Referenced
| Page | URL Pattern | Data |
|------|-------------|------|
| Coach Profile | `/profil/trainer/{id}` | Bio, license, career history |
| Gemeinsame Spiele | `/gemeinsameSpiele/spieler/{player_id}` | Who they played WITH (as player) |
| Eingesetzte Spieler | `/eingesetzteSpieler/trainer/{id}` | Players used (as coach) |

## Additional Context
- "Network is key in football and especially in the industry of coaches management"
- "Small and very interconnected bubble where everybody has crossed paths"
- Manual example profile exists "in column L" (Excel-based, not available here)
- Team is "not AI-affine at all" — needs turnkey solution
- Framed as competitive edge for the agency

## Scope
- 100-200 biggest clubs globally
- All coaches per club (head, assistant, youth)
- Read-only information tool (confirmed by Carl)
