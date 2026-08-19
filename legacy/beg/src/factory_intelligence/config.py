"""
KORG PA800 Factory Intelligence - Configuration

Central configuration for the Factory Intelligence system.
"""

from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "factory"
CANONICAL_FACTORY_DIR = DATA_DIR / "Factory Styles"
REPORTS_DIR = BASE_DIR / "reports"

# Expected dataset properties
EXPECTED_STYLE_COUNT = 252
MIDI_EXTENSIONS = {".mid", ".MID"}

# Analysis constants
DEFAULT_TICKS_PER_BEAT = 480  # Common PPQN value
VELOCITY_HISTOGRAM_BUCKETS = 10  # 0-12, 13-25, ..., 115-127
DURATION_HISTOGRAM_BUCKETS = 10

# Important CC numbers to track explicitly
IMPORTANT_CC_NUMBERS = [
    0,    # Bank Select MSB
    6,    # Data Entry MSB
    32,   # Bank Select LSB
    38,   # Data Entry LSB
    64,   # Damper Pedal
    65,   # Portamento
    98,   # NRPN LSB
    99,   # NRPN MSB
    100,  # RPN LSB
    101,  # RPN MSB
    120,  # All Sound Off
    121,  # Reset All Controllers
    123,  # All Notes Off
]

# KORG SysEx manufacturer ID
KORG_MANUFACTURER_ID = bytes([0x42])

# Track role detection thresholds
DRUM_CHANNEL = 9  # MIDI channel 10 (0-indexed)
BASS_NOTE_THRESHOLD = 48  # C3 - notes below this are likely bass
LOW_NOTE_THRESHOLD = 36  # C2 - very low notes
HIGH_NOTE_THRESHOLD = 84  # C6 - very high notes

# Pattern detection parameters
MIN_PATTERN_LENGTH_TICKS = 480  # Minimum 1 beat
MAX_PATTERN_LENGTH_TICKS = 15360  # Maximum ~8 bars at 480 PPQN
PATTERN_REPETITION_THRESHOLD = 0.7  # 70% similarity for pattern matching

# Section detection parameters
MIN_SECTION_LENGTH_TICKS = 1920  # Minimum 1 bar at 480 PPQN
SECTION_GAP_THRESHOLD_TICKS = 960  # Gap indicating section boundary

# Report settings
JSON_INDENT = 2
INCLUDE_RAW_EVENTS = False  # Set True for debugging, False for production
