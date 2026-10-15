@echo off
rem Double-click to run the signal copier in its own window. MT5 must be open
rem with Algo Trading on. Ctrl+C stops it; open trades stay in MT5.
title Signal Copier
cd /d "%~dp0.."
python -m signal_copier.copier %*
echo.
echo Copier stopped.
pause
