import os, requests, hmac
from fastapi import Header, HTTPException

IAM_BASE_URL=(os.getenv('IAM_BASE_URL') or os.getenv('JANUS_BASE_URL') or '').rstrip('/')
SERVICE_TOKEN=os.getenv('CONSTELLATION_SERVICE_TOKEN','')
EDGE_API_KEY=os.getenv('CONSTELLATION_EDGE_API_KEY','')
ROLE_ORDER={'observer':1,'operator':2,'mission_controller':3,'flight_director':4,'administrator':5}

def _roles(data):
    raw=data.get('roles') or data.get('scopes') or []
    if isinstance(raw,str): raw=raw.replace(',',' ').split()
    return {str(x).lower() for x in raw}

def require_edge_key(x_edge_key: str|None = Header(default=None)):
    if not EDGE_API_KEY:
        raise HTTPException(503,'Edge service identity not configured')
    if not x_edge_key or not hmac.compare_digest(x_edge_key,EDGE_API_KEY):
        raise HTTPException(401,'Invalid edge service credential')
    return {'sub':'constellation-edge','service_identity':True}

def require_role(min_role='observer'):
    def dep(authorization: str|None = Header(default=None)):
        if not authorization or not authorization.lower().startswith('bearer '):
            raise HTTPException(401,'Bearer token required')
        token=authorization.split(' ',1)[1]
        if SERVICE_TOKEN and token==SERVICE_TOKEN:
            return {'sub':'constellation-service','roles':['administrator']}
        if not IAM_BASE_URL: raise HTTPException(503,'JANUS/IAM not configured')
        try:
            r=requests.post(f'{IAM_BASE_URL}/v1/auth/introspect',json={'token':token},timeout=5)
            r.raise_for_status(); data=r.json()
        except requests.RequestException as e:
            raise HTTPException(503,f'IAM introspection unavailable: {e}')
        if not data.get('active',data.get('ok',False)): raise HTTPException(401,'Invalid or inactive token')
        highest=max([ROLE_ORDER.get(r,0) for r in _roles(data)] or [0])
        if highest < ROLE_ORDER[min_role]: raise HTTPException(403,f'{min_role} role required')
        return data
    return dep
