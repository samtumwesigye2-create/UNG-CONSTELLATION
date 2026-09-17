"""Production ASGI entrypoint for UNG-CONSTELLATION.

Railway launches this module. The core API remains in app.main, while this
entrypoint exposes browser-facing Mission Control and Remote Sensor Hub views.
"""
from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .main import app


# Capture the existing Mission Control renderer so the production entrypoint can
# add navigation without duplicating the satellite console implementation.
_mission_control = next(
    route.endpoint
    for route in app.router.routes
    if getattr(route, "path", None) == "/mission-control"
    and "GET" in (getattr(route, "methods", None) or set())
)


SENSOR_HUB_HTML = r'''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>UNG-CONSTELLATION · Sensor Hub</title><style>
body{font-family:system-ui;background:#06111d;color:#e8f1fb;margin:0}.w{max-width:1200px;margin:auto;padding:14px}.top{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.c{background:#0c1b29;border:1px solid #24506d;border-radius:15px;padding:15px;margin:12px 0}.g{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.x{background:#07131f;padding:12px;border-radius:9px}.m{color:#91a8bb}.ok{color:#68e3a1}.warn{color:#ffd166}button,input{padding:11px;border-radius:8px;border:1px solid #315b77;background:#07131f;color:white}button{font-weight:700;cursor:pointer}.event{padding:12px;border-bottom:1px solid #18364c}.event b{color:#68e3a1}.nav{display:inline-block;padding:10px 12px;border:1px solid #315b77;border-radius:8px;color:#e8f1fb;text-decoration:none;font-weight:700}.token{width:min(520px,90%)}@media(max-width:700px){.g{grid-template-columns:1fr 1fr}}
</style></head><body><div class="w"><div class="top"><a class="nav" href="/mission-control">← MISSION CONTROL</a><h2>REMOTE SENSOR HUB</h2></div>
<div class="c"><b>CONSTELLATION SENSOR OPERATIONS</b><p class="m">Authenticated field sensors → Sensor Hub → NEXUS / PULSAR → downstream UNG systems</p></div>
<div class="c"><h3>Operator Access</h3><input class="token" id="token" type="password" placeholder="JANUS bearer token"><button id="connect">CONNECT</button><p id="auth" class="m">Enter an authorized observer/operator token to load protected sensor data.</p></div>
<div class="c"><h3>Hub Status</h3><div class="g"><div class="x">HUB<br><b id="hub">LOCKED</b></div><div class="x">DATABASE<br><b id="db">--</b></div><div class="x">ROUTE<br><b id="route">--</b></div><div class="x">EVENTS<br><b id="count">--</b></div></div></div>
<div class="c"><h3>Event Types / U-Codes</h3><div id="codes" class="m">Connect to load registered sensor event types.</div></div>
<div class="c"><div class="top"><h3>Recent Sensor Events</h3><button id="refresh">REFRESH</button></div><div id="events" class="m">No protected event data loaded.</div></div>
</div><script>
const E=id=>document.getElementById(id);const base='/v1/tracker/sensor-hub';function headers(){let t=E('token').value.trim();return t?{'Authorization':'Bearer '+t}:{}}
async function load(){E('auth').textContent='Connecting…';try{let [sr,er]=await Promise.all([fetch(base+'/status',{headers:headers()}),fetch(base+'/events?limit=50',{headers:headers()})]);if(!sr.ok||!er.ok)throw new Error(sr.status===401||er.status===401?'Authorization required or token rejected':'Sensor Hub API unavailable');let s=await sr.json(),e=await er.json(),ev=e.events||[];E('hub').textContent='ONLINE';E('hub').className='ok';let d=s.database||{};E('db').textContent=d.connected?'READY':(d.configured?'UNAVAILABLE':'NOT CONFIGURED');let i=s.integration||{};E('route').textContent=(i.route||i.mode||i.via||'LOCAL').toString().toUpperCase();E('count').textContent=ev.length;E('codes').innerHTML=Object.entries(s.u_codes||{}).map(([k,v])=>'<div class="event"><b>'+v+'</b> · '+k+'</div>').join('')||'No U-Codes returned.';E('events').innerHTML=ev.length?ev.map(v=>'<div class="event"><b>'+v.u_code+'</b> · '+v.sensor_id+' · '+v.event_type+'<br><span class="m">'+(v.observed_at||v.received_at||'')+' · delivery '+JSON.stringify(v.delivery||{})+'</span></div>').join(''):'No sensor events received yet.';E('auth').textContent='Protected Sensor Hub data loaded.'}catch(err){E('hub').textContent='LOCKED';E('hub').className='warn';E('auth').textContent=err.message}}
E('connect').onclick=load;E('refresh').onclick=load;
</script></body></html>'''


@app.get("/sensor-hub", response_class=HTMLResponse, include_in_schema=False)
def sensor_hub_console():
    return SENSOR_HUB_HTML


@app.middleware("http")
async def browser_ui(request: Request, call_next):
    path = request.url.path
    if request.method in {"GET", "HEAD"} and path == "/":
        return RedirectResponse(url="/mission-control", status_code=307)
    if request.method == "GET" and path == "/mission-control":
        html = _mission_control()
        nav = '<div style="margin:0 0 12px"><a href="/sensor-hub" style="display:inline-block;padding:10px 12px;border:1px solid #315b77;border-radius:8px;color:#e8f1fb;text-decoration:none;font-weight:700">REMOTE SENSOR HUB →</a></div>'
        html = html.replace('<h2>UNG-CONSTELLATION · Mission Control</h2>', '<h2>UNG-CONSTELLATION · Mission Control</h2>'+nav, 1)
        return HTMLResponse(html)
    return await call_next(request)
