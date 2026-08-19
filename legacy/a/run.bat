@echo off
REM ============================================================================
REM KORG PA800 MIDI Optimizer - Run GUI Application
REM ============================================================================
REM This script launches the MIDI Optimizer desktop application
REM

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Python is not installed or not in PATH
    echo.
    echo Please install Python from: https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

REM Check if required files exist
if not exist "midi_optimizer_gui.py" (
    echo.
    echo ERROR: midi_optimizer_gui.py not found
    echo.
    echo Please ensure you're in the correct directory.
    echo.
    pause
    exit /b 1
)

if not exist "ai_database.json" (
    echo.
    echo ERROR: ai_database.json not found
    echo.
    echo This file is required to run MIDI Optimizer.
    echo Please ensure all files are in the same directory.
    echo.
    pause
    exit /b 1
)

REM Run the application
echo.
echo Starting KORG PA800 MIDI Optimizer...
echo.

python midi_optimizer_gui.py

REM If application crashes, show error
if errorlevel 1 (
    echo.
    echo ERROR: Application failed to start
    echo.
    echo Troubleshooting:
    echo 1. Make sure Python 3.7+ is installed
    echo 2. Check that all required files are present:
    echo    - midi_optimizer_core.py
    echo    - midi_optimizer_gui.py
    echo    - ai_database.json
    echo 3. Try running from command line:
    echo    python midi_optimizer_gui.py
    echo.
    pause
)
