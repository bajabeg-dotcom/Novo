@echo off
echo ==========================================
echo  PA800 REGRESSION TEST SUITE
echo ==========================================
echo.
echo Pokrecem sigurnosne provjere...
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo Greska: Python nije instaliran ili nije u PATH-u!
    pause
    exit /b 1
)

python run_regression_tests.py

echo.
echo ==========================================
if errorlevel 1 (
    echo STATUS: TESTOVI PALI - NE SMIJETE KORISTITI OPTIMIZER
    echo ==========================================
    color 4F
) else (
    echo STATUS: TESTOVI PROSLI - SUSTAV JE SIGURAN
    echo ==========================================
    color 2F
)
echo.
pause
