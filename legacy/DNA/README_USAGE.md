# Song MIDI Optimizer - User Guide

## Overview
Professional MIDI optimization tool based on **Factory Styles** and **Gold Standards** principles.

## Features

### 🎵 IMPORT - OPTIMIZE - EXPORT Workflow

1. **IMPORT**: Load any MIDI file for analysis
2. **ANALYZE**: Comprehensive analysis with quality scoring
3. **OPTIMIZE**: Apply corpus-based optimization rules
4. **EXPORT**: Save optimized MIDI with metadata

### 📊 Three Optimization Corpora

#### Factory Styles (Standard)
- Professional factory-style optimization
- Velocity range: 40-127
- Quantize resolution: 480 ticks
- Focus: Consistency and playability

#### Gold Standards (Premium)
- Premium quality optimization
- Velocity range: 50-127
- Quantize resolution: 960 ticks (higher precision)
- Includes articulation and expression controls
- Focus: Expressive performance

#### Balanced (Recommended)
- Combines best of both corpora
- Factory reliability + Gold expressiveness
- Ideal for most use cases

### 🔍 Analysis Features
- Track-by-track statistics
- Velocity analysis (min/max/average)
- Note range detection
- Quality scoring (0-100)
- Issue detection:
  - Low velocity warnings
  - Missing dynamic variation
  - Empty tracks

### ⚙️ Optimization Rules

**Velocity Optimization:**
- Ensures minimum velocity thresholds
- Adds natural variation
- Applies accent boosts on beat positions
- Maintains maximum velocity limits

**Timing Optimization:**
- Quantization to grid
- Optional humanization
- Configurable resolution

**Duration Optimization:**
- Note length adjustments
- Rest threshold management

**Note Density:**
- Prevents overcrowding
- Manages simultaneous notes

## Installation

```bash
pip install mido pillow
apt-get install python3-tk  # For GUI
```

## Usage

### GUI Mode
```bash
python song_midi_optimizer.py
```

### Programmatic Usage
```python
from song_midi_optimizer import CorpusRules, MIDIAnalyzer, MIDIOptimizer
import mido

# Load MIDI file
midi_file = mido.MidiFile('input.mid')

# Analyze
analyzer = MIDIAnalyzer()
stats = analyzer.analyze(midi_file)
print(f"Quality Score: {stats['quality_score']}/100")

# Optimize
corpus = CorpusRules()
rules = corpus.get_combined_rules('balanced')  # or 'factory' or 'gold'
optimizer = MIDIOptimizer(rules)
optimized = optimizer.optimize(midi_file)

# Save
optimized.save('output_optimized.mid')
```

## GUI Tabs

### 📥 Import Tab
- Browse and select MIDI files
- Load and analyze files
- View recent files

### 🔍 Analysis Tab
- File statistics
- Track details
- Quality score display
- Detected issues list

### ⚙️ Optimization Tab
- Select corpus (Factory/Gold/Balanced)
- Configure optimization options
- Preview active rules
- Run optimization

### 📤 Export Tab
- Set output filename
- Choose MIDI format (Type 0/Type 1)
- Add metadata (title, artist, copyright)
- Export log

## Keyboard Shortcuts
- `Ctrl+I`: Import MIDI
- `Ctrl+R`: Run Optimization
- `Ctrl+E`: Export MIDI

## Requirements
- Python 3.8+
- mido (MIDI processing)
- tkinter (GUI)
- pillow (image support)

## License
Professional music production tool
