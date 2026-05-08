#!/usr/bin/with-contenv bash
set -euo pipefail

mkdir -p /config/appdaemon/apps
mkdir -p /config/appdaemon/apps/vacuum_automation
mkdir -p /config/appdaemon/storage
mkdir -p /config/vacuum_arrival_automation

cp -R /opt/vacuum_automation/app/vacuum_automation/. /config/appdaemon/apps/vacuum_automation/
python /opt/vacuum_automation/render_addon_config.py

# Automatically create Helper entities if they don't exist
echo "Setting up Helper entities..."
python /opt/vacuum_automation/helper_setup.py &

python /opt/vacuum_automation/redirect_dashboard.py &
echo "Generated config files in /config/vacuum_arrival_automation"
exec appdaemon -c /config/appdaemon
