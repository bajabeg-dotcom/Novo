@echo off
setlocal EnableExtensions
chcp 65001 >nul 2>&1

set "ROOT=%~dp0"
cd /d "%ROOT%" || goto :fail

echo ============================================================
echo   Python MIDI Enhancer - Windows installation
echo ============================================================
echo.

set "PY_CMD="
where py >nul 2>&1
if not errorlevel 1 set "PY_CMD=py -3"
if not defined PY_CMD (
    where python >nul 2>&1
    if not errorlevel 1 set "PY_CMD=python"
)
if not defined PY_CMD (
    echo ERROR: Python 3 nije pronadjen.
    echo Instaliraj Python 3.11 ili noviji sa https://www.python.org/
    echo Pri instalaciji ukljuci opciju "Add Python to PATH".
    goto :fail
)

%PY_CMD% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
if errorlevel 1 (
    echo ERROR: Potreban je Python 3.11 ili noviji.
    goto :fail
)

%PY_CMD% -c "import tkinter"
if errorlevel 1 (
    echo ERROR: Ovaj Python nema tkinter/Tk podrsku potrebnu za desktop GUI.
    echo Preporuka: instaliraj sluzbeni Windows Python sa python.org.
    goto :fail
)

if not exist "%ROOT%.venv\Scripts\python.exe" (
    echo [1/6] Kreiram lokalni virtualni environment .venv ...
    %PY_CMD% -m venv "%ROOT%.venv"
    if errorlevel 1 goto :fail
) else (
    echo [1/6] Postojeci .venv je pronadjen.
)

set "VENV_PY=%ROOT%.venv\Scripts\python.exe"
if not exist "%VENV_PY%" (
    echo ERROR: .venv Python nije kreiran.
    goto :fail
)

 echo [2/6] Provjeravam pip ...
"%VENV_PY%" -m pip --version
if errorlevel 1 goto :fail

 echo [3/6] Instaliram pinned K01 PDF extractor iz lokalnog vendor foldera ...
"%VENV_PY%" -m pip install --no-index --find-links="%ROOT%vendor" --require-hashes -r "%ROOT%requirements-k01.txt"
if errorlevel 1 goto :fail

if /I "%~1"=="minimal" goto :skip_optional
set "INSTALL_OPTIONAL=Y"
set /p "INSTALL_OPTIONAL=Instalirati preporucene MIDI biblioteke numpy/mido/pretty_midi/music21? [Y/n]: "
if /I "%INSTALL_OPTIONAL%"=="N" goto :skip_optional
if /I "%INSTALL_OPTIONAL%"=="NO" goto :skip_optional

 echo [4/6] Instaliram opcionalne MIDI biblioteke sa Python Package Indexa ...
"%VENV_PY%" -m pip install -r "%ROOT%requirements-optional.txt"
if errorlevel 1 (
    echo WARNING: Jedna ili vise opcionalnih biblioteka nije instalirana.
    echo Ugradjeni parser i GUI i dalje mogu raditi.
)
goto :after_optional

:skip_optional
 echo [4/6] Opcionalne MIDI biblioteke su preskocene.

:after_optional
 echo [5/6] Provjeravam K01 i Evidence Registry ...
"%VENV_PY%" "%ROOT%registry\generate_pa800_factory.py" --check
if errorlevel 1 goto :fail
"%VENV_PY%" "%ROOT%registry\build_registry.py" --check
if errorlevel 1 goto :fail

 echo [6/6] Pokrecem import i registry smoke provjeru ...
"%VENV_PY%" -c "import tkinter, midi_gui; from pa800_registry import load_factory_registry; assert len(load_factory_registry().entries) == 1071; print('Smoke check PASS - Tk', tkinter.TkVersion)"
if errorlevel 1 goto :fail

> "%ROOT%.venv\midi_enhancer_installed.txt" echo Installation PASS

echo.
echo ============================================================
echo   INSTALACIJA JE USPJESNO ZAVRSENA
echo ============================================================
echo Pokreni aplikaciju dvostrukim klikom na run.bat
echo Za konzolne poruke koristi: run.bat console
echo.
pause
exit /b 0

:fail
echo.
echo ============================================================
echo   INSTALACIJA NIJE ZAVRSENA
 echo Provjeri gornju ERROR poruku. Originalni MIDI podaci nisu mijenjani.
echo ============================================================
echo.
pause
exit /b 1
