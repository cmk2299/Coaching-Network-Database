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
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
import json

# Database path
BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "data" / "coaches.db"

def parse_german_date(date_str: str) -> Optional[str]:
    """
    Parse German date format 'DD.MM.YYYY' to ISO 'YYYY-MM-DD'.
    Handles formats like '15.06.1983 (42)' or '01.07.2024' or 'vsl. 30.06.2028'.
    Returns None if no valid date found.
    """
    if not date_str:
        return None
    match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', str(date_str))
    if match:
        return f"{match.group(3)}-{match.group(2)}-{match.group(1)}"
    return None


def parse_career_period(period_str: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse career period string into (start_date, end_date) in ISO format.

    Handles formats like:
    - '24/25 (01.07.2024) - vsl. 30.06.2029'
    - '22/23 (01.12.2022) - 23/24 (30.06.2024)'
    - '24/25 (01.07.2024) - -'
    - '05/06 (01.07.2005) - 16/17 (30.06.2016)'

    Returns (start_date_iso, end_date_iso) — either can be None.
    """
    if not period_str:
        return None, None

    # Find all DD.MM.YYYY patterns in the string
    dates = re.findall(r'(\d{2}\.\d{2}\.\d{4})', period_str)

    start_date = parse_german_date(dates[0]) if len(dates) >= 1 else None
    end_date = parse_german_date(dates[1]) if len(dates) >= 2 else None

    return start_date, end_date


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

        Handles JSON profiles from tmp/preloaded/ with:
        - German date format DOB ('15.06.1983 (42)')
        - Career period strings ('24/25 (01.07.2024) - vsl. 30.06.2029')
        - birthplace, contract_until, agent_url fields
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get or create coach
        coach_id = self.get_or_create_coach(tm_id, profile_data.get("name", "Unknown"))

        # Parse DOB from German format
        dob_iso = parse_german_date(profile_data.get("dob"))

        # Parse contract_until from German format
        contract_until_iso = parse_german_date(profile_data.get("contract_until"))

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
                birthplace = ?,
                contract_until = ?,
                last_updated_at = ?
            WHERE id = ?
        """, (
            profile_data.get("name"),
            dob_iso,
            profile_data.get("nationality"),
            profile_data.get("license"),
            profile_data.get("agent"),
            profile_data.get("agent_url"),  # Store agency URL
            profile_data.get("image_url"),
            profile_data.get("birthplace"),
            contract_until_iso,
            datetime.now(),
            coach_id
        ))

        # Save career stations (static)
        # JSON has 'period' string — parse into start_date / end_date
        for station in profile_data.get("career_history", []):
            # Try explicit start_date/end_date first, fall back to period parsing
            start_date = station.get("start_date")
            end_date = station.get("end_date")

            if not start_date and station.get("period"):
                start_date, end_date = parse_career_period(station["period"])

            cursor.execute("""
                INSERT OR IGNORE INTO career_stations
                (coach_id, club_name, role, start_date, end_date, games, wins, draws, losses, ppg)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                coach_id,
                station.get("club"),
                station.get("role"),
                start_date,
                end_date,
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

    # ========== SPORTDIREKTOR FUNCTIONS (for Trainerberater) ==========

    def get_or_create_sd(self, name: str, current_club: str = None) -> int:
        """
        Get SD id from database, or create if doesn't exist.
        Returns: sd_id
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Try to find existing
        cursor.execute("SELECT id FROM sportdirektoren WHERE name = ?", (name,))
        row = cursor.fetchone()

        if row:
            sd_id = row[0]
        else:
            # Create new
            cursor.execute("""
                INSERT INTO sportdirektoren (name, current_club, added_at)
                VALUES (?, ?, ?)
            """, (name, current_club, datetime.now()))
            sd_id = cursor.lastrowid
            conn.commit()

        conn.close()
        return sd_id

    def add_sd_coach_relationship(self, sd_name: str, coach_tm_id: int,
                                   relationship_type: str, club_name: str,
                                   period: str, outcome: str = None, notes: str = None):
        """
        Add a relationship between SD and Coach.

        Args:
            sd_name: Name of Sportdirektor
            coach_tm_id: Transfermarkt ID of coach
            relationship_type: "hired", "worked_together", "indirect"
            club_name: Where they worked together
            period: "2024-present" or "2022-2023"
            outcome: "Promoted", "Successful", "Fired", etc.
            notes: Additional context
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get or create SD
        sd_id = self.get_or_create_sd(sd_name, club_name)

        # Get coach
        cursor.execute("SELECT id FROM coaches WHERE tm_id = ?", (coach_tm_id,))
        coach_row = cursor.fetchone()
        if not coach_row:
            conn.close()
            raise ValueError(f"Coach with tm_id {coach_tm_id} not found in database")

        coach_id = coach_row[0]

        # Parse period
        period_start = None
        period_end = None
        if "-" in period:
            parts = period.split("-")
            period_start = parts[0].strip()
            period_end = parts[1].strip() if parts[1].strip().lower() != "present" else None

        # Insert relationship
        cursor.execute("""
            INSERT OR IGNORE INTO sd_coach_relationships
            (sd_id, coach_id, relationship_type, club_name, period_start, period_end, outcome, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (sd_id, coach_id, relationship_type, club_name, period_start, period_end, outcome, notes))

        conn.commit()
        conn.close()

    def find_sd_connections_for_coach(self, coach_tm_id: int) -> dict:
        """
        TRAINERBERATER FEATURE: Find all SD connections for a coach.

        Returns categorized connections:
        - existing: SDs who hired this coach
        - indirect: SDs in same network/clubs
        - no_relationship: SDs who might fit but no connection yet
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Existing relationships
        cursor.execute("""
            SELECT
                sd.name as sd_name,
                sd.current_club,
                sd.current_role,
                rel.relationship_type,
                rel.club_name as worked_at,
                rel.period_start,
                rel.period_end,
                rel.outcome,
                rel.notes,
                CASE
                    WHEN rel.period_end IS NULL THEN 'active'
                    ELSE 'past'
                END as status
            FROM coaches c
            JOIN sd_coach_relationships rel ON c.id = rel.coach_id
            JOIN sportdirektoren sd ON rel.sd_id = sd.id
            WHERE c.tm_id = ?
            ORDER BY rel.period_start DESC
        """, (coach_tm_id,))

        existing = [dict(row) for row in cursor.fetchall()]

        conn.close()

        return {
            "existing": existing,
            "indirect": [],  # TODO: Implement indirect connections
            "no_relationship": []  # TODO: Implement potential fits
        }

    def find_coaches_for_sd(self, sd_name: str) -> List[dict]:
        """
        TRAINERBERATER FEATURE: Find all coaches hired by this SD.
        Shows hiring pattern for pitching similar coaches.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                c.name as coach_name,
                c.tm_id,
                c.nationality,
                c.dob,
                c.license_level,
                rel.club_name,
                rel.period_start,
                rel.period_end,
                rel.outcome,
                rel.notes
            FROM sportdirektoren sd
            JOIN sd_coach_relationships rel ON sd.id = rel.sd_id
            JOIN coaches c ON rel.coach_id = c.id
            WHERE sd.name = ?
              AND rel.relationship_type = 'hired'
            ORDER BY rel.period_start DESC
        """, (sd_name,))

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return results

    def find_matching_sds_for_coach_profile(self, nationality: str = None,
                                             license_level: str = None,
                                             min_age: int = None,
                                             max_age: int = None) -> List[dict]:
        """
        TRAINERBERATER FEATURE: Reverse search - find SDs who hire coaches
        matching this profile.

        Example: "Welche SDs hired German coaches mit UEFA Pro?"
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Build query dynamically
        query = """
            SELECT
                sd.name as sd_name,
                sd.current_club,
                sd.current_role,
                COUNT(DISTINCT c.id) as coaches_hired,
                GROUP_CONCAT(DISTINCT c.name) as coaches_list,
                AVG(CASE
                    WHEN rel.outcome LIKE '%romot%' OR rel.outcome LIKE '%uccessful%'
                    THEN 1 ELSE 0
                END) as success_rate
            FROM sportdirektoren sd
            JOIN sd_coach_relationships rel ON sd.id = rel.sd_id
            JOIN coaches c ON rel.coach_id = c.id
            WHERE rel.relationship_type = 'hired'
        """

        params = []

        if nationality:
            query += " AND c.nationality = ?"
            params.append(nationality)

        if license_level:
            query += " AND c.license_level = ?"
            params.append(license_level)

        # TODO: Add age filtering when we have proper DOB data

        query += """
            GROUP BY sd.id
            HAVING coaches_hired >= 2
            ORDER BY coaches_hired DESC, success_rate DESC
        """

        cursor.execute(query, params)

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
