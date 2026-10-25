@echo off
rem Watchlist feed: prices from MT5 to AURON's dashboard, once a minute. Read-only.
rem Started by Windows at logon (shortcut in the Startup folder); restarts a minute
rem after it stops. Stop it with tools\stop_helpers.bat.
title AURON market feed
cd /d "%~dp0.."
timeout /t 60 /nobreak >nul
:run
python -m signal_copier.market_feed
echo.
echo Market feed stopped -- starting again in 60 s.
timeout /t 60 /nobreak >nul
goto run
