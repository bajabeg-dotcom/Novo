@echo off
REM ============================================================================
REM KORG PA800 MIDI Optimizer - Windows Installation Script
REM ============================================================================
REM
REM This script:
REM 1. Checks Python installation
REM 2. Verifies required files
REM 3. Creates desktop shortcut (optional)
REM 4. Displays next steps
REM

setlocal enabledelayedexpansion

cls
echo.
echo ============================================================================
echo  KORG PA800 MIDI Optimizer - Installation
echo ============================================================================
echo.

REM Check Python installation
echo Checking Python installation...
python --version >nul 2>&1

if errorlevel 1 (
    echo.
    echo ERROR: Python is not installed or not in PATH
    echo.
    echo Please install Python 3.7 or higher from:
    echo https://www.python.org/downloads/
    echo.
    echo Make sure to CHECK "Add Python to PATH" during installation!
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version') do set PYTHON_VERSION=%%i
echo  OK: %PYTHON_VERSION% found

REM Check required files
echo.
echo Checking required files...
set MISSING_FILES=0

if not exist "midi_optimizer_core.py" (
    echo  ERROR: midi_optimizer_core.py not found
    set MISSING_FILES=1
)

if not exist "midi_optimizer_gui.py" (
    echo  ERROR: midi_optimizer_gui.py not found
    set MISSING_FILES=1
)

if not exist "midi_optimizer_cli.py" (
    echo  ERROR: midi_optimizer_cli.py not found
    set MISSING_FILES=1
)

if not exist "ai_database.json" (
    echo  ERROR: ai_database.json not found (REQUIRED!)
    set MISSING_FILES=1
)

if %MISSING_FILES%==1 (
    echo.
    echo ERROR: Missing required files!
    echo.
    echo Required files:
    echo  - midi_optimizer_core.py
    echo  - midi_optimizer_gui.py
    echo  - midi_optimizer_cli.py
    echo  - ai_database.json
    echo.
    echo Please ensure all files are in the same directory.
    echo.
    pause
    exit /b 1
)

echo  OK: All required files found
echo  - midi_optimizer_core.py
echo  - midi_optimizer_gui.py
echo  - midi_optimizer_cli.py
echo  - ai_database.json

REM Check tkinter
echo.
echo Checking tkinter (required for GUI)...
python -m tkinter >nul 2>&1

if errorlevel 1 (
    echo.
    echo WARNING: tkinter not found!
    echo.
    echo tkinter is required for the GUI application.
    echo To install tkinter:
    echo.
    echo On Windows:
    echo   Run Python installer and select "tcl/tk and IDLE"
    echo.
    echo You can still use the CLI tool:
    echo   python midi_optimizer_cli.py --help
    echo.
) else (
    echo  OK: tkinter found (GUI will work)
)

REM Optional: Create desktop shortcut
echo.
echo ============================================================================
echo  Setup Complete
echo ============================================================================
echo.
echo Would you like to create a desktop shortcut? (Y/N)
set /p CREATE_SHORTCUT=Enter choice: 

if /i "%CREATE_SHORTCUT%"=="Y" (
    echo.
    echo Creating desktop shortcut...
    
    REM Get username
    for /f "tokens=*" %%a in ('whoami /user /fo csv /nh') do (
        for /f "tokens=3 delims=\" %%b in ('echo %%a') do set USERNAME=%%b
    )
    
    set DESKTOP_PATH=%USERPROFILE%\Desktop
    set SHORTCUT_PATH=!DESKTOP_PATH!\KORG MIDI Optimizer.lnk
    
    REM Create VBS script for shortcut
    set VBS_FILE=%TEMP%\create_shortcut.vbs
    
    (
        echo Set oWS = WScript.CreateObject("WScript.Shell"^)
        echo sLinkFile = "!SHORTCUT_PATH!"
        echo Set oLink = oWS.CreateShortcut(sLinkFile^)
        echo oLink.TargetPath = "!CD!\midi_optimizer_gui.py"
        echo oLink.WorkingDirectory = "!CD!"
        echo oLink.Description = "KORG PA800 MIDI Optimizer"
        echo oLink.IconLocation = "!CD!\icon.ico"
        echo oLink.Save
    ) > "!VBS_FILE!"
    
    cscript "!VBS_FILE!" >nul 2>&1
    
    if exist "!SHORTCUT_PATH!" (
        echo  OK: Desktop shortcut created
    ) else (
        echo  Note: Could not create desktop shortcut
        echo        You can run: python midi_optimizer_gui.py
    )
    
    del "!VBS_FILE!" >nul 2>&1
)

echo.
echo ============================================================================
echo  INSTALLATION COMPLETE
echo ============================================================================
echo.
echo Ready to use MIDI Optimizer!
echo.
echo QUICK START:
echo  1. Desktop GUI: python midi_optimizer_gui.py
echo  2. Command Line: python midi_optimizer_cli.py --help
echo  3. Analyze MIDI: python midi_optimizer_cli.py analyze file.mid
echo.
echo DOCUMENTATION:
echo  - Read: MIDI_OPTIMIZER_README.md
echo  - Full Guide: MIDI_OPTIMIZER_GUIDE.md
echo.
echo WINDOWS SHORTCUTS:
echo  - Use run.bat to launch GUI
echo  - Use optimize.bat to optimize single file
echo.
echo Questions? See MIDI_OPTIMIZER_GUIDE.md for complete documentation.
echo.
pause
