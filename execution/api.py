#!/usr/bin/env python3
"""
projectFIVE Coach Network API

FastAPI backend serving SQLite data for dynamic queries.
Replaces pre-rendered static HTML for interactive use cases.

Usage:
    uvicorn execution.api:app --reload --port 8000
    # or:
    python execution/api.py

Endpoints:
    GET /                       → API info + stats
    GET /coaches                → All BL coaches (filterable by league)
    GET /coaches/{tm_id}        → Single coach detail + career
    GET /coaches/{tm_id}/network → Full network data (contacts, stations)
    GET /persons/{tm_id}        → Person detail
    GET /search?q=Kovac         → Search persons by name
    GET /transitions            → All career transitions
    GET /clubs/{tm_id}          → Club detail + current staff
    GET /stats                  → Database statistics
    GET /query                  → Ad-hoc SQL (read-only, parameterized)
"""

import sqlite3
import json
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

BASE = Path(__file__).parent.parent
DB_PATH = BASE / "data" / "coaches.db"
NETWORKS_DIR = BASE / "data" / "networks"

app = FastAPI(
    title="projectFIVE Coach Network API",
    version="1.0.0",
    description="SQLite-backed API for German football coach networks",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


# ── DB Helper ─────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def rows_to_dicts(rows):
    return [dict(r) for r in rows]


def row_to_dict(row):
    return dict(row) if row else None


# ── Root ──────────────────────────────────────────────────────────────

@app.get("/")
def root():
    conn = get_db()
    stats = {}
    for table in ["clubs", "persons", "career_history", "squad_entries",
                   "staff_entries", "career_transitions"]:
        stats[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    conn.close()
    return {
        "name": "projectFIVE Coach Network API",
        "version": "1.0.0",
        "database": str(DB_PATH),
        "tables": stats,
    }


# ── Coaches ───────────────────────────────────────────────────────────

@app.get("/coaches")
def list_coaches(
    league: Optional[str] = Query(None, description="Filter by league: BL1, BL2, BL3"),
    season: int = Query(2025, description="Season year (default: 2025)"),
):
    """All current head coaches with club + league info."""
    conn = get_db()
    sql = """
        SELECT p.tm_id, p.name, p.nationality, p.dob, p.license, p.image_url,
               s.club_tm_id, c.name as club_name, cs.league,
               (SELECT COUNT(*) FROM career_history WHERE person_tm_id = p.tm_id) as career_stations
        FROM staff_entries s
        JOIN persons p ON p.tm_id = s.person_tm_id
        JOIN clubs c ON c.tm_id = s.club_tm_id
        JOIN club_seasons cs ON cs.club_tm_id = s.club_tm_id AND cs.season = ?
        WHERE s.is_head_coach = 1
    """
    params = [season]
    if league:
        sql += " AND cs.league = ?"
        params.append(league)
    sql += " ORDER BY cs.league, c.name"

    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return rows_to_dicts(rows)


@app.get("/coaches/{tm_id}")
def get_coach(tm_id: int):
    """Full coach detail: profile + career history."""
    conn = get_db()
    person = conn.execute("SELECT * FROM persons WHERE tm_id = ?", (tm_id,)).fetchone()
    if not person:
        conn.close()
        raise HTTPException(404, "Coach not found")

    career = conn.execute("""
        SELECT club_name, role, role_category, season_from, season_to, games, points_per_game
        FROM career_history WHERE person_tm_id = ?
        ORDER BY season_from DESC
    """, (tm_id,)).fetchall()

    # Current staff position
    staff = conn.execute("""
        SELECT s.club_tm_id, c.name as club_name, s.section, s.is_head_coach
        FROM staff_entries s
        JOIN clubs c ON c.tm_id = s.club_tm_id
        WHERE s.person_tm_id = ?
    """, (tm_id,)).fetchall()

    conn.close()
    return {
        "person": row_to_dict(person),
        "career": rows_to_dicts(career),
        "staff_positions": rows_to_dicts(staff),
    }


@app.get("/coaches/{tm_id}/network")
def get_coach_network(tm_id: int):
    """Full pre-built network data for a coach (contacts, stations, drilldown)."""
    network_path = NETWORKS_DIR / f"{tm_id}.json"
    if not network_path.exists():
        raise HTTPException(404, f"Network not built for tm_id {tm_id}")

    with open(network_path) as f:
        network = json.load(f)
    return network


# ── Persons ───────────────────────────────────────────────────────────

@app.get("/persons/{tm_id}")
def get_person(tm_id: int):
    """Person detail: profile + squad history + career + transitions."""
    conn = get_db()
    person = conn.execute("SELECT * FROM persons WHERE tm_id = ?", (tm_id,)).fetchone()
    if not person:
        conn.close()
        raise HTTPException(404, "Person not found")

    career = conn.execute("""
        SELECT * FROM career_history WHERE person_tm_id = ?
        ORDER BY season_from DESC
    """, (tm_id,)).fetchall()

    squads = conn.execute("""
        SELECT sq.season, sq.club_tm_id, c.name as club_name, sq.position, sq.shirt_number
        FROM squad_entries sq
        JOIN clubs c ON c.tm_id = sq.club_tm_id
        WHERE sq.person_tm_id = ?
        ORDER BY sq.season DESC
    """, (tm_id,)).fetchall()

    transitions = conn.execute("""
        SELECT * FROM career_transitions WHERE person_tm_id = ?
    """, (tm_id,)).fetchall()

    conn.close()
    return {
        "person": row_to_dict(person),
        "career": rows_to_dicts(career),
        "squads": rows_to_dicts(squads),
        "transitions": rows_to_dicts(transitions),
    }


# ── Search ────────────────────────────────────────────────────────────

@app.get("/search")
def search_persons(
    q: str = Query(..., min_length=2, description="Search term"),
    type: Optional[str] = Query(None, description="Filter: trainer, spieler"),
    limit: int = Query(25, le=100),
):
    """Search persons by name (prefix match)."""
    conn = get_db()
    sql = "SELECT tm_id, name, type, nationality, current_club_name, image_url FROM persons WHERE name LIKE ?"
    params = [f"%{q}%"]
    if type:
        sql += " AND type = ?"
        params.append(type)
    sql += " ORDER BY name LIMIT ?"
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return rows_to_dicts(rows)


# ── Transitions ───────────────────────────────────────────────────────

@app.get("/transitions")
def list_transitions(
    to_role: Optional[str] = Query(None, description="Filter: coaching_staff, scouting, management"),
    limit: int = Query(100, le=500),
):
    """All career transitions (player → coach/SD/scout)."""
    conn = get_db()
    sql = """
        SELECT p.tm_id, p.name, p.nationality, p.image_url,
               ct.from_role, ct.to_role, ct.transition_season, ct.club_name
        FROM career_transitions ct
        JOIN persons p ON p.tm_id = ct.person_tm_id
    """
    params = []
    if to_role:
        sql += " WHERE ct.to_role = ?"
        params.append(to_role)
    sql += " ORDER BY ct.transition_season DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return rows_to_dicts(rows)


# ── Clubs ─────────────────────────────────────────────────────────────

@app.get("/clubs/{tm_id}")
def get_club(tm_id: int):
    """Club detail: info + current staff + league history."""
    conn = get_db()
    club = conn.execute("SELECT * FROM clubs WHERE tm_id = ?", (tm_id,)).fetchone()
    if not club:
        conn.close()
        raise HTTPException(404, "Club not found")

    staff = conn.execute("""
        SELECT se.person_tm_id, p.name, se.section, se.role, se.is_head_coach, p.image_url
        FROM staff_entries se
        JOIN persons p ON p.tm_id = se.person_tm_id
        WHERE se.club_tm_id = ?
        ORDER BY se.is_head_coach DESC, se.section
    """, (tm_id,)).fetchall()

    seasons = conn.execute("""
        SELECT season, league FROM club_seasons WHERE club_tm_id = ? ORDER BY season DESC
    """, (tm_id,)).fetchall()

    conn.close()
    return {
        "club": row_to_dict(club),
        "staff": rows_to_dicts(staff),
        "seasons": rows_to_dicts(seasons),
    }


# ── Stats ─────────────────────────────────────────────────────────────

@app.get("/stats")
def stats():
    """Database statistics and coverage metrics."""
    conn = get_db()

    result = {
        "persons": {
            "total": conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0],
            "trainers": conn.execute("SELECT COUNT(*) FROM persons WHERE type='trainer'").fetchone()[0],
            "players": conn.execute("SELECT COUNT(*) FROM persons WHERE type='spieler'").fetchone()[0],
            "with_profile": conn.execute("SELECT COUNT(*) FROM persons WHERE profile_scraped=1").fetchone()[0],
            "with_image": conn.execute("SELECT COUNT(*) FROM persons WHERE image_url IS NOT NULL").fetchone()[0],
            "with_nationality": conn.execute("SELECT COUNT(*) FROM persons WHERE nationality IS NOT NULL").fetchone()[0],
        },
        "clubs": {
            "total": conn.execute("SELECT COUNT(*) FROM clubs").fetchone()[0],
            "bl_registry": conn.execute("SELECT COUNT(*) FROM clubs WHERE country='Deutschland'").fetchone()[0],
            "foreign_stubs": conn.execute("SELECT COUNT(*) FROM clubs WHERE country='Ausland/Sonstige'").fetchone()[0],
        },
        "career_history": conn.execute("SELECT COUNT(*) FROM career_history").fetchone()[0],
        "squad_entries": conn.execute("SELECT COUNT(*) FROM squad_entries").fetchone()[0],
        "staff_entries": conn.execute("SELECT COUNT(*) FROM staff_entries").fetchone()[0],
        "career_transitions": conn.execute("SELECT COUNT(*) FROM career_transitions").fetchone()[0],
        "networks_built": len(list(NETWORKS_DIR.glob("*.json"))) if NETWORKS_DIR.exists() else 0,
    }

    conn.close()
    return result


# ── Shared Stations Query ─────────────────────────────────────────────

@app.get("/shared-stations")
def shared_stations(
    person_a: int = Query(..., description="First person tm_id"),
    person_b: int = Query(..., description="Second person tm_id"),
):
    """Find clubs + seasons where two persons overlapped."""
    conn = get_db()

    # Career overlap (coaches)
    career_overlap = conn.execute("""
        SELECT a.club_name, a.season_from, a.role as role_a, b.role as role_b
        FROM career_history a
        JOIN career_history b ON a.club_tm_id = b.club_tm_id AND a.season_from = b.season_from
        WHERE a.person_tm_id = ? AND b.person_tm_id = ?
        ORDER BY a.season_from DESC
    """, (person_a, person_b)).fetchall()

    # Squad overlap (players)
    squad_overlap = conn.execute("""
        SELECT a.club_tm_id, c.name as club_name, a.season
        FROM squad_entries a
        JOIN squad_entries b ON a.club_tm_id = b.club_tm_id AND a.season = b.season
        JOIN clubs c ON c.tm_id = a.club_tm_id
        WHERE a.person_tm_id = ? AND b.person_tm_id = ?
        ORDER BY a.season DESC
    """, (person_a, person_b)).fetchall()

    conn.close()
    return {
        "career_overlap": rows_to_dicts(career_overlap),
        "squad_overlap": rows_to_dicts(squad_overlap),
    }


# ── Ad-hoc Read-Only Query ───────────────────────────────────────────

BLOCKED_KEYWORDS = {"insert", "update", "delete", "drop", "alter", "create", "attach", "pragma"}

@app.get("/query")
def adhoc_query(
    sql: str = Query(..., description="Read-only SQL query"),
    limit: int = Query(100, le=1000),
):
    """Execute a read-only SQL query against the database."""
    # Safety: block write operations
    sql_lower = sql.lower().strip()
    for kw in BLOCKED_KEYWORDS:
        if kw in sql_lower:
            raise HTTPException(400, f"Write operation '{kw}' not allowed")

    if not sql_lower.startswith("select"):
        raise HTTPException(400, "Only SELECT queries allowed")

    # Add LIMIT if not present
    if "limit" not in sql_lower:
        sql = sql.rstrip(";") + f" LIMIT {limit}"

    conn = get_db()
    try:
        rows = conn.execute(sql).fetchall()
        result = rows_to_dicts(rows)
    except sqlite3.OperationalError as e:
        conn.close()
        raise HTTPException(400, f"SQL error: {e}")

    conn.close()
    return {"rows": result, "count": len(result)}


# ── Refresh (trigger staff scrape + network rebuild) ──────────────────

@app.post("/refresh/{club_tm_id}")
def refresh_club(club_tm_id: int):
    """
    Refresh a club's staff data from TM, rebuild affected coach networks,
    and regenerate dashboards. Call this after a coaching change.

    Example: POST /refresh/3  (1.FC Köln)
    """
    import subprocess, time as _time

    steps = []
    t0 = _time.time()

    # 1. Scrape staff for this club
    try:
        result = subprocess.run(
            ["python3", "execution/scrape_squads.py", "--staff-only",
             f"--club={club_tm_id}"],
            capture_output=True, text=True, timeout=60,
            cwd=str(BASE)
        )
        steps.append({"step": "scrape_staff", "ok": result.returncode == 0,
                       "output": result.stdout[-500:] if result.stdout else result.stderr[-500:]})
    except Exception as e:
        steps.append({"step": "scrape_staff", "ok": False, "error": str(e)})

    # 2. Find head coach at this club
    conn = get_db()
    coach_row = conn.execute("""
        SELECT se.person_tm_id, p.name
        FROM staff_entries se
        JOIN persons p ON p.tm_id = se.person_tm_id
        WHERE se.club_tm_id = ? AND se.is_head_coach = 1
    """, (club_tm_id,)).fetchone()
    conn.close()

    if not coach_row:
        steps.append({"step": "find_coach", "ok": False, "error": "No head coach found for this club"})
        return {"steps": steps, "elapsed": _time.time() - t0}

    coach_id = coach_row["person_tm_id"]
    coach_name = coach_row["name"]
    steps.append({"step": "find_coach", "ok": True, "coach": coach_name, "tm_id": coach_id})

    # 3. Rebuild network for this coach
    try:
        result = subprocess.run(
            ["python3", "execution/generate_all_bl_coaches.py", "--only", str(coach_id)],
            capture_output=True, text=True, timeout=120,
            cwd=str(BASE)
        )
        steps.append({"step": "rebuild_network", "ok": result.returncode == 0,
                       "output": result.stdout[-500:] if result.stdout else result.stderr[-500:]})
    except Exception as e:
        steps.append({"step": "rebuild_network", "ok": False, "error": str(e)})

    # 4. Rebuild SQLite
    try:
        result = subprocess.run(
            ["python3", "execution/build_sqlite.py"],
            capture_output=True, text=True, timeout=60,
            cwd=str(BASE)
        )
        steps.append({"step": "rebuild_db", "ok": result.returncode == 0})
    except Exception as e:
        steps.append({"step": "rebuild_db", "ok": False, "error": str(e)})

    elapsed = _time.time() - t0
    all_ok = all(s.get("ok") for s in steps)
    return {
        "success": all_ok,
        "club_tm_id": club_tm_id,
        "coach": coach_name if coach_row else None,
        "steps": steps,
        "elapsed": round(elapsed, 1),
        "note": "Run 'cd output && npx vercel deploy --prod' to push to production" if all_ok else None,
    }


@app.get("/refresh/clubs")
def list_refreshable_clubs():
    """List all clubs with head coaches (for refresh UI)."""
    conn = get_db()
    rows = conn.execute("""
        SELECT c.tm_id, c.name, p.name as coach_name, cs.league
        FROM staff_entries se
        JOIN clubs c ON c.tm_id = se.club_tm_id
        JOIN persons p ON p.tm_id = se.person_tm_id
        LEFT JOIN club_seasons cs ON cs.club_tm_id = c.tm_id AND cs.season = 2025
        WHERE se.is_head_coach = 1
        ORDER BY cs.league, c.name
    """).fetchall()
    conn.close()
    return rows_to_dicts(rows)


# ── Run directly ──────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    print(f"\n  projectFIVE API starting...")
    print(f"  Database: {DB_PATH}")
    print(f"  Docs: http://localhost:8000/docs\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
