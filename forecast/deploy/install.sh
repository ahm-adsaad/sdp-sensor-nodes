#!/usr/bin/env bash
# Install or update the forecast service on the VPS. Run from anywhere:
#   bash /opt/sdp-sensor-nodes/forecast/deploy/install.sh
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
cd "$here"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --disable-pip-version-check -r requirements.txt
mkdir -p data models out
for unit in deploy/forecast-*.service deploy/forecast-*.timer; do
  sed "s#__FORECAST_DIR__#$here#g" "$unit" | sudo tee "/etc/systemd/system/$(basename "$unit")" > /dev/null
done
sudo systemctl daemon-reload
for timer in deploy/forecast-*.timer; do
  sudo systemctl enable --now "$(basename "$timer")"
done
systemctl list-timers 'forecast-*' --no-pager
