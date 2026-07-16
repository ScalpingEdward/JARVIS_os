@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 scripts\phoenix_launcher.py stop
) else (
  python scripts\phoenix_launcher.py stop
)
