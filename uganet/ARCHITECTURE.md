# UGANET — Uganda Grid Area Network

UGANET is the private local/edge network layer for UNG systems. It is distinct from HERMES: UGANET provides local connectivity; HERMES provides communications services over available networks.

## Ground Station 001

- UGANET-GW-001: MacBook Mission Control / local gateway
- CONSTELLATION-EDGE-001: Raspberry Pi hardware controller
- SDR-001: RTL-SDR receive hardware
- Future: GNSS-001, ROTATOR-001, RADIO-001, TNC-001
- Cloud: UNG-CONSTELLATION via secure outbound connectivity

## Network zones

1. OPERATOR — Mission Control workstation and authorized operator devices.
2. EDGE — Raspberry Pi and trusted UNG edge controllers.
3. RF-HARDWARE — SDR/radio/TNC/rotator/GNSS equipment where network-capable.
4. MANAGEMENT — administrative access; restricted from ordinary clients.
5. GUEST/UNTRUSTED — isolated; no access to operational equipment.

## Security baseline

- No inbound Internet exposure is required for Ground Station 001.
- Cloud synchronization originates outbound from the station.
- JANUS/IAM identities authorize UNG applications; local device credentials remain separate.
- Do not bridge guest/untrusted clients into EDGE or RF-HARDWARE.
- Firewall default deny between zones; permit only required service flows.
- RF transmit remains disabled by default. CONSTELLATION_NO_TRANSMIT=true.
- Record device identity, station identity, health and synchronization events for audit.

## Resilience

The MacBook is the initial UGANET gateway but UGANET is not architecturally dependent on it. A dedicated router/firewall can replace the gateway later without changing CONSTELLATION edge identities or cloud APIs.

CONSTELLATION-EDGE-001 continues scheduled receive/pass operations from its local queue during WAN/cloud outages and synchronizes results after connectivity returns.
