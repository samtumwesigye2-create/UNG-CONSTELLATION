import json, os
from contextlib import contextmanager

DATABASE_URL = os.getenv('DATABASE_URL','').strip()

def enabled(): return bool(DATABASE_URL)

def connect():
    if not DATABASE_URL: raise RuntimeError('DATABASE_URL not configured')
    import psycopg
    return psycopg.connect(DATABASE_URL)

def init_db():
    if not enabled(): return False
    ddl='''
    CREATE TABLE IF NOT EXISTS constellation_audit(
      id BIGSERIAL PRIMARY KEY, ts TIMESTAMPTZ NOT NULL DEFAULT NOW(), actor TEXT,
      action TEXT NOT NULL, resource TEXT, details JSONB NOT NULL DEFAULT '{}'::jsonb);
    CREATE TABLE IF NOT EXISTS constellation_telemetry(
      id BIGSERIAL PRIMARY KEY, ts TIMESTAMPTZ NOT NULL DEFAULT NOW(), satellite TEXT NOT NULL,
      station_id TEXT, protocol TEXT, payload JSONB NOT NULL);
    CREATE TABLE IF NOT EXISTS constellation_commands(
      id UUID PRIMARY KEY, satellite TEXT NOT NULL, payload_hex TEXT NOT NULL, status TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), expires_at TIMESTAMPTZ, approved_by TEXT[],
      sent_at TIMESTAMPTZ, error TEXT, metadata JSONB NOT NULL DEFAULT '{}'::jsonb);
    CREATE TABLE IF NOT EXISTS constellation_cdm_events(
      id BIGSERIAL PRIMARY KEY, object_primary TEXT NOT NULL, object_secondary TEXT NOT NULL,
      tca TIMESTAMPTZ, miss_distance_km DOUBLE PRECISION, probability DOUBLE PRECISION,
      source TEXT, payload JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW());
    CREATE TABLE IF NOT EXISTS constellation_stations(
      id TEXT PRIMARY KEY, name TEXT NOT NULL, lat DOUBLE PRECISION, lon DOUBLE PRECISION,
      elevation_m DOUBLE PRECISION DEFAULT 0, capabilities JSONB NOT NULL DEFAULT '{}'::jsonb,
      enabled BOOLEAN NOT NULL DEFAULT TRUE, updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW());
    '''
    with connect() as c:
        with c.cursor() as cur: cur.execute(ddl)
        c.commit()
    return True

def readiness():
    if not enabled(): return {'configured':False,'connected':False}
    try:
        with connect() as c:
            with c.cursor() as cur:
                cur.execute('SELECT 1'); cur.fetchone()
        return {'configured':True,'connected':True}
    except Exception as e:
        return {'configured':True,'connected':False,'error':str(e)}

def audit(actor, action, resource='', details=None):
    if not enabled(): return
    with connect() as c:
        with c.cursor() as cur:
            cur.execute('INSERT INTO constellation_audit(actor,action,resource,details) VALUES(%s,%s,%s,%s)',
                        (actor,action,resource,json.dumps(details or {})))
        c.commit()

def save_telemetry(satellite, station_id, protocol, payload):
    if not enabled(): return
    with connect() as c:
        with c.cursor() as cur:
            cur.execute('INSERT INTO constellation_telemetry(satellite,station_id,protocol,payload) VALUES(%s,%s,%s,%s)',
                        (satellite,station_id,protocol,json.dumps(payload)))
        c.commit()

def save_cdm(cdm):
    if not enabled(): return
    with connect() as c:
        with c.cursor() as cur:
            cur.execute('''INSERT INTO constellation_cdm_events(object_primary,object_secondary,tca,miss_distance_km,probability,source,payload)
                           VALUES(%s,%s,%s,%s,%s,%s,%s)''',
                        (cdm.get('object_primary'),cdm.get('object_secondary'),cdm.get('tca'),cdm.get('miss_distance_km'),
                         cdm.get('probability'),cdm.get('source'),json.dumps(cdm)))
        c.commit()
