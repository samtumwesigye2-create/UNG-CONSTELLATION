import os
from fastapi import FastAPI, Body, Depends, HTTPException
from fastapi.responses import HTMLResponse
from . import db, ccsds, integrations, operations, orbit
from .security import require_role

app=FastAPI(title='UNG-CONSTELLATION',version='1.2.0')
NO_TRANSMIT=os.getenv('CONSTELLATION_NO_TRANSMIT','true').lower() not in ('0','false','no')

@app.on_event('startup')
def startup():
    try: db.init_db()
    except Exception: pass

@app.get('/')
def root(): return {'service':'UNG-CONSTELLATION','name':'National Satellite & Orbital Operations System','version':'1.2.0','no_transmit':NO_TRANSMIT,'mission_control':'/mission-control'}
@app.get('/health')
def health(): return {'status':'ok','service':'UNG-CONSTELLATION'}
@app.get('/ready')
def ready():
    d=db.readiness(); return {'ready':(not d['configured']) or d['connected'],'database':d,'integrations':integrations.status(),'no_transmit':NO_TRANSMIT}
@app.get('/v1/system')
def system(): return {'service':'UNG-CONSTELLATION','mission':'Satellite tracking, orbital operations, ground-station coordination and telemetry','version':'1.2.0','integrations':integrations.status(),'no_transmit':NO_TRANSMIT}

@app.get('/mission-control',response_class=HTMLResponse)
def mission_control():
 return '''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>UNG-CONSTELLATION</title><style>
*{box-sizing:border-box}body{font-family:system-ui,-apple-system,sans-serif;background:#06111d;color:#e8f1fb;margin:0}.bar{padding:18px 20px;background:#0c1b2a;border-bottom:1px solid #24445e;position:sticky;top:0;z-index:2}.title{font-size:27px;font-weight:800;letter-spacing:.3px}.muted{color:#91a8bb}.wrap{padding:14px;display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));max-width:1300px;margin:auto}.card{background:#0c1b29;border:1px solid #24506d;border-radius:16px;padding:16px;min-height:130px}.wide{grid-column:1/-1}.ok{color:#68e3a1}.warn{color:#ffd166}.bad{color:#ff7b7b}.big{font-size:27px;font-weight:800}.metric{font-size:21px;font-weight:700}.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.mini{background:#081521;border-radius:10px;padding:10px}.node{padding:10px 0;border-bottom:1px solid #18364c}.pill{display:inline-block;border:1px solid #315b77;border-radius:999px;padding:4px 8px;font-size:12px;margin:2px}.search{display:flex;gap:8px;flex-wrap:wrap}input{flex:1;min-width:150px;background:#07131f;color:#fff;border:1px solid #315b77;border-radius:9px;padding:11px}button{background:#dceeff;border:0;border-radius:9px;padding:11px 14px;font-weight:700}table{width:100%;border-collapse:collapse;font-size:13px}td,th{text-align:left;padding:8px;border-bottom:1px solid #18364c}@media(max-width:600px){.grid3{grid-template-columns:1fr}.title{font-size:23px}.wrap{padding:10px}}</style></head><body>
<div class="bar"><div class="title">UNG-CONSTELLATION</div><div class="muted">National Satellite & Orbital Operations System · Mission Control</div></div><div class="wrap">
<div class="card"><div class="muted">CONTROL PLANE</div><div id="health" class="big">CHECKING</div><p class="muted">Railway + PostgreSQL</p></div>
<div class="card"><div class="muted">RF SAFETY</div><div class="big warn">NO TRANSMIT</div><p>Receive-only until explicitly commissioned and authorized.</p></div>
<div class="card"><div class="muted">GROUND STATION</div><div class="metric">UGANET-GS-001</div><p class="muted">GW-001 · EDGE-001 · SDR-001</p></div>
<div class="card wide"><h3>Station Health</h3><div class="grid3"><div class="mini"><div class="muted">Edge</div><div id="edgeState" class="metric warn">WAITING</div></div><div class="mini"><div class="muted">SDR</div><div id="sdrState" class="metric warn">NOT COMMISSIONED</div></div><div class="mini"><div class="muted">GNSS / Timing</div><div id="gnssState" class="metric warn">NOT COMMISSIONED</div></div></div></div>
<div class="card wide"><h3>Satellite Tracking</h3><div class="search"><input id="norad" placeholder="NORAD ID"><input id="lat" type="number" step="any" placeholder="Station latitude"><input id="lon" type="number" step="any" placeholder="Station longitude"><button onclick="track()">TRACK</button></div><div id="trackResult" class="muted" style="margin-top:12px">Enter a stored NORAD ID and station coordinates.</div></div>
<div class="card"><h3>Edge Nodes</h3><div id="nodes" class="muted">Waiting for first Pi heartbeat.</div></div>
<div class="card"><h3>Live Operations</h3><div class="pill">TLE</div><div class="pill">SGP4</div><div class="pill">PASS PREDICTION</div><div class="pill">CCSDS</div><div class="pill">TELEMETRY</div><div class="pill">CDM</div><div class="pill">DOPPLER</div><div class="pill">UGANET</div><p class="muted">Hardware values become live when Ground Station 001 is commissioned.</p></div>
<div class="card wide"><h3>Upcoming Passes</h3><div id="passes" class="muted">Select a satellite with TRACK to calculate the next 24 hours.</div></div>
</div><script>
async function refresh(){try{let h=await fetch('/ready').then(r=>r.json());let e=document.getElementById('health');e.textContent=h.ready?'READY':'DEGRADED';e.className='big '+(h.ready?'ok':'bad')}catch(e){}try{let j=await fetch('/v1/edge/nodes').then(r=>r.json()),n=j.nodes||[];document.getElementById('nodes').innerHTML=n.length?n.map(x=>'<div class="node"><b>'+x.id+'</b><br><span class="muted">'+x.hostname+' · '+x.last_seen+'</span></div>').join(''):'Waiting for first Pi heartbeat.';if(n.length){document.getElementById('edgeState').textContent='ONLINE';document.getElementById('edgeState').className='metric ok';let h=n[0].health||{},c=n[0].capabilities||{};if(h.rtl_sdr?.ok||c.rtl_sdr){document.getElementById('sdrState').textContent='ONLINE';document.getElementById('sdrState').className='metric ok'}if(h.gnss?.gpsd||c.gnss){document.getElementById('gnssState').textContent='ONLINE';document.getElementById('gnssState').className='metric ok'}}}catch(e){}}
async function track(){let id=norad.value,la=Number(lat.value),lo=Number(lon.value);if(!id||Number.isNaN(la)||Number.isNaN(lo))return;trackResult.textContent='Calculating orbit…';try{let headers={'Content-Type':'application/json'},body=JSON.stringify({norad_id:id,lat:la,lon:lo,elevation_m:0});let p=await fetch('/v1/orbit/position',{method:'POST',headers,body});if(p.status==401||p.status==403){trackResult.textContent='JANUS/IAM operator sign-in required for orbital data.';return}let d=await p.json();if(!p.ok){trackResult.textContent=d.detail||'Tracking failed';return}let x=d.position;trackResult.innerHTML='<b>'+d.satellite+'</b> · AZ '+Number(x.azimuth_deg).toFixed(1)+'° · EL '+Number(x.elevation_deg).toFixed(1)+'° · RANGE '+Number(x.range_km).toFixed(0)+' km';let q=await fetch('/v1/orbit/passes',{method:'POST',headers,body:JSON.stringify({norad_id:id,station_id:'UGANET-GS-001',lat:la,lon:lo,elevation_m:0,hours:24,min_elevation_deg:10,persist:false})});let z=await q.json(),ps=z.passes||[];passes.innerHTML=ps.length?'<table><tr><th>AOS</th><th>MAX EL</th><th>LOS</th></tr>'+ps.slice(0,8).map(v=>'<tr><td>'+v.aos+'</td><td>'+Number(v.max_elevation_deg).toFixed(1)+'°</td><td>'+v.los+'</td></tr>').join('')+'</table>':'No qualifying pass in next 24 hours.'}catch(e){trackResult.textContent='Unable to reach tracking service.'}}
refresh();setInterval(refresh,10000);</script></body></html>'''

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
def validate_command(command:dict=Body(...),user=Depends(require_role('mission_controller'))):
    result=operations.validate_command(command,NO_TRANSMIT); db.audit(user.get('sub'),'command.preflight',command.get('satellite',''),{'valid':result.get('valid'),'no_transmit':NO_TRANSMIT})
    if not result.get('valid'): raise HTTPException(400,result.get('reason'))
    return result
