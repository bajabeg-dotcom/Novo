# 🎹 KORG PA800 MIDI Optimizer — Windows Batch Files Guide

**For Windows Users — Easy Setup & Usage**

---

## 📦 What's Included

After installation, you'll have these convenient batch files:

### Setup & Configuration
- **`install.bat`** — Installation & setup wizard
- **`run.bat`** — Launch GUI application

### MIDI Processing
- **`optimize.bat`** — Optimize single MIDI file
- **`analyze.bat`** — Analyze MIDI file structure
- **`batch_process.bat`** — Process entire directories

---

## 🚀 Quick Start (Windows)

### Step 1: Installation

```bash
1. Extract all files to a folder
2. Double-click: install.bat
3. Follow the wizard
```

The installer will:
- ✅ Check Python installation
- ✅ Verify all required files
- ✅ Check tkinter (for GUI)
- ✅ Create desktop shortcut (optional)

### Step 2: Run Application

**Option A: GUI (Easiest)**
```bash
Double-click: run.bat
```

**Option B: Command Line**
```bash
Double-click: optimize.bat
Drag MIDI file onto it
Or type: optimize.bat C:\path\to\file.mid
```

---

## 📋 Detailed Usage

### `install.bat` — Setup Wizard

**What it does:**
1. Checks Python 3.7+ installation
2. Verifies all required files
3. Tests tkinter for GUI support
4. Optionally creates desktop shortcut

**How to use:**
```bash
1. Double-click install.bat
2. Follow on-screen instructions
3. Answer Y/N questions
4. Done!
```

**If it fails:**
- Python not installed → Install from python.org
- Files missing → Ensure all files in same folder
- tkinter error → Use CLI instead (optimize.bat works fine)

---

### `run.bat` — Launch GUI

**What it does:**
- Launches desktop GUI application
- Drag & drop MIDI files
- Select optimization strategy
- Process files with visual feedback

**How to use:**
```bash
Double-click: run.bat
OR
Right-click on desktop shortcut (if created)
```

**If GUI doesn't start:**
```bash
1. Check Python: python --version (should be 3.7+)
2. Try from Command Prompt:
   cd C:\path\to\optimizer
   python midi_optimizer_gui.py
```

---

### `optimize.bat` — Optimize Single File

**What it does:**
- Optimizes one MIDI file
- Creates optimized output file
- Shows detailed results

**How to use:**

**Method 1: Drag & Drop**
```
1. Double-click optimize.bat (or leave open)
2. Drag MIDI file onto window
3. Choose output filename
4. Done!
```

**Method 2: Command Line**
```bash
optimize.bat C:\Music\song.mid
optimize.bat C:\Music\song.mid C:\Music\song_opt.mid
optimize.bat C:\Music\song.mid C:\Music\song_opt.mid EXPRESSIVE
```

**Method 3: File Explorer**
```
1. Right-click MIDI file
2. Send to → optimize.bat
3. File optimized in same folder
```

**Arguments:**
```
optimize.bat <input.mid> [output.mid] [strategy]

input.mid    - Required: MIDI file to optimize
output.mid   - Optional: Where to save (default: input_optimized.mid)
strategy     - Optional: AUTHENTIC/EXPRESSIVE/BALANCED/AGGRESSIVE
               (default: AUTHENTIC)
```

**Examples:**
```bash
optimize.bat song.mid
→ Creates: song_optimized.mid

optimize.bat song.mid song_KORG.mid
→ Creates: song_KORG.mid

optimize.bat song.mid song_exp.mid EXPRESSIVE
→ Creates: song_exp.mid with expressive strategy

optimize.bat "C:\My Music\track.mid" "C:\Output\track_opt.mid"
→ Full paths work too
```

---

### `analyze.bat` — Analyze MIDI File

**What it does:**
- Examines MIDI structure
- Shows program/sound usage
- Displays velocity ranges
- Detects register distribution
- Helps understand what optimization will do

**How to use:**

**Method 1: Drag & Drop**
```
1. Double-click analyze.bat
2. Drag MIDI file onto window
3. Analyze completes automatically
```

**Method 2: Command Line**
```bash
analyze.bat C:\Music\song.mid
```

**What you'll see:**
```
File: song.mid
Total notes: 2,847
Programs used: 5

Program Details:
  Prog  25:  847 notes, Vel  50- 127  (Drums)
  Prog  34:  564 notes, Vel  60- 120  (Bass)
  ...

Register Distribution:
  Low:   185 (6.5%)
  Mid:  2,389 (83.9%)
  High:  273 (9.6%)
```

**Use before optimizing to:**
- Understand current velocity distribution
- Choose best strategy
- Predict optimization impact

---

### `batch_process.bat` — Optimize Directory

**What it does:**
- Processes all MIDI files in a folder
- Creates output folder with optimized files
- Shows progress for each file
- Detailed summary at end

**How to use:**

**Method 1: Interactive (Easiest)**
```bash
1. Double-click batch_process.bat
2. Answer prompts for folders & strategy
3. Confirm to start processing
4. Done!
```

**Method 2: Command Line**
```bash
batch_process.bat C:\Music\MIDI C:\Music\Optimized AUTHENTIC

Arguments:
  [input_folder]   - Folder with MIDI files (default: current folder)
  [output_folder]  - Where to save (default: input\optimized)
  [strategy]       - AUTHENTIC/EXPRESSIVE/BALANCED/AGGRESSIVE
                    (default: AUTHENTIC)
```

**Examples:**
```bash
batch_process.bat
→ Uses current folder, creates \optimized subfolder

batch_process.bat C:\Music
→ Processes C:\Music\*.mid, outputs to C:\Music\optimized

batch_process.bat C:\Music C:\Optimized EXPRESSIVE
→ Processes C:\Music, outputs to C:\Optimized with EXPRESSIVE strategy
```

**What happens:**
```
1. Scans folder for all .mid files
2. Shows count of files found
3. Asks for confirmation
4. Processes each file
5. Shows detailed progress
6. Displays summary with success/failures
```

---

## 🎯 Optimization Strategies

All batch files support these strategies:

### `AUTHENTIC` (Default)
- Match factory patterns exactly
- Best for: Professional work, reference
- **Use this if unsure**

### `EXPRESSIVE`
- Emphasize dynamics
- Best for: Emotional performances
- **Use this for more dramatic effect**

### `BALANCED`
- Conservative adjustments
- Best for: First-time optimization
- **Safe choice**

### `AGGRESSIVE`
- Maximize character
- Best for: Artistic interpretations
- **Bold adjustments**

---

## 💡 Common Workflows

### Workflow 1: Optimize Single Song

```bash
1. Double-click run.bat
   → GUI opens
2. Drag MIDI file into window
3. Select AUTHENTIC strategy
4. Click "Optimize MIDI"
5. Result saved automatically
```

### Workflow 2: Quick File Optimization

```bash
1. Double-click optimize.bat
2. Drag song.mid onto it
3. Optimized file created in same folder
```

### Workflow 3: Batch Process Collection

```bash
1. Place all MIDI files in C:\Music\MyCollection
2. Double-click batch_process.bat
3. Set input to C:\Music\MyCollection
4. Set output to C:\Music\MyCollection\Optimized
5. Choose AUTHENTIC strategy
6. Confirm and wait
7. All files optimized!
```

### Workflow 4: Analyze Before Optimizing

```bash
1. Double-click analyze.bat
2. Drag song.mid onto it
3. Review analysis results
4. Decide on best strategy
5. Use optimize.bat with chosen strategy
```

### Workflow 5: Compare Strategies

```bash
1. Analyze file: analyze.bat song.mid
2. Optimize with AUTHENTIC: optimize.bat song.mid song_auth.mid AUTHENTIC
3. Optimize with EXPRESSIVE: optimize.bat song.mid song_exp.mid EXPRESSIVE
4. Load both into DAW
5. Compare and choose
```

---

## 🔧 Troubleshooting

### Problem: "Python not found"
**Solution:**
1. Install Python from python.org
2. Run installer again and CHECK "Add Python to PATH"
3. Restart computer
4. Try again

### Problem: "ai_database.json not found"
**Solution:**
1. Ensure file is in same folder as batch files
2. Check filename is exact (case-sensitive on some systems)
3. Download file again if corrupted

### Problem: GUI won't launch
**Solution:**
1. Try from command line first:
   ```bash
   python midi_optimizer_gui.py
   ```
2. If error, use CLI instead:
   ```bash
   optimize.bat file.mid
   ```

### Problem: No velocity changes (0% adjusted)
**Solution:**
1. Analyze file first: `analyze.bat file.mid`
2. Check current velocity distribution
3. Try different strategy (EXPRESSIVE or AGGRESSIVE)
4. File may already be optimized

### Problem: File won't optimize
**Solution:**
1. Verify MIDI file is valid:
   ```bash
   analyze.bat problematic_file.mid
   ```
2. Check file isn't read-only (right-click → Properties)
3. Try with different output filename
4. Check disk space

### Problem: Very slow processing
**Solution:**
1. Close other applications
2. Check disk space
3. Process smaller batches
4. Run overnight for large batches

---

## 📊 Performance Tips

**For best results:**
1. Analyze first → understand structure
2. Start with AUTHENTIC strategy
3. Try different strategies → compare results
4. Use BALANCED if unsure

**For large libraries:**
1. Use batch_process.bat
2. Start with small batch (10 files)
3. Review results
4. Process full library when satisfied
5. Process overnight if needed (script runs unattended)

---

## 🎓 Learning Path

**Day 1: Basic Usage**
1. Run install.bat
2. Double-click run.bat
3. Drag test MIDI file
4. Try AUTHENTIC strategy
5. Review result

**Day 2: Exploration**
1. Use analyze.bat on various files
2. Try different strategies
3. Compare before/after
4. Understand what optimization does

**Day 3: Integration**
1. Use optimize.bat for single files
2. Use batch_process.bat for collections
3. Integrate into workflow
4. Share optimized results

**Advanced: CLI Integration**
1. Read MIDI_OPTIMIZER_GUIDE.md
2. Use Python API for custom workflows
3. Build batch processing scripts
4. Integrate with other tools

---

## 📝 Important Notes

### File Safety
- ✅ Original MIDI files **never modified**
- ✅ Always creates new output file
- ✅ Safe to batch process entire libraries
- ✅ Can delete output if unsatisfied

### Compatibility
- ✅ Works with all MIDI 1.0 files
- ✅ Works with all DAWs (Ableton, Logic, Cubase, FL Studio, etc.)
- ✅ Preserves all MIDI data (notes, timing, CC, tempo)
- ✅ Modifies only velocity values

### Performance
| File Size | Processing Time |
|-----------|-----------------|
| 1,000 notes | < 1 second |
| 10,000 notes | 2-3 seconds |
| 100,000 notes | 15-20 seconds |

### Batch Limits
- Single batch: process 100+ files at once
- Total size: limited only by disk space
- No memory limits (streams files)
- Can run overnight

---

## 🎁 Shortcuts & Tips

### Create Desktop Shortcuts (Manually)

**For optimize.bat:**
1. Right-click optimize.bat
2. Send to → Desktop (create shortcut)
3. Right-click shortcut → Properties
4. Target: `C:\path\to\optimize.bat`
5. Done!

**For run.bat:**
1. Right-click run.bat
2. Send to → Desktop (create shortcut)
3. Name it: "KORG MIDI Optimizer"
4. Done!

### Windows Explorer Integration

**Add to context menu:**
1. Right-click optimize.bat
2. Send to → Desktop (create shortcut)
3. Right-click shortcut → Copy
4. Navigate to: `C:\Users\USERNAME\AppData\Roaming\Microsoft\Windows\SendTo`
5. Paste shortcut there
6. Now you can right-click MIDI files → Send to → optimize.bat

---

## 📞 Getting Help

**If something doesn't work:**

1. **Check basic requirements:**
   ```bash
   python --version           # Should be 3.7+
   python -m tkinter          # Should open window
   ```

2. **Verify all files present:**
   - midi_optimizer_core.py ✓
   - midi_optimizer_gui.py ✓
   - midi_optimizer_cli.py ✓
   - ai_database.json ✓

3. **Try command line:**
   ```bash
   python midi_optimizer_cli.py analyze test.mid
   ```

4. **Read documentation:**
   - MIDI_OPTIMIZER_README.md — Quick start
   - MIDI_OPTIMIZER_GUIDE.md — Complete guide
   - SOUND_BEHAVIOUR_ANALYSIS.md — Technical details

---

## 🚀 You're Ready!

**Start with:**
```bash
Double-click: install.bat
Then: run.bat
```

Everything is set up for Windows.

**Questions?**
Read MIDI_OPTIMIZER_GUIDE.md for complete documentation.

---

**🎹 KORG PA800 MIDI Optimizer — Windows Edition**

*Transform your MIDI with factory-authentic dynamics*
