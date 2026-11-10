@echo off
setlocal
cd /d "%~dp0"
if not exist logs mkdir logs
if not exist cache mkdir cache
where py >nul 2>nul
if errorlevel 1 goto nopy
if not exist .venv\Scripts\python.exe (
    py -3.10 -m venv .venv
    if errorlevel 1 py -3.11 -m venv .venv
)
if not exist .venv\Scripts\python.exe goto fail
echo Installing dependencies. Log: logs\install-user.log
rem Respect administrator proxy / PIP_NO_INDEX policy. Never bypass network restrictions.
if exist wheelhouse\*.whl (
    .venv\Scripts\python.exe -m pip install --no-index --find-links wheelhouse -r requirements.txt > logs\install-user.log 2>&1
) else (
    .venv\Scripts\python.exe -m pip install -r requirements.txt --cache-dir cache\pip > logs\install-user.log 2>&1
)
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m pip check >> logs\install-user.log 2>&1
if errorlevel 1 goto fail
.venv\Scripts\python.exe scripts\download_assets.py >> logs\install-user.log 2>&1
if errorlevel 1 echo Noto font download failed. The app can use a Windows-installed font.
echo Installed. Open run.bat. Download AI models in the application's Model Manager.
pause
exit /b 0
:nopy
echo Python launcher not found. Install Python 3.10 or 3.11 x64, then run this file again.
pause
exit /b 1
:fail
echo Installation FAILED. See logs\install-user.log. No success was assumed.
pause
exit /b 1
