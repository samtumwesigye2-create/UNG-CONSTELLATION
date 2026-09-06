import os
from fastapi import FastAPI, Body, Depends, HTTPException
from . import db, ccsds, integrations, operations
from .security import require_role

app=FastAPI(title='UNG-CONSTELLATION',version='1.0.0')
NO_TRANSMIT=os.getenv('CONSTELLATION_NO_TRANSMIT','true').lower() not in ('0','false','no')

@app.on_event('startup')
def startup():
    try: db.init_db()
    except Exception: pass

@app.get('/')
def root():
    return {'service':'UNG-CONSTELLATION','name':'National Satellite & Orbital Operations System','version':'1.0.0','no_transmit':NO_TRANSMIT}

@app.get('/health')
def health():
    return {'status':'ok','service':'UNG-CONSTELLATION'}

@app.get('/ready')
def ready():
    d=db.readiness()
    return {'ready': (not d['configured']) or d['connected'], 'database':d, 'integrations':integrations.status(), 'no_transmit':NO_TRANSMIT}

@app.get('/v1/system')
def system():
    return {'service':'UNG-CONSTELLATION','mission':'Satellite tracking, orbital operations, ground-station coordination and telemetry','integrations':integrations.status(),'no_transmit':NO_TRANSMIT}

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
