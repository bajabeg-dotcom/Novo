@echo off
setlocal
cd /d "%~dp0"
title Korg Pa800 MIDI Enhancer

py -c "import pa800_enhancer" >nul 2>&1
if errorlevel 1 (
    echo Prva instalacija aplikacije...
    py -m pip install --user -e .
    if errorlevel 1 goto :error
)

if not exist "data\pa800-enhancer.db" (
    py -m pa800_enhancer database init "data\pa800-enhancer.db"
    if errorlevel 1 goto :error
)

py -m pa800_enhancer ui %*
if errorlevel 1 goto :error
exit /b 0

:error
echo.
echo Aplikacija se nije mogla pokrenuti. Posalji tekst ove greske.
pause
exit /b 1
