import os
from fastapi import FastAPI, Body, Depends, HTTPException
from fastapi.responses import HTMLResponse
from . import db, ccsds, integrations, operations, orbit
from .security import require_role

app=FastAPI(title='UNG-CONSTELLATION',version='1.1.0')
NO_TRANSMIT=os.getenv('CONSTELLATION_NO_TRANSMIT','true').lower() not in ('0','false','no')

@app.on_event('startup')
def startup():
    try: db.init_db()
    except Exception: pass

@app.get('/')
def root():
    return {'service':'UNG-CONSTELLATION','name':'National Satellite & Orbital Operations System','version':'1.1.0','no_transmit':NO_TRANSMIT,'mission_control':'/mission-control'}

@app.get('/health')
def health():
    return {'status':'ok','service':'UNG-CONSTELLATION'}

@app.get('/ready')
def ready():
    d=db.readiness()
    return {'ready': (not d['configured']) or d['connected'], 'database':d, 'integrations':integrations.status(), 'no_transmit':NO_TRANSMIT}

@app.get('/v1/system')
def system():
    return {'service':'UNG-CONSTELLATION','mission':'Satellite tracking, orbital operations, ground-station coordination and telemetry','version':'1.1.0','integrations':integrations.status(),'no_transmit':NO_TRANSMIT}

@app.get('/mission-control',response_class=HTMLResponse)
def mission_control():
    return '''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>UNG-CONSTELLATION Mission Control</title><style>
body{font-family:system-ui,-apple-system,sans-serif;background:#07111d;color:#e8f0f8;margin:0}.bar{padding:18px 22px;background:#0e1c2b;border-bottom:1px solid #24435f}.wrap{padding:18px;display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(260px,1fr))}.card{background:#0d1b29;border:1px solid #23445f;border-radius:14px;padding:16px}.ok{color:#79e0a6}.warn{color:#ffd166}.big{font-size:28px;font-weight:700}.muted{color:#93a9bc}code{color:#9dd7ff}button{padding:9px 12px;border-radius:9px;border:0;background:#dfefff}.row{display:flex;gap:8px;flex-wrap:wrap}input{background:#07111d;color:white;border:1px solid #315875;padding:8px;border-radius:8px;max-width:100%}</style></head><body>
<div class="bar"><div class="big">UNG-CONSTELLATION</div><div class="muted">National Satellite & Orbital Operations System · Mission Control</div></div>
<div class="wrap"><div class="card"><h3>Control Plane</h3><div id="health">Loading…</div><p class="muted">Railway cloud backend + PostgreSQL</p></div><div class="card"><h3>RF Safety</h3><div class="big warn">NO TRANSMIT</div><p>Uplink remains disabled until explicitly commissioned and authorized.</p></div><div class="card"><h3>UGANET-GS-001</h3><p>Gateway: <b>UGANET-GW-001</b></p><p>Edge: <b>CONSTELLATION-EDGE-001</b></p><p>Receiver: <b>SDR-001</b></p></div><div class="card"><h3>Edge Nodes</h3><div id="nodes">No node heartbeat received yet.</div></div><div class="card"><h3>Tracking API</h3><p><code>POST /v1/orbit/position</code></p><p><code>POST /v1/orbit/passes</code></p><p><code>POST /v1/tle</code></p></div><div class="card"><h3>Operations</h3><p>CCSDS · telemetry · CDM/conjunction · station selection · pass plans · audit · UGANET edge sync</p></div></div>
<script>async function load(){let h=await fetch('/ready').then(r=>r.json());document.getElementById('health').innerHTML=h.ready?'<span class="ok big">READY</span>':'<span class="warn big">DEGRADED</span>';try{let n=await fetch('/v1/edge/nodes').then(r=>r.json());document.getElementById('nodes').innerHTML=n.nodes.length?n.nodes.map(x=>'<div><b>'+x.id+'</b> · '+x.hostname+' · '+x.last_seen+'</div>').join(''):'No node heartbeat received yet.'}catch(e){}}load();setInterval(load,10000);</script></body></html>'''

@app.post('/v1/tle')
def save_tle(norad_id:str=Body(...), name:str=Body(...), line1:str=Body(...), line2:str=Body(...), source:str=Body(default='manual'), user=Depends(require_role('operator'))):
    db.upsert_tle(norad_id,name,line1,line2,source)
    db.audit(user.get('sub'),'tle.upsert',norad_id,{'name':name,'source':source})
    return {'accepted':True,'norad_id':norad_id}

@app.post('/v1/orbit/position')
def orbital_position(norad_id:str=Body(...), lat:float=Body(...), lon:float=Body(...), elevation_m:float=Body(default=0.0), at:str|None=Body(default=None), user=Depends(require_role('observer'))):
    tle=db.get_tle(norad_id)
    if not tle: raise HTTPException(404,'TLE not found')
    return {'satellite':tle['name'],'norad_id':norad_id,'position':orbit.position(tle['name'],tle['line1'],tle['line2'],lat,lon,elevation_m,at)}

@app.post('/v1/orbit/passes')
def predict_passes(norad_id:str=Body(...), station_id:str=Body(default='UGANET-GS-001'), lat:float=Body(...), lon:float=Body(...), elevation_m:float=Body(default=0.0), hours:int=Body(default=24), min_elevation_deg:float=Body(default=10.0), persist:bool=Body(default=True), user=Depends(require_role('observer'))):
    tle=db.get_tle(norad_id)
    if not tle: raise HTTPException(404,'TLE not found')
    ps=orbit.passes(tle['name'],tle['line1'],tle['line2'],lat,lon,elevation_m,hours,min_elevation_deg)
    if persist:
        for p in ps: db.save_pass_plan(tle['name'],norad_id,station_id,p)
    return {'satellite':tle['name'],'norad_id':norad_id,'station_id':station_id,'passes':ps}

@app.post('/v1/edge/heartbeat')
def edge_heartbeat(node_id:str=Body(...), station_id:str=Body(default='UGANET-GS-001'), hostname:str=Body(...), receive_only:bool=Body(default=True), capabilities:dict=Body(default={}), health:dict=Body(default={})):
    if not receive_only and NO_TRANSMIT: raise HTTPException(403,'Cloud policy requires receive-only edge mode')
    db.edge_heartbeat(node_id,station_id,hostname,receive_only,capabilities,health)
    return {'accepted':True,'node_id':node_id,'cloud_no_transmit':NO_TRANSMIT}

@app.get('/v1/edge/nodes')
def edge_nodes():
    return {'nodes':db.list_edge_nodes()}

@app.post('/v1/ccsds/decode')
def decode_ccsds(payload_hex:str=Body(...,embed=True), user=Depends(require_role('observer'))):
    try: return ccsds.decode_space_packet(bytes.fromhex(payload_hex))
    except ValueError as e: raise HTTPException(400,str(e))

@app.post('/v1/telemetry')
def ingest_telemetry(satellite:str=Body(...), station_id:str|None=Body(default=None), protocol:str=Body(default='ccsds'), payload:dict=Body(default={}), user=Depends(require_role('operator'))):
    db.save_telemetry(satellite,station_id,protocol,payload)
    db.audit(user.get('sub'),'telemetry.ingest',satellite,{'station_id':station_id,'protocol':protocol})
    return {'accepted':True}

@app.post('/v1/telemetry/alarms/evaluate')
def evaluate_alarms(fields:dict=Body(...), limits:dict=Body(...), user=Depends(require_role('operator'))):
    alarms=operations.telemetry_alarms(fields,limits)
    if any(a['severity']=='critical' for a in alarms): integrations.publish_event('spacecraft.telemetry.critical',{'alarms':alarms})
    db.audit(user.get('sub'),'telemetry.alarm.evaluate','telemetry',{'count':len(alarms)})
    return {'alarms':alarms}

@app.post('/v1/network/select-station')
def select_station(pass_candidates:list=Body(...), stations:dict=Body(...), station_health:dict=Body(default={}), user=Depends(require_role('operator'))):
    return {'selected':operations.choose_station(pass_candidates,stations,station_health)}

@app.post('/v1/cdm')
def ingest_cdm(cdm:dict=Body(...), user=Depends(require_role('mission_controller'))):
    if not cdm.get('object_primary') or not cdm.get('object_secondary'): raise HTTPException(400,'object_primary and object_secondary required')
    db.save_cdm(cdm)
    db.audit(user.get('sub'),'cdm.ingest',f"{cdm['object_primary']}:{cdm['object_secondary']}",cdm)
    integrations.publish_event('orbit.conjunction.cdm',cdm)
    return {'accepted':True}

@app.post('/v1/commands/validate')
def validate_command(command:dict=Body(...), user=Depends(require_role('mission_controller'))):
    result=operations.validate_command(command,NO_TRANSMIT)
    db.audit(user.get('sub'),'command.preflight',command.get('satellite',''),{'valid':result.get('valid'),'no_transmit':NO_TRANSMIT})
    if not result.get('valid'): raise HTTPException(400,result.get('reason'))
    return result
