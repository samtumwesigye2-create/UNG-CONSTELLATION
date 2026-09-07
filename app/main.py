import os
from fastapi import FastAPI, Body, Depends, HTTPException
from fastapi.responses import HTMLResponse
from . import db, ccsds, integrations, operations, orbit, catalog
from .security import require_role

app=FastAPI(title='UNG-CONSTELLATION',version='1.4.0')
NO_TRANSMIT=os.getenv('CONSTELLATION_NO_TRANSMIT','true').lower() not in ('0','false','no')

@app.on_event('startup')
def startup():
    try: db.init_db()
    except Exception: pass

@app.get('/')
def root(): return {'service':'UNG-CONSTELLATION','name':'National Satellite & Orbital Operations System','version':'1.4.0','no_transmit':NO_TRANSMIT,'mission_control':'/mission-control'}
@app.get('/health')
def health(): return {'status':'ok','service':'UNG-CONSTELLATION'}
@app.get('/ready')
def ready():
    d=db.readiness(); return {'ready':(not d['configured']) or d['connected'],'database':d,'integrations':integrations.status(),'no_transmit':NO_TRANSMIT}
@app.get('/v1/system')
def system(): return {'service':'UNG-CONSTELLATION','mission':'Satellite tracking, orbital operations, ground-station coordination and telemetry','version':'1.4.0','integrations':integrations.status(),'no_transmit':NO_TRANSMIT}
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

@app.get('/mission-control',response_class=HTMLResponse)
def mission_control():
 return '''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>UNG-CONSTELLATION</title><style>*{box-sizing:border-box}body{font-family:system-ui,-apple-system,sans-serif;background:#06111d;color:#e8f1fb;margin:0}.bar{padding:18px 20px;background:#0c1b2a;border-bottom:1px solid #24445e}.wrap{padding:14px;display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));max-width:1300px;margin:auto}.card{background:#0c1b29;border:1px solid #24506d;border-radius:16px;padding:16px}.wide{grid-column:1/-1}.ok{color:#68e3a1}.warn{color:#ffd166}.big{font-size:27px;font-weight:800}.muted{color:#91a8bb}.search{display:flex;gap:8px;flex-wrap:wrap}input{flex:1;min-width:140px;background:#07131f;color:#fff;border:1px solid #315b77;border-radius:9px;padding:11px}button{background:#dceeff;border:0;border-radius:9px;padding:11px 14px;font-weight:700}.result{padding:9px;border-bottom:1px solid #18364c;cursor:pointer}canvas{width:100%;height:auto;background:#071725;border-radius:12px;border:1px solid #24445e}table{width:100%;font-size:12px;border-collapse:collapse}td,th{padding:7px;border-bottom:1px solid #18364c;text-align:left}</style></head><body><div class="bar"><div class="big">UNG-CONSTELLATION</div><div class="muted">National Satellite & Orbital Operations System · Mission Control</div></div><div class="wrap"><div class="card"><div class="muted">CONTROL PLANE</div><div id="health" class="big">CHECKING</div></div><div class="card"><div class="muted">RF SAFETY</div><div class="big warn">NO TRANSMIT</div></div><div class="card"><div class="muted">GROUND STATION</div><div class="big">UGANET-GS-001</div></div><div class="card wide"><h3>Satellite Search & Tracking</h3><div class="search"><input id="satq" placeholder="Search satellite, e.g. ISS"><button onclick="searchSat()">SEARCH</button></div><div id="results" class="muted"></div><div class="search"><input id="norad" placeholder="NORAD ID"><input id="lat" type="number" step="any" placeholder="Station latitude"><input id="lon" type="number" step="any" placeholder="Station longitude"><button onclick="track()">TRACK</button></div><div id="trackResult" class="muted"></div></div><div class="card wide"><h3>Live Orbital Map</h3><canvas id="map" width="1000" height="480"></canvas><div class="muted">Ground track: previous 45 min → next 90 min · circle = approximate horizon footprint</div></div><div class="card wide"><h3>Upcoming Passes</h3><div id="passes" class="muted">Select a satellite.</div></div></div><script>
let current=null,trackPoints=[];function xy(lat,lon){return [(lon+180)/360*1000,(90-lat)/180*480]}function draw(){let c=map.getContext('2d');c.clearRect(0,0,1000,480);c.fillStyle='#071725';c.fillRect(0,0,1000,480);c.strokeStyle='#173b52';c.lineWidth=1;for(let x=0;x<=1000;x+=100){c.beginPath();c.moveTo(x,0);c.lineTo(x,480);c.stroke()}for(let y=0;y<=480;y+=80){c.beginPath();c.moveTo(0,y);c.lineTo(1000,y);c.stroke()}if(trackPoints.length){c.strokeStyle='#6bbcff';c.lineWidth=2;let prev=null;for(let p of trackPoints){let q=xy(p.lat,p.lon);if(prev&&Math.abs(q[0]-prev[0])<500){c.beginPath();c.moveTo(prev[0],prev[1]);c.lineTo(q[0],q[1]);c.stroke()}prev=q}}if(current){let q=xy(current.subpoint_lat,current.subpoint_lon);let r=current.visibility_radius_deg/360*1000;c.strokeStyle='#68e3a1';c.beginPath();c.arc(q[0],q[1],r,0,Math.PI*2);c.stroke();c.fillStyle='#ffd166';c.beginPath();c.arc(q[0],q[1],7,0,Math.PI*2);c.fill()}let la=Number(lat.value),lo=Number(lon.value);if(!Number.isNaN(la)&&!Number.isNaN(lo)){let q=xy(la,lo);c.fillStyle='#ff7b7b';c.fillRect(q[0]-4,q[1]-4,8,8)}}
async function searchSat(){let q=satq.value.trim();if(q.length<2)return;results.textContent='Searching…';let d=await fetch('/v1/catalog/search?q='+encodeURIComponent(q)).then(r=>r.json());results.innerHTML=(d.satellites||[]).map(x=>'<div class="result" onclick="norad.value=\''+x.norad_id+'\'"><b>'+x.name+'</b> · NORAD '+x.norad_id+'</div>').join('')||'No matches'}
async function track(){let id=norad.value.trim(),la=Number(lat.value),lo=Number(lon.value);if(!id||Number.isNaN(la)||Number.isNaN(lo))return;trackResult.textContent='Calculating…';let d=await fetch('/v1/catalog/track?norad_id='+id+'&lat='+la+'&lon='+lo).then(r=>r.json());if(d.detail){trackResult.textContent=d.detail;return}current=d.position;trackResult.innerHTML='<b>'+d.satellite+'</b> · AZ '+current.azimuth_deg.toFixed(1)+'° · EL '+current.elevation_deg.toFixed(1)+'° · RANGE '+current.range_km.toFixed(0)+' km · ALT '+current.altitude_km.toFixed(0)+' km · FOOTPRINT '+current.visibility_radius_km.toFixed(0)+' km';let g=await fetch('/v1/catalog/ground-track?norad_id='+id).then(r=>r.json());trackPoints=g.points||[];draw();let ps=d.passes||[];passes.innerHTML=ps.length?'<table><tr><th>AOS</th><th>MAX EL</th><th>LOS</th></tr>'+ps.slice(0,8).map(v=>'<tr><td>'+v.rise.time+'</td><td>'+Number(v.max_elevation_deg).toFixed(1)+'°</td><td>'+v.set.time+'</td></tr>').join('')+'</table>':'No qualifying pass in next 24 hours.'}
async function refresh(){try{let h=await fetch('/ready').then(r=>r.json());health.textContent=h.ready?'READY':'DEGRADED';health.className='big '+(h.ready?'ok':'warn')}catch(e){}}refresh();draw();setInterval(refresh,10000);</script></body></html>'''

@app.post('/v1/tle')
def save_tle(norad_id:str=Body(...),name:str=Body(...),line1:str=Body(...),line2:str=Body(...),source:str=Body(default='manual'),user=Depends(require_role('operator'))): db.upsert_tle(norad_id,name,line1,line2,source); return {'accepted':True}
@app.post('/v1/orbit/position')
def orbital_position(norad_id:str=Body(...),lat:float=Body(...),lon:float=Body(...),elevation_m:float=Body(default=0.0),at:str|None=Body(default=None),user=Depends(require_role('observer'))):
    tle=db.get_tle(norad_id)
    if not tle: raise HTTPException(404,'TLE not found')
    return {'satellite':tle['name'],'position':orbit.position(tle['name'],tle['line1'],tle['line2'],lat,lon,elevation_m,at)}
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
def ingest_telemetry(satellite:str=Body(...),station_id:str|None=Body(default=None),protocol:str=Body(default='ccsds'),payload:dict=Body(default={}),user=Depends(require_role('operator'))): db.save_telemetry(satellite,station_id,protocol,payload); return {'accepted':True}
@app.post('/v1/commands/validate')
def validate_command(command:dict=Body(...),user=Depends(require_role('mission_controller'))):
    result=operations.validate_command(command,NO_TRANSMIT)
    if not result.get('valid'): raise HTTPException(400,result.get('reason'))
    return result
