from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PS1 = ROOT / "edge" / "windows-rtl-sdr-edge.ps1"
CMD = ROOT / "edge" / "run-windows-rtl-sdr.cmd"


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
