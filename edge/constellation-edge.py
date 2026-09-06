#!/usr/bin/env python3
"""UNG-CONSTELLATION Raspberry Pi edge agent.
Receive-only by default. Discovers SDR/GNSS/rigctld and reports local node health.
"""
import json, os, shutil, socket, subprocess, time
from pathlib import Path

CONFIG = Path(os.getenv("CONSTELLATION_EDGE_CONFIG", "/etc/ung-constellation/edge.json"))
NO_TRANSMIT = os.getenv("CONSTELLATION_NO_TRANSMIT", "true").lower() != "false"

def cmd_exists(name): return shutil.which(name) is not None

def run(args, timeout=5):
    try:
        p=subprocess.run(args,capture_output=True,text=True,timeout=timeout,check=False)
        return {"ok":p.returncode==0,"rc":p.returncode,"stdout":p.stdout[-4000:],"stderr":p.stderr[-2000:]}
    except Exception as e: return {"ok":False,"error":str(e)}

def tcp_probe(host,port):
    try:
        with socket.create_connection((host,port),timeout=1): return True
    except OSError: return False

def snapshot():
    sdr = run(["rtl_test","-t"],8) if cmd_exists("rtl_test") else {"ok":False,"reason":"rtl_test not installed"}
    return {
      "service":"UNG-CONSTELLATION-EDGE",
      "hostname":socket.gethostname(),
      "receive_only":NO_TRANSMIT,
      "rtl_sdr":sdr,
      "hamlib":{"rigctld":tcp_probe("127.0.0.1",4532),"rotctld":tcp_probe("127.0.0.1",4533)},
      "gnss":{"gpsd":tcp_probe("127.0.0.1",2947)},
      "kiss":{"configured":False,"note":"KISS TNC transport adapter reserved; disabled until hardware is configured"},
      "iq_capture":{"rtl_sdr_available":cmd_exists("rtl_sdr")},
      "offline_pass_execution":{"enabled":True,"queue":"/var/lib/ung-constellation/passes"},
      "timestamp":time.time()
    }

if __name__ == "__main__": print(json.dumps(snapshot(),indent=2))
