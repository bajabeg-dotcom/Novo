@echo off
REM ==========================================
REM X10 THINK - MIDI INTELLIGENCE ENGINE
REM Run GUI Application Script
REM ==========================================

echo.
echo ========================================
echo  STARTING X10 THINK GUI
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

echo [INFO] Starting X10 Think GUI...
echo.

REM Add src directory to PYTHONPATH
set PYTHONPATH=%CD%\src;%PYTHONPATH%

REM Run the GUI entry point
python -m x10_think.gui_main

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Application exited with an error.
    echo Check the logs for details.
    pause
)
