#!/usr/bin/env bash
set -euo pipefail
if [ "$(id -u)" -ne 0 ]; then echo "Run with sudo"; exit 1; fi
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y rtl-sdr hamlib-utils gpsd gpsd-clients chrony python3 python3-venv python3-soapysdr soapysdr-module-rtlsdr git curl
install -d -m 0755 /opt/ung-constellation /etc/ung-constellation /var/lib/ung-constellation/passes /var/lib/ung-constellation/iq /var/lib/ung-constellation/outbox
install -m 0755 edge/constellation-edge.py /opt/ung-constellation/constellation-edge.py
install -m 0755 edge/doppler-receiver.py /opt/ung-constellation/doppler-receiver.py
install -m 0755 edge/iq-monitor.py /opt/ung-constellation/iq-monitor.py
cat >/etc/ung-constellation/edge.json <<'EOF'
{"mode":"receive-only","station_id":"UGANET-GS-001","node_id":"CONSTELLATION-EDGE-001","rigctld":"127.0.0.1:4532","rotctld":"127.0.0.1:4533","gpsd":"127.0.0.1:2947","pass_queue":"/var/lib/ung-constellation/passes","iq_dir":"/var/lib/ung-constellation/iq","outbox":"/var/lib/ung-constellation/outbox","doppler_state":"/var/lib/ung-constellation/doppler.json","spectrum_state":"/var/lib/ung-constellation/spectrum.json"}
EOF
cat >/etc/default/ung-constellation-doppler <<'EOF'
CONSTELLATION_NO_TRANSMIT=true
CONSTELLATION_CLOUD_URL=https://ung-constellation-production.up.railway.app
CONSTELLATION_NORAD_ID=
CONSTELLATION_STATION_LAT=
CONSTELLATION_STATION_LON=
CONSTELLATION_STATION_ELEVATION_M=0
CONSTELLATION_RECEIVE_FREQUENCY_HZ=
CONSTELLATION_DOPPLER_SECONDS=5
EOF
cat >/etc/default/ung-constellation-spectrum <<'EOF'
CONSTELLATION_NO_TRANSMIT=true
CONSTELLATION_DOPPLER_STATE=/var/lib/ung-constellation/doppler.json
CONSTELLATION_SPECTRUM_STATE=/var/lib/ung-constellation/spectrum.json
CONSTELLATION_IQ_DIR=/var/lib/ung-constellation/iq
CONSTELLATION_SPECTRUM_SPAN_HZ=200000
CONSTELLATION_SPECTRUM_BIN_HZ=5000
CONSTELLATION_SPECTRUM_SECONDS=10
CONSTELLATION_IQ_CAPTURE=false
CONSTELLATION_IQ_SECONDS=5
CONSTELLATION_IQ_SAMPLE_RATE=1024000
EOF
cat >/etc/systemd/system/ung-constellation-edge.service <<'EOF'
[Unit]
Description=UNG-CONSTELLATION Ground Station Edge
After=network-online.target gpsd.service
Wants=network-online.target
[Service]
Type=simple
Environment=CONSTELLATION_NO_TRANSMIT=true
Environment=CONSTELLATION_CLOUD_URL=https://ung-constellation-production.up.railway.app
Environment=CONSTELLATION_NODE_ID=CONSTELLATION-EDGE-001
Environment=CONSTELLATION_STATION_ID=UGANET-GS-001
Environment=CONSTELLATION_HEARTBEAT_SECONDS=60
ExecStart=/opt/ung-constellation/constellation-edge.py --daemon
Restart=always
RestartSec=10
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/ung-constellation
[Install]
WantedBy=multi-user.target
EOF
cat >/etc/systemd/system/ung-constellation-doppler.service <<'EOF'
[Unit]
Description=UNG-CONSTELLATION Receive-Only Doppler Controller
After=network-online.target ung-constellation-edge.service
Wants=network-online.target
[Service]
Type=simple
EnvironmentFile=/etc/default/ung-constellation-doppler
ExecStart=/opt/ung-constellation/doppler-receiver.py
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/ung-constellation
[Install]
WantedBy=multi-user.target
EOF
cat >/etc/systemd/system/ung-constellation-spectrum.service <<'EOF'
[Unit]
Description=UNG-CONSTELLATION Receive-Only Spectrum and IQ Monitor
After=ung-constellation-doppler.service
Wants=ung-constellation-doppler.service
[Service]
Type=simple
EnvironmentFile=/etc/default/ung-constellation-spectrum
ExecStart=/opt/ung-constellation/iq-monitor.py
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/ung-constellation
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable ung-constellation-edge.service
printf '\nUNG-CONSTELLATION edge installed in RECEIVE-ONLY mode.\nEdge: sudo systemctl start ung-constellation-edge\nDoppler: configure /etc/default/ung-constellation-doppler, then sudo systemctl enable --now ung-constellation-doppler\nSpectrum: sudo systemctl enable --now ung-constellation-spectrum\nIQ recording is OFF by default; enable only when storage policy is configured.\n'
