-- Hardware Probe Results Table
CREATE TABLE IF NOT EXISTS hardware_probes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    address TEXT UNIQUE NOT NULL,
    sound_name TEXT NOT NULL,
    bank_msb INTEGER NOT NULL,
    bank_lsb INTEGER NOT NULL,
    program INTEGER NOT NULL,
    description TEXT,
    hardware_confirmed BOOLEAN DEFAULT FALSE,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Probe Results Table
CREATE TABLE IF NOT EXISTS probe_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    probe_id INTEGER NOT NULL,
    actual_sound_name TEXT,
    os_version TEXT,
    resource_version TEXT,
    test_passed BOOLEAN NOT NULL,
    confidence_score REAL NOT NULL,
    timestamp TEXT NOT NULL,
    notes TEXT,
    FOREIGN KEY (probe_id) REFERENCES hardware_probes(id)
);

INSERT INTO hardware_probes (address, sound_name, bank_msb, bank_lsb, program, description, hardware_confirmed, status) VALUES ('00:00:20', 'Finger Bass', 0, 0, 32, 'Finger-style bass sound', true, 'hardware_confirmed');
INSERT INTO hardware_probes (address, sound_name, bank_msb, bank_lsb, program, description, hardware_confirmed, status) VALUES ('00:00:21', 'Picked Bass', 0, 0, 33, 'Picked bass sound', false, 'pending');
INSERT INTO hardware_probes (address, sound_name, bank_msb, bank_lsb, program, description, hardware_confirmed, status) VALUES ('00:00:22', 'Slap Bass', 0, 0, 34, 'Slap bass sound', false, 'pending');
INSERT INTO hardware_probes (address, sound_name, bank_msb, bank_lsb, program, description, hardware_confirmed, status) VALUES ('00:00:19', 'Clean Guitar', 0, 0, 25, 'Clean electric guitar', false, 'pending');
INSERT INTO hardware_probes (address, sound_name, bank_msb, bank_lsb, program, description, hardware_confirmed, status) VALUES ('00:00:1E', 'Dist Guitar', 0, 0, 30, 'Distortion guitar', false, 'pending');
INSERT INTO hardware_probes (address, sound_name, bank_msb, bank_lsb, program, description, hardware_confirmed, status) VALUES ('00:00:1F', 'PowerChord Guitar', 0, 0, 31, 'Power chord guitar', false, 'pending');
INSERT INTO hardware_probes (address, sound_name, bank_msb, bank_lsb, program, description, hardware_confirmed, status) VALUES ('78:00:00', 'Pop Std. Kit', 120, 0, 0, 'Standard pop drum kit', false, 'pending');
INSERT INTO hardware_probes (address, sound_name, bank_msb, bank_lsb, program, description, hardware_confirmed, status) VALUES ('00:00:00', 'Concert Grand', 0, 0, 0, 'Acoustic piano', false, 'pending');
INSERT INTO hardware_probes (address, sound_name, bank_msb, bank_lsb, program, description, hardware_confirmed, status) VALUES ('00:00:04', 'Electric Piano', 0, 0, 4, 'EP sound', false, 'pending');
INSERT INTO hardware_probes (address, sound_name, bank_msb, bank_lsb, program, description, hardware_confirmed, status) VALUES ('00:00:30', 'String Ensemble', 0, 0, 48, 'String ensemble', false, 'pending');
INSERT INTO hardware_probes (address, sound_name, bank_msb, bank_lsb, program, description, hardware_confirmed, status) VALUES ('00:00:38', 'Trumpet', 0, 0, 56, 'Trumpet', false, 'pending');
INSERT INTO hardware_probes (address, sound_name, bank_msb, bank_lsb, program, description, hardware_confirmed, status) VALUES ('00:00:41', 'Alto Sax', 0, 0, 65, 'Alto saxophone', false, 'pending');
INSERT INTO hardware_probes (address, sound_name, bank_msb, bank_lsb, program, description, hardware_confirmed, status) VALUES ('00:00:50', 'Lead Synth', 0, 0, 80, 'Synth lead', false, 'pending');
INSERT INTO hardware_probes (address, sound_name, bank_msb, bank_lsb, program, description, hardware_confirmed, status) VALUES ('00:00:58', 'Pad Synth', 0, 0, 88, 'Synth pad', false, 'pending');