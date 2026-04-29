@echo off
cd /d "%~dp0"
echo ============================================
echo  CNBC Turk - WatchFolder + REST API
echo ============================================
echo.
echo  Input     : %~dp0WatchFolder\input\
echo  Raporlar  : %~dp0WatchFolder\output\
echo  API       : http://localhost:8000/api/status
echo.
echo  Durdurmak icin: Ctrl+C
echo.
venv\Scripts\python.exe run_server.py
pause
