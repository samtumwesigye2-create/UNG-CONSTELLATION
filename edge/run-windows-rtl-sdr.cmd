@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 windows_rtl_sdr_edge.py --scan --output constellation-windows-rtl-sdr-state.json
) else (
  python windows_rtl_sdr_edge.py --scan --output constellation-windows-rtl-sdr-state.json
)
echo.
echo UNG-CONSTELLATION RTL-SDR diagnostic finished.
echo State file: %~dp0constellation-windows-rtl-sdr-state.json
 pause
