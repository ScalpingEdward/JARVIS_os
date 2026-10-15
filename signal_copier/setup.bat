@echo off
rem One-time setup: Python packages, .env, Telegram login. Safe to run again.
title Signal Copier - Setup
cd /d "%~dp0.."

python --version >nul 2>&1
if errorlevel 1 (
    echo Python is missing. Install it from https://www.python.org/downloads/
    echo and tick "Add python.exe to PATH" in the installer. Then run this again.
    pause
    exit /b 1
)

echo [1/3] Installing packages...
python -m pip install --upgrade -r signal_copier\requirements.txt
if errorlevel 1 (
    echo Installing failed -- see the message above.
    pause
    exit /b 1
)

if not exist signal_copier\.env (
    copy signal_copier\.env.example signal_copier\.env >nul
    echo [2/3] Fill in signal_copier\.env now ^(see ANLEITUNG.md^), save, close Notepad.
    notepad signal_copier\.env
) else (
    echo [2/3] signal_copier\.env exists already.
)

echo [3/3] Telegram login: phone number, the code Telegram sends, your 2FA password if set.
python -m signal_copier.telegram_check
echo.
echo Setup done. If the last lines show messages of the group, start the copier with start.bat.
pause
