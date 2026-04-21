@echo off
title City of Harare Financial Management System
echo.
echo  ================================================
echo   CITY OF HARARE — FINANCIAL MANAGEMENT SYSTEM
echo   Version 2.0  ^|  University of Zimbabwe 2026
echo  ================================================
echo.
echo [1/3] Installing dependencies...
cd backend
pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo ERROR: pip install failed. Ensure Python 3.10+ is installed.
    pause
    exit /b 1
)
echo [2/3] Seeding database...
python seed.py
echo [3/3] Starting server...
echo.
echo  System URL: http://localhost:8000
echo  API Docs:   http://localhost:8000/docs
echo  Health:     http://localhost:8000/api/health
echo.
echo  Login credentials:
echo   admin / admin123  (System Administrator)
echo   t.muromba / password123  (Accountant)
echo   auditor1 / password123  (Internal Auditor)
echo   r.officer1 / password123  (Revenue Officer)
echo   budget1 / password123  (Budget Officer)
echo.
echo  Press Ctrl+C to stop the server.
echo.
start "" http://localhost:8000
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
