@echo off
REM Installs the KORG PA800 Optimizer into a local virtual environment.
REM Run this once (or again after pulling updates). Requires Python 3.11+
REM already installed and available as "python" on PATH.
REM
REM NOTE: written and syntax-checked on Linux (no Windows machine was
REM available to actually run this) -- please report any issue running
REM it on real Windows so it can be fixed.

setlocal

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found on PATH.
    echo Install Python 3.11 or newer from https://www.python.org/downloads/
    echo and make sure to check "Add python.exe to PATH" during setup.
    pause
    exit /b 1
)

echo Checking Python version...
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
if errorlevel 1 (
    echo [ERROR] Python 3.11 or newer is required.
    python --version
    pause
    exit /b 1
)

if not exist ".venv" (
    echo Creating virtual environment in .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create the virtual environment.
        pause
        exit /b 1
    )
) else (
    echo Virtual environment .venv already exists, reusing it.
)

echo Installing dependencies ^(this may take a minute^)...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
    echo [ERROR] Failed to upgrade pip.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m pip install -e .
if errorlevel 1 (
    echo [ERROR] Failed to install the package and its dependencies.
    pause
    exit /b 1
)

echo.
echo Install complete. Run "run.bat" to start the web GUI.
pause
