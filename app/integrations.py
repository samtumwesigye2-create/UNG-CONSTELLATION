import os, requests

SERVICES={k:os.getenv(f'{k}_BASE_URL','').rstrip('/') for k in ['ATLAS','PULSAR','HERMES','HORUS','NOVA','NEMSIS','SENTINEL','NEXUS']}

def status():
    return {k:{'configured':bool(v),'url':v if v else None} for k,v in SERVICES.items()}

def publish_event(event_type,payload):
    url=SERVICES.get('PULSAR')
    if not url: return {'sent':False,'reason':'PULSAR not configured'}
    try:
        r=requests.post(f'{url}/v1/events',json={'type':event_type,'payload':payload},timeout=5)
        return {'sent':r.ok,'status_code':r.status_code,'via':'PULSAR'}
    except requests.RequestException as e:
        return {'sent':False,'error':str(e),'via':'PULSAR'}

def sensor_hub_status():
    nexus=SERVICES.get('NEXUS')
    pulsar=SERVICES.get('PULSAR')
    return {
        'nexus_configured':bool(nexus),
        'pulsar_fallback_configured':bool(pulsar),
        'route':'NEXUS' if nexus else ('PULSAR' if pulsar else 'LOCAL_ONLY'),
    }

def publish_sensor_event(event):
    """Forward a normalized Remote Sensor Hub event without exposing credentials."""
    nexus=SERVICES.get('NEXUS')
    if nexus:
        headers={'Content-Type':'application/json'}
        token=os.getenv('NEXUS_TOKEN','').strip()
        if token: headers['Authorization']=f'Bearer {token}'
        try:
            r=requests.post(f'{nexus}/v1/inbound',json=event,headers=headers,timeout=5)
            return {'sent':r.ok,'status_code':r.status_code,'via':'NEXUS'}
        except requests.RequestException as e:
            return {'sent':False,'error':str(e),'via':'NEXUS'}
    result=publish_event(event.get('event_type','sensor.reading.received'),event)
    if not result.get('sent') and result.get('reason')=='PULSAR not configured':
        result={'sent':False,'reason':'NEXUS and PULSAR not configured','via':'LOCAL_ONLY'}
    return result
