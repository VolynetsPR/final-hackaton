import os, sqlite3
DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'olympiad.sqlite3')

def get_connection():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_schema(con):
    con.executescript('''
    PRAGMA foreign_keys = ON;
    CREATE TABLE IF NOT EXISTS participants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL UNIQUE,
        region TEXT NOT NULL,
        class_num INTEGER NOT NULL,
        school TEXT,
        school_region TEXT
    );
    CREATE TABLE IF NOT EXISTS snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tour INTEGER NOT NULL,
        minute INTEGER NOT NULL,
        status TEXT,
        title TEXT,
        problem_count INTEGER NOT NULL,
        source_name TEXT,
        UNIQUE(tour, minute)
    );
    CREATE TABLE IF NOT EXISTS results (
        snapshot_id INTEGER NOT NULL,
        participant_id INTEGER NOT NULL,
        rank_text TEXT,
        rank_start INTEGER,
        rank_end INTEGER,
        p1 INTEGER DEFAULT 0, p2 INTEGER DEFAULT 0, p3 INTEGER DEFAULT 0, p4 INTEGER DEFAULT 0,
        p5 INTEGER DEFAULT 0, p6 INTEGER DEFAULT 0, p7 INTEGER DEFAULT 0, p8 INTEGER DEFAULT 0,
        total INTEGER DEFAULT 0,
        PRIMARY KEY(snapshot_id, participant_id),
        FOREIGN KEY(snapshot_id) REFERENCES snapshots(id) ON DELETE CASCADE,
        FOREIGN KEY(participant_id) REFERENCES participants(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS regional_students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        city TEXT NOT NULL,
        name TEXT NOT NULL,
        class_num INTEGER,
        school TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_results_participant ON results(participant_id);
    CREATE INDEX IF NOT EXISTS idx_snapshots_tour_minute ON snapshots(tour, minute);
    ''')
    con.commit()
