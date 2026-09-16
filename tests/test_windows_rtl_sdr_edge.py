from pathlib import Path
import importlib.util
import json
import subprocess

MODULE_PATH = Path(__file__).resolve().parents[1] / "edge" / "windows_rtl_sdr_edge.py"


def load_module():
    assert MODULE_PATH.exists(), "Windows RTL-SDR edge launcher is missing"
    spec = importlib.util.spec_from_file_location("windows_rtl_sdr_edge", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_rtl_test_command_is_receive_only():
    mod = load_module()
    assert mod.build_rtl_test_command() == ["rtl_test", "-t"]


def test_build_power_command_uses_requested_frequency_window():
    mod = load_module()
    cmd = mod.build_power_command(center_hz=137_900_000, span_hz=200_000, bin_hz=5_000)
    assert cmd == ["rtl_power", "-f", "137800000:138000000:5000", "-i", "1", "-1"]


def test_parse_rtl_test_detects_supported_device():
    mod = load_module()
    sample = "Found 1 device(s):\n  0:  Realtek, RTL2838UHIDIR, SN: 00000001\nUsing device 0: Generic RTL2832U OEM\nSupported gain values (29):"
    result = mod.parse_rtl_test_output(sample)
    assert result["device_detected"] is True
    assert "Generic RTL2832U OEM" in result["device"]


def test_diagnostic_state_reports_missing_tools_without_crashing(monkeypatch):
    mod = load_module()
    monkeypatch.setattr(mod.shutil, "which", lambda name: None)
    state = mod.collect_diagnostics()
    assert state["ok"] is False
    assert state["receive_only"] is True
    assert state["tools"]["rtl_test"] is False
    assert state["tools"]["rtl_power"] is False
