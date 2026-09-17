"""Remote Sensor Hub integrated into UNG-CONSTELLATION.

Accepts authenticated field-sensor readings, normalizes them into the UGATU
sensor-event envelope, persists delivery state when PostgreSQL is configured,
and forwards the normalized event into NEXUS (or PULSAR as the existing
CONSTELLATION event-backbone fallback).
"""
from datetime import datetime, timezone
import json
import uuid

from fastapi import APIRouter, Body, Depends, HTTPException

from . import db, integrations
from .security import require_edge_key, require_role

router = APIRouter(prefix="/sensor-hub", tags=["remote-sensor-hub"])

U_CODES = {
    "sensor.reading.received": "U-9210",
    "sensor.threshold.alert": "U-9220",
    "sensor.offline": "U-9230",
    "sensor.restored": "U-9240",
    "sensor.data_quality.exception": "U-9250",
    "sensor.calibration.maintenance": "U-9260",
    "sensor.manual_reading": "U-9270",
    "sensor.event.acknowledged": "U-9280",
    "sensor.integration.audit": "U-9290",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_event(sensor_id: str, data: dict, event_type: str = "sensor.reading.received", observed_at: str | None = None, metadata: dict | None = None) -> dict:
    sensor_id = (sensor_id or "").strip()
    if not sensor_id:
        raise ValueError("sensor_id is required")
    if not isinstance(data, dict):
        raise ValueError("data must be a JSON object")
    if event_type not in U_CODES:
        raise ValueError(f"unsupported event_type: {event_type}")
    received_at = _now()
    return {
        "message_id": str(uuid.uuid4()),
        "u_code": U_CODES[event_type],
        "event_type": event_type,
        "source_system": "UNG-CONSTELLATION",
        "source_function": "REMOTE-SENSOR-HUB",
        "sensor_id": sensor_id,
        "observed_at": observed_at or received_at,
        "received_at": received_at,
        "data": data,
        "metadata": {"schema_version": "1.0", "transport": "https", **(metadata or {})},
    }


def _ensure_table() -> None:
    if not db.enabled():
        return
    with db.connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""CREATE TABLE IF NOT EXISTS constellation_sensor_events(
                id BIGSERIAL PRIMARY KEY,
                message_id UUID UNIQUE NOT NULL,
                sensor_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                u_code TEXT NOT NULL,
                observed_at TIMESTAMPTZ,
                received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                payload JSONB NOT NULL,
                delivery JSONB NOT NULL DEFAULT '{}'::jsonb
            );
            CREATE INDEX IF NOT EXISTS constellation_sensor_events_sensor_idx
            ON constellation_sensor_events(sensor_id, received_at DESC);""")
        conn.commit()


def _persist(event: dict, delivery: dict) -> None:
    if not db.enabled():
        return
    _ensure_table()
    with db.connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO constellation_sensor_events(message_id,sensor_id,event_type,u_code,observed_at,payload,delivery) VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(message_id) DO UPDATE SET delivery=EXCLUDED.delivery",
                (event["message_id"], event["sensor_id"], event["event_type"], event["u_code"], event["observed_at"], json.dumps(event), json.dumps(delivery)),
            )
        conn.commit()


def _recent(limit: int) -> list[dict]:
    if not db.enabled():
        return []
    _ensure_table()
    with db.connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT message_id,sensor_id,event_type,u_code,observed_at,received_at,payload,delivery FROM constellation_sensor_events ORDER BY received_at DESC LIMIT %s", (max(1, min(limit, 200)),))
            rows = cur.fetchall()
    return [{"message_id": str(r[0]), "sensor_id": r[1], "event_type": r[2], "u_code": r[3], "observed_at": r[4].isoformat() if r[4] else None, "received_at": r[5].isoformat(), "payload": r[6], "delivery": r[7]} for r in rows]


@router.get("/status")
def status(user=Depends(require_role("observer"))):
    return {
        "service": "UNG-CONSTELLATION",
        "function": "REMOTE-SENSOR-HUB",
        "database": db.readiness(),
        "integration": integrations.sensor_hub_status(),
        "u_codes": U_CODES,
    }


@router.get("/events")
def events(limit: int = 50, user=Depends(require_role("observer"))):
    return {"events": _recent(limit)}


@router.post("/readings", status_code=202)
def ingest_reading(
    sensor_id: str = Body(...),
    data: dict = Body(...),
    event_type: str = Body(default="sensor.reading.received"),
    observed_at: str | None = Body(default=None),
    metadata: dict = Body(default={}),
    edge=Depends(require_edge_key),
):
    try:
        event = normalize_event(sensor_id, data, event_type, observed_at, metadata)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    delivery = integrations.publish_sensor_event(event)
    _persist(event, delivery)
    db.audit(edge.get("sub"), "sensor_hub.ingest", event["sensor_id"], {"message_id": event["message_id"], "u_code": event["u_code"], "delivery": delivery})
    return {"accepted": True, "event": event, "delivery": delivery}
