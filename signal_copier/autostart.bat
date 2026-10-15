@echo off
rem Started by Windows at logon (shortcut in the Startup folder, see
rem "python -m signal_copier.profiles autostart <name>"). Waits a minute for
rem network and Telegram, then keeps the copier running: if it stops -- a
rem crash, a lost connection -- it starts again a minute later. The copier
rem starts its own MT5 from the profile's "terminal" path.
rem Close this window to stop it for good.
title Copier %1 (autostart)
cd /d "%~dp0.."
timeout /t 60 /nobreak >nul
:run
python -m signal_copier.copier %1
echo.
echo Copier stopped -- starting again in 60 s. Close this window to stop it for good.
timeout /t 60 /nobreak >nul
goto run
