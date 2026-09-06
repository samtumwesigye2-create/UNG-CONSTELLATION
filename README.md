# UNG-CONSTELLATION

National Satellite & Orbital Operations System.

This repository hosts the cloud control plane for satellite tracking, orbital operations, telemetry, ground-station coordination, conjunction handling, mission planning, SDR/radio integration hooks, and UNG platform interoperability.

## Architecture
- Cloud: FastAPI control plane, PostgreSQL persistence, JANUS/IAM authorization, ATLAS/PULSAR/HERMES/HORUS/NOVA/NEMSIS/SENTINEL integrations.
- Edge: Raspberry Pi ground-station node for Hamlib radio/rotator control, RTL-SDR, KISS TNC, IQ capture, GNSS timing, and offline pass execution.

## Safety
RF transmit functions remain disabled by default. `CONSTELLATION_NO_TRANSMIT=true` should remain enabled until licensed hardware and approved operating procedures are in place.
