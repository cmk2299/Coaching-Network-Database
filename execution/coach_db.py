#!/usr/bin/env python3
"""
Database wrapper for Football Coaches Intelligence
Handles storage and retrieval of coach data with incremental updates

Strategy:
- STATIC data (career history, teammates): Scrape once, store forever
- DYNAMIC data (current club, recent results): Update weekly
- MANUAL data (decision makers, contacts): Curated by agents

Benefits:
- Scale to 150 clubs without 150x scraping time
- Only scrape changes, not everything
- Historical data preserved even if TM changes
"""

import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import json

# Database path
BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "data" / "coaches.db"

class CoachDB:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_PATH
        self._ensure_db()

    def _ensure_db(self):
        """Create database and tables if they don't exist."""
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.db_path)

        # Read schema from file
        schema_path = Path(__file__).parent / "db_schema.sql"
        if schema_path.exists():
            with open(schema_path, 'r') as f:
                conn.executescript(f.read())

        conn.commit()
        conn.close()

    def get_or_create_coach(self, tm_id: int, name: str) -> int:
        """
        Get coach_id from database, or create if doesn't exist.
        Returns: coach_id
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Try to find existing
        cursor.execute("SELECT id FROM coaches WHERE tm_id = ?", (tm_id,))
        row = cursor.fetchone()

        if row:
            coach_id = row[0]
        else:
            # Create new
            cursor.execute("""
                INSERT INTO coaches (tm_id, name, first_scraped_at)
                VALUES (?, ?, ?)
            """, (tm_id, name, datetime.now()))
            coach_id = cursor.lastrowid
            conn.commit()

        conn.close()
        return coach_id

    def should_scrape_profile(self, tm_id: int, max_age_days: int = 7) -> bool:
        """
        Check if we need to scrape this coach's profile.
        Returns: True if never scraped OR last scraped > max_age_days ago
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT last_updated_at
            FROM coaches
            WHERE tm_id = ?
        """, (tm_id,))

        row = cursor.fetchone()
        conn.close()

        if not row or not row[0]:
            return True  # Never scraped

        last_updated = datetime.fromisoformat(row[0])
        age_days = (datetime.now() - last_updated).days

        return age_days > max_age_days

    def save_coach_profile(self, tm_id: int, profile_data: dict):
        """
        Save coach profile (static data).
        This should only be called once per coach unless data changes.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get or create coach
        coach_id = self.get_or_create_coach(tm_id, profile_data.get("name", "Unknown"))

        # Update coach record
        cursor.execute("""
            UPDATE coaches
            SET name = ?,
                dob = ?,
                nationality = ?,
                license_level = ?,
                agent_name = ?,
                agent_agency = ?,
                image_url = ?,
                last_updated_at = ?
            WHERE id = ?
        """, (
            profile_data.get("name"),
            profile_data.get("dob"),
            profile_data.get("nationality"),
            profile_data.get("license"),
            profile_data.get("agent"),
            profile_data.get("agent_url"),  # Store agency URL
            profile_data.get("image_url"),
            datetime.now(),
            coach_id
        ))

        # Save career stations (static)
        for station in profile_data.get("career_history", []):
            cursor.execute("""
                INSERT OR IGNORE INTO career_stations
                (coach_id, club_name, role, start_date, end_date, games, wins, draws, losses, ppg)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                coach_id,
                station.get("club"),
                station.get("role"),
                station.get("start_date"),
                station.get("end_date"),
                station.get("games"),
                station.get("wins"),
                station.get("draws"),
                station.get("losses"),
                station.get("ppg")
            ))

        conn.commit()
        conn.close()

        return coach_id

    def save_current_status(self, tm_id: int, current_club: str, current_role: str):
        """
        Update current club/role (dynamic data).
        This should be updated weekly.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        coach_id = self.get_or_create_coach(tm_id, "")  # Name not needed here

        cursor.execute("""
            INSERT OR REPLACE INTO coach_current_status
            (coach_id, current_club, current_role, updated_at)
            VALUES (?, ?, ?, ?)
        """, (coach_id, current_club, current_role, datetime.now()))

        conn.commit()
        conn.close()

    def save_players_used(self, tm_id: int, players_data: List[dict]):
        """
        Save players coached by this coach.
        Only insert new records (seasons not yet stored).
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        coach_id = self.get_or_create_coach(tm_id, "")

        for player in players_data:
            cursor.execute("""
                INSERT OR IGNORE INTO players_used
                (coach_id, player_name, player_tm_id, position, nationality,
                 age_when_coached, club_name, season, games, goals, assists,
                 minutes_total, minutes_avg, current_club)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                coach_id,
                player.get("name"),
                player.get("tm_id"),
                player.get("position"),
                player.get("nationality"),
                player.get("age"),
                player.get("club"),
                player.get("season"),
                player.get("games"),
                player.get("goals"),
                player.get("assists"),
                player.get("minutes_total"),
                player.get("avg_minutes"),
                player.get("current_club")
            ))

        conn.commit()
        conn.close()

    def get_coach_profile(self, tm_id: int) -> Optional[dict]:
        """
        Retrieve full coach profile from database.
        Returns None if not found.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Return rows as dicts
        cursor = conn.cursor()

        # Get coach basic info
        cursor.execute("SELECT * FROM coaches WHERE tm_id = ?", (tm_id,))
        coach_row = cursor.fetchone()

        if not coach_row:
            conn.close()
            return None

        coach = dict(coach_row)

        # Get career stations
        cursor.execute("""
            SELECT * FROM career_stations
            WHERE coach_id = ?
            ORDER BY start_date DESC
        """, (coach['id'],))

        coach['career_history'] = [dict(row) for row in cursor.fetchall()]

        # Get current status
        cursor.execute("""
            SELECT * FROM coach_current_status
            WHERE coach_id = ?
        """, (coach['id'],))

        status_row = cursor.fetchone()
        if status_row:
            coach['current_status'] = dict(status_row)

        conn.close()
        return coach

    def find_coaches_by_position_usage(self, position: str, min_games: int = 20) -> List[dict]:
        """
        AGENT FEATURE: Find coaches who use a specific position heavily.

        Example: position="Attacking Midfield", min_games=20
        Returns coaches who gave AMs 20+ games on average
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                c.name as coach_name,
                c.tm_id,
                cs.current_club,
                COUNT(*) as players_used,
                AVG(p.games) as avg_games,
                AVG(p.minutes_avg) as avg_minutes,
                SUM(CASE WHEN p.games >= ? THEN 1 ELSE 0 END) as starters
            FROM coaches c
            JOIN coach_current_status cs ON c.id = cs.coach_id
            JOIN players_used p ON c.id = p.coach_id
            WHERE p.position = ?
              AND p.games >= 10
            GROUP BY c.id
            HAVING avg_games >= ?
            ORDER BY avg_games DESC
        """, (min_games, position, min_games))

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return results

    def find_transfer_opportunities(self, coach_tm_id: int) -> List[dict]:
        """
        AGENT FEATURE: Find players who played 20+ games under this coach
        but now play elsewhere (could follow coach to new club).
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                p.player_name,
                p.position,
                p.games,
                p.minutes_avg,
                p.club_name as played_at,
                p.current_club,
                cs.current_club as coach_current_club
            FROM players_used p
            JOIN coaches c ON p.coach_id = c.id
            JOIN coach_current_status cs ON c.id = cs.coach_id
            WHERE c.tm_id = ?
              AND p.games >= 20
              AND p.current_club IS NOT NULL
              AND p.current_club != cs.current_club
            ORDER BY p.games DESC
        """, (coach_tm_id,))

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return results

# Singleton instance
_db = None

def get_db() -> CoachDB:
    """Get or create global database instance."""
    global _db
    if _db is None:
        _db = CoachDB()
    return _db
