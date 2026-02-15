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
    birthplace TEXT,
    contract_until DATE,

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

-- Sportdirektor profiles (NEW - for Trainerberater use case)
CREATE TABLE IF NOT EXISTS sportdirektoren (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    current_club TEXT,
    current_role TEXT,
    nationality TEXT,
    dob DATE,

    -- Contact info
    phone TEXT,
    email TEXT,
    linkedin_url TEXT,
    tm_url TEXT,

    -- Career tracking
    clubs_worked_at TEXT, -- JSON array of clubs
    years_experience INTEGER,

    -- Metadata
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SD ↔ Coach relationships (CRITICAL for Trainerberater)
CREATE TABLE IF NOT EXISTS sd_coach_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sd_id INTEGER NOT NULL,
    coach_id INTEGER NOT NULL,

    -- Relationship details
    relationship_type TEXT, -- "hired", "worked_together", "indirect"
    club_name TEXT,
    period_start DATE,
    period_end DATE,

    -- Context
    hire_reason TEXT, -- "Promotion specialist", "Young talent", etc.
    outcome TEXT, -- "Promoted", "Fired after 6 months", "Successful", etc.
    notes TEXT,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (sd_id) REFERENCES sportdirektoren(id),
    FOREIGN KEY (coach_id) REFERENCES coaches(id),
    UNIQUE(sd_id, coach_id, club_name, period_start)
);

-- SD hiring patterns (derived from relationships)
CREATE VIEW IF NOT EXISTS v_sd_hiring_patterns AS
SELECT
    sd.name as sd_name,
    sd.current_club,
    COUNT(DISTINCT rel.coach_id) as coaches_hired,
    AVG(CASE
        WHEN rel.outcome LIKE '%Promoted%' OR rel.outcome LIKE '%Successful%'
        THEN 1 ELSE 0
    END) as success_rate,
    GROUP_CONCAT(DISTINCT c.nationality) as nationalities_hired,
    AVG(c.age) as avg_coach_age_hired
FROM sportdirektoren sd
LEFT JOIN sd_coach_relationships rel ON sd.id = rel.sd_id
LEFT JOIN coaches c ON rel.coach_id = c.id
WHERE rel.relationship_type = 'hired'
GROUP BY sd.id;

-- Coach relationship finder (for "Wer kennt meinen Trainer?")
CREATE VIEW IF NOT EXISTS v_coach_sd_connections AS
SELECT
    c.name as coach_name,
    c.id as coach_id,
    sd.name as sd_name,
    sd.id as sd_id,
    sd.current_club as sd_current_club,
    rel.relationship_type,
    rel.club_name as worked_at,
    rel.period_start,
    rel.period_end,
    rel.outcome,
    CASE
        WHEN rel.relationship_type = 'hired' AND rel.period_end IS NULL THEN 'active'
        WHEN rel.relationship_type = 'hired' THEN 'past'
        ELSE rel.relationship_type
    END as connection_status
FROM coaches c
JOIN sd_coach_relationships rel ON c.id = rel.coach_id
JOIN sportdirektoren sd ON rel.sd_id = sd.id
ORDER BY c.name, rel.period_start DESC;

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
