#!/usr/bin/env python3
"""UNG-CONSTELLATION receive-only IQ/spectrum monitor for RTL-SDR.

Reads Doppler state, samples a narrow RF window with rtl_power, derives peak/noise/SNR,
and optionally captures bounded raw IQ files with rtl_sdr. Never transmits.
"""
import csv, json, math, os, shutil, signal, subprocess, time
from pathlib import Path

NO_TRANSMIT=os.getenv('CONSTELLATION_NO_TRANSMIT','true').lower() not in ('0','false','no')
if not NO_TRANSMIT: raise SystemExit('Refusing to start unless receive-only mode is enabled')
DOPPLER=Path(os.getenv('CONSTELLATION_DOPPLER_STATE','/var/lib/ung-constellation/doppler.json'))
STATE=Path(os.getenv('CONSTELLATION_SPECTRUM_STATE','/var/lib/ung-constellation/spectrum.json'))
IQ_DIR=Path(os.getenv('CONSTELLATION_IQ_DIR','/var/lib/ung-constellation/iq'))
SPAN=max(25000,int(os.getenv('CONSTELLATION_SPECTRUM_SPAN_HZ','200000')))
BIN=max(1000,int(os.getenv('CONSTELLATION_SPECTRUM_BIN_HZ','5000')))
INTERVAL=max(2.0,float(os.getenv('CONSTELLATION_SPECTRUM_SECONDS','10')))
CAPTURE=os.getenv('CONSTELLATION_IQ_CAPTURE','false').lower() in ('1','true','yes')
IQ_SECONDS=max(1,min(60,int(os.getenv('CONSTELLATION_IQ_SECONDS','5'))))
SAMPLE_RATE=max(240000,int(os.getenv('CONSTELLATION_IQ_SAMPLE_RATE','1024000')))
_running=True

def stop(*_):
    global _running; _running=False
signal.signal(signal.SIGTERM,stop); signal.signal(signal.SIGINT,stop)

def atomic(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix('.tmp'); tmp.write_text(json.dumps(obj,indent=2)); tmp.replace(path)

def center_hz():
    d=json.loads(DOPPLER.read_text()); return float(d.get('receive_hz') or d.get('nominal_hz') or 0),d

def scan(center):
    if not shutil.which('rtl_power'): raise RuntimeError('rtl_power not installed')
    lo=max(1000,int(center-SPAN/2)); hi=int(center+SPAN/2)
    cmd=['rtl_power','-f',f'{lo}:{hi}:{BIN}','-i','1','-1']
    p=subprocess.run(cmd,capture_output=True,text=True,timeout=8,check=False)
    if p.returncode!=0: raise RuntimeError((p.stderr or 'rtl_power failed')[-500:])
    rows=[]
    for line in p.stdout.splitlines():
        try:
            r=next(csv.reader([line])); start=float(r[2]); stopf=float(r[3]); step=float(r[4]); powers=[float(x) for x in r[6:] if x.strip()]
            for i,pw in enumerate(powers): rows.append({'frequency_hz':start+i*step,'power_db':pw})
        except Exception: continue
    if not rows: raise RuntimeError('No spectrum bins returned')
    vals=sorted(x['power_db'] for x in rows); noise=vals[max(0,min(len(vals)-1,int(len(vals)*0.35)))]
    peak=max(rows,key=lambda x:x['power_db']); snr=peak['power_db']-noise
    return rows,peak,noise,snr

def capture_iq(center):
    if not CAPTURE or not shutil.which('rtl_sdr'): return None
    IQ_DIR.mkdir(parents=True,exist_ok=True); ts=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime()); out=IQ_DIR/f'iq-{int(center)}-{ts}.cu8'; samples=SAMPLE_RATE*IQ_SECONDS
    p=subprocess.run(['rtl_sdr','-f',str(int(center)),'-s',str(SAMPLE_RATE),'-n',str(samples),str(out)],capture_output=True,text=True,timeout=IQ_SECONDS+10,check=False)
    if p.returncode!=0:
        try: out.unlink()
        except Exception: pass
        return {'ok':False,'error':(p.stderr or '')[-500:]}
    return {'ok':True,'path':str(out),'bytes':out.stat().st_size,'sample_rate':SAMPLE_RATE,'duration_s':IQ_SECONDS}

while _running:
    stamp=time.time()
    try:
        center,dstate=center_hz()
        if center<=0: raise RuntimeError('No valid Doppler receive frequency available')
        bins,peak,noise,snr=scan(center); iq=capture_iq(center)
        state={'ok':True,'timestamp':stamp,'center_hz':center,'span_hz':SPAN,'bin_hz':BIN,'peak':peak,'noise_floor_db':noise,'snr_db':snr,'bins':bins,'iq_capture':iq,'receive_only':True,'norad_id':dstate.get('norad_id')}
    except Exception as e:
        state={'ok':False,'timestamp':stamp,'error':str(e),'receive_only':True}
    atomic(STATE,state); print(json.dumps({k:v for k,v in state.items() if k!='bins'}),flush=True); time.sleep(INTERVAL)
