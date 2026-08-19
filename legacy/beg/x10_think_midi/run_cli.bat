@echo off
REM ==========================================
REM X10 THINK - MIDI INTELLIGENCE ENGINE
REM Run CLI Application Script
REM ==========================================

echo.
echo ========================================
echo  X10 THINK COMMAND LINE INTERFACE
echo ========================================
echo.

REM Check if virtual environment exists
if not exist "venv" (
    echo [ERROR] Virtual environment not found!
    echo Please run install.bat first.
    pause
    exit /b 1
)

echo [INFO] Activating virtual environment...
call venv\Scripts\activate.bat

REM Add src directory to PYTHONPATH
set PYTHONPATH=%CD%\src;%PYTHONPATH%

echo.
echo Available commands:
echo   x10-think analyze ^<midi_file^>    - Analyze a MIDI file
echo   x10-think process ^<midi_file^>    - Process and enhance a MIDI file
echo   x10-think gui                      - Start the GUI
echo   x10-think --help                   - Show all options
echo.
echo Example:
echo   x10-think analyze my_song.mid
echo.

REM Run the CLI with passed arguments or start interactive mode
if "%~1"=="" (
    echo [INFO] Starting CLI in interactive mode...
    python -m x10_think.cli
) else (
    echo [INFO] Executing: x10-think %*
    python -m x10_think.cli %*
)

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Command exited with an error.
    echo Check the logs for details.
    pause
)
