@echo off
title CLIENT - RF Planner
cd /d "%~dp0"

echo ============================================================
echo   CLIENT - RF PLANNER
echo   Tests et commandes
echo ============================================================
echo.
echo Commandes utiles :
echo   - Test API Link Budget :
echo     Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/link-budget" ...
echo.
echo   - Test API Plan Sites :
echo     Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/plan-sites" ...
echo.
echo   - Git status : git status
echo.

powershell -NoExit -Command "Set-Location '%~dp0'"
