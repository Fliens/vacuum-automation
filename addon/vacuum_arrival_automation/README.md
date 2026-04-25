# Vacuum Arrival Automation Add-on

This folder contains a Supervisor add-on scaffold that bundles:

- the AppDaemon automation app
- generated AppDaemon config from add-on options
- an ingress dashboard for status and controls

## What It Gives You

- a real Home Assistant add-on package structure
- one place to ship the automation code
- local persistence under `/config/appdaemon/storage`
- generated helper YAML files under `/config/vacuum_arrival_automation`

## Current State

This is a pragmatic first add-on packaging of the project.

It is intended to:

1. install AppDaemon in the container
2. copy the bundled automation app into `/config/appdaemon/apps/vacuum_automation`
3. render `/config/appdaemon/apps/vacuum_arrival_automation.yaml` from add-on options
4. generate helper YAML files for the configured entities and rooms
5. refresh the managed Home Assistant connection in `appdaemon.yaml` on every start
6. expose an ingress dashboard in the Home Assistant sidebar
7. start AppDaemon against Home Assistant Core

After install, the user configures the add-on through its options. The add-on then generates:

- `/config/appdaemon/apps/vacuum_arrival_automation.yaml`
- `/config/vacuum_arrival_automation/helpers.generated.yaml`

The user still needs to:

- import the generated helper package into Home Assistant
- validate the result in a real Home Assistant Supervisor setup

Travel mode can now be configured in two ways:

- a home-centered travel radius for "away for a long time"
- an optional hard maximum distance from home as a safety cutoff
