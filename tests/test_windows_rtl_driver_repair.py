from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "edge" / "repair-windows-rtl-sdr-driver.ps1"
LAUNCHER = ROOT / "edge" / "run-windows-rtl-driver-repair.cmd"


def test_repair_script_targets_only_interface_zero():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "VID_0BDA&PID_2838&MI_00" in text
    assert "--iid 0" in text
    assert "--vid 0x0BDA" in text
    assert "--pid 0x2838" in text


def test_repair_script_uses_winusb_and_is_non_destructive():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "--type 0" in text
    assert "/delete-driver" not in text.lower()
    assert "remove-pnpdevice" not in text.lower()
    assert "disable-pnpdevice" not in text.lower()


def test_repair_script_verifies_driver_after_install():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "DEVPKEY_Device_Service" in text
    assert "WinUSB" in text
    assert "constellation-rtl-driver-repair-state.json" in text


def test_launcher_exists_and_requests_powershell():
    text = LAUNCHER.read_text(encoding="utf-8").lower()
    assert "powershell" in text
    assert "repair-windows-rtl-sdr-driver.ps1" in text
