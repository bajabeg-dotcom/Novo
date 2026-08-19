# X10 Think - Python MIDI Intelligence Engine

[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Code Style](https://img.shields.io/badge/code%20style-black-black.svg)](https://github.com/psf/black)

A **professional-grade Python desktop application** that intelligently analyzes and enhances Standard MIDI Files using deterministic musical rules, music theory principles, and instrument-specific performance logic.

## Key Features

### 🎵 Core Capabilities

- **Comprehensive MIDI Analysis** - Full parsing of all MIDI events including notes, CC, program changes, pitch bend, aftertouch, SysEx, and meta events
- **Intelligent Track Classification** - Automatic classification of tracks into 20+ musical roles (Melody, Bass, Drums, Guitar, Strings, etc.)
- **Harmonic Analysis** - Key detection, chord recognition, progression analysis, cadence detection, and tension mapping
- **Rule-Based Articulation System (RX)** - Instrument-specific articulations for realistic performance modeling
- **Deterministic Humanization** - Realistic performance variations without any randomness - all derived from musical context

### 🎹 Instrument-Specific Processing

| Instrument | Articulations |
|------------|---------------|
| Piano | Legato, Staccato, Accent, Pedal simulation, Velocity shaping |
| Guitar | Downstroke/Upstroke, Fingerpicking, Palm muting, Slides, Hammer-ons |
| Bass | Fingerstyle, Pick style, Slap/Pop, Ghost notes, Dead notes |
| Drums | Ghost notes, Hi-hat patterns, Fills, Flams, Rolls |
| Strings | Legato, Marcato, Spiccato, Tremolo, Pizzicato |
| Brass | Falls, Doits, Shakes, Swells, Punch dynamics |
| Winds | Breath modeling, Legato phrasing, Tongue attacks |

### 🔧 Technical Highlights

- **100% Rule-Based** - No neural networks, machine learning, or AI training required
- **Fully Deterministic** - All transformations are explainable and reproducible
- **DAW-Compatible Export** - Standard MIDI files that work in any DAW
- **Extensible Plugin Architecture** - Add custom rules and processing modules
- **SQLite Database** - Persistent storage for projects, analysis results, and settings
- **Professional GUI** - PyQt6-based interface with dark mode support

## Installation

### From Source

```bash
git clone https://github.com/x10think/x10-think-midi.git
cd x10-think-midi
pip install -e .
```

### With GUI Support

```bash
pip install -e ".[gui]"
```

### Development Mode

```bash
pip install -e ".[dev]"
```

## Quick Start

### Command Line Interface

```bash
# Process a MIDI file
x10-think process input.mid output.mid

# Analyze a MIDI file
x10-think analyze input.mid

# Run in interactive mode
x10-think
```

### Python API

```python
from x10_think import Application

# Initialize the application
app = Application()
app.initialize()

# Process a MIDI file
result = app.engine_coordinator.process_midi_file(
    input_path="input.mid",
    output_path="output.mid"
)

if result.success:
    print(f"Processed in {result.processing_time_ms:.2f}ms")
    print(f"Analysis: {result.analysis_data}")

# Cleanup
app.shutdown()
```

### GUI Mode

```bash
x10-think --gui
```

Or programmatically:

```python
from x10_think import Application

app = Application()
app.initialize()
app.run(gui_mode=True)
```

## Architecture

```
x10_think/
├── core/               # Core application components
│   ├── application.py  # Main application class
│   ├── engine.py       # Engine coordinator
│   ├── config_manager.py
│   └── event_bus.py
├── engines/            # Processing engines
│   ├── parser/         # MIDI parsing and export
│   ├── track_intelligence/  # Track classification
│   ├── rx/             # Articulation rules
│   ├── humanization/   # Performance humanization
│   ├── harmony/        # Harmonic analysis
│   ├── expression/     # Controller automation
│   ├── velocity/       # Velocity shaping
│   └── musical_rules/  # Rule validation
├── gui/                # User interface
│   └── main_window.py
├── database/           # SQLite persistence
│   └── __init__.py
├── utils/              # Utility functions
│   ├── midi_utils.py
│   └── music_theory.py
└── plugins/            # Extension point
    └── __init__.py
```

## Engine Pipeline

The MIDI processing pipeline follows this sequence:

1. **Parser Engine** - Extract all MIDI events
2. **Track Intelligence** - Classify each track's role
3. **Harmony Engine** - Analyze key, chords, progressions
4. **RX Engine** - Apply instrument-specific articulations
5. **Velocity Engine** - Shape velocities per instrument
6. **Expression Engine** - Add controller automation
7. **Humanization Engine** - Apply realistic variations
8. **Musical Rules Engine** - Validate against musical rules

## Configuration

Configuration is managed via YAML:

```yaml
# config.yaml
app_name: "X10 Think MIDI Intelligence Engine"
debug_mode: false

# Engine configurations
parser_engine:
  enabled: true
  strict_mode: false

rx_engine:
  enabled: true
  parameters:
    apply_piano_articulations: true
    apply_guitar_articulations: true

humanization_engine:
  enabled: true
  parameters:
    timing_variation_ms: 10.0
    velocity_variation: 5
```

## Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=x10_think

# Run specific test module
pytest tests/unit/test_parser.py
```

## Documentation

Full documentation is available at [https://x10think.github.io/docs](https://x10think.github.io/docs)

```bash
# Build documentation locally
cd docs
make html
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please read our [Contributing Guidelines](CONTRIBUTING.md) first.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Acknowledgments

- Built on deterministic music theory principles
- Inspired by professional arranger workstation behavior
- Designed for musicians, by musicians

---

**X10 Think** - Intelligent MIDI Processing Without AI
