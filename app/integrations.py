import os, requests

SERVICES={k:os.getenv(f'{k}_BASE_URL','').rstrip('/') for k in ['ATLAS','PULSAR','HERMES','HORUS','NOVA','NEMSIS','SENTINEL']}

def status():
    return {k:{'configured':bool(v),'url':v if v else None} for k,v in SERVICES.items()}

def publish_event(event_type,payload):
    url=SERVICES.get('PULSAR')
    if not url: return {'sent':False,'reason':'PULSAR not configured'}
    try:
        r=requests.post(f'{url}/v1/events',json={'type':event_type,'payload':payload},timeout=5)
        return {'sent':r.ok,'status_code':r.status_code}
    except requests.RequestException as e:
        return {'sent':False,'error':str(e)}
