#!/usr/bin/env python3
"""UNG-CONSTELLATION edge agent: authenticated receive-only health + automatic pass archive lifecycle."""
import json,os,shutil,socket,subprocess,sys,time,urllib.request
from pathlib import Path
NO_TRANSMIT=os.getenv('CONSTELLATION_NO_TRANSMIT','true').lower()!='false';CLOUD_URL=os.getenv('CONSTELLATION_CLOUD_URL','https://ung-constellation-production.up.railway.app').rstrip('/');EDGE_API_KEY=os.getenv('CONSTELLATION_EDGE_API_KEY','');NODE_ID=os.getenv('CONSTELLATION_NODE_ID','CONSTELLATION-EDGE-001');STATION_ID=os.getenv('CONSTELLATION_STATION_ID','UGANET-GS-001');OUTBOX=Path(os.getenv('CONSTELLATION_OUTBOX','/var/lib/ung-constellation/outbox'));SPECTRUM_STATE=Path(os.getenv('CONSTELLATION_SPECTRUM_STATE','/var/lib/ung-constellation/spectrum.json'));DOPPLER_STATE=Path(os.getenv('CONSTELLATION_DOPPLER_STATE','/var/lib/ung-constellation/doppler.json'));SESSION_STATE=Path(os.getenv('CONSTELLATION_SESSION_STATE','/var/lib/ung-constellation/pass-session.json'));INTERVAL=max(10,int(os.getenv('CONSTELLATION_HEARTBEAT_SECONDS','15')));MIN_EL=float(os.getenv('CONSTELLATION_PASS_MIN_ELEVATION_DEG','0'))
def cmd_exists(n):return shutil.which(n) is not None
def run(a,timeout=5):
 try:
  p=subprocess.run(a,capture_output=True,text=True,timeout=timeout,check=False);return {'ok':p.returncode==0,'rc':p.returncode,'stdout':p.stdout[-4000:],'stderr':p.stderr[-2000:]}
 except Exception as e:return {'ok':False,'error':str(e)}
def tcp_probe(h,p):
 try:
  with socket.create_connection((h,p),timeout=1):return True
 except OSError:return False
def read_json(p):
 try:return json.loads(p.read_text())
 except Exception:return None
def write_json(p,v):
 p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix('.tmp');t.write_text(json.dumps(v));t.replace(p)
def rf_state():
 s=read_json(SPECTRUM_STATE);d=read_json(DOPPLER_STATE)
 if not s and not d:return {'available':False}
 out={'available':True,'spectrum':None,'doppler':None}
 if d:out['doppler']={k:d.get(k) for k in ('ok','timestamp','norad_id','nominal_hz','receive_hz','doppler_shift_hz','radial_velocity_m_s','azimuth_deg','elevation_deg','range_km','hardware_tuned','mode')}
 if s:
  bins=s.get('bins') or []
  if len(bins)>160:
   step=max(1,len(bins)//160);bins=bins[::step][:160]
  out['spectrum']={'ok':s.get('ok'),'timestamp':s.get('timestamp'),'center_hz':s.get('center_hz'),'span_hz':s.get('span_hz'),'bin_hz':s.get('bin_hz'),'peak':s.get('peak'),'noise_floor_db':s.get('noise_floor_db'),'snr_db':s.get('snr_db'),'norad_id':s.get('norad_id'),'bins':bins,'iq_capture':s.get('iq_capture')}
 return out
def snapshot():
 sdr=run(['rtl_test','-t'],8) if cmd_exists('rtl_test') else {'ok':False,'reason':'rtl_test not installed'}
 return {'service':'UNG-CONSTELLATION-EDGE','hostname':socket.gethostname(),'receive_only':NO_TRANSMIT,'rtl_sdr':sdr,'hamlib':{'rigctld':tcp_probe('127.0.0.1',4532),'rotctld':tcp_probe('127.0.0.1',4533)},'gnss':{'gpsd':tcp_probe('127.0.0.1',2947)},'kiss':{'configured':False},'iq_capture':{'rtl_sdr_available':cmd_exists('rtl_sdr')},'rf':rf_state(),'offline_pass_execution':{'enabled':True,'queue':'/var/lib/ung-constellation/passes'},'timestamp':time.time()}
def post_json(path,payload,timeout=8):
 headers={'Content-Type':'application/json'}
 if EDGE_API_KEY:headers['X-Edge-Key']=EDGE_API_KEY
 req=urllib.request.Request(CLOUD_URL+path,data=json.dumps(payload).encode(),headers=headers,method='POST')
 with urllib.request.urlopen(req,timeout=timeout) as r:return r.status,json.loads(r.read().decode() or '{}')
def heartbeat(s):
 cap={'rtl_sdr':bool((s.get('rtl_sdr') or {}).get('ok')),'rigctld':bool((s.get('hamlib') or {}).get('rigctld')),'rotctld':bool((s.get('hamlib') or {}).get('rotctld')),'gpsd':bool((s.get('gnss') or {}).get('gpsd')),'iq_capture':bool((s.get('iq_capture') or {}).get('rtl_sdr_available')),'spectrum':bool((((s.get('rf') or {}).get('spectrum') or {}).get('ok'))),'offline_pass_execution':True};return post_json('/v1/edge/heartbeat',{'node_id':NODE_ID,'station_id':STATION_ID,'hostname':s['hostname'],'receive_only':NO_TRANSMIT,'capabilities':cap,'health':s})
def queue(path,payload):
 OUTBOX.mkdir(parents=True,exist_ok=True);write_json(OUTBOX/(str(int(time.time()*1000))+'.json'),{'path':path,'payload':payload})
def flush_outbox():
 OUTBOX.mkdir(parents=True,exist_ok=True);sent=0
 for f in sorted(OUTBOX.glob('*.json')):
  try:
   i=json.loads(f.read_text());post_json(i['path'],i['payload']);f.unlink();sent+=1
  except Exception:break
 return sent
def pass_lifecycle(s):
 rf=(s.get('rf') or {});d=rf.get('doppler') or {};sp=rf.get('spectrum') or {};active=bool(d.get('ok')) and float(d.get('elevation_deg') or -90)>=MIN_EL and bool(d.get('norad_id'));session=read_json(SESSION_STATE)
 if active and not session:
  write_json(SESSION_STATE,{'norad_id':str(d.get('norad_id')),'started':time.time(),'started_iso':d.get('timestamp'),'max_snr_db':sp.get('snr_db'),'receive_only':True});return 'started'
 if active and session:
  if sp.get('snr_db') is not None:session['max_snr_db']=max(float(session.get('max_snr_db') or -999),float(sp['snr_db']));write_json(SESSION_STATE,session)
  return 'active'
 if not active and session:
  mins=max(2,int((time.time()-float(session.get('started',time.time())))/60)+3);payload={'node_id':NODE_ID,'station_id':STATION_ID,'norad_id':session.get('norad_id'),'minutes':mins,'iq_reference':None}
  try:post_json('/v1/edge/receptions/archive',payload)
  except Exception:queue('/v1/edge/receptions/archive',payload)
  try:SESSION_STATE.unlink()
  except Exception:pass
  return 'archived'
 return 'idle'
def cycle():
 s=snapshot();state=pass_lifecycle(s);result={'snapshot':s,'pass_session':state,'cloud':{'connected':False}}
 try:
  status,response=heartbeat(s);result['cloud']={'connected':status<300,'status':status,'response':response,'outbox_flushed':flush_outbox()}
 except Exception as e:result['cloud']={'connected':False,'error':str(e)}
 print(json.dumps(result),flush=True)
def main():
 if not NO_TRANSMIT:raise SystemExit('Refusing to run: CONSTELLATION_NO_TRANSMIT must remain true')
 if not EDGE_API_KEY:raise SystemExit('Refusing to run: CONSTELLATION_EDGE_API_KEY is required')
 if '--daemon' not in sys.argv:cycle();return
 while True:cycle();time.sleep(INTERVAL)
if __name__=='__main__':main()
