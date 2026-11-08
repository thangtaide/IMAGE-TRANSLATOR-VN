@echo off
setlocal
cd /d "%~dp0"
if not exist "%~dp0.venv\Scripts\pythonw.exe" (
    echo Chua co Python trong .venv. Doc AI_SETUP_HANDOFF.md de cai dat.
    pause
    exit /b 1
)
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0main.py"
exit /b 0
