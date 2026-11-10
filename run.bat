@echo off
setlocal
cd /d "%~dp0"
if exist dist\ImageTranslatorVN\ImageTranslatorVN.exe (
    start "" "dist\ImageTranslatorVN\ImageTranslatorVN.exe"
    exit /b 0
)
if not exist .venv\Scripts\pythonw.exe (
    echo Run install.bat first.
    pause
    exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" "main.py"
