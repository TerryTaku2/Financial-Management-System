@echo off
title City of Harare FMS - Starting...
color 0A

echo.
echo  ============================================================
echo   CITY OF HARARE - FINANCIAL MANAGEMENT SYSTEM v1.0
echo   Revenue Leakage Mitigation Platform
echo   Dissertation Project - Terrence Muromba, 2026
echo  ============================================================
echo.

:: Use Python 3.14 explicitly - it has all required packages
set PYTHON=C:\Python314\python.exe
set PIP=C:\Python314\Scripts\pip.exe

:: Verify Python 3.14 is present
if not exist "%PYTHON%" (
    echo [ERROR] Python 3.14 not found at %PYTHON%
    echo Please run: pip install -r requirements.txt  using your installed Python.
    pause
    exit /b 1
)

echo [1/3] Installing / verifying dependencies...
"%PIP%" install -r requirements.txt --quiet --no-warn-script-location
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

echo [2/3] Initialising database...
cd backend
"%PYTHON%" database.py
if %errorlevel% neq 0 (
    echo [ERROR] Database initialisation failed.
    pause
    exit /b 1
)
"%PYTHON%" seed.py

echo [3/3] Starting FMS server...
echo.
echo  System ready!
echo  Open your browser and go to:
echo     http://localhost:8001/static/pages/login.html
echo.
echo  Default Login Credentials:
echo     Admin:           admin / admin123
echo     Revenue Officer: r.officer1 / password123
echo     Auditor:         auditor1 / password123
echo     Budget Officer:  budget1 / password123
echo.
echo  Press CTRL+C to stop the server.
echo  ============================================================
echo.

:: Open browser after a 4-second delay (gives uvicorn time to bind the port)
start "" cmd /c "timeout /t 4 /nobreak >nul && start http://127.0.0.1:8001/static/pages/login.html"

:: Start the server (blocks until CTRL+C)
"%PYTHON%" -m uvicorn main:app --host 127.0.0.1 --port 8001 --reload

pause
