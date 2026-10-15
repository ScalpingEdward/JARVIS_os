@echo off
rem New account = new profile: folder, desktop shortcuts, settings in Notepad.
title Neues Profil
cd /d "%~dp0.."
echo Name fuer das Profil, nur Kleinbuchstaben, Ziffern, _ und -
echo Beispiel: roboforex_cent
set /p NAME=Name:
python -m signal_copier.profiles new %NAME%
echo.
echo In Notepad eintragen: "terminal" = Pfad zur terminal64.exe dieses Kontos
echo (z. B. "C:\\Program Files\\RoboForex MT5\\terminal64.exe", Backslashes doppelt),
echo "login" = Kontonummer, dazu Gruppen und Risiko. Speichern.
echo Dann ueber die neue Desktop-Verknuepfung "Copier %NAME%" starten.
echo Beim ersten Start fragt er nach Telefonnummer und Telegram-Code.
pause
