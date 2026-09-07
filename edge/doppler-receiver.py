#!/usr/bin/env python3
"""UNG-CONSTELLATION receive-only Doppler controller.

Polls cloud Doppler predictions and keeps a local receive-frequency plan. If
SoapySDR is installed and an RTL-SDR is present, it dynamically tunes the
receiver. Otherwise it remains in plan-only mode and never transmits.
"""
import json, os, signal, sys, time, urllib.parse, urllib.request
from pathlib import Path

CLOUD_URL=os.getenv('CONSTELLATION_CLOUD_URL','https://ung-constellation-production.up.railway.app').rstrip('/')
NORAD_ID=os.getenv('CONSTELLATION_NORAD_ID','').strip()
LAT=float(os.getenv('CONSTELLATION_STATION_LAT','0'))
LON=float(os.getenv('CONSTELLATION_STATION_LON','0'))
ELEVATION_M=float(os.getenv('CONSTELLATION_STATION_ELEVATION_M','0'))
NOMINAL_HZ=float(os.getenv('CONSTELLATION_RECEIVE_FREQUENCY_HZ','0'))
INTERVAL=max(1.0,float(os.getenv('CONSTELLATION_DOPPLER_SECONDS','5')))
STATE=Path(os.getenv('CONSTELLATION_DOPPLER_STATE','/var/lib/ung-constellation/doppler.json'))
NO_TRANSMIT=os.getenv('CONSTELLATION_NO_TRANSMIT','true').lower() not in ('0','false','no')
_running=True

if not NO_TRANSMIT:
    raise SystemExit('Refusing to start: CONSTELLATION_NO_TRANSMIT must remain true')
if not NORAD_ID or NOMINAL_HZ<=0:
    raise SystemExit('Set CONSTELLATION_NORAD_ID and CONSTELLATION_RECEIVE_FREQUENCY_HZ')

class Receiver:
    def __init__(self):
        self.dev=None; self.mode='plan-only'; self.error=None
        try:
            import SoapySDR
            from SoapySDR import SOAPY_SDR_RX
            self.SoapySDR=SoapySDR; self.RX=SOAPY_SDR_RX
            self.dev=SoapySDR.Device(dict(driver='rtlsdr'))
            self.mode='soapy-rtlsdr'
        except Exception as e:
            self.error=str(e)
    def tune(self,hz):
        if not self.dev: return False
        self.dev.setFrequency(self.RX,0,float(hz)); return True

def cloud_doppler():
    qs=urllib.parse.urlencode({'norad_id':NORAD_ID,'lat':LAT,'lon':LON,'elevation_m':ELEVATION_M,'frequency_hz':NOMINAL_HZ})
    with urllib.request.urlopen(CLOUD_URL+'/v1/catalog/doppler?'+qs,timeout=10) as r:
        return json.loads(r.read().decode())

def save_state(payload):
    STATE.parent.mkdir(parents=True,exist_ok=True)
    tmp=STATE.with_suffix('.tmp'); tmp.write_text(json.dumps(payload,indent=2)); tmp.replace(STATE)

def stop(*_):
    global _running; _running=False

signal.signal(signal.SIGTERM,stop); signal.signal(signal.SIGINT,stop)
rx=Receiver()

while _running:
    stamp=time.time()
    try:
        result=cloud_doppler(); d=result['doppler']; hz=float(d['receive_frequency_hz'])
        tuned=rx.tune(hz)
        state={'ok':True,'timestamp':stamp,'mode':rx.mode,'norad_id':NORAD_ID,'nominal_hz':NOMINAL_HZ,'receive_hz':hz,'doppler_shift_hz':d['doppler_shift_hz'],'radial_velocity_m_s':d['radial_velocity_m_s'],'azimuth_deg':d['azimuth_deg'],'elevation_deg':d['elevation_deg'],'range_km':d['range_km'],'hardware_tuned':tuned,'receive_only':True,'receiver_error':rx.error}
    except Exception as e:
        state={'ok':False,'timestamp':stamp,'mode':rx.mode,'norad_id':NORAD_ID,'error':str(e),'receive_only':True,'receiver_error':rx.error}
    save_state(state); print(json.dumps(state),flush=True); time.sleep(INTERVAL)
