-- RX Profiles Table
CREATE TABLE IF NOT EXISTS rx_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sound_name TEXT UNIQUE NOT NULL,
    rx_type TEXT NOT NULL,
    bank_msb INTEGER NOT NULL,
    bank_lsb INTEGER NOT NULL,
    program INTEGER NOT NULL,
    version TEXT NOT NULL,
    resource_version TEXT NOT NULL,
    hardware_confirmed BOOLEAN DEFAULT FALSE,
    confidence_score REAL DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Velocity Zones Table
CREATE TABLE IF NOT EXISTS velocity_zones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL,
    min_velocity INTEGER NOT NULL,
    max_velocity INTEGER NOT NULL,
    sample_name TEXT NOT NULL,
    trigger_type TEXT NOT NULL,
    key_switch_note INTEGER,
    description TEXT,
    FOREIGN KEY (profile_id) REFERENCES rx_profiles(id)
);

-- Key Zones Table
CREATE TABLE IF NOT EXISTS key_zones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL,
    min_key INTEGER NOT NULL,
    max_key INTEGER NOT NULL,
    velocity_switch_low TEXT,
    velocity_switch_high TEXT,
    noise_trigger TEXT,
    FOREIGN KEY (profile_id) REFERENCES rx_profiles(id)
);

-- Special Rules Table
CREATE TABLE IF NOT EXISTS special_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL,
    rule_key TEXT NOT NULL,
    rule_value TEXT NOT NULL,
    FOREIGN KEY (profile_id) REFERENCES rx_profiles(id)
);

INSERT INTO rx_profiles (sound_name, rx_type, bank_msb, bank_lsb, program, version, resource_version, hardware_confirmed, confidence_score) VALUES ('Finger Bass RX', 'finger_bass', 0, 0, 32, '1.0.0', 'Pa800_OS_v1.0', false, 0.85);
INSERT INTO rx_profiles (sound_name, rx_type, bank_msb, bank_lsb, program, version, resource_version, hardware_confirmed, confidence_score) VALUES ('Picked Bass RX', 'picked_bass', 0, 0, 33, '1.0.0', 'Pa800_OS_v1.0', false, 0.8);
INSERT INTO rx_profiles (sound_name, rx_type, bank_msb, bank_lsb, program, version, resource_version, hardware_confirmed, confidence_score) VALUES ('Slap Bass RX', 'slap_bass', 0, 0, 34, '1.0.0', 'Pa800_OS_v1.0', false, 0.78);
INSERT INTO rx_profiles (sound_name, rx_type, bank_msb, bank_lsb, program, version, resource_version, hardware_confirmed, confidence_score) VALUES ('Clean Guitar RX', 'clean_guitar', 0, 0, 25, '1.0.0', 'Pa800_OS_v1.0', false, 0.82);
INSERT INTO rx_profiles (sound_name, rx_type, bank_msb, bank_lsb, program, version, resource_version, hardware_confirmed, confidence_score) VALUES ('Dist Guitar RX', 'dist_guitar', 0, 0, 30, '1.0.0', 'Pa800_OS_v1.0', false, 0.79);
INSERT INTO rx_profiles (sound_name, rx_type, bank_msb, bank_lsb, program, version, resource_version, hardware_confirmed, confidence_score) VALUES ('PowerChord RX', 'power_chord', 0, 0, 31, '1.0.0', 'Pa800_OS_v1.0', false, 0.88);
INSERT INTO rx_profiles (sound_name, rx_type, bank_msb, bank_lsb, program, version, resource_version, hardware_confirmed, confidence_score) VALUES ('Pop Std. Kit RX', 'pop_drum_kit', 120, 0, 0, '1.0.0', 'Pa800_OS_v1.0', false, 0.9);