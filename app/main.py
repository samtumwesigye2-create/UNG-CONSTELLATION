import os
from fastapi import FastAPI, Body, Depends, HTTPException
from fastapi.responses import HTMLResponse
from . import db, ccsds, integrations, operations, orbit, catalog
from .security import require_role
from .tracker_api import router as tracker_router
app=FastAPI(title='UNG-CONSTELLATION',version='1.9.0');NO_TRANSMIT=os.getenv('CONSTELLATION_NO_TRANSMIT','true').lower() not in ('0','false','no')
app.include_router(tracker_router)
@app.on_event('startup')
def startup():
 try:db.init_db()
 except Exception:pass
@app.get('/')
def root():return {'service':'UNG-CONSTELLATION','version':'1.9.0','no_transmit':NO_TRANSMIT,'mission_control':'/mission-control','sat_tracker_engine':'/v1/tracker/snapshot'}
@app.get('/health')
def health():return {'status':'ok','service':'UNG-CONSTELLATION'}
@app.get('/ready')
def ready():
 d=db.readiness();return {'ready':(not d['configured']) or d['connected'],'database':d,'integrations':integrations.status(),'no_transmit':NO_TRANSMIT}
@app.get('/v1/system')
def system():return {'service':'UNG-CONSTELLATION','version':'1.9.0','integrations':integrations.status(),'no_transmit':NO_TRANSMIT,'sat_tracker_paired':True}
@app.get('/v1/catalog/search')
def catalog_search(q:str,limit:int=20):
 if len((q or '').strip())<2:raise HTTPException(400,'q must contain at least 2 characters')
 try:
  rows=catalog.search_name(q,max(1,min(limit,50)));return {'query':q,'count':len(rows),'satellites':[{'norad_id':x['norad_id'],'name':x['name'],'source':x['source']} for x in rows]}
 except Exception as e:raise HTTPException(502,f'Catalog lookup failed: {e}')
@app.get('/v1/catalog/track')
def catalog_track(norad_id:str,lat:float,lon:float,elevation_m:float=0,hours:int=24,min_elevation_deg:float=10):
 try:
  t=catalog.fetch_by_catnr(norad_id);return {'satellite':t['name'],'norad_id':t['norad_id'],'source':t['source'],'position':orbit.position(t['name'],t['line1'],t['line2'],lat,lon,elevation_m),'passes':orbit.passes(t['name'],t['line1'],t['line2'],lat,lon,elevation_m,hours,min_elevation_deg)}
 except Exception as e:raise HTTPException(502,f'Tracking lookup failed: {e}')
@app.get('/v1/catalog/ground-track')
def ground(norad_id:str,minutes_before:int=45,minutes_after:int=90,step_seconds:int=60):
 try:
  t=catalog.fetch_by_catnr(norad_id);return {'satellite':t['name'],'norad_id':t['norad_id'],'points':orbit.ground_track(t['name'],t['line1'],t['line2'],minutes_before,minutes_after,step_seconds)}
 except Exception as e:raise HTTPException(502,str(e))
@app.get('/v1/catalog/doppler')
def doppler(norad_id:str,lat:float,lon:float,frequency_hz:float,elevation_m:float=0):
 try:
  t=catalog.fetch_by_catnr(norad_id);return {'satellite':t['name'],'norad_id':t['norad_id'],'doppler':orbit.doppler(t['name'],t['line1'],t['line2'],lat,lon,frequency_hz,elevation_m),'no_transmit':True}
 except Exception as e:raise HTTPException(502,str(e))
@app.get('/v1/rf/history')
def rf_history(node_id:str='CONSTELLATION-EDGE-001',minutes:int=30,limit:int=240):return {'node_id':node_id,'samples':db.rf_history(node_id,minutes,limit)}
@app.get('/v1/receptions')
def receptions(limit:int=50):return {'receptions':db.list_archives(limit)}
@app.post('/v1/receptions/archive')
def archive(node_id:str=Body(default='CONSTELLATION-EDGE-001'),norad_id:str|None=Body(default=None),satellite:str|None=Body(default=None),minutes:int=Body(default=30),station_id:str=Body(default='UGANET-GS-001'),iq_reference:str|None=Body(default=None),user=Depends(require_role('operator'))):
 aid=db.archive_recent_pass(node_id,norad_id,satellite,minutes,station_id,iq_reference)
 if aid is None:raise HTTPException(404,'No RF samples found for requested pass window')
 db.audit(user.get('sub'),'reception.archive',str(aid),{'node_id':node_id,'norad_id':norad_id,'receive_only':True});return {'accepted':True,'archive_id':aid,'no_transmit':True}
@app.get('/v1/edge/nodes')
def edge_nodes():return {'nodes':db.list_edge_nodes()}
@app.post('/v1/edge/heartbeat')
def edge_heartbeat(node_id:str=Body(...),station_id:str=Body(default='UGANET-GS-001'),hostname:str=Body(...),receive_only:bool=Body(default=True),capabilities:dict=Body(default={}),health:dict=Body(default={})):
 if not receive_only and NO_TRANSMIT:raise HTTPException(403,'Cloud policy requires receive-only edge mode')
 db.edge_heartbeat(node_id,station_id,hostname,receive_only,capabilities,health);return {'accepted':True,'node_id':node_id,'cloud_no_transmit':NO_TRANSMIT}
@app.get('/mission-control',response_class=HTMLResponse)
def mc():return '''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>UNG-CONSTELLATION</title><style>body{font-family:system-ui;background:#06111d;color:#e8f1fb;margin:0}.w{max-width:1200px;margin:auto;padding:14px}.c{background:#0c1b29;border:1px solid #24506d;border-radius:15px;padding:15px;margin:12px 0}.m{color:#91a8bb}.warn{color:#ffd166}input,button{padding:10px;margin:3px;border-radius:8px;border:1px solid #315b77;background:#07131f;color:white}button{font-weight:700}.g{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.x{background:#07131f;padding:10px;border-radius:9px}canvas{width:100%;height:300px;background:#07131f;border-radius:10px}.row{padding:9px;border-bottom:1px solid #18364c;cursor:pointer}@media(max-width:700px){.g{grid-template-columns:1fr 1fr}}</style></head><body><div class="w"><h2>UNG-CONSTELLATION · Mission Control</h2><div class="c"><b>RF SAFETY <span class="warn">NO TRANSMIT</span></b> · UGANET-GS-001 · Sat-Tracker Engine Paired</div><div class="c"><h3>Satellite Tracking</h3><input id="q" placeholder="Satellite"><button id="search">SEARCH</button><div id="res"></div><input id="norad" placeholder="NORAD"><input id="lat" placeholder="Latitude"><input id="lon" placeholder="Longitude"><input id="freq" placeholder="Receive Hz"><button id="track">TRACK</button><p id="status" class="m"></p></div><div class="c"><h3>RF Signal</h3><div class="g"><div class="x">EDGE<br><b id="edge">WAITING</b></div><div class="x">SNR<br><b id="snr">--</b></div><div class="x">PEAK<br><b id="peak">--</b></div><div class="x">NOISE<br><b id="noise">--</b></div></div></div><div class="c"><h3>Live Spectrum</h3><canvas id="sp"></canvas></div><div class="c"><h3>RF Waterfall / Replay</h3><canvas id="wf"></canvas><p id="wfmeta" class="m">Live 30-minute PostgreSQL history</p></div><div class="c"><h3>Completed Passes</h3><button id="reload">REFRESH ARCHIVES</button><div id="archives" class="m">No archived passes yet.</div></div><div class="c"><h3>Orbital Map</h3><canvas id="map"></canvas></div><div class="c"><h3>Upcoming Passes</h3><div id="passes" class="m"></div></div></div><script>const E=id=>document.getElementById(id);let timer;function spectrum(c,b){let x=c.getContext('2d'),r=c.getBoundingClientRect(),w=r.width,h=r.height;c.width=w*devicePixelRatio;c.height=h*devicePixelRatio;x.scale(devicePixelRatio,devicePixelRatio);x.fillStyle='#07131f';x.fillRect(0,0,w,h);if(!b||b.length<2)return;let v=b.map(z=>+z.power_db),mn=Math.min(...v),mx=Math.max(...v);x.strokeStyle='#68e3a1';x.beginPath();b.forEach((z,i)=>{let xx=i/(b.length-1)*w,yy=h-(+z.power_db-mn)/(mx-mn||1)*(h-20)-10;i?x.lineTo(xx,yy):x.moveTo(xx,yy)});x.stroke()}function waterfall(s){let c=E('wf'),x=c.getContext('2d'),r=c.getBoundingClientRect(),w=r.width,h=r.height;c.width=w*devicePixelRatio;c.height=h*devicePixelRatio;x.scale(devicePixelRatio,devicePixelRatio);x.fillStyle='#07131f';x.fillRect(0,0,w,h);let all=s.flatMap(a=>(a.bins||[]).map(b=>+b.power_db));if(!all.length)return;let mn=Math.min(...all),mx=Math.max(...all),rh=h/s.length;s.forEach((a,j)=>(a.bins||[]).forEach((z,i)=>{let n=(+z.power_db-mn)/(mx-mn||1);x.fillStyle='hsl('+(240-240*n)+',90%,'+(25+40*n)+'%)';x.fillRect(i/a.bins.length*w,j*rh,w/a.bins.length+1,rh+1)}))}async function rf(){try{let j=await fetch('/v1/edge/nodes').then(r=>r.json()),n=(j.nodes||[])[0],s=(((n||{}).health||{}).rf||{}).spectrum||{};E('edge').textContent=s.ok?'ONLINE':'WAITING';E('snr').textContent=s.ok?(+s.snr_db).toFixed(1)+' dB':'--';E('peak').textContent=s.ok?(+(s.peak||{}).power_db).toFixed(1)+' dB':'--';E('noise').textContent=s.ok?(+s.noise_floor_db).toFixed(1)+' dB':'--';spectrum(E('sp'),s.bins||[]);let h=await fetch('/v1/rf/history?minutes=30&limit=180').then(r=>r.json());waterfall(h.samples||[])}catch(e){E('edge').textContent='OFFLINE'}}async function archives(){let j=await fetch('/v1/receptions?limit=30').then(r=>r.json()),a=j.receptions||[];E('archives').innerHTML=a.length?a.map(v=>'<div class="row" data-n="'+(v.norad_id||'')+'" data-min="'+Math.max(1,Math.ceil((new Date(v.end_time)-new Date(v.start_time))/60000)+2)+'">#'+v.id+' · '+(v.satellite||('NORAD '+v.norad_id))+' · '+v.sample_count+' samples · MAX SNR '+Number(v.max_snr_db||0).toFixed(1)+' dB</div>').join(''):'No archived passes yet.';E('archives').querySelectorAll('.row').forEach(r=>r.onclick=async()=>{let h=await fetch('/v1/rf/history?node_id=CONSTELLATION-EDGE-001&minutes='+r.dataset.min+'&limit=1000').then(x=>x.json());let s=(h.samples||[]).filter(x=>!r.dataset.n||x.norad_id==r.dataset.n);waterfall(s);E('wfmeta').textContent='ARCHIVE REPLAY · '+s.length+' RF samples'})}E('reload').onclick=archives;E('search').onclick=async()=>{let j=await fetch('/v1/catalog/search?q='+encodeURIComponent(E('q').value)).then(r=>r.json());E('res').innerHTML=(j.satellites||[]).map(s=>'<div data-n="'+s.norad_id+'">'+s.name+' · '+s.norad_id+'</div>').join('');E('res').querySelectorAll('[data-n]').forEach(d=>d.onclick=()=>E('norad').value=d.dataset.n)};function omap(points,p,la,lo){let c=E('map'),x=c.getContext('2d'),r=c.getBoundingClientRect(),w=r.width,h=r.height;c.width=w*devicePixelRatio;c.height=h*devicePixelRatio;x.scale(devicePixelRatio,devicePixelRatio);x.fillStyle='#07131f';x.fillRect(0,0,w,h);x.strokeStyle='#68e3a1';x.beginPath();let last=null;points.forEach(z=>{let xx=(z.lon+180)/360*w,yy=(90-z.lat)/180*h;if(last!==null&&Math.abs(xx-last)>w/2){x.stroke();x.beginPath()}x.lineTo(xx,yy);last=xx});x.stroke()}E('track').onclick=async function go(){let id=E('norad').value,la=+E('lat').value,lo=+E('lon').value;if(!id)return;let t=await fetch('/v1/tracker/snapshot?norad_id='+id+'&lat='+la+'&lon='+lo).then(r=>r.json()),p=t.position;E('status').textContent=t.satellite+' · AZ '+p.azimuth_deg.toFixed(1)+'° · EL '+p.elevation_deg.toFixed(1)+'° · RANGE '+p.range_km.toFixed(0)+' km · TLE '+Number(t.metadata.tle_age_days).toFixed(1)+'d';omap(t.ground_track||[],p,la,lo);E('passes').innerHTML=(t.passes||[]).slice(0,8).map(v=>v.rise.time+' · MAX '+Number(v.max_elevation_deg).toFixed(1)+'°<br>').join('');let f=+E('freq').value;if(f>0){let d=await fetch('/v1/catalog/doppler?norad_id='+id+'&lat='+la+'&lon='+lo+'&frequency_hz='+f).then(r=>r.json());E('status').textContent+=' · RX '+(d.doppler.receive_frequency_hz/1e6).toFixed(6)+' MHz'}clearTimeout(timer);timer=setTimeout(go,5000)};rf();archives();setInterval(rf,10000)</script></body></html>'''
@app.post('/v1/tle')
def save_tle(norad_id:str=Body(...),name:str=Body(...),line1:str=Body(...),line2:str=Body(...),source:str=Body(default='manual'),user=Depends(require_role('operator'))):db.upsert_tle(norad_id,name,line1,line2,source);return {'accepted':True}
@app.post('/v1/orbit/position')
def orbital_position(norad_id:str=Body(...),lat:float=Body(...),lon:float=Body(...),elevation_m:float=Body(default=0),at:str|None=Body(default=None),user=Depends(require_role('observer'))):
 t=db.get_tle(norad_id)
 if not t:raise HTTPException(404,'TLE not found')
 return orbit.position(t['name'],t['line1'],t['line2'],lat,lon,elevation_m,at)
@app.post('/v1/orbit/passes')
def pp(norad_id:str=Body(...),station_id:str=Body(default='UGANET-GS-001'),lat:float=Body(...),lon:float=Body(...),elevation_m:float=Body(default=0),hours:int=Body(default=24),min_elevation_deg:float=Body(default=10),persist:bool=Body(default=True),user=Depends(require_role('observer'))):
 t=db.get_tle(norad_id)
 if not t:raise HTTPException(404,'TLE not found')
 ps=orbit.passes(t['name'],t['line1'],t['line2'],lat,lon,elevation_m,hours,min_elevation_deg)
 if persist:
  for p in ps:db.save_pass_plan(t['name'],norad_id,station_id,p)
 return {'passes':ps}
@app.post('/v1/ccsds/decode')
def decode(payload_hex:str=Body(...,embed=True),user=Depends(require_role('observer'))):return ccsds.decode_space_packet(bytes.fromhex(payload_hex))
@app.post('/v1/telemetry')
def telemetry(satellite:str=Body(...),station_id:str|None=Body(default=None),protocol:str=Body(default='ccsds'),payload:dict=Body(default={}),user=Depends(require_role('operator'))):db.save_telemetry(satellite,station_id,protocol,payload);return {'accepted':True}
@app.post('/v1/telemetry/alarms/evaluate')
def alarms(fields:dict=Body(...),limits:dict=Body(...),user=Depends(require_role('operator'))):return {'alarms':operations.telemetry_alarms(fields,limits)}
@app.post('/v1/network/select-station')
def station(pass_candidates:list=Body(...),stations:dict=Body(...),station_health:dict=Body(default={}),user=Depends(require_role('operator'))):return {'selected':operations.choose_station(pass_candidates,stations,station_health)}
@app.post('/v1/cdm')
def cdm(cdm:dict=Body(...),user=Depends(require_role('mission_controller'))):db.save_cdm(cdm);return {'accepted':True}
@app.post('/v1/commands/validate')
def command(command:dict=Body(...),schema:dict=Body(...),approvals:list=Body(default=[]),user=Depends(require_role('mission_controller'))):return operations.validate_command(command,schema,approvals,NO_TRANSMIT)
