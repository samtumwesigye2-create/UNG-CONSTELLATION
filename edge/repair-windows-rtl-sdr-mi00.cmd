@echo off
setlocal
cd /d "%~dp0"
net session >nul 2>&1
if %errorlevel% neq 0 (
  powershell -NoProfile -Command "Start-Process powershell.exe -Verb RunAs -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File ""%~dp0repair-windows-rtl-sdr-mi00.ps1""'"
  exit /b
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0repair-windows-rtl-sdr-mi00.ps1"
echo.
pause
