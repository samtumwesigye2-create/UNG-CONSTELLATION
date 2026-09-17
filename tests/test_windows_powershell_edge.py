from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PS1 = ROOT / "edge" / "windows-rtl-sdr-edge.ps1"
CMD = ROOT / "edge" / "run-windows-rtl-sdr.cmd"
REPAIR = ROOT / "edge" / "repair-windows-rtl-sdr-mi00.ps1"
REPAIR_CMD = ROOT / "edge" / "repair-windows-rtl-sdr-mi00.cmd"


def test_powershell_edge_exists_and_is_receive_only():
    assert PS1.exists(), "PowerShell RTL-SDR diagnostic is missing"
    text = PS1.read_text(encoding="utf-8")
    assert "rtlsdr_open" in text
    assert "rtlsdr_read_sync" in text
    assert "rtlsdr_set_center_freq" in text
    assert "137900000" in text
    assert "transmit" not in text.lower()


def test_windows_launcher_uses_powershell_not_python():
    text = CMD.read_text(encoding="utf-8").lower()
    assert "powershell" in text
    assert "python" not in text
    assert "py -3" not in text


def test_mi00_repair_helper_is_targeted_and_never_deletes_drivers():
    assert REPAIR.exists(), "MI_00 WinUSB repair helper is missing"
    text = REPAIR.read_text(encoding="utf-8")
    assert "$targetId = 'VID_0BDA&PID_2838&MI_00'" in text
    assert "VID = 0x0BDA" in text
    assert "PID = 0x2838" in text
    assert "MI = 0x00" in text
    assert "if ($before.service -ne 'RTL2832UUSB')" in text
    assert "DEVPKEY_Device_Service" in text
    assert "DEVPKEY_Device_DriverProvider" in text
    assert "Remove-PnpDevice" not in text
    assert "/delete-driver" not in text


def test_mi00_repair_launcher_elevates_powershell():
    assert REPAIR_CMD.exists(), "MI_00 repair launcher is missing"
    text = REPAIR_CMD.read_text(encoding="utf-8").lower()
    assert "runas" in text
    assert "repair-windows-rtl-sdr-mi00.ps1" in text


def test_repair_verifies_both_interfaces_and_diagnostic_after_installer():
    text = REPAIR.read_text(encoding="utf-8")
    assert "-Wait -PassThru" in text
    assert "MI_01" in text
    assert "Interface 1 changed" in text
    assert "windows-rtl-sdr-edge.ps1" in text
    assert text.index("-Wait -PassThru") < text.index("Get-DriverState $deviceAfter")
    assert text.index("$after.service -ne 'WinUSB'") < text.index("windows-rtl-sdr-edge.ps1")


def test_repair_does_not_overwrite_zadig_configuration_or_guess_among_dongles():
    text = REPAIR.read_text(encoding="utf-8")
    assert "zadig.ini" not in text
    assert "Multiple RTL-SDR Interface 0 devices" in text
    assert "Get-AuthenticodeSignature" in text
