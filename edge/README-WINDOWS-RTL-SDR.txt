UNG-CONSTELLATION Windows RTL-SDR diagnostic

1. Keep the extracted SDR++ folder in your Downloads directory so rtlsdr.dll is available.
2. Double-click run-windows-rtl-sdr.cmd.
3. The diagnostic uses Windows PowerShell; Python is not required.
4. It opens the RTL-SDR receive-only, tunes to 137.9 MHz, reads a bounded IQ sample, and writes constellation-windows-rtl-sdr-state.json.
5. If another SDR application has the dongle open, close that application and run the diagnostic again.
