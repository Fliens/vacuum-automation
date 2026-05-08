# GhostVacuum

Smart vacuum automation for Home Assistant - cleans while you're away and finishes before you return.

Based on the [`Tasshack/dreame-vacuum`](https://github.com/Tasshack/dreame-vacuum) custom integration.

## What It Does

- Cleans only while everybody in the home is away
- Plans one room at a time based on return ETA and distance
- Stops automatic cleaning if someone gets back too early
- Supports multiple residents through `presence_entities`
- Supports any city or region through `travel_pause_zone`
- Learns real room durations from successful runs
- Keeps a persistent run history database on disk
- Publishes weekly stats and room stats as Home Assistant sensors
- Lets you edit room weight, interval, duration, and enable state from the UI
- Provides an add-on sidebar dashboard for status and controls
- Ships a Supervisor add-on with option-based config rendering

## Main Concepts

### Occupancy

- `presence_entities`: everyone who lives there
- Cleaning starts only when all of them are away
- Cleaning stops when one of them comes back

### Travel Model

- `travel_person_entity`: whose commute should drive the ETA logic
- `waze_entity`: preferred source for return ETA
- `distance_entity`: optional direct distance source
- Fallback: calculate distance from `travel_person_entity` to `zone.home`

### Long Trip Pause

- `travel_pause_zone`: your city or usual region
- After `travel_pause_after_hours` outside that zone, the automation pauses
- If you do not need this, leave it out

### Learning

- Successful runs are stored in a persistent history file
- Room durations are learned from the last few successful runs
- Learned durations become the planning duration when learning is enabled

## Add-on Dashboard

The Supervisor add-on provides a built-in sidebar dashboard for:

- Live status
- Occupancy summary
- Travel logic status
- Automation toggles
- Notification toggles

## Local Dashboard Development

You can run the add-on dashboard locally with mocked Home Assistant data:

```bash
./scripts/dev_dashboard.sh
```

Then open:

```text
http://127.0.0.1:8099
```

Running the command again restarts the previously tracked local dashboard, so you
do not need to manually `pkill` old Python processes while iterating.

- The server reads the dashboard from modular files in `addon/ghostvacuum/dashboard/`:
- `index.html` — landing dashboard markup
- `styles.css` — all CSS styles
- `scripts.js` — client-side JavaScript (drag/drop, polling, interactions)

The server assembles these files on every request, allowing you to edit individual
components without restarting. See [dashboard/README.md](addon/ghostvacuum/dashboard/README.md)
for a complete guide to the structure and data attributes.

Useful commands:

```bash
./scripts/dev_dashboard.sh status
./scripts/dev_dashboard.sh stop
./scripts/dev_dashboard.sh restart
```

To use another port:

```bash
SIDEBAR_REDIRECT_PORT=8100 ./scripts/dev_dashboard.sh
```

## Sensors Exposed by the App

- `sensor.vacuum_automation_status`
- `sensor.vacuum_automation_active_room`
- `sensor.vacuum_automation_next_room`
- `sensor.vacuum_automation_travel_time`
- `sensor.vacuum_automation_return_window`
- `sensor.vacuum_automation_distance_to_home`
- `sensor.vacuum_automation_weekly_runs`
- `sensor.vacuum_automation_weekly_minutes`
- `sensor.vacuum_automation_history`

## UI Helpers

Global helpers:

- `input_boolean.vacuum_automation_enabled`
- `input_boolean.vacuum_automation_learning_enabled`
- `input_number.vacuum_automation_start_hour`
- `input_number.vacuum_automation_end_hour`
- `input_number.vacuum_automation_return_buffer`
- `input_number.vacuum_automation_fallback_speed`
- `input_number.vacuum_automation_default_travel_time`

Per-room helpers follow this pattern:

- `input_boolean.vacuum_automation_<room>_enabled`
- `input_number.vacuum_automation_<room>_weight`
- `input_number.vacuum_automation_<room>_interval_h`
- `input_number.vacuum_automation_<room>_duration_min`

Example rooms included in the sample setup:

- `bad`
- `kueche`
- `wohnzimmer`
- `schlafzimmer`

## Repo Layout

- `apps/vacuum_automation/`: AppDaemon app and sample config
- `setup/`: helper and zone examples
- `addon/ghostvacuum/`: Supervisor add-on with generated config, helpers, and an ingress dashboard
- `INSTALLATION.md`: setup guide
