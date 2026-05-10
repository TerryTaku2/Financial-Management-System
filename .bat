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

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.10+ from https://www.python.org
    pause
    exit /b 1
)

echo [1/3] Installing dependencies...
pip install -r requirements.txt --quiet

echo [2/3] Initialising database...
cd backend
python database.py
python seed.py

echo [3/3] Starting FMS server...
echo.
echo  System ready!
echo  Open your browser and go to:
echo     http://localhost:8001/static/pages/login.html
echo.
echo  Default Login Credentials:
echo     Admin:          admin / admin123
echo     Revenue Officer: r.officer1 / password123
echo     Auditor:        auditor1 / password123
echo     Budget Officer: budget1 / password123
echo.
echo  Press CTRL+C to stop the server.
echo  ============================================================
echo.

start "" http://localhost:8001/static/pages/login.html
uvicorn main:app --host 0.0.0.0 --port 8001 --reload

pause
