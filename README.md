# UNG-CONSTELLATION

National Satellite, Orbital & Remote Sensor Operations System.

This repository hosts the cloud control plane for satellite tracking, orbital operations, telemetry, ground-station coordination, conjunction handling, mission planning, SDR/radio integration hooks, remote sensor ingestion, and UNG platform interoperability.

## Architecture
- Cloud: FastAPI control plane, PostgreSQL persistence, JANUS/IAM authorization, NEXUS/PULSAR event forwarding, and ATLAS/HERMES/HORUS/NOVA/NEMSIS/SENTINEL integrations.
- Edge: Raspberry Pi ground-station node for Hamlib radio/rotator control, RTL-SDR, KISS TNC, IQ capture, GNSS timing, offline pass execution, and authenticated field-sensor gateways.
- Remote Sensor Hub: now a native CONSTELLATION function. It validates sensor readings, normalizes them into the UGATU sensor-event envelope, preserves the original payload, persists delivery state, and forwards events through NEXUS with PULSAR fallback when configured.

## Remote Sensor Hub API
The integrated API is mounted under `/v1/tracker/sensor-hub`:
- `POST /v1/tracker/sensor-hub/readings` — authenticated field-sensor ingestion.
- `GET /v1/tracker/sensor-hub/status` — operator/observer status and routing state.
- `GET /v1/tracker/sensor-hub/events` — recent persisted sensor events.

The sensor U-Code mapping preserves the existing Remote Sensor Hub contract (`U-9210` through `U-9290`). Credentials remain server-side and are never returned to sensors or browsers.

## Safety
RF transmit functions remain disabled by default. `CONSTELLATION_NO_TRANSMIT=true` should remain enabled until licensed hardware and approved operating procedures are in place.
