# 🎹 KORG PA800 MIDI Optimizer

**Turn ordinary MIDI into authentic KORG PA800 performances.**

## Overview

MIDI Optimizer enhances your MIDI files using intelligent velocity adjustments based on **real factory KORG PA800 sound analysis**.

Instead of generic MIDI, get velocity curves and dynamics that match how KORG sounds are actually used in professional compositions.

### Key Features

✅ **Smart Velocity Optimization** — Uses 107 KORG sound behaviour models  
✅ **Multiple Strategies** — Authentic, Expressive, Balanced, or Aggressive  
✅ **Batch Processing** — Optimize entire music libraries at once  
✅ **Detailed Analysis** — Understand your MIDI structure  
✅ **No Dependencies** — Pure Python, works everywhere  

---

## Quick Start

### Desktop Application (5 seconds)

```bash
python midi_optimizer_gui.py
```

![GUI Screenshot]
1. Drag MIDI file into window
2. Choose strategy
3. Click "Optimize"
4. Done!

### Command Line (Developers)

```bash
# Single file
python midi_optimizer_cli.py optimize input.mid output.mid

# Analyze
python midi_optimizer_cli.py analyze input.mid

# Batch process
python midi_optimizer_cli.py batch /input /output
```

### Python API (Integration)

```python
from midi_optimizer_core import MIDIOptimizerApp, OptimizationStrategy

app = MIDIOptimizerApp()
app.optimize_file("input.mid", "output.mid", OptimizationStrategy.AUTHENTIC)
```

---

## Optimization Strategies

### 🎯 **AUTHENTIC** (Default)
Match factory patterns exactly.  
**Best for:** Professional productions, reference material

### 🎨 **EXPRESSIVE**
Emphasize dynamics for more emotional performances.  
**Best for:** Melodic passages, emotional songs

### ⚖️ **BALANCED**
Conservative adjustments, preserves original intent.  
**Best for:** Safe, first-time optimization

### 💪 **AGGRESSIVE**
Maximize sound character with bold adjustments.  
**Best for:** Artistic interpretations, special effects

---

## What It Does

### Before
```
Velocity:  65   65   65   70   65   68   65   65
Character: flat flat flat flat flat flat flat flat
```

### After (AUTHENTIC)
```
Velocity:  75   78   72   85   74   82   76   79
Character: natural dynamics matching factory patterns
```

---

## How It Works

1. **Analyzes** your MIDI file structure
2. **Identifies** which KORG sounds (programs) are used
3. **Queries** Sound Behaviour Models for each program
4. **Optimizes** velocities to match factory patterns
5. **Preserves** notes, timing, and musicality

**Result:** Authentic KORG PA800 dynamics in your MIDI.

---

## System Requirements

- **Python:** 3.7+
- **OS:** Windows, macOS, Linux
- **RAM:** 100 MB minimum
- **Disk:** 500 MB for files
- **Dependencies:** None! (Pure Python)

## Installation

1. Download/clone repository
2. Ensure `ai_database.json` is present
3. Run application:

```bash
# Desktop
python midi_optimizer_gui.py

# Command line
python midi_optimizer_cli.py --help
```

---

## Documentation

See **`MIDI_OPTIMIZER_GUIDE.md`** for complete documentation including:
- Detailed strategy explanations
- Real-world usage examples
- Integration workflows
- Troubleshooting guide
- Advanced techniques

---

## Technical Details

### Sound Behaviour Models
- Based on analysis of 3,211 factory MIDI files
- 107 unique KORG sounds characterized
- 508,504 note events analyzed
- **Confidence:** OBSERVED (from real factory data)

### Optimization Engine
- Intelligent velocity clustering
- Pitch-aware velocity adjustment
- Duration-aware dynamics
- Role-based playing styles

### Performance
- **Small files** (< 1,000 notes): < 1 second
- **Medium files** (< 10,000 notes): 2-3 seconds  
- **Large files** (< 100,000 notes): 15-20 seconds
- **Memory:** Efficient streaming, no limits

---

## Examples

### Example 1: Optimize Single File
```bash
python midi_optimizer_cli.py optimize song.mid song_optimized.mid --strategy AUTHENTIC
```

### Example 2: Batch Process Directory
```bash
python midi_optimizer_cli.py batch ~/music/midi ~/music/optimized
```

### Example 3: Analyze MIDI Structure
```bash
python midi_optimizer_cli.py analyze song.mid
```

Output shows:
- Total notes and programs used
- Velocity ranges per program
- Register distribution
- Optimization opportunities

---

## Files Included

### Core Application
- `midi_optimizer_core.py` — Main optimization engine
- `midi_optimizer_gui.py` — Desktop GUI application
- `midi_optimizer_cli.py` — Command-line interface

### Data & Models
- `ai_database.json` — Sound Behaviour Models (required)
- `phase1_usage_fingerprints.json` — Sound usage patterns
- `phase2_velocity_behaviour.json` — Velocity analysis

### Documentation
- `MIDI_OPTIMIZER_GUIDE.md` — Complete user guide
- `MIDI_OPTIMIZER_README.md` — This file
- `SOUND_BEHAVIOUR_ANALYSIS.md` — Technical details

---

## Use Cases

### 🎵 **Music Production**
Enhance MIDI tracks with authentic KORG dynamics.

### 🎓 **Education**
Learn how professional composers structure velocity.

### 🤖 **AI/ML**
Use as foundation for MIDI generation models.

### 📊 **Research**
Analyze KORG PA800 usage patterns.

### 🎼 **Arrangement**
Create realistic MIDI based on factory patterns.

---

## FAQ

**Q: Does it change my original file?**  
A: No. Always creates new output file. Original untouched.

**Q: What MIDI versions does it support?**  
A: MIDI 1.0, all formats and tempos.

**Q: Can I use it commercially?**  
A: Yes! No restrictions on commercial use.

**Q: Does it work with all DAWs?**  
A: Yes. Standard MIDI format works everywhere.

**Q: Can I undo optimization?**  
A: Keep original file. Output is new file anyway.

---

## Performance Tips

### For Best Results:
1. Use AUTHENTIC strategy for reference
2. Analyze file first to understand structure
3. Start with BALANCED if unsure
4. Experiment with strategies
5. Compare before/after

### For Large Collections:
1. Use batch processing
2. Process overnight if needed
3. Monitor disk space
4. Keep originals as backup

---

## Troubleshooting

### File won't open
```bash
# Try analyzing first
python midi_optimizer_cli.py analyze problem.mid
```

### No velocity changes
- MIDI already matches patterns (good!)
- Try EXPRESSIVE or AGGRESSIVE strategy
- Check velocity range with analyze

### Out of memory
- Process smaller batches
- Close other applications
- Increase system RAM if recurring

---

## Contributing

Found a bug? Have suggestions? Want to contribute?

1. Test the application
2. Document issues clearly
3. Suggest improvements
4. Share results!

---

## Version History

### 1.0 (August 6, 2026)
- Initial release
- Three interfaces (GUI, CLI, API)
- Four optimization strategies
- Batch processing support
- Complete documentation

---

## License

**Free for all uses** — Personal, educational, commercial.

Based on KORG PA800 factory analysis. No proprietary KORG data used.

---

## About

Built using **Sound Behaviour Intelligence** extracted from forensic analysis of KORG PA800 factory styles and patterns.

**Not reconstructing KORG sounds.** Using observed factory MIDI patterns to optimize your compositions.

---

## Next Steps

1. **Install:** Download application files
2. **Try:** Run GUI or analyze a MIDI file
3. **Explore:** Test different strategies
4. **Integrate:** Add to your workflow
5. **Share:** Show us your results!

---

## Support

- **Documentation:** See MIDI_OPTIMIZER_GUIDE.md
- **Technical:** See SOUND_BEHAVIOUR_ANALYSIS.md
- **Issues:** Test with analyze command first

---

**Ready to make your MIDI sound like factory?**

```bash
python midi_optimizer_gui.py
```

🎹 **KORG PA800 MIDI Optimizer — Version 1.0**

