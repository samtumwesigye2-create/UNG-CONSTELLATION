import os
from fastapi import FastAPI, Body, Depends, HTTPException
from fastapi.responses import HTMLResponse
from . import db, ccsds, integrations, operations, orbit, catalog
from .security import require_role

app=FastAPI(title='UNG-CONSTELLATION',version='1.6.0')
NO_TRANSMIT=os.getenv('CONSTELLATION_NO_TRANSMIT','true').lower() not in ('0','false','no')

@app.on_event('startup')
def startup():
    try: db.init_db()
    except Exception: pass

@app.get('/')
def root(): return {'service':'UNG-CONSTELLATION','name':'National Satellite & Orbital Operations System','version':'1.6.0','no_transmit':NO_TRANSMIT,'mission_control':'/mission-control'}
@app.get('/health')
def health(): return {'status':'ok','service':'UNG-CONSTELLATION'}
@app.get('/ready')
def ready():
    d=db.readiness(); return {'ready':(not d['configured']) or d['connected'],'database':d,'integrations':integrations.status(),'no_transmit':NO_TRANSMIT}
@app.get('/v1/system')
def system(): return {'service':'UNG-CONSTELLATION','mission':'Satellite tracking, orbital operations, ground-station coordination and telemetry','version':'1.6.0','integrations':integrations.status(),'no_transmit':NO_TRANSMIT}
@app.get('/v1/catalog/search')
def catalog_search(q:str,limit:int=20):
    q=(q or '').strip()
    if len(q)<2: raise HTTPException(400,'q must contain at least 2 characters')
    try:
        rows=catalog.search_name(q,max(1,min(limit,50))); return {'query':q,'count':len(rows),'satellites':[{'norad_id':x['norad_id'],'name':x['name'],'source':x['source']} for x in rows]}
    except Exception as e: raise HTTPException(502,f'Catalog lookup failed: {e}')
@app.get('/v1/catalog/track')
def catalog_track(norad_id:str,lat:float,lon:float,elevation_m:float=0.0,hours:int=24,min_elevation_deg:float=10.0):
    try:
        tle=catalog.fetch_by_catnr(norad_id); pos=orbit.position(tle['name'],tle['line1'],tle['line2'],lat,lon,elevation_m); ps=orbit.passes(tle['name'],tle['line1'],tle['line2'],lat,lon,elevation_m,hours,min_elevation_deg)
        return {'satellite':tle['name'],'norad_id':tle['norad_id'],'source':tle['source'],'position':pos,'passes':ps}
    except Exception as e: raise HTTPException(502,f'Tracking lookup failed: {e}')
@app.get('/v1/catalog/ground-track')
def catalog_ground_track(norad_id:str,minutes_before:int=45,minutes_after:int=90,step_seconds:int=60):
    try:
        tle=catalog.fetch_by_catnr(norad_id); points=orbit.ground_track(tle['name'],tle['line1'],tle['line2'],minutes_before,minutes_after,step_seconds)
        return {'satellite':tle['name'],'norad_id':tle['norad_id'],'source':tle['source'],'points':points}
    except Exception as e: raise HTTPException(502,f'Ground-track lookup failed: {e}')
@app.get('/v1/catalog/doppler')
def catalog_doppler(norad_id:str,lat:float,lon:float,frequency_hz:float,elevation_m:float=0.0):
    try:
        tle=catalog.fetch_by_catnr(norad_id); d=orbit.doppler(tle['name'],tle['line1'],tle['line2'],lat,lon,frequency_hz,elevation_m)
        return {'satellite':tle['name'],'norad_id':tle['norad_id'],'source':tle['source'],'doppler':d,'no_transmit':True}
    except ValueError as e: raise HTTPException(400,str(e))
    except Exception as e: raise HTTPException(502,f'Doppler lookup failed: {e}')

@app.get('/mission-control',response_class=HTMLResponse)
def mission_control():
 return '''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>UNG-CONSTELLATION</title><style>*{box-sizing:border-box}body{font-family:system-ui;background:#06111d;color:#e8f1fb;margin:0}.bar{padding:18px;background:#0c1b2a}.wrap{padding:14px;max-width:1200px;margin:auto}.card{background:#0c1b29;border:1px solid #24506d;border-radius:16px;padding:16px;margin-bottom:12px}.ok{color:#68e3a1}.warn{color:#ffd166}.bad{color:#ff7b7b}.muted{color:#91a8bb}.search{display:flex;gap:8px;flex-wrap:wrap}input{flex:1;min-width:140px;background:#07131f;color:#fff;border:1px solid #315b77;border-radius:9px;padding:11px}button{padding:11px 14px;border:0;border-radius:9px;font-weight:700}#map,#spectrumBox{width:100%;height:340px;background:#07131f;border-radius:12px;position:relative;overflow:hidden}canvas{width:100%;height:100%}.metric{font-size:20px;font-weight:700}.rfgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.mini{background:#07131f;border-radius:10px;padding:12px}.big{font-size:24px;font-weight:800}@media(max-width:700px){.rfgrid{grid-template-columns:1fr 1fr}}</style></head><body><div class="bar"><h2>UNG-CONSTELLATION · Mission Control</h2><div class="muted">Orbital Tracking · Ground Track · Receive-Only Doppler · RF Spectrum</div></div><div class="wrap"><div class="card"><b>RF SAFETY: <span class="warn">NO TRANSMIT</span></b> · UGANET-GS-001</div><div class="card"><h3>Satellite Operations</h3><div class="search"><input id="q" placeholder="Satellite name"><button onclick="searchSat()">SEARCH</button></div><div id="results" class="muted"></div><div class="search" style="margin-top:10px"><input id="norad" placeholder="NORAD ID"><input id="lat" type="number" step="any" placeholder="Station latitude"><input id="lon" type="number" step="any" placeholder="Station longitude"><input id="freq" type="number" step="1" placeholder="Receive frequency Hz"><button onclick="track()">TRACK</button></div><p id="status" class="muted">Select a satellite and enter station coordinates.</p></div><div class="card"><h3>Live Receive Doppler</h3><div id="doppler" class="metric muted">Enter a receive frequency to calculate Doppler correction.</div></div><div class="card"><h3>RF Signal</h3><div class="rfgrid"><div class="mini"><div class="muted">EDGE</div><div id="rfEdge" class="big warn">WAITING</div></div><div class="mini"><div class="muted">SNR</div><div id="rfSnr" class="big muted">-- dB</div></div><div class="mini"><div class="muted">PEAK</div><div id="rfPeak" class="big muted">-- dB</div></div><div class="mini"><div class="muted">NOISE FLOOR</div><div id="rfNoise" class="big muted">-- dB</div></div></div><p id="rfMeta" class="muted">Waiting for CONSTELLATION-EDGE-001 spectrum heartbeat.</p></div><div class="card"><h3>Live Spectrum</h3><div id="spectrumBox"><canvas id="sp"></canvas></div></div><div class="card"><h3>Orbital Map</h3><div id="map"><canvas id="cv"></canvas></div></div><div class="card"><h3>Upcoming Passes</h3><div id="passes" class="muted">Waiting for tracking selection.</div></div></div><script>
let timer=null;
async function searchSat(){let s=await fetch('/v1/catalog/search?q='+encodeURIComponent(q.value)).then(r=>r.json());results.innerHTML=(s.satellites||[]).map(x=>'<div style="padding:8px;border-bottom:1px solid #18364c" onclick="norad.value=\''+x.norad_id+'\'">'+x.name+' · NORAD '+x.norad_id+'</div>').join('')}
function draw(points,pos,la,lo){let c=cv,x=c.getContext('2d'),r=c.getBoundingClientRect();c.width=r.width*devicePixelRatio;c.height=r.height*devicePixelRatio;x.scale(devicePixelRatio,devicePixelRatio);let w=r.width,h=r.height;x.fillStyle='#07131f';x.fillRect(0,0,w,h);x.strokeStyle='#18364c';for(let a=-60;a<=60;a+=30){let y=(90-a)/180*h;x.beginPath();x.moveTo(0,y);x.lineTo(w,y);x.stroke()}for(let o=-120;o<=120;o+=60){let xx=(o+180)/360*w;x.beginPath();x.moveTo(xx,0);x.lineTo(xx,h);x.stroke()}x.strokeStyle='#68e3a1';x.beginPath();let last=null;points.forEach(p=>{let xx=(p.lon+180)/360*w,yy=(90-p.lat)/180*h;if(last&&Math.abs(xx-last)>w/2){x.stroke();x.beginPath()}x.lineTo(xx,yy);last=xx});x.stroke();function dot(a,b,col,rad){x.fillStyle=col;x.beginPath();x.arc((b+180)/360*w,(90-a)/180*h,rad,0,Math.PI*2);x.fill()}dot(la,lo,'#ffd166',5);dot(pos.subpoint_lat,pos.subpoint_lon,'#ff7b7b',6)}
function drawSpectrum(bins){let c=sp,x=c.getContext('2d'),r=c.getBoundingClientRect();c.width=r.width*devicePixelRatio;c.height=r.height*devicePixelRatio;x.scale(devicePixelRatio,devicePixelRatio);let w=r.width,h=r.height;x.fillStyle='#07131f';x.fillRect(0,0,w,h);if(!bins||bins.length<2){x.fillStyle='#91a8bb';x.fillText('No live RF samples yet',18,30);return}let vals=bins.map(b=>Number(b.power_db)),mn=Math.min(...vals),mx=Math.max(...vals);if(mx<=mn)mx=mn+1;x.strokeStyle='#68e3a1';x.lineWidth=2;x.beginPath();bins.forEach((b,i)=>{let xx=i/(bins.length-1)*w,yy=h-((Number(b.power_db)-mn)/(mx-mn))*(h-24)-12;i?x.lineTo(xx,yy):x.moveTo(xx,yy)});x.stroke();x.fillStyle='#91a8bb';x.fillText(mx.toFixed(1)+' dB',8,14);x.fillText(mn.toFixed(1)+' dB',8,h-8)}
async function refreshRF(){try{let j=await fetch('/v1/edge/nodes').then(r=>r.json()),n=(j.nodes||[])[0];if(!n){rfEdge.textContent='WAITING';drawSpectrum([]);return}let rf=((n.health||{}).rf||{}),s=rf.spectrum||{},d=rf.doppler||{};if(s.ok){rfEdge.textContent='ONLINE';rfEdge.className='big ok';rfSnr.textContent=Number(s.snr_db).toFixed(1)+' dB';rfPeak.textContent=Number((s.peak||{}).power_db).toFixed(1)+' dB';rfNoise.textContent=Number(s.noise_floor_db).toFixed(1)+' dB';rfMeta.textContent='Center '+(Number(s.center_hz)/1e6).toFixed(6)+' MHz · NORAD '+(s.norad_id||'--')+' · '+new Date(Number(s.timestamp)*1000).toLocaleTimeString();drawSpectrum(s.bins||[])}else{rfEdge.textContent=rf.available?'NO DATA':'WAITING';rfEdge.className='big warn';drawSpectrum([])}if(d&&d.receive_hz){rfMeta.textContent+=' · RX '+(Number(d.receive_hz)/1e6).toFixed(6)+' MHz'}}catch(e){rfEdge.textContent='OFFLINE';rfEdge.className='big bad'}}
async function track(){let id=norad.value.trim(),la=Number(lat.value),lo=Number(lon.value);if(!id||Number.isNaN(la)||Number.isNaN(lo))return;let t=await fetch('/v1/catalog/track?norad_id='+id+'&lat='+la+'&lon='+lo).then(r=>r.json()),g=await fetch('/v1/catalog/ground-track?norad_id='+id).then(r=>r.json());let p=t.position;status.textContent=t.satellite+' · AZ '+p.azimuth_deg.toFixed(1)+'° · EL '+p.elevation_deg.toFixed(1)+'° · RANGE '+p.range_km.toFixed(0)+' km';draw(g.points||[],p,la,lo);passes.innerHTML=(t.passes||[]).slice(0,8).map(v=>'<div>'+v.rise.time+' · MAX '+Number(v.max_elevation_deg).toFixed(1)+'° · '+v.set.time+'</div>').join('')||'No qualifying pass.';let f=Number(freq.value);if(f>0){let d=await fetch('/v1/catalog/doppler?norad_id='+id+'&lat='+la+'&lon='+lo+'&frequency_hz='+f).then(r=>r.json());let z=d.doppler;doppler.innerHTML='Nominal '+(z.nominal_frequency_hz/1e6).toFixed(6)+' MHz · Shift '+z.doppler_shift_hz.toFixed(0)+' Hz · <span class="ok">Receive '+(z.receive_frequency_hz/1e6).toFixed(6)+' MHz</span> · Radial '+z.radial_velocity_m_s.toFixed(0)+' m/s'}if(timer)clearTimeout(timer);timer=setTimeout(track,5000)}
refreshRF();setInterval(refreshRF,5000);
</script></body></html>'''

@app.post('/v1/tle')
def save_tle(norad_id:str=Body(...),name:str=Body(...),line1:str=Body(...),line2:str=Body(...),source:str=Body(default='manual'),user=Depends(require_role('operator'))): db.upsert_tle(norad_id,name,line1,line2,source); db.audit(user.get('sub'),'tle.upsert',norad_id,{'name':name,'source':source}); return {'accepted':True,'norad_id':norad_id}
@app.post('/v1/orbit/position')
def orbital_position(norad_id:str=Body(...),lat:float=Body(...),lon:float=Body(...),elevation_m:float=Body(default=0.0),at:str|None=Body(default=None),user=Depends(require_role('observer'))):
    tle=db.get_tle(norad_id)
    if not tle: raise HTTPException(404,'TLE not found')
    return {'satellite':tle['name'],'norad_id':norad_id,'position':orbit.position(tle['name'],tle['line1'],tle['line2'],lat,lon,elevation_m,at)}
@app.post('/v1/orbit/passes')
def predict_passes(norad_id:str=Body(...),station_id:str=Body(default='UGANET-GS-001'),lat:float=Body(...),lon:float=Body(...),elevation_m:float=Body(default=0.0),hours:int=Body(default=24),min_elevation_deg:float=Body(default=10.0),persist:bool=Body(default=True),user=Depends(require_role('observer'))):
    tle=db.get_tle(norad_id)
    if not tle: raise HTTPException(404,'TLE not found')
    ps=orbit.passes(tle['name'],tle['line1'],tle['line2'],lat,lon,elevation_m,hours,min_elevation_deg)
    if persist:
        for p in ps: db.save_pass_plan(tle['name'],norad_id,station_id,p)
    return {'satellite':tle['name'],'norad_id':norad_id,'station_id':station_id,'passes':ps}
@app.post('/v1/edge/heartbeat')
def edge_heartbeat(node_id:str=Body(...),station_id:str=Body(default='UGANET-GS-001'),hostname:str=Body(...),receive_only:bool=Body(default=True),capabilities:dict=Body(default={}),health:dict=Body(default={})):
    if not receive_only and NO_TRANSMIT: raise HTTPException(403,'Cloud policy requires receive-only edge mode')
    db.edge_heartbeat(node_id,station_id,hostname,receive_only,capabilities,health); return {'accepted':True,'node_id':node_id,'cloud_no_transmit':NO_TRANSMIT}
@app.get('/v1/edge/nodes')
def edge_nodes(): return {'nodes':db.list_edge_nodes()}
@app.post('/v1/ccsds/decode')
def decode_ccsds(payload_hex:str=Body(...,embed=True),user=Depends(require_role('observer'))):
    try:return ccsds.decode_space_packet(bytes.fromhex(payload_hex))
    except ValueError as e:raise HTTPException(400,str(e))
@app.post('/v1/telemetry')
def ingest_telemetry(satellite:str=Body(...),station_id:str|None=Body(default=None),protocol:str=Body(default='ccsds'),payload:dict=Body(default={}),user=Depends(require_role('operator'))): db.save_telemetry(satellite,station_id,protocol,payload); db.audit(user.get('sub'),'telemetry.ingest',satellite,{'station_id':station_id,'protocol':protocol}); return {'accepted':True}
@app.post('/v1/telemetry/alarms/evaluate')
def evaluate_alarms(fields:dict=Body(...),limits:dict=Body(...),user=Depends(require_role('operator'))):
    alarms=operations.telemetry_alarms(fields,limits)
    if any(a['severity']=='critical' for a in alarms): integrations.publish_event('spacecraft.telemetry.critical',{'alarms':alarms})
    db.audit(user.get('sub'),'telemetry.alarm.evaluate','telemetry',{'count':len(alarms)}); return {'alarms':alarms}
@app.post('/v1/network/select-station')
def select_station(pass_candidates:list=Body(...),stations:dict=Body(...),station_health:dict=Body(default={}),user=Depends(require_role('operator'))): return {'selected':operations.choose_station(pass_candidates,stations,station_health)}
@app.post('/v1/cdm')
def ingest_cdm(cdm:dict=Body(...),user=Depends(require_role('mission_controller'))):
    if not cdm.get('object_primary') or not cdm.get('object_secondary'): raise HTTPException(400,'object_primary and object_secondary required')
    db.save_cdm(cdm); db.audit(user.get('sub'),'cdm.ingest',f"{cdm['object_primary']}:{cdm['object_secondary']}",cdm); integrations.publish_event('orbit.conjunction.cdm',cdm); return {'accepted':True}
@app.post('/v1/commands/validate')
def validate_command(command:dict=Body(...),schema:dict=Body(...),approvals:list=Body(default=[]),user=Depends(require_role('mission_controller'))):
    result=operations.validate_command(command,schema,approvals,NO_TRANSMIT); db.save_command(command.get('satellite','unknown'),command,result['state'],user.get('sub'),approvals); db.audit(user.get('sub'),'command.validate',command.get('satellite','unknown'),result); return result
