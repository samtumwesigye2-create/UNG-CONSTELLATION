from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPAIR = ROOT / "edge" / "repair-windows-rtl-sdr-mi00.ps1"
LAUNCHER = ROOT / "edge" / "run-windows-rtl-sdr-repair.cmd"


def test_repair_helper_targets_only_interface_zero():
    text = REPAIR.read_text(encoding="utf-8")
    assert "VID_0BDA&PID_2838&MI_00" in text
    assert "MI_01" not in text


def test_repair_helper_does_not_delete_driver_packages():
    text = REPAIR.read_text(encoding="utf-8").lower()
    assert "/delete-driver" not in text
    assert "remove-pnpdevice" not in text


def test_repair_helper_verifies_winusb_before_diagnostic():
    text = REPAIR.read_text(encoding="utf-8")
    assert "DEVPKEY_Device_Service" in text
    assert "WinUSB" in text
    assert "windows-rtl-sdr-edge.ps1" in text


def test_one_click_repair_launcher_exists():
    text = LAUNCHER.read_text(encoding="utf-8").lower()
    assert "powershell" in text
    assert "repair-windows-rtl-sdr-mi00.ps1" in text
