@echo off
cd /d "%~dp0"

py -m pip install --user -e .
if errorlevel 1 pause & exit /b 1

if not exist data mkdir data
py -m pa800_enhancer database init data\pa800-enhancer.db

echo Instalacija i baza su zavrsene.
pause