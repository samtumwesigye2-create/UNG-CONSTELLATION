#!/usr/bin/env python3
"""Read-only Hamlib observer for UNG-CONSTELLATION edge nodes.
Queries rigctld/rotctld state only; never issues tune, mode, PTT, or position commands.
"""
import json,os,socket,time
from pathlib import Path
HOST=os.getenv('HAMLIB_HOST','127.0.0.1');RIG_PORT=int(os.getenv('HAMLIB_RIG_PORT','4532'));ROT_PORT=int(os.getenv('HAMLIB_ROT_PORT','4533'));OUT=Path(os.getenv('CONSTELLATION_HAMLIB_STATE','/var/lib/ung-constellation/hamlib.json'));INTERVAL=max(2,int(os.getenv('CONSTELLATION_HAMLIB_SECONDS','5')))

def query(port,cmd):
 try:
  with socket.create_connection((HOST,port),timeout=2) as s:
   s.sendall((cmd+'\n').encode());return s.recv(4096).decode(errors='replace').strip()
 except Exception:return None

def snapshot():
 f=query(RIG_PORT,'f');p=query(ROT_PORT,'p');freq=None;az=None;el=None
 try:freq=float((f or '').splitlines()[0])
 except Exception:pass
 try:
  q=(p or '').splitlines();az=float(q[0]);el=float(q[1])
 except Exception:pass
 return {'timestamp':time.time(),'receive_only':True,'rigctld':{'reachable':f is not None,'frequency_hz':freq},'rotctld':{'reachable':p is not None,'azimuth_deg':az,'elevation_deg':el}}

def write(v):
 OUT.parent.mkdir(parents=True,exist_ok=True);tmp=OUT.with_suffix('.tmp');tmp.write_text(json.dumps(v));tmp.replace(OUT)

def main():
 once='--daemon' not in __import__('sys').argv
 while True:
  v=snapshot();write(v);print(json.dumps(v),flush=True)
  if once:return
  time.sleep(INTERVAL)
if __name__=='__main__':main()
