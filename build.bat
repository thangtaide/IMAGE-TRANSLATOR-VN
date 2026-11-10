@echo off
setlocal
cd /d "%~dp0"
set "ITVN_VALIDATE_BUILD=0"
if /i "%~1"=="--validated" set "ITVN_VALIDATE_BUILD=1"
if not "%~1"=="" if /i not "%~1"=="--validated" goto usage
if not exist logs mkdir logs
if not exist .venv\Scripts\python.exe goto fail
set ITVN_BUILD_NAME=ImageTranslatorVN
if exist dist\ImageTranslatorVN\ImageTranslatorVN.exe for /f %%N in ('.venv\Scripts\python.exe scripts\build_name.py') do set ITVN_BUILD_NAME=%%N
set ITVN_BUILD_LOG=logs\build-%ITVN_BUILD_NAME%.log
echo Build mode: packaging only; application validation was not requested. > "%ITVN_BUILD_LOG%"
if "%ITVN_VALIDATE_BUILD%"=="0" goto dependencies
.venv\Scripts\python.exe scripts\check_build_ready.py >> "%ITVN_BUILD_LOG%" 2>&1
if errorlevel 1 goto notready
echo Build mode: validated prerequisites and regression tests. >> "%ITVN_BUILD_LOG%"
:dependencies
.venv\Scripts\python.exe -m pip check >> "%ITVN_BUILD_LOG%" 2>&1
if errorlevel 1 goto fail
if "%ITVN_VALIDATE_BUILD%"=="0" goto package
.venv\Scripts\python.exe -m pytest -q >> "%ITVN_BUILD_LOG%" 2>&1
if errorlevel 1 goto fail
:package
echo Packaging with PyInstaller. Log: %ITVN_BUILD_LOG%
.venv\Scripts\python.exe -m PyInstaller --noconfirm ImageTranslatorVN.spec >> "%ITVN_BUILD_LOG%" 2>&1
if errorlevel 1 goto fail
if not exist dist\%ITVN_BUILD_NAME%\%ITVN_BUILD_NAME%.exe goto fail
echo Build completed: dist\%ITVN_BUILD_NAME%\%ITVN_BUILD_NAME%.exe
echo Build log: %ITVN_BUILD_LOG%
echo Packaging success does not verify GUI, OCR, translation or EXE runtime.
pause
exit /b 0
:notready
type "%ITVN_BUILD_LOG%"
echo Validated build SKIPPED. Run GUI and offline E2E validation first.
echo To package without running tests, run build.bat without --validated.
pause
exit /b 2
:usage
echo Usage: build.bat [--validated]
exit /b 2
:fail
echo Build FAILED. Read %ITVN_BUILD_LOG%. No executable was verified.
pause
exit /b 1
