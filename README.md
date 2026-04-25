# Vacuum Automation

Arrival-aware vacuum automation for Home Assistant based on the
[`Tasshack/dreame-vacuum`](https://github.com/Tasshack/dreame-vacuum) custom
integration.

## What It Can Do Now

- clean only while everybody in the home is away
- plan one room at a time based on return ETA and distance
- stop automatic cleaning if someone gets back too early
- support multiple residents through `presence_entities`
- support any city or region through `travel_pause_zone`
- learn real room durations from successful runs
- keep a persistent run history database on disk
- publish weekly stats and room stats as Home Assistant sensors
- let you edit room weight, interval, duration, and enable state from the UI
- deep-link push notifications into the dashboard
- provide both a standard dashboard and a Mushroom dashboard
- ship a Supervisor add-on scaffold in `addon/` with option-based config rendering

## Main Concepts

### Occupancy

- `presence_entities`: everyone who lives there
- cleaning starts only when all of them are away
- cleaning stops when one of them comes back

### Travel Model

- `travel_person_entity`: whose commute should drive the ETA logic
- `waze_entity`: preferred source for return ETA
- `distance_entity`: optional direct distance source
- fallback: calculate distance from `travel_person_entity` to `zone.home`

### Long Trip Pause

- `travel_pause_zone`: your city or usual region
- after `travel_pause_after_hours` outside that zone, the automation pauses
- if you do not need this, leave it out

### Learning

- successful runs are stored in a persistent history file
- room durations are learned from the last few successful runs
- learned durations become the planning duration when learning is enabled

## Dashboards

### Standard Dashboard

File: `dashboard/vacuum_automation_dashboard.yaml`

Includes:

- live status
- occupancy summary
- return ETA and cleaning window
- weekly stats
- recent runs
- room ranking
- editable global and per-room helpers

### Mushroom Dashboard

File: `dashboard/vacuum_automation_mushroom_dashboard.yaml`

Requires:

- Mushroom cards
- ApexCharts Card

Includes the same information with a more polished presentation.

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
- `dashboard/`: standard and Mushroom dashboards
- `setup/`: helper and zone examples
- `addon/vacuum_arrival_automation/`: Supervisor add-on scaffold with generated config, helpers, and dashboards
- `INSTALLATION.md`: setup guide
