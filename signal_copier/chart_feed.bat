@echo off
rem Charts for AURON's dashboard (candles, trade-review history, ticket prices) in their own process,
rem so a chart never holds up the copiers. Read-only towards MT5. Started by Windows at logon
rem (shortcut in the Startup folder); restarts 10 s after it stops. Close this window to stop it.
title AURON chart feed
cd /d "%~dp0.."
:run
python -m signal_copier.chart_feed
echo.
echo Chart feed stopped -- starting again in 10 s.
timeout /t 10 /nobreak >nul
goto run
