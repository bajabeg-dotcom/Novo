@echo off
setlocal EnableExtensions
chcp 65001 >nul 2>&1

set "ROOT=%~dp0"
cd /d "%ROOT%" || goto :fail

set "VENV_PY=%ROOT%.venv\Scripts\python.exe"
set "VENV_PYW=%ROOT%.venv\Scripts\pythonw.exe"

if not exist "%VENV_PY%" (
    echo ERROR: Lokalna instalacija nije pronadjena.
    echo Prvo pokreni install.bat.
    goto :fail
)

if /I "%~1"=="console" (
    echo Pokrecem Python MIDI Enhancer u konzolnom nacinu ...
    "%VENV_PY%" "%ROOT%midi_gui.py"
    if errorlevel 1 goto :fail
    exit /b 0
)

if /I "%~1"=="check" (
    echo Provjeravam instalaciju i K01 registry ...
    "%VENV_PY%" "%ROOT%registry\generate_pa800_factory.py" --check
    if errorlevel 1 goto :fail
    "%VENV_PY%" "%ROOT%registry\build_registry.py" --check
    if errorlevel 1 goto :fail
    "%VENV_PY%" -c "import tkinter, midi_gui; from pa800_registry import load_factory_registry; assert len(load_factory_registry().entries) == 1071; print('Installation check PASS')"
    if errorlevel 1 goto :fail
    pause
    exit /b 0
)

if not exist "%VENV_PYW%" (
    echo ERROR: pythonw.exe nije pronadjen u .venv.
    echo Pokusaj: run.bat console
    goto :fail
)

start "Python MIDI Enhancer" "%VENV_PYW%" "%ROOT%midi_gui.py"
if errorlevel 1 goto :fail
exit /b 0

:fail
echo.
echo Aplikacija nije pokrenuta. Originalni MIDI podaci nisu mijenjani.
echo Za detaljnu gresku pokreni: run.bat console
echo.
pause
exit /b 1
