import json, os
DATABASE_URL=os.getenv('DATABASE_URL','').strip()
def enabled():return bool(DATABASE_URL)
def connect():
 if not DATABASE_URL:raise RuntimeError('DATABASE_URL not configured')
 import psycopg;return psycopg.connect(DATABASE_URL)
def init_db():
 if not enabled():return False
 ddl='''CREATE TABLE IF NOT EXISTS constellation_audit(id BIGSERIAL PRIMARY KEY,ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),actor TEXT,action TEXT NOT NULL,resource TEXT,details JSONB NOT NULL DEFAULT '{}'::jsonb);CREATE TABLE IF NOT EXISTS constellation_telemetry(id BIGSERIAL PRIMARY KEY,ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),satellite TEXT NOT NULL,station_id TEXT,protocol TEXT,payload JSONB NOT NULL);CREATE TABLE IF NOT EXISTS constellation_commands(id UUID PRIMARY KEY,satellite TEXT NOT NULL,payload_hex TEXT NOT NULL,status TEXT NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),expires_at TIMESTAMPTZ,approved_by TEXT[],sent_at TIMESTAMPTZ,error TEXT,metadata JSONB NOT NULL DEFAULT '{}'::jsonb);CREATE TABLE IF NOT EXISTS constellation_cdm_events(id BIGSERIAL PRIMARY KEY,object_primary TEXT NOT NULL,object_secondary TEXT NOT NULL,tca TIMESTAMPTZ,miss_distance_km DOUBLE PRECISION,probability DOUBLE PRECISION,source TEXT,payload JSONB NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW());CREATE TABLE IF NOT EXISTS constellation_stations(id TEXT PRIMARY KEY,name TEXT NOT NULL,lat DOUBLE PRECISION,lon DOUBLE PRECISION,elevation_m DOUBLE PRECISION DEFAULT 0,capabilities JSONB NOT NULL DEFAULT '{}'::jsonb,enabled BOOLEAN NOT NULL DEFAULT TRUE,updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW());CREATE TABLE IF NOT EXISTS constellation_tle(norad_id TEXT PRIMARY KEY,name TEXT NOT NULL,line1 TEXT NOT NULL,line2 TEXT NOT NULL,source TEXT,fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW());CREATE TABLE IF NOT EXISTS constellation_edge_nodes(id TEXT PRIMARY KEY,station_id TEXT,hostname TEXT,receive_only BOOLEAN NOT NULL DEFAULT TRUE,capabilities JSONB NOT NULL DEFAULT '{}'::jsonb,health JSONB NOT NULL DEFAULT '{}'::jsonb,last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),enabled BOOLEAN NOT NULL DEFAULT TRUE);CREATE TABLE IF NOT EXISTS constellation_pass_plans(id BIGSERIAL PRIMARY KEY,satellite TEXT NOT NULL,norad_id TEXT,station_id TEXT,rise_time TIMESTAMPTZ,culmination_time TIMESTAMPTZ,set_time TIMESTAMPTZ,max_elevation_deg DOUBLE PRECISION,status TEXT NOT NULL DEFAULT 'planned',details JSONB NOT NULL DEFAULT '{}'::jsonb,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW());CREATE TABLE IF NOT EXISTS constellation_rf_samples(id BIGSERIAL PRIMARY KEY,ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),node_id TEXT NOT NULL,station_id TEXT,norad_id TEXT,center_hz DOUBLE PRECISION,snr_db DOUBLE PRECISION,noise_floor_db DOUBLE PRECISION,peak_frequency_hz DOUBLE PRECISION,peak_power_db DOUBLE PRECISION,bins JSONB NOT NULL DEFAULT '[]'::jsonb);CREATE INDEX IF NOT EXISTS constellation_rf_samples_ts_idx ON constellation_rf_samples(ts DESC);CREATE TABLE IF NOT EXISTS constellation_reception_archives(id BIGSERIAL PRIMARY KEY,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),node_id TEXT,station_id TEXT,norad_id TEXT,satellite TEXT,start_time TIMESTAMPTZ,end_time TIMESTAMPTZ,max_snr_db DOUBLE PRECISION,sample_count INTEGER NOT NULL DEFAULT 0,iq_reference TEXT,metadata JSONB NOT NULL DEFAULT '{}'::jsonb);'''
 with connect() as c:
  with c.cursor() as cur:cur.execute(ddl)
  c.commit()
 return True
def readiness():
 if not enabled():return {'configured':False,'connected':False}
 try:
  with connect() as c:
   with c.cursor() as cur:cur.execute('SELECT 1');cur.fetchone()
  return {'configured':True,'connected':True}
 except Exception as e:return {'configured':True,'connected':False,'error':str(e)}
def audit(actor,action,resource='',details=None):
 if enabled():
  with connect() as c:
   with c.cursor() as cur:cur.execute('INSERT INTO constellation_audit(actor,action,resource,details) VALUES(%s,%s,%s,%s)',(actor,action,resource,json.dumps(details or {})))
   c.commit()
def save_telemetry(satellite,station_id,protocol,payload):
 if enabled():
  with connect() as c:
   with c.cursor() as cur:cur.execute('INSERT INTO constellation_telemetry(satellite,station_id,protocol,payload) VALUES(%s,%s,%s,%s)',(satellite,station_id,protocol,json.dumps(payload)))
   c.commit()
def save_cdm(x):
 if enabled():
  with connect() as c:
   with c.cursor() as cur:cur.execute('INSERT INTO constellation_cdm_events(object_primary,object_secondary,tca,miss_distance_km,probability,source,payload) VALUES(%s,%s,%s,%s,%s,%s,%s)',(x.get('object_primary'),x.get('object_secondary'),x.get('tca'),x.get('miss_distance_km'),x.get('probability'),x.get('source'),json.dumps(x)))
   c.commit()
def upsert_tle(norad_id,name,line1,line2,source='manual'):
 if enabled():
  with connect() as c:
   with c.cursor() as cur:cur.execute('INSERT INTO constellation_tle(norad_id,name,line1,line2,source) VALUES(%s,%s,%s,%s,%s) ON CONFLICT(norad_id) DO UPDATE SET name=EXCLUDED.name,line1=EXCLUDED.line1,line2=EXCLUDED.line2,source=EXCLUDED.source,fetched_at=NOW()',(str(norad_id),name,line1,line2,source))
   c.commit()
def get_tle(n):
 if not enabled():return None
 with connect() as c:
  with c.cursor() as cur:cur.execute('SELECT norad_id,name,line1,line2,source,fetched_at FROM constellation_tle WHERE norad_id=%s',(str(n),));r=cur.fetchone()
 return None if not r else {'norad_id':r[0],'name':r[1],'line1':r[2],'line2':r[3],'source':r[4],'fetched_at':r[5].isoformat()}
def edge_heartbeat(node_id,station_id,hostname,receive_only,capabilities,health):
 if not enabled():return
 with connect() as c:
  with c.cursor() as cur:
   cur.execute('INSERT INTO constellation_edge_nodes(id,station_id,hostname,receive_only,capabilities,health) VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(id) DO UPDATE SET station_id=EXCLUDED.station_id,hostname=EXCLUDED.hostname,receive_only=EXCLUDED.receive_only,capabilities=EXCLUDED.capabilities,health=EXCLUDED.health,last_seen=NOW()',(node_id,station_id,hostname,bool(receive_only),json.dumps(capabilities or {}),json.dumps(health or {})))
   s=((health or {}).get('rf') or {}).get('spectrum') or (health or {}).get('spectrum') or {}
   if s.get('ok') and s.get('bins'):
    p=s.get('peak') or {};cur.execute('INSERT INTO constellation_rf_samples(node_id,station_id,norad_id,center_hz,snr_db,noise_floor_db,peak_frequency_hz,peak_power_db,bins) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)',(node_id,station_id,s.get('norad_id'),s.get('center_hz'),s.get('snr_db'),s.get('noise_floor_db'),p.get('frequency_hz'),p.get('power_db'),json.dumps(s.get('bins') or [])))
  c.commit()
def list_edge_nodes():
 if not enabled():return []
 with connect() as c:
  with c.cursor() as cur:cur.execute('SELECT id,station_id,hostname,receive_only,capabilities,health,last_seen,enabled FROM constellation_edge_nodes ORDER BY last_seen DESC');rows=cur.fetchall()
 return [{'id':r[0],'station_id':r[1],'hostname':r[2],'receive_only':r[3],'capabilities':r[4],'health':r[5],'last_seen':r[6].isoformat(),'enabled':r[7]} for r in rows]
def rf_history(node_id='CONSTELLATION-EDGE-001',minutes=30,limit=240):
 if not enabled():return []
 with connect() as c:
  with c.cursor() as cur:cur.execute("SELECT ts,center_hz,snr_db,noise_floor_db,peak_frequency_hz,peak_power_db,bins,norad_id FROM constellation_rf_samples WHERE node_id=%s AND ts>=NOW()-(%s * INTERVAL '1 minute') ORDER BY ts DESC LIMIT %s",(node_id,max(1,min(minutes,1440)),max(1,min(limit,1000))));rows=cur.fetchall()
 return [{'time':r[0].isoformat(),'center_hz':r[1],'snr_db':r[2],'noise_floor_db':r[3],'peak_frequency_hz':r[4],'peak_power_db':r[5],'bins':r[6],'norad_id':r[7]} for r in reversed(rows)]
def archive_recent_pass(node_id='CONSTELLATION-EDGE-001',norad_id=None,satellite=None,minutes=30,station_id='UGANET-GS-001',iq_reference=None):
 if not enabled():return None
 with connect() as c:
  with c.cursor() as cur:
   cur.execute("SELECT MIN(ts),MAX(ts),MAX(snr_db),COUNT(*) FROM constellation_rf_samples WHERE node_id=%s AND (%s IS NULL OR norad_id=%s) AND ts>=NOW()-(%s * INTERVAL '1 minute')",(node_id,norad_id,norad_id,max(1,min(minutes,1440))));r=cur.fetchone()
   if not r or not r[3]:return None
   cur.execute('INSERT INTO constellation_reception_archives(node_id,station_id,norad_id,satellite,start_time,end_time,max_snr_db,sample_count,iq_reference,metadata) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id',(node_id,station_id,norad_id,satellite,r[0],r[1],r[2],r[3],iq_reference,json.dumps({'receive_only':True,'window_minutes':minutes})));aid=cur.fetchone()[0]
  c.commit()
 return aid
def list_archives(limit=50):
 if not enabled():return []
 with connect() as c:
  with c.cursor() as cur:cur.execute('SELECT id,node_id,station_id,norad_id,satellite,start_time,end_time,max_snr_db,sample_count,iq_reference,metadata FROM constellation_reception_archives ORDER BY created_at DESC LIMIT %s',(max(1,min(limit,200)),));rows=cur.fetchall()
 return [{'id':r[0],'node_id':r[1],'station_id':r[2],'norad_id':r[3],'satellite':r[4],'start_time':r[5].isoformat() if r[5] else None,'end_time':r[6].isoformat() if r[6] else None,'max_snr_db':r[7],'sample_count':r[8],'iq_reference':r[9],'metadata':r[10]} for r in rows]
def archive_samples(archive_id,limit=1000):
 if not enabled():return None
 with connect() as c:
  with c.cursor() as cur:
   cur.execute('SELECT id,node_id,station_id,norad_id,satellite,start_time,end_time,max_snr_db,sample_count,iq_reference,metadata FROM constellation_reception_archives WHERE id=%s',(int(archive_id),));a=cur.fetchone()
   if not a:return None
   cur.execute('SELECT ts,center_hz,snr_db,noise_floor_db,peak_frequency_hz,peak_power_db,bins,norad_id FROM constellation_rf_samples WHERE node_id=%s AND ts BETWEEN %s AND %s AND (%s IS NULL OR norad_id=%s) ORDER BY ts ASC LIMIT %s',(a[1],a[5],a[6],a[3],a[3],max(1,min(int(limit),5000))));rows=cur.fetchall()
 archive={'id':a[0],'node_id':a[1],'station_id':a[2],'norad_id':a[3],'satellite':a[4],'start_time':a[5].isoformat() if a[5] else None,'end_time':a[6].isoformat() if a[6] else None,'max_snr_db':a[7],'sample_count':a[8],'iq_reference':a[9],'metadata':a[10]}
 samples=[{'time':r[0].isoformat(),'center_hz':r[1],'snr_db':r[2],'noise_floor_db':r[3],'peak_frequency_hz':r[4],'peak_power_db':r[5],'bins':r[6],'norad_id':r[7]} for r in rows]
 return {'archive':archive,'samples':samples}
def save_pass_plan(satellite,norad_id,station_id,p):
 if not enabled():return
 with connect() as c:
  with c.cursor() as cur:cur.execute('INSERT INTO constellation_pass_plans(satellite,norad_id,station_id,rise_time,culmination_time,set_time,max_elevation_deg,details) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',(satellite,str(norad_id) if norad_id is not None else None,station_id,(p.get('rise') or {}).get('time'),(p.get('culmination') or {}).get('time'),(p.get('set') or {}).get('time'),p.get('max_elevation_deg'),json.dumps(p)))
  c.commit()
