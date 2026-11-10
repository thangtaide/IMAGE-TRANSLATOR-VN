@echo off
setlocal
cd /d "%~dp0"
set APP=dist\ImageTranslatorVN-20261106T101857052219Z\ImageTranslatorVN-20261106T101857052219Z.exe
if not exist "%APP%" goto missing
start "" "%APP%"
exit /b 0
:missing
echo Updated executable not found. Read BUILD_REPORT.md. The original run.bat is preserved.
pause
exit /b 1
