# GhostVacuum Add-on

This folder contains the Home Assistant Supervisor add-on that bundles:

- the AppDaemon automation app
- generated AppDaemon config from add-on options
- automatic helper creation via Home Assistant API
- an ingress dashboard for status and controls

## What It Gives You

- A real Home Assistant add-on package structure
- One place to ship the automation code
- Local persistence under `/config/appdaemon/storage`
- Automatic helper entity creation - no manual YAML import needed

## How It Works

1. Installs AppDaemon in the container
2. Copies the bundled automation app into `/config/appdaemon/apps/vacuum_automation`
3. Renders `/config/appdaemon/apps/vacuum_arrival_automation.yaml` from add-on options
4. Automatically creates helper entities via the Home Assistant API
5. Refreshes the managed Home Assistant connection in `appdaemon.yaml` on every start
6. Exposes an ingress dashboard in the Home Assistant sidebar
7. Starts AppDaemon against Home Assistant Core

## Configuration

After install, configure the add-on through its options:

- `vacuum_entity`: Your vacuum robot entity
- `presence_entities`: List of person entities to track
- `rooms`: YAML list of rooms with segment IDs
- `waze_entity` or `distance_entity`: For travel time estimation

## Features

### Simulation Mode

Test the add-on without a real vacuum by enabling `simulation_mode`. The automation will calculate everything but skip actual vacuum commands.

### Travel Mode

- `travel_pause_radius_km`: Local radius around home; outside for too long triggers travel mode
- `max_distance_km`: Hard maximum distance for immediate travel mode activation

### Helper Management

- Helpers are created automatically on startup
- Missing helpers are detected and recreated during runtime
- Cleanup endpoint available for uninstallation
