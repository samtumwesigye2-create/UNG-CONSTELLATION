UNG-CONSTELLATION Windows RTL-SDR diagnostic

1. Keep the extracted SDR++ folder in your Downloads directory so rtlsdr.dll is available.
2. Double-click run-windows-rtl-sdr.cmd.
3. The diagnostic uses Windows PowerShell; Python is not required.
4. It opens the RTL-SDR receive-only, tunes to 137.9 MHz, reads a bounded IQ sample, and writes constellation-windows-rtl-sdr-state.json.
5. If another SDR application has the dongle open, close that application and run the diagnostic again.

Interface 0 repair (only when Windows reports Service RTL2832UUSB)

1. Keep the receiver plugged in and close SDR++ or other SDR programs.
2. Put the official signed Zadig executable from https://zadig.akeo.ie/ in Downloads.
3. Double-click repair-windows-rtl-sdr-mi00.cmd and approve Windows elevation.
4. The helper verifies there is exactly one RTL2832U Interface 0 and opens Zadig.
   In Zadig, choose Device > Load Preset Device, load the MI00 preset the helper
   created beside this script, verify WinUSB is selected, click Install/Replace
   Driver, then close Zadig. Do not choose the composite parent or Interface 1.
5. The helper then checks that Interface 0 uses WinUSB, Interface 1's driver
   stayed unchanged, and the receive-only sample test passes. It writes the
   result to constellation-windows-rtl-sdr-driver-state.json. A nonzero exit
   means repair or diagnosis was not verified; read the state files for details.

The helper does not silently install a driver. Zadig must create and install
the device-specific Windows package on the laptop. No other driver packages
are deleted or replaced by the helper.
