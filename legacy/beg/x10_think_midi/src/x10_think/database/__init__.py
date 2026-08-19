"""
Database Module

SQLite-based persistent storage for:
- Projects
- MIDI analysis results
- Track metadata
- Instrument profiles
- RX rule sets
- Velocity models
- Expression profiles
- Harmony analysis data
- Humanization rules
- Optimization history
- Application settings
"""

from typing import Optional, Dict, Any, List
from pathlib import Path
import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Database management class for X10 Think.
    
    Handles all database operations including schema creation,
    CRUD operations, and connection management.
    """
    
    def __init__(self, db_path: str) -> None:
        """
        Initialize the database manager.
        
        Args:
            db_path: Path to the SQLite database file.
        """
        self._db_path = db_path
        self._connection: Optional[sqlite3.Connection] = None
        logger.debug(f"DatabaseManager initialized with path: {db_path}")
    
    def initialize(self) -> bool:
        """
        Initialize the database and create tables if needed.
        
        Returns:
            True if initialization was successful, False otherwise.
        """
        try:
            self._connect()
            self._create_tables()
            logger.info("Database initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Database initialization failed: {e}", exc_info=True)
            return False
    
    def close(self) -> None:
        """Close the database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.debug("Database connection closed")
    
    def _connect(self) -> None:
        """Establish database connection."""
        self._connection = sqlite3.connect(self._db_path)
        self._connection.row_factory = sqlite3.Row
        logger.debug("Database connection established")
    
    def _create_tables(self) -> None:
        """Create all required database tables."""
        cursor = self._connection.cursor()
        
        # Projects table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                midi_file_path TEXT,
                status TEXT DEFAULT 'active'
            )
        ''')
        
        # Tracks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                track_index INTEGER NOT NULL,
                name TEXT,
                role TEXT,
                program INTEGER,
                channel INTEGER,
                FOREIGN KEY (project_id) REFERENCES projects(id),
                UNIQUE(project_id, track_index)
            )
        ''')
        
        # Analysis results table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS analysis_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                analysis_type TEXT NOT NULL,
                data JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            )
        ''')
        
        # Instrument profiles table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS instrument_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                program_number INTEGER,
                velocity_profile JSON,
                expression_profile JSON,
                articulation_rules JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # RX rules table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rx_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT,
                rule_data JSON NOT NULL,
                enabled BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Humanization rules table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS humanization_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                instrument_type TEXT,
                rule_data JSON NOT NULL,
                enabled BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Processing history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS processing_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                input_file TEXT,
                output_file TEXT,
                processing_time_ms REAL,
                success BOOLEAN,
                errors TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            )
        ''')
        
        # Application settings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create indexes for performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tracks_project ON tracks(project_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_analysis_project ON analysis_results(project_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_history_project ON processing_history(project_id)')
        
        self._connection.commit()
        logger.debug("Database tables created successfully")
    
    # Project operations
    def create_project(self, name: str, midi_file_path: Optional[str] = None) -> int:
        """Create a new project."""
        cursor = self._connection.cursor()
        cursor.execute(
            'INSERT INTO projects (name, midi_file_path) VALUES (?, ?)',
            (name, midi_file_path)
        )
        self._connection.commit()
        project_id = cursor.lastrowid
        logger.info(f"Created project: {name} (ID: {project_id})")
        return project_id
    
    def get_project(self, project_id: int) -> Optional[Dict]:
        """Get a project by ID."""
        cursor = self._connection.cursor()
        cursor.execute('SELECT * FROM projects WHERE id = ?', (project_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def list_projects(self) -> List[Dict]:
        """List all projects."""
        cursor = self._connection.cursor()
        cursor.execute('SELECT * FROM projects ORDER BY updated_at DESC')
        return [dict(row) for row in cursor.fetchall()]
    
    def update_project(self, project_id: int, **kwargs) -> bool:
        """Update a project."""
        if not kwargs:
            return False
        
        set_clause = ', '.join(f"{k} = ?" for k in kwargs.keys())
        values = list(kwargs.values()) + [project_id]
        
        cursor = self._connection.cursor()
        cursor.execute(
            f'UPDATE projects SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            values
        )
        self._connection.commit()
        return cursor.rowcount > 0
    
    # Track operations
    def add_track(self, project_id: int, track_index: int, 
                 name: str = "", role: str = "", 
                 program: int = 0, channel: int = 0) -> int:
        """Add a track to a project."""
        cursor = self._connection.cursor()
        cursor.execute('''
            INSERT INTO tracks (project_id, track_index, name, role, program, channel)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (project_id, track_index, name, role, program, channel))
        self._connection.commit()
        return cursor.lastrowid
    
    def get_tracks(self, project_id: int) -> List[Dict]:
        """Get all tracks for a project."""
        cursor = self._connection.cursor()
        cursor.execute(
            'SELECT * FROM tracks WHERE project_id = ? ORDER BY track_index',
            (project_id,)
        )
        return [dict(row) for row in cursor.fetchall()]
    
    # Settings operations
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get an application setting."""
        cursor = self._connection.cursor()
        cursor.execute('SELECT value FROM app_settings WHERE key = ?', (key,))
        row = cursor.fetchone()
        return row['value'] if row else default
    
    def set_setting(self, key: str, value: str) -> bool:
        """Set an application setting."""
        cursor = self._connection.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO app_settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        ''', (key, value))
        self._connection.commit()
        return True
    
    # Analysis operations
    def save_analysis(self, project_id: int, analysis_type: str, 
                     data: Dict) -> int:
        """Save analysis results."""
        import json
        cursor = self._connection.cursor()
        cursor.execute('''
            INSERT INTO analysis_results (project_id, analysis_type, data)
            VALUES (?, ?, ?)
        ''', (project_id, analysis_type, json.dumps(data)))
        self._connection.commit()
        return cursor.lastrowid
    
    def get_analysis(self, project_id: int, 
                    analysis_type: str) -> Optional[Dict]:
        """Get analysis results."""
        import json
        cursor = self._connection.cursor()
        cursor.execute('''
            SELECT data FROM analysis_results 
            WHERE project_id = ? AND analysis_type = ?
            ORDER BY created_at DESC LIMIT 1
        ''', (project_id, analysis_type))
        row = cursor.fetchone()
        if row:
            return json.loads(row['data'])
        return None
    
    def log_processing(self, project_id: Optional[int], input_file: str,
                      output_file: Optional[str], processing_time_ms: float,
                      success: bool, errors: Optional[str] = None) -> int:
        """Log a processing operation."""
        cursor = self._connection.cursor()
        cursor.execute('''
            INSERT INTO processing_history 
            (project_id, input_file, output_file, processing_time_ms, success, errors)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (project_id, input_file, output_file, processing_time_ms, success, errors))
        self._connection.commit()
        return cursor.lastrowid
