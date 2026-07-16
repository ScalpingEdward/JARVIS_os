@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 scripts\phoenix_launcher.py start
) else (
  python scripts\phoenix_launcher.py start
)
if errorlevel 1 pause
