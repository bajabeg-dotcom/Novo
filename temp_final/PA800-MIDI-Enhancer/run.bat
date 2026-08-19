@echo off
cd /d "%~dp0"

if not exist data\pa800-enhancer.db (
    if not exist data mkdir data
    py -m pa800_enhancer database init data\pa800-enhancer.db
)

py -m pa800_enhancer ui %*
if errorlevel 1 pause