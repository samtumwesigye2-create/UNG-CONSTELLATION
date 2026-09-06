from datetime import datetime, timezone

def telemetry_alarms(fields:dict, limits:dict):
    alarms=[]
    for name,value in fields.items():
        rule=limits.get(name) or {}
        if not isinstance(value,(int,float)): continue
        lo=rule.get('min'); hi=rule.get('max'); critical_lo=rule.get('critical_min'); critical_hi=rule.get('critical_max')
        severity=None
        if critical_lo is not None and value<critical_lo: severity='critical'
        elif critical_hi is not None and value>critical_hi: severity='critical'
        elif lo is not None and value<lo: severity='warning'
        elif hi is not None and value>hi: severity='warning'
        if severity: alarms.append({'field':name,'value':value,'severity':severity,'rule':rule})
    return alarms

def choose_station(pass_candidates:list, stations:dict, station_health:dict):
    ranked=[]
    for candidate in pass_candidates:
        sid=str(candidate.get('station_id',''))
        station=stations.get(sid,{})
        health=station_health.get(sid,{})
        if not sid or station.get('enabled',True) is False or health.get('online',True) is False: continue
        score=float(candidate.get('max_elevation_deg',0))*2 + float(candidate.get('duration_s',0))/60
        score+=float(health.get('score',0))*10
        if station.get('preferred'): score+=25
        ranked.append((score,candidate))
    return max(ranked,key=lambda x:x[0])[1] if ranked else None

def validate_command(command:dict,no_transmit:bool=True):
    payload=command.get('payload_hex','')
    try: bytes.fromhex(payload)
    except Exception: return {'valid':False,'reason':'payload_hex is not valid hex','transmit':False}
    expires=command.get('expires_at')
    if expires:
        try:
            if datetime.fromisoformat(expires.replace('Z','+00:00'))<=datetime.now(timezone.utc):
                return {'valid':False,'reason':'command expired','transmit':False}
        except ValueError:
            return {'valid':False,'reason':'invalid expires_at','transmit':False}
    approvals=command.get('approved_by') or []
    required=int(command.get('required_approvals',2))
    if len(set(approvals))<required:
        return {'valid':False,'reason':f'{required} approvals required','transmit':False}
    return {'valid':True,'transmit':False if no_transmit else True,'message':'preflight passed'}
