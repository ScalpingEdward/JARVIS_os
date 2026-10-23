@echo off
rem AURON's hands at the laptop (tools/desk_runner.py): opens, closes and moves windows on Brano's word,
rem only the fixed list of actions; program files wait for his click on the dashboard.
rem Starts with Windows through a shortcut in shell:startup. Close this window to stop it.
title AURON Laptop-Helfer
cd /d "%~dp0"
:run
python tools\desk_runner.py
echo Laptop-Helfer stopped -- starting again in 10 s.
timeout /t 10 /nobreak >nul
goto run
