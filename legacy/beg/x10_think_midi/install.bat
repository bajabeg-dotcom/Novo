@echo off
REM ==========================================
REM X10 THINK - MIDI INTELLIGENCE ENGINE
REM Installation Script for Windows
REM ==========================================

echo.
echo ========================================
echo  X10 THINK MIDI INSTALLER
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.9+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo [OK] Python detected.
python --version

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo.
    echo [INFO] Creating virtual environment...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created.
) else (
    echo [INFO] Virtual environment already exists.
)

echo.
echo [INFO] Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo [INFO] Upgrading pip...
python -m pip install --upgrade pip

echo.
echo [INFO] Installing dependencies from requirements.txt...
if exist "requirements.txt" (
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [WARNING] Some dependencies might have failed, but continuing...
    )
) else (
    echo [ERROR] requirements.txt not found!
    pause
    exit /b 1
)

echo.
echo [INFO] Installing X10 Think package in development mode...
if exist "setup.py" (
    pip install -e .
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install package.
        pause
        exit /b 1
    )
) else (
    echo [ERROR] setup.py not found!
    pause
    exit /b 1
)

echo.
echo ========================================
echo  INSTALLATION COMPLETED SUCCESSFULLY!
echo ========================================
echo.
echo You can now run the application using:
echo   - run_gui.bat      (Start Graphical Interface)
echo   - run_cli.bat      (Command Line Interface)
echo.
pause
