@echo off
REM ============================================================================
REM KORG PA800 MIDI Optimizer - Batch File Optimizer
REM ============================================================================
REM This script allows you to optimize MIDI files via command line
REM Usage: optimize.bat <input.mid> [output.mid] [strategy]
REM
REM Examples:
REM   optimize.bat song.mid
REM   optimize.bat song.mid song_optimized.mid
REM   optimize.bat song.mid song_optimized.mid EXPRESSIVE
REM
REM Strategies: AUTHENTIC (default), EXPRESSIVE, BALANCED, AGGRESSIVE
REM

setlocal enabledelayedexpansion

cls
echo.
echo ============================================================================
echo  KORG PA800 MIDI Optimizer - File Optimizer
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
    echo USAGE: optimize.bat ^<input.mid^> [output.mid] [strategy]
    echo.
    echo EXAMPLES:
    echo   optimize.bat song.mid
    echo   optimize.bat song.mid song_optimized.mid
    echo   optimize.mid song.mid song_optimized.mid EXPRESSIVE
    echo.
    echo STRATEGIES:
    echo   AUTHENTIC  - Match factory patterns exactly (default)
    echo   EXPRESSIVE - Emphasize dynamics
    echo   BALANCED   - Conservative adjustments
    echo   AGGRESSIVE - Maximize character
    echo.
    echo QUICK START:
    echo   1. Drag MIDI file onto this batch file, OR
    echo   2. Run: optimize.bat C:\path\to\song.mid
    echo.
    pause
    exit /b 1
)

REM Get input file
set INPUT_FILE=%~1

REM Check if input file exists
if not exist "!INPUT_FILE!" (
    echo.
    echo ERROR: Input file not found: !INPUT_FILE!
    echo.
    pause
    exit /b 1
)

REM Get output file (default: input_optimized.mid)
if "%~2"=="" (
    for %%a in ("!INPUT_FILE!") do set OUTPUT_FILE=%%~da%%~pa%%~na_optimized.mid
) else (
    set OUTPUT_FILE=%~2
)

REM Get strategy (default: AUTHENTIC)
if "%~3"=="" (
    set STRATEGY=AUTHENTIC
) else (
    set STRATEGY=%~3
)

REM Validate strategy
if /i not "%STRATEGY%"=="AUTHENTIC" if /i not "%STRATEGY%"=="EXPRESSIVE" if /i not "%STRATEGY%"=="BALANCED" if /i not "%STRATEGY%"=="AGGRESSIVE" (
    echo.
    echo ERROR: Invalid strategy: %STRATEGY%
    echo.
    echo Valid strategies:
    echo   AUTHENTIC
    echo   EXPRESSIVE
    echo   BALANCED
    echo   AGGRESSIVE
    echo.
    pause
    exit /b 1
)

echo Input file:  !INPUT_FILE!
echo Output file: !OUTPUT_FILE!
echo Strategy:   !STRATEGY!
echo.
echo Optimizing MIDI file...
echo.

REM Run optimizer
python midi_optimizer_cli.py optimize "!INPUT_FILE!" "!OUTPUT_FILE!" --strategy !STRATEGY!

if errorlevel 1 (
    echo.
    echo ERROR: Optimization failed
    echo.
    echo Troubleshooting:
    echo - Ensure input file is valid MIDI
    echo - Check file paths are correct
    echo - Try using absolute paths
    echo - Check disk space
    echo.
) else (
    echo.
    echo SUCCESS: File optimized!
    echo Output: !OUTPUT_FILE!
    echo.
)

pause
