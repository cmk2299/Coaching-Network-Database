-- Football Coaches Intelligence Database
-- Optimized for agent use case: player placement

-- Core Entities
CREATE TABLE IF NOT EXISTS coaches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tm_id INTEGER UNIQUE NOT NULL,
    name TEXT NOT NULL,
    dob DATE,
    nationality TEXT,
    license_level TEXT,
    agent_name TEXT,
    agent_agency TEXT,
    image_url TEXT,

    -- Metadata
    first_scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(tm_id)
);

-- Career history (static - rarely changes)
CREATE TABLE IF NOT EXISTS career_stations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coach_id INTEGER NOT NULL,
    club_name TEXT NOT NULL,
    club_tm_id INTEGER,
    role TEXT, -- "Trainer", "Co-Trainer", etc.
    start_date DATE,
    end_date DATE,
    games INTEGER,
    wins INTEGER,
    draws INTEGER,
    losses INTEGER,
    ppg REAL,

    -- Metadata
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (coach_id) REFERENCES coaches(id),
    UNIQUE(coach_id, club_name, start_date)
);

-- Current status (dynamic - update weekly)
CREATE TABLE IF NOT EXISTS coach_current_status (
    coach_id INTEGER PRIMARY KEY,
    current_club TEXT,
    current_club_tm_id INTEGER,
    current_role TEXT,
    appointed_date DATE,

    -- Recent performance (last 10 games)
    recent_games INTEGER,
    recent_wins INTEGER,
    recent_ppg REAL,

    -- Metadata
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (coach_id) REFERENCES coaches(id)
);

-- Players used (CRITICAL for agent use case)
CREATE TABLE IF NOT EXISTS players_used (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coach_id INTEGER NOT NULL,
    player_name TEXT NOT NULL,
    player_tm_id INTEGER,
    position TEXT, -- "Attacking Midfield", "Left Winger", etc.
    nationality TEXT,
    age_when_coached INTEGER,

    -- Usage stats (KEY for agents!)
    club_name TEXT,
    season TEXT, -- "2023/24"
    games INTEGER,
    goals INTEGER,
    assists INTEGER,
    minutes_total INTEGER,
    minutes_avg REAL,

    -- Current club (for transfer opportunity detection)
    current_club TEXT,
    current_club_updated_at TIMESTAMP,

    -- Metadata
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (coach_id) REFERENCES coaches(id),
    UNIQUE(coach_id, player_name, season)
);

-- Decision Makers (manual curation)
CREATE TABLE IF NOT EXISTS decision_makers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coach_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    role TEXT, -- "Sportdirektor", "CEO", etc.
    club_name TEXT,
    connection_type TEXT, -- "hiring_manager", "sports_director", "executive"
    period TEXT,
    notes TEXT,

    -- Contact info (future)
    phone TEXT,
    email TEXT,
    linkedin_url TEXT,

    -- Metadata
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    added_by TEXT, -- "manual" or "scraped"

    FOREIGN KEY (coach_id) REFERENCES coaches(id)
);

-- Teammates (static - from playing career)
CREATE TABLE IF NOT EXISTS teammates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coach_id INTEGER NOT NULL,
    teammate_name TEXT NOT NULL,
    teammate_tm_id INTEGER,
    shared_club TEXT,
    shared_matches INTEGER,
    period_start DATE,
    period_end DATE,

    -- Current role (dynamic)
    is_coach BOOLEAN DEFAULT 0,
    is_director BOOLEAN DEFAULT 0,
    current_role TEXT,
    current_club TEXT,

    -- Metadata
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    role_updated_at TIMESTAMP,

    FOREIGN KEY (coach_id) REFERENCES coaches(id),
    UNIQUE(coach_id, teammate_name, shared_club)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_players_position ON players_used(position);
CREATE INDEX IF NOT EXISTS idx_players_games ON players_used(games);
CREATE INDEX IF NOT EXISTS idx_players_minutes ON players_used(minutes_avg);
CREATE INDEX IF NOT EXISTS idx_career_coach ON career_stations(coach_id);
CREATE INDEX IF NOT EXISTS idx_decision_makers_coach ON decision_makers(coach_id);

-- Views for common queries

-- Agent View: Find coaches who use specific positions heavily
CREATE VIEW IF NOT EXISTS v_position_usage AS
SELECT
    c.name as coach_name,
    c.id as coach_id,
    cs.current_club,
    p.position,
    COUNT(*) as players_used,
    AVG(p.games) as avg_games,
    AVG(p.minutes_avg) as avg_minutes,
    SUM(CASE WHEN p.games >= 20 THEN 1 ELSE 0 END) as starters
FROM coaches c
JOIN coach_current_status cs ON c.id = cs.coach_id
JOIN players_used p ON c.id = p.coach_id
WHERE p.games >= 10
GROUP BY c.id, p.position;

-- Agent View: Players who could follow coach
CREATE VIEW IF NOT EXISTS v_transfer_opportunities AS
SELECT
    c.name as coach_name,
    cs.current_club as coach_current_club,
    p.player_name,
    p.position,
    p.games,
    p.minutes_avg,
    p.current_club as player_current_club,
    CASE
        WHEN p.current_club != cs.current_club THEN 1
        ELSE 0
    END as is_opportunity
FROM coaches c
JOIN coach_current_status cs ON c.id = cs.coach_id
JOIN players_used p ON c.id = p.coach_id
WHERE p.games >= 20
  AND p.current_club IS NOT NULL
  AND p.current_club != cs.current_club;
