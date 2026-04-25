# Installation

## Path A: Keep Using AppDaemon Directly

### Requirements

1. Home Assistant
2. AppDaemon
3. Dreame Vacuum integration
4. Presence entities for everybody living there
5. A push target such as `notify.mobile_app_*`
6. Ideally a Waze ETA sensor

### 1. Copy the App

Copy `apps/vacuum_automation/` to:

```text
/config/appdaemon/apps/vacuum_automation/
```

### 2. Merge the App Config

Use `apps/vacuum_automation/apps.yaml` as your starting point.

Must adjust:

- `vacuum_entity`
- `notify_service`
- `presence_entities`
- `person_entity`
- `travel_person_entity`
- `waze_entity`
- room `segment_id` values

Recommended:

- `dashboard_path`
- `travel_pause_zone`
- `enabled_entity`
- `learning_enabled_entity`

### 3. Create Helpers

Use `setup/helpers.yaml` as a starting point.

This creates:

- restart state helper
- global runtime controls
- per-room controls
- learning on/off switch

### 4. Optional Pause Zone

Use `setup/travel_pause_zone.yaml` as an example and replace it with your own city or
region if you want long-trip pausing.

### 5. Import a Dashboard

Choose one:

- `dashboard/vacuum_automation_dashboard.yaml`
- `dashboard/vacuum_automation_mushroom_dashboard.yaml`

The Mushroom version additionally requires:

- Mushroom
- ApexCharts Card

## Path B: Use the Supervisor Add-on Scaffold

The folder `addon/vacuum_arrival_automation/` contains a first Supervisor add-on
packaging of the project.

It bundles:

- the AppDaemon app
- generated AppDaemon config
- generated helper package
- generated dashboards

High-level flow:

1. add the repo as an add-on repository
2. install the add-on
3. fill in the add-on options for your entities and room segment IDs
4. start the add-on so it can generate `/config/appdaemon/apps/vacuum_arrival_automation.yaml`
5. import `/config/vacuum_arrival_automation/helpers.generated.yaml`
6. include `/config/vacuum_arrival_automation/lovelace_dashboards.generated.yaml` in your Home Assistant YAML config
7. restart Home Assistant so the dashboard appears in the sidebar

Example include in `configuration.yaml`:

```yaml
lovelace: !include /config/vacuum_arrival_automation/lovelace_dashboards.generated.yaml
```

If you already have a `lovelace:` section, merge the generated `dashboards:` entries into it instead of replacing your existing config.

The most important option fields are:

- `vacuum_entity`
- `presence_entities`
- `person_entity`
- `travel_person_entity`
- `waze_entity` or `distance_entity`
- `home_override_enabled`, `home_latitude`, `home_longitude`
- `travel_pause_radius_km`
- `max_distance_km`
- `rooms`

For long trips, there are now two separate controls:

- `travel_pause_radius_km`: local radius around your home point; if you stay outside it for longer than `travel_pause_after_hours`, travel mode activates
- `max_distance_km`: hard safety limit from home; once exceeded, travel mode activates immediately

If `home_override_enabled` is `false`, the app uses `home_zone` as the center point. If it is `true`, the dashboard helpers can override the home location with latitude and longitude.

`rooms` is entered as YAML in the add-on options, for example:

```yaml
- id: kueche
  name: Kueche
  segment_id: 16
  interval_h: 48
  weight: 1.2
  duration_min: 12
  enabled: true
  icon: mdi:silverware-fork-knife
```

## Statistics and Learning

The automation writes a persistent history file to:

```text
/config/appdaemon/apps/vacuum_automation/storage/history.json
```

That file is used for:

- recent run history
- weekly statistics
- learned room durations

## Multi-Person Homes

Put all residents into `presence_entities`.

Behavior:

- cleaning starts only when all are away
- cleaning stops if any person returns

The ETA model still uses one configured `travel_person_entity`, because the app
needs one concrete commute to plan against.

## Travel Pause Zone

Replace `travel_pause_zone` with your own city or region, or remove it
completely.

Nothing in the automation requires any specific city anymore.
