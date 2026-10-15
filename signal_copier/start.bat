@echo off
rem Runs one profile in its own window:  start.bat <profile> [--dry]
rem Without a name the only profile runs. Its MT5 must be installed; Algo
rem Trading on. Ctrl+C stops it; open trades stay in MT5.
title Copier %1
cd /d "%~dp0.."
python -m signal_copier.copier %*
echo.
echo Copier stopped.
pause
