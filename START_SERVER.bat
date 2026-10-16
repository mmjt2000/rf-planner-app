@echo off
title SERVEUR - RF Planner
cd /d "%~dp0"

echo ============================================================
echo   SERVEUR - RF PLANNER
echo   Uvicorn sur http://127.0.0.1:8000
echo ============================================================
echo.
echo Pour ARRETER : Ctrl+C dans cette fenetre
echo.

python -m uvicorn serveur_simple:app --host 127.0.0.1 --port 8000

pause
