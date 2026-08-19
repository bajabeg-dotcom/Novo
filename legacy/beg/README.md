# KORG PA800 Factory Intelligence

Factory Style MIDI analysis layer for KORG PA800 arranger workstation.

## Purpose

This project extracts measurable structure, statistics, pattern behavior, timing, velocity, event and track DNA from the 252 KORG PA800 Factory Style MIDI files.

## Important Distinction

**Factory Style MIDI ≠ Song MIDI**

- Factory Style MIDI represents generative arranger material (pattern-based accompaniment)
- Song MIDI represents linear song performance
- Track roles in Factory Styles are NOT equivalent to song instruments
- Section detection is heuristic, not deterministic

## Dataset

- **Canonical Location**: `data/factory/Factory Styles/`
- **Expected Files**: 252 unique Factory Styles
- **Format**: Standard MIDI files (.mid)

## Architecture

```
src/factory_intelligence/
├── __init__.py          # Package initialization
├── config.py            # Configuration constants
├── discovery.py         # Dataset discovery and validation
├── midi_parser.py       # Raw MIDI parsing
├── event_analyzer.py    # Event-level analysis
├── track_analyzer.py    # Track role analysis
├── pattern_analyzer.py  # Pattern and section detection
├── statistics.py        # Aggregate statistics
├── fingerprints.py      # Style fingerprinting
├── models.py            # Data models
└── reporter.py          # Report generation
```

## Installation

```bash
pip install -e .
```

## Usage

```bash
python test_factory.py
pytest
```

## Reports

Generated reports are placed in `reports/`:
- `factory_dataset_report.json` - Raw + derived data
- `factory_dataset_summary.txt` - Human-readable summary

## Data Integrity

Original Factory MIDI files are **READ ONLY**. The program never:
- Overwrites
- Transposes
- Quantizes
- Humanizes
- Normalizes
- Renames
- Moves
- Modifies

All derived information goes to `reports/`.

## Terminology

- **OBSERVED**: Directly measured from MIDI data
- **DERIVED**: Calculated from observed data
- **HEURISTIC**: Inferred using rules (not guaranteed)
- **UNKNOWN**: Cannot be determined from available data

## Phase 1 Goals

1. [ ] Canonical dataset found
2. [ ] 252 Factory Styles found
3. [ ] 252/252 readable
4. [ ] No canonical duplicates
5. [ ] Raw MIDI events preserved
6. [ ] Track analysis complete
7. [ ] Note analysis complete
8. [ ] Velocity analysis complete
9. [ ] Timing analysis complete
10. [ ] CC analysis complete
11. [ ] Program Change analysis complete
12. [ ] SysEx analysis complete
13. [ ] Pattern analysis complete
14. [ ] Fingerprints generated
15. [ ] Global statistics generated
16. [ ] JSON report generated
17. [ ] Human-readable report generated
18. [ ] Unit tests pass
19. [ ] Integration tests pass
