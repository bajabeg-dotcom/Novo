
-- PA800 MIDI Enhancer Forensic Evidence Database Schema
-- Generated: 2026-08-19T18:17:43.003720
-- Forensic Level: 5 (SHA-256 + MD5 + Metadata + MIDI Structure + Markers)

-- Tablica za hashove datoteka
CREATE TABLE IF NOT EXISTS file_hashes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT UNIQUE NOT NULL,
    file_name TEXT NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    sha256_hash TEXT NOT NULL,
    md5_hash TEXT NOT NULL,
    modified_time TIMESTAMP NOT NULL,
    created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    forensic_level INTEGER DEFAULT 5,
    confidence REAL DEFAULT 1.0
);

-- Tablica za MIDI analize
CREATE TABLE IF NOT EXISTS midi_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT UNIQUE NOT NULL,
    midi_type INTEGER,
    ticks_per_beat INTEGER,
    total_tracks INTEGER,
    total_notes INTEGER,
    total_time_seconds REAL,
    note_min INTEGER,
    note_max INTEGER,
    velocity_min INTEGER,
    velocity_max INTEGER,
    channels_used TEXT, -- JSON array
    markers_count INTEGER,
    tempo_changes_count INTEGER,
    key_signatures_count INTEGER,
    programs_count INTEGER,
    has_lyrics BOOLEAN,
    has_pitch_bend BOOLEAN,
    analysis_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tablica za trackove
CREATE TABLE IF NOT EXISTS midi_tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id INTEGER NOT NULL,
    track_index INTEGER NOT NULL,
    track_name TEXT,
    channel INTEGER,
    notes_count INTEGER,
    program_changes_count INTEGER,
    controller_events_count INTEGER,
    pitch_bends_count INTEGER,
    lyrics_count INTEGER,
    FOREIGN KEY (analysis_id) REFERENCES midi_analyses(id)
);

-- Tablica za RX profile
CREATE TABLE IF NOT EXISTS rx_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_name TEXT UNIQUE NOT NULL,
    instrument_type TEXT NOT NULL, -- 'bass', 'guitar', 'drums'
    bank_msb INTEGER NOT NULL,
    bank_lsb INTEGER NOT NULL,
    program INTEGER NOT NULL,
    channel INTEGER DEFAULT 0,
    velocity_zones TEXT, -- JSON array
    key_zones TEXT, -- JSON object
    noise_triggers TEXT, -- JSON object
    multisample_switches TEXT, -- JSON object
    rx_switches TEXT, -- JSON object
    confirmed BOOLEAN DEFAULT FALSE,
    confidence REAL,
    source TEXT,
    created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tablica za hardware probe rezultate
CREATE TABLE IF NOT EXISTS hardware_probes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bank_msb INTEGER NOT NULL,
    bank_lsb INTEGER NOT NULL,
    program INTEGER NOT NULL,
    channel INTEGER DEFAULT 0,
    expected_name TEXT NOT NULL,
    actual_name TEXT,
    os_version TEXT,
    resource_version TEXT,
    test_run_1_result TEXT,
    test_run_2_result TEXT,
    confirmed BOOLEAN DEFAULT FALSE,
    test_timestamp TIMESTAMP,
    tester_notes TEXT
);

-- Tablica za regression testove
CREATE TABLE IF NOT EXISTS regression_tests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    test_name TEXT UNIQUE NOT NULL,
    test_type TEXT NOT NULL,
    original_tracks INTEGER,
    optimized_tracks INTEGER,
    original_notes INTEGER,
    optimized_notes INTEGER,
    tracks_preserved BOOLEAN,
    notes_preserved BOOLEAN,
    lyrics_preserved BOOLEAN,
    pitch_bend_preserved BOOLEAN,
    passed BOOLEAN,
    test_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    details TEXT -- JSON
);

-- Tablica za gap analysis (nedovršene stavke)
CREATE TABLE IF NOT EXISTS gap_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id TEXT UNIQUE NOT NULL,
    category TEXT NOT NULL, -- 'P0', 'P1', 'P2'
    description TEXT NOT NULL,
    status TEXT NOT NULL, -- 'missing', 'partial', 'candidate'
    confidence REAL,
    priority TEXT,
    completion_criteria TEXT,
    evidence_path TEXT,
    created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indeksi za brže pretraživanje
CREATE INDEX IF NOT EXISTS idx_file_hashes_sha256 ON file_hashes(sha256_hash);
CREATE INDEX IF NOT EXISTS idx_midi_analyses_file_path ON midi_analyses(file_path);
CREATE INDEX IF NOT EXISTS idx_rx_profiles_instrument ON rx_profiles(instrument_type);
CREATE INDEX IF NOT EXISTS idx_hardware_probes_address ON hardware_probes(bank_msb, bank_lsb, program, channel);
CREATE INDEX IF NOT EXISTS idx_regression_tests_passed ON regression_tests(passed);
