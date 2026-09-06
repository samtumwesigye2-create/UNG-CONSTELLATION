#!/usr/bin/env python3
"""UNG-CONSTELLATION Raspberry Pi edge agent.
Receive-only by default. Discovers SDR/GNSS/rigctld and reports local node health.
"""
import json, os, shutil, socket, subprocess, time, urllib.request, urllib.error
from pathlib import Path

CONFIG = Path(os.getenv("CONSTELLATION_EDGE_CONFIG", "/etc/ung-constellation/edge.json"))
NO_TRANSMIT = os.getenv("CONSTELLATION_NO_TRANSMIT", "true").lower() != "false"
CLOUD_URL = os.getenv("CONSTELLATION_CLOUD_URL", "https://ung-constellation-production.up.railway.app").rstrip('/')
NODE_ID = os.getenv("CONSTELLATION_NODE_ID", "CONSTELLATION-EDGE-001")
STATION_ID = os.getenv("CONSTELLATION_STATION_ID", "UGANET-GS-001")
OUTBOX = Path(os.getenv("CONSTELLATION_OUTBOX", "/var/lib/ung-constellation/outbox"))

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

def post_json(path,payload,timeout=8):
    data=json.dumps(payload).encode()
    req=urllib.request.Request(CLOUD_URL+path,data=data,headers={'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return r.status, json.loads(r.read().decode() or '{}')

def heartbeat(s):
    capabilities={
        'rtl_sdr':bool((s.get('rtl_sdr') or {}).get('ok')),
        'rigctld':bool((s.get('hamlib') or {}).get('rigctld')),
        'rotctld':bool((s.get('hamlib') or {}).get('rotctld')),
        'gpsd':bool((s.get('gnss') or {}).get('gpsd')),
        'iq_capture':bool((s.get('iq_capture') or {}).get('rtl_sdr_available')),
        'offline_pass_execution':True,
    }
    payload={'node_id':NODE_ID,'station_id':STATION_ID,'hostname':s['hostname'],'receive_only':NO_TRANSMIT,'capabilities':capabilities,'health':s}
    return post_json('/v1/edge/heartbeat',payload)

def flush_outbox():
    OUTBOX.mkdir(parents=True,exist_ok=True)
    sent=0
    for f in sorted(OUTBOX.glob('*.json')):
        try:
            item=json.loads(f.read_text())
            post_json(item['path'],item['payload'])
            f.unlink(); sent+=1
        except Exception:
            break
    return sent

def main():
    s=snapshot(); result={'snapshot':s,'cloud':{'connected':False}}
    try:
        status,response=heartbeat(s)
        result['cloud']={'connected':status<300,'status':status,'response':response,'outbox_flushed':flush_outbox()}
    except Exception as e:
        result['cloud']={'connected':False,'error':str(e)}
    print(json.dumps(result,indent=2))

if __name__ == "__main__": main()
