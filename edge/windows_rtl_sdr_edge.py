#!/usr/bin/env python3
"""Receive-only Windows RTL-SDR edge diagnostic for UNG-CONSTELLATION.

This helper validates the local RTL-SDR command-line toolchain and can sample a
small spectrum window without transmitting. It is intentionally independent of
SDR++ so CONSTELLATION can prove the hardware/data path directly.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

RECEIVE_ONLY = True
DEFAULT_CENTER_HZ = 137_900_000
DEFAULT_SPAN_HZ = 200_000
DEFAULT_BIN_HZ = 5_000


def build_rtl_test_command() -> list[str]:
    return ["rtl_test", "-t"]


def build_power_command(center_hz: int, span_hz: int = DEFAULT_SPAN_HZ, bin_hz: int = DEFAULT_BIN_HZ) -> list[str]:
    half = int(span_hz) // 2
    lo = max(1_000, int(center_hz) - half)
    hi = int(center_hz) + half
    return ["rtl_power", "-f", f"{lo}:{hi}:{int(bin_hz)}", "-i", "1", "-1"]


def parse_rtl_test_output(text: str) -> dict:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    device_line = next((line for line in lines if line.lower().startswith("using device")), "")
    found = any("found " in line.lower() and "device" in line.lower() for line in lines)
    detected = bool(device_line) or (found and not any("found 0 device" in line.lower() for line in lines))
    return {
        "device_detected": detected,
        "device": device_line or None,
        "raw": text[-2000:],
    }


def _run(command: list[str], timeout: int = 10) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)


def collect_diagnostics() -> dict:
    tools = {name: bool(shutil.which(name)) for name in ("rtl_test", "rtl_power", "rtl_sdr")}
    state = {
        "ok": False,
        "timestamp": time.time(),
        "receive_only": RECEIVE_ONLY,
        "platform": os.name,
        "tools": tools,
        "device_detected": False,
        "device": None,
    }
    if not tools["rtl_test"]:
        state["error"] = "rtl_test not found on PATH"
        return state

    try:
        proc = _run(build_rtl_test_command())
    except Exception as exc:
        state["error"] = f"rtl_test failed to run: {exc}"
        return state

    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    parsed = parse_rtl_test_output(output)
    state.update({"device_detected": parsed["device_detected"], "device": parsed["device"]})
    state["rtl_test_returncode"] = proc.returncode
    if not parsed["device_detected"]:
        state["error"] = "No RTL-SDR device detected by rtl_test"
        state["rtl_test_output"] = parsed["raw"]
        return state

    state["ok"] = proc.returncode == 0
    if not state["ok"]:
        state["error"] = "RTL-SDR detected, but rtl_test returned an error"
        state["rtl_test_output"] = parsed["raw"]
    return state


def sample_spectrum(center_hz: int, span_hz: int, bin_hz: int) -> dict:
    if not shutil.which("rtl_power"):
        return {"ok": False, "error": "rtl_power not found on PATH", "receive_only": True}
    command = build_power_command(center_hz, span_hz, bin_hz)
    try:
        proc = _run(command, timeout=12)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "receive_only": True, "command": command}
    return {
        "ok": proc.returncode == 0,
        "receive_only": True,
        "command": command,
        "returncode": proc.returncode,
        "stdout": (proc.stdout or "")[-4000:],
        "stderr": (proc.stderr or "")[-2000:],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="UNG-CONSTELLATION Windows RTL-SDR receive-only edge diagnostic")
    parser.add_argument("--center-hz", type=int, default=DEFAULT_CENTER_HZ)
    parser.add_argument("--span-hz", type=int, default=DEFAULT_SPAN_HZ)
    parser.add_argument("--bin-hz", type=int, default=DEFAULT_BIN_HZ)
    parser.add_argument("--scan", action="store_true", help="Run one bounded receive-only rtl_power spectrum sample")
    parser.add_argument("--output", type=Path, help="Optional JSON output file")
    args = parser.parse_args()

    state = collect_diagnostics()
    if args.scan and state.get("device_detected"):
        state["spectrum"] = sample_spectrum(args.center_hz, args.span_hz, args.bin_hz)
        state["ok"] = bool(state.get("ok") and state["spectrum"].get("ok"))

    rendered = json.dumps(state, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    return 0 if state.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
