@echo off
REM ============================================================================
REM KORG PA800 MIDI Optimizer - MIDI File Analyzer
REM ============================================================================
REM This script analyzes MIDI file structure without modifying it
REM Usage: analyze.bat <input.mid>
REM
REM Shows:
REM   - Total number of notes
REM   - Programs/sounds used
REM   - Velocity ranges
REM   - Register distribution
REM

setlocal enabledelayedexpansion

cls
echo.
echo ============================================================================
echo  KORG PA800 MIDI Optimizer - File Analyzer
echo ============================================================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found
    echo Please install Python: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Check arguments
if "%~1"=="" (
    echo.
    echo USAGE: analyze.bat ^<input.mid^>
    echo.
    echo EXAMPLES:
    echo   analyze.bat song.mid
    echo   analyze.bat "C:\My Music\track.mid"
    echo.
    echo QUICK START:
    echo   1. Drag MIDI file onto this batch file, OR
    echo   2. Run: analyze.bat C:\path\to\song.mid
    echo.
    echo This analyzes your MIDI file and shows:
    echo   - Total notes
    echo   - Programs/sounds used
    echo   - Velocity ranges
    echo   - Register distribution (low/mid/high)
    echo.
    pause
    exit /b 1
)

REM Get input file
set INPUT_FILE=%~1

REM Check if input file exists
if not exist "!INPUT_FILE!" (
    echo.
    echo ERROR: File not found: !INPUT_FILE!
    echo.
    pause
    exit /b 1
)

echo Input file: !INPUT_FILE!
echo.
echo Analyzing MIDI file...
echo.
echo ============================================================================
echo.

REM Run analyzer
python midi_optimizer_cli.py analyze "!INPUT_FILE!"

if errorlevel 1 (
    echo.
    echo ERROR: Analysis failed
    echo.
    echo Troubleshooting:
    echo - Ensure file is valid MIDI
    echo - Try using absolute path
    echo - Check file permissions
    echo.
) else (
    echo.
    echo ============================================================================
    echo Analysis complete!
    echo.
)

pause
