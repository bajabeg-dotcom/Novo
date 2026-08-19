@echo off
REM ============================================================================
REM KORG PA800 MIDI Optimizer - Batch Processing
REM ============================================================================
REM This script processes all MIDI files in a directory
REM Usage: batch_process.bat [input_folder] [output_folder] [strategy]
REM
REM Examples:
REM   batch_process.bat
REM   batch_process.bat C:\Music\MIDI
REM   batch_process.bat C:\Music\MIDI C:\Music\Optimized
REM   batch_process.bat C:\Music\MIDI C:\Music\Optimized EXPRESSIVE
REM
REM If no folders specified, uses current directory
REM

setlocal enabledelayedexpansion

cls
echo.
echo ============================================================================
echo  KORG PA800 MIDI Optimizer - Batch Processing
echo ============================================================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found
    echo Please install Python: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Set default folders
if "%~1"=="" (
    set INPUT_FOLDER=.
    echo No input folder specified, using current directory
) else (
    set INPUT_FOLDER=%~1
)

if "%~2"=="" (
    set OUTPUT_FOLDER=%INPUT_FOLDER%\optimized
    echo No output folder specified, using: %OUTPUT_FOLDER%
) else (
    set OUTPUT_FOLDER=%~2
)

REM Set default strategy
if "%~3"=="" (
    set STRATEGY=AUTHENTIC
) else (
    set STRATEGY=%~3
)

REM Check input folder
if not exist "!INPUT_FOLDER!" (
    echo.
    echo ERROR: Input folder not found: !INPUT_FOLDER!
    echo.
    pause
    exit /b 1
)

REM Create output folder if it doesn't exist
if not exist "!OUTPUT_FOLDER!" (
    mkdir "!OUTPUT_FOLDER!"
    echo Created output folder: !OUTPUT_FOLDER!
)

REM Show summary
echo.
echo ============================================================================
echo BATCH PROCESSING SETTINGS
echo ============================================================================
echo Input folder:   !INPUT_FOLDER!
echo Output folder:  !OUTPUT_FOLDER!
echo Strategy:       !STRATEGY!
echo.

REM Count MIDI files
setlocal enabledelayedexpansion
set MIDI_COUNT=0
for /r "!INPUT_FOLDER!" %%f in (*.mid) do set /a MIDI_COUNT+=1

echo Found !MIDI_COUNT! MIDI files
echo.

if !MIDI_COUNT! equ 0 (
    echo No MIDI files found in !INPUT_FOLDER!
    echo.
    echo USAGE: batch_process.bat [input_folder] [output_folder] [strategy]
    echo.
    echo EXAMPLES:
    echo   batch_process.bat
    echo   batch_process.bat C:\Music\MIDI
    echo   batch_process.bat C:\Music\MIDI C:\Music\Optimized
    echo   batch_process.bat C:\Music\MIDI C:\Music\Optimized EXPRESSIVE
    echo.
    pause
    exit /b 1
)

REM Ask for confirmation
echo Are you sure you want to process !MIDI_COUNT! files? (Y/N)
set /p CONFIRM=Enter choice: 

if /i not "%CONFIRM%"=="Y" (
    echo Cancelled.
    pause
    exit /b 0
)

echo.
echo Starting batch processing...
echo.

REM Run batch processor
python midi_optimizer_cli.py batch "!INPUT_FOLDER!" "!OUTPUT_FOLDER!" --strategy !STRATEGY!

if errorlevel 1 (
    echo.
    echo Batch processing finished with errors
    echo.
) else (
    echo.
    echo ============================================================================
    echo Batch processing complete!
    echo ============================================================================
    echo.
    echo Optimized files saved to: !OUTPUT_FOLDER!
    echo.
)

pause
