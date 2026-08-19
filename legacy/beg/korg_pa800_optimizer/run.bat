@echo off
REM Starts the KORG PA800 Optimizer web GUI and opens it in your browser.
REM Run install.bat first if you haven't already.
REM
REM NOTE: written and syntax-checked on Linux (no Windows machine was
REM available to actually run this) -- please report any issue running
REM it on real Windows so it can be fixed.

setlocal

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found.
    echo Please run install.bat first.
    pause
    exit /b 1
)

echo Starting KORG PA800 Optimizer at http://127.0.0.1:5000/
echo Press Ctrl+C to stop the server.
echo.

".venv\Scripts\python.exe" app.py

pause
