@echo off
rem AURON for the LG TV: serves the dashboard on :8090 to the TV only (TV_IPS), rewritten for its old
rem browser -- see gate.mjs. Started by Windows at logon (shortcut in the Startup folder); restarts 10 s
rem after it stops. Log: tools\tv_gate\tv_gate.log. Stop it with tools\stop_helpers.bat.
title AURON tv gate
cd /d "%~dp0"
if not exist node_modules\esbuild call npm install --no-audit --no-fund
:run
node gate.mjs >> tv_gate.log 2>&1
echo.
echo TV gate stopped -- starting again in 10 s.
timeout /t 10 /nobreak >nul
goto run
