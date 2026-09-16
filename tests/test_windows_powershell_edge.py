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


def test_mi00_repair_helper_is_targeted_and_verifies_result():
    assert REPAIR.exists(), "MI_00 WinUSB repair helper is missing"
    text = REPAIR.read_text(encoding="utf-8")
    assert "$targetId = 'VID_0BDA&PID_2838&MI_00'" in text
    assert "'--iid', '0'" in text
    assert "'--type', '0'" in text
    assert "DEVPKEY_Device_Service" in text
    assert "DEVPKEY_Device_DriverProvider" in text
    assert "Remove-PnpDevice" not in text
    assert "/delete-driver" not in text


def test_mi00_repair_launcher_elevates_powershell():
    assert REPAIR_CMD.exists(), "MI_00 repair launcher is missing"
    text = REPAIR_CMD.read_text(encoding="utf-8").lower()
    assert "runas" in text
    assert "repair-windows-rtl-sdr-mi00.ps1" in text
