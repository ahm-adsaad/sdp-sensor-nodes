#!/usr/bin/env bash
# Install or update the forecast service on the VPS. Run from anywhere:
#   bash /opt/sdp-sensor-nodes/forecast/deploy/install.sh
set -euo pipefail
if [ "$(id -u)" -eq 0 ]; then echo "run install.sh as the user that owns the checkout, not root" >&2; exit 1; fi
here="$(cd "$(dirname "$0")/.." && pwd)"
cd "$here"
user="$(id -un)"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --disable-pip-version-check -r requirements.txt
mkdir -p data models out
[ -f .env ] || echo "warning: forecast/.env is missing; predict and ratio will fail until it exists" >&2
for unit in deploy/forecast-*.service deploy/forecast-*.timer; do
  sed -e "s#__FORECAST_DIR__#$here#g" -e "s#__FORECAST_USER__#$user#g" "$unit" | sudo tee "/etc/systemd/system/$(basename "$unit")" > /dev/null
done
sudo systemctl daemon-reload
for timer in deploy/forecast-*.timer; do
  sudo systemctl enable --now "$(basename "$timer")"
done
systemctl list-timers 'forecast-*' --no-pager
