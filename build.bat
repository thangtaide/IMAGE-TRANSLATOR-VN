@echo off
setlocal
cd /d "%~dp0"
if not exist logs mkdir logs
if not exist .venv\Scripts\python.exe goto fail
set ITVN_BUILD_NAME=ImageTranslatorVN
if exist dist\ImageTranslatorVN\ImageTranslatorVN.exe for /f %%N in ('.venv\Scripts\python.exe scripts\build_name.py') do set ITVN_BUILD_NAME=%%N
set ITVN_BUILD_LOG=logs\build-%ITVN_BUILD_NAME%.log
.venv\Scripts\python.exe scripts\check_build_ready.py
if errorlevel 1 goto notready
.venv\Scripts\python.exe -m pip check > %ITVN_BUILD_LOG% 2>&1
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m pytest -q >> %ITVN_BUILD_LOG% 2>&1
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m PyInstaller --noconfirm ImageTranslatorVN.spec >> %ITVN_BUILD_LOG% 2>&1
if errorlevel 1 goto fail
if not exist dist\%ITVN_BUILD_NAME%\%ITVN_BUILD_NAME%.exe goto fail
echo Build completed: dist\%ITVN_BUILD_NAME%\%ITVN_BUILD_NAME%.exe
echo Build log: %ITVN_BUILD_LOG%
pause
exit /b 0
:notready
echo Build SKIPPED. Run real GUI and offline E2E validation successfully before packaging.
pause
exit /b 2
:fail
echo Build FAILED. Read %ITVN_BUILD_LOG%. No executable was verified.
pause
exit /b 1
