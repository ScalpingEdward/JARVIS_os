@echo off
rem AURON's code runner (tools/code_runner.py): picks up code wishes from AURON, lets Claude Code
rem prepare them on a separate branch, and puts them live only after Brano's "Freigeben".
rem For autostart: a shortcut to this file in shell:startup. Close this window to stop it.
title AURON Code-Runner
cd /d "%~dp0"
:run
python tools\code_runner.py
echo Code-Runner stopped -- starting again in 30 s.
timeout /t 30 /nobreak >nul
goto run
