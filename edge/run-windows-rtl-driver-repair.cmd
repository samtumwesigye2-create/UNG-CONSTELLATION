@echo off
setlocal
cd /d "%~dp0"
echo UNG-CONSTELLATION Windows RTL-SDR driver repair
echo Target: USB VID_0BDA PID_2838 Interface 0 only
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0repair-windows-rtl-sdr-driver.ps1"
set RC=%ERRORLEVEL%
echo.
if "%RC%"=="0" (
  echo Driver repair workflow completed.
) else (
  echo Driver repair workflow reported an error. Exit code: %RC%
)
echo State file: %~dp0constellation-rtl-driver-repair-state.json
echo.
pause
exit /b %RC%
