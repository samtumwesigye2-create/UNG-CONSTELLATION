#!/usr/bin/env bash
set -euo pipefail
if [ "$(id -u)" -ne 0 ]; then echo "Run with sudo"; exit 1; fi
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y rtl-sdr hamlib-utils gpsd gpsd-clients chrony python3 python3-venv git curl
install -d -m 0755 /opt/ung-constellation /etc/ung-constellation /var/lib/ung-constellation/passes /var/lib/ung-constellation/iq
install -m 0755 edge/constellation-edge.py /opt/ung-constellation/constellation-edge.py
cat >/etc/ung-constellation/edge.json <<'EOF'
{"mode":"receive-only","rigctld":"127.0.0.1:4532","rotctld":"127.0.0.1:4533","gpsd":"127.0.0.1:2947","pass_queue":"/var/lib/ung-constellation/passes","iq_dir":"/var/lib/ung-constellation/iq"}
EOF
cat >/etc/systemd/system/ung-constellation-edge.service <<'EOF'
[Unit]
Description=UNG-CONSTELLATION Ground Station Edge
After=network-online.target gpsd.service
Wants=network-online.target
[Service]
Type=oneshot
Environment=CONSTELLATION_NO_TRANSMIT=true
ExecStart=/opt/ung-constellation/constellation-edge.py
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/ung-constellation
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable ung-constellation-edge.service
printf '\nUNG-CONSTELLATION edge installed in RECEIVE-ONLY mode.\nRun: sudo systemctl start ung-constellation-edge && sudo journalctl -u ung-constellation-edge -n 100 --no-pager\n'
