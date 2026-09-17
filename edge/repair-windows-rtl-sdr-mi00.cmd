@echo off
setlocal
cd /d "%~dp0"
net session >nul 2>&1
if %errorlevel% neq 0 (
  powershell -NoProfile -Command "Start-Process powershell.exe -Verb RunAs -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File ""%~dp0repair-windows-rtl-sdr-mi00.ps1""'"
  exit /b
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0repair-windows-rtl-sdr-mi00.ps1"
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (echo Driver and receiver check passed.) else (echo Driver repair did not pass. Exit code: %RC%)
echo State file: %~dp0constellation-windows-rtl-sdr-driver-state.json
pause
exit /b %RC%
