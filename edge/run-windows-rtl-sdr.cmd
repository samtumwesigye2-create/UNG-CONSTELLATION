@echo off
setlocal
cd /d "%~dp0"

echo UNG-CONSTELLATION Windows RTL-SDR diagnostic
echo Receive-only hardware test
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0windows-rtl-sdr-edge.ps1"
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (
  echo Diagnostic completed successfully.
) else (
  echo Diagnostic reported an error. Exit code: %RC%
)
echo State file: %~dp0constellation-windows-rtl-sdr-state.json
 echo.
pause
exit /b %RC%
