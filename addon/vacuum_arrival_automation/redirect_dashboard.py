#!/usr/bin/env python3
"""Ingress dashboard for the vacuum automation add-on."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, List

import yaml


OPTIONS_PATH = Path("/data/options.json")
SUPERVISOR_CORE_API = "http://supervisor/core/api"


def load_options() -> dict:
    try:
        return json.loads(OPTIONS_PATH.read_text())
    except Exception:
        return {}


def parse_rooms(raw_rooms: Any) -> List[dict]:
    if isinstance(raw_rooms, list):
        parsed = raw_rooms
    else:
        try:
            parsed = yaml.safe_load(raw_rooms or "[]")
        except Exception:
            parsed = []

    rooms = []
    for item in parsed or []:
        if not isinstance(item, dict):
            continue
        room_id = str(item.get("id") or item.get("slug") or "").strip()
        room_name = str(item.get("name") or room_id or "Room").strip()
        if not room_id:
            continue
        rooms.append(
            {
                "id": room_id,
                "name": room_name,
                "icon": str(item.get("icon") or "mdi:floor-plan"),
                "segment_id": item.get("segment_id"),
            }
        )
    return rooms


def api_request(path: str, method: str = "GET", payload: dict | None = None):
    token = os.environ.get("SUPERVISOR_TOKEN", "")
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        f"{SUPERVISOR_CORE_API}{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        raw = response.read().decode("utf-8")
        return json.loads(raw) if raw else None


def state_for(entity_id: str):
    try:
        return api_request(f"/states/{entity_id}")
    except Exception:
        return None


def service_call(domain: str, service: str, entity_id: str, data: dict | None = None):
    payload = {"entity_id": entity_id}
    if data:
        payload.update(data)
    return api_request(
        f"/services/{domain}/{service}",
        method="POST",
        payload=payload,
    )


def helper_entities(options: dict, rooms: List[dict]) -> Dict[str, Any]:
    prefix = options.get("dashboard_prefix", "vacuum_automation")
    helper_prefix = options.get("helper_prefix", "vacuum_automation")
    room_entities = []
    for room in rooms:
        room_id = room["id"]
        room_entities.append(
            {
                "id": room_id,
                "name": room["name"],
                "icon": room["icon"],
                "enabled": f"input_boolean.{helper_prefix}_{room_id}_enabled",
                "weight": f"input_number.{helper_prefix}_{room_id}_weight",
                "interval_h": f"input_number.{helper_prefix}_{room_id}_interval_h",
                "duration_min": f"input_number.{helper_prefix}_{room_id}_duration_min",
            }
        )

    return {
        "sensors": {
            "status": f"sensor.{prefix}_status",
            "active_room": f"sensor.{prefix}_active_room",
            "next_room": f"sensor.{prefix}_next_room",
            "travel_time": f"sensor.{prefix}_travel_time",
            "return_window": f"sensor.{prefix}_return_window",
            "distance_to_home": f"sensor.{prefix}_distance_to_home",
            "weekly_runs": f"sensor.{prefix}_weekly_runs",
            "weekly_minutes": f"sensor.{prefix}_weekly_minutes",
            "history": f"sensor.{prefix}_history",
        },
        "global": {
            "enabled": options.get("enabled_entity", f"input_boolean.{helper_prefix}_enabled"),
            "learning": options.get(
                "learning_enabled_entity",
                f"input_boolean.{helper_prefix}_learning_enabled",
            ),
            "travel_logic": options.get(
                "travel_mode_enabled_entity",
                f"input_boolean.{helper_prefix}_travel_mode_enabled",
            ),
            "start_push": options.get(
                "start_notifications_enabled_entity",
                f"input_boolean.{helper_prefix}_start_notifications_enabled",
            ),
            "return_push": options.get(
                "return_summary_enabled_entity",
                f"input_boolean.{helper_prefix}_return_summary_enabled",
            ),
            "custom_home": options.get(
                "home_override_enabled_entity",
                f"input_boolean.{helper_prefix}_home_override_enabled",
            ),
            "start_hour": options.get(
                "start_hour_entity", f"input_number.{helper_prefix}_start_hour"
            ),
            "end_hour": options.get(
                "end_hour_entity", f"input_number.{helper_prefix}_end_hour"
            ),
            "return_buffer": options.get(
                "return_buffer_entity",
                f"input_number.{helper_prefix}_return_buffer",
            ),
            "fallback_speed": options.get(
                "fallback_speed_entity",
                f"input_number.{helper_prefix}_fallback_speed",
            ),
            "default_travel_time": options.get(
                "default_travel_time_entity",
                f"input_number.{helper_prefix}_default_travel_time",
            ),
            "home_latitude": options.get(
                "home_latitude_entity",
                f"input_number.{helper_prefix}_home_latitude",
            ),
            "home_longitude": options.get(
                "home_longitude_entity",
                f"input_number.{helper_prefix}_home_longitude",
            ),
            "travel_pause_radius": options.get(
                "travel_pause_radius_entity",
                f"input_number.{helper_prefix}_travel_pause_radius",
            ),
            "max_distance_km": options.get(
                "max_distance_km_entity",
                f"input_number.{helper_prefix}_max_distance_km",
            ),
        },
        "rooms": room_entities,
    }


def collect_states(entity_map: Dict[str, Any]) -> Dict[str, Any]:
    data: Dict[str, Any] = {"sensors": {}, "global": {}, "rooms": []}
    for key, entity_id in entity_map["sensors"].items():
        data["sensors"][key] = state_for(entity_id)
    for key, entity_id in entity_map["global"].items():
        data["global"][key] = state_for(entity_id)
    for room in entity_map["rooms"]:
        room_state = dict(room)
        for key in ["enabled", "weight", "interval_h", "duration_min"]:
            room_state[f"{key}_state"] = state_for(room[key])
        data["rooms"].append(room_state)
    return data


def build_summary() -> dict:
    options = load_options()
    rooms = parse_rooms(options.get("rooms"))
    entity_map = helper_entities(options, rooms)
    states = collect_states(entity_map)
    status_state = states["sensors"].get("status") or {}
    history_state = states["sensors"].get("history") or {}
    status_attrs = status_state.get("attributes", {}) if isinstance(status_state, dict) else {}
    history_attrs = history_state.get("attributes", {}) if isinstance(history_state, dict) else {}
    return {
        "options": {
            "vacuum_entity": options.get("vacuum_entity"),
            "notify_service": options.get("notify_service"),
            "presence_entities": options.get("presence_entities"),
            "person_entity": options.get("person_entity"),
            "travel_person_entity": options.get("travel_person_entity"),
            "waze_entity": options.get("waze_entity"),
            "distance_entity": options.get("distance_entity"),
            "home_zone": options.get("home_zone"),
            "travel_pause_zone": options.get("travel_pause_zone"),
            "travel_pause_after_hours": options.get("travel_pause_after_hours"),
            "history_weeks": options.get("history_weeks"),
            "learning_window": options.get("learning_window"),
        },
        "entities": entity_map,
        "states": states,
        "status": {
            "reason": status_attrs.get("reason"),
            "presence_summary": status_attrs.get("presence_summary", []),
            "cleaned_during_absence": status_attrs.get("cleaned_during_absence", []),
            "away_since": status_attrs.get("away_since"),
            "travel_mode_reason": status_attrs.get("travel_mode_reason"),
            "distance_km": status_attrs.get("distance_km"),
            "travel_pause_radius_km": status_attrs.get("travel_pause_radius_km"),
            "max_distance_km": status_attrs.get("max_distance_km"),
            "travel_home_zone": status_attrs.get("travel_home_zone"),
            "travel_home_zone_distance_km": status_attrs.get("travel_home_zone_distance_km"),
            "time_window": status_attrs.get("time_window", {}),
            "room_queue": status_attrs.get("room_queue", []),
            "room_stats": status_attrs.get("room_stats", []),
            "recent_runs": status_attrs.get("recent_runs", []),
            "weekly_stats": status_attrs.get("weekly_stats", []),
            "history_entries": status_attrs.get("history_entries", 0),
        },
        "history": {
            "weekly_stats": history_attrs.get("weekly_stats", []),
            "recent_runs": history_attrs.get("recent_runs", []),
        },
    }


HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Vacuum Automation Dashboard</title>
  <style>
    :root {
      --bg: #f2f4ef;
      --panel: rgba(255,255,255,0.88);
      --panel-strong: #ffffff;
      --ink: #152019;
      --muted: #607065;
      --line: rgba(21,32,25,0.1);
      --accent: #1f7a53;
      --accent-2: #dff5ea;
      --accent-3: #0d5c3c;
      --danger: #b4513f;
      --shadow: 0 20px 50px rgba(16, 31, 23, 0.08);
      --radius: 22px;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: var(--ink);
      font-family: ui-sans-serif, system-ui, -apple-system, sans-serif;
      background:
        radial-gradient(circle at top left, rgba(31,122,83,0.14), transparent 28%),
        radial-gradient(circle at top right, rgba(12,94,60,0.12), transparent 22%),
        linear-gradient(180deg, #edf3ed 0%, #f8faf8 100%);
    }
    .shell {
      max-width: 1500px;
      margin: 0 auto;
      padding: 26px;
    }
    .hero {
      background: linear-gradient(135deg, #143528 0%, #1d6144 45%, #2b8960 100%);
      color: white;
      border-radius: 30px;
      padding: 28px;
      box-shadow: var(--shadow);
      position: relative;
      overflow: hidden;
      margin-bottom: 18px;
    }
    .hero::after {
      content: "";
      position: absolute;
      inset: auto -40px -40px auto;
      width: 220px;
      height: 220px;
      border-radius: 999px;
      background: rgba(255,255,255,0.08);
    }
    .hero-top {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: flex-start;
      flex-wrap: wrap;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      background: rgba(255,255,255,0.14);
      border: 1px solid rgba(255,255,255,0.14);
      border-radius: 999px;
      font-size: 12px;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }
    .hero h1 {
      margin: 14px 0 10px;
      font-size: clamp(34px, 5vw, 58px);
      line-height: 0.94;
    }
    .hero p {
      margin: 0;
      max-width: 760px;
      color: rgba(255,255,255,0.88);
      font-size: 16px;
    }
    .status-chip {
      background: rgba(255,255,255,0.14);
      border: 1px solid rgba(255,255,255,0.16);
      border-radius: 18px;
      padding: 14px 18px;
      min-width: 220px;
    }
    .status-chip .label {
      color: rgba(255,255,255,0.7);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      margin-bottom: 6px;
    }
    .status-chip .value {
      font-size: 28px;
      font-weight: 800;
    }
    .layout {
      display: grid;
      grid-template-columns: 1.45fr 0.95fr;
      gap: 18px;
    }
    .stack {
      display: grid;
      gap: 18px;
    }
    .grid {
      display: grid;
      gap: 14px;
    }
    .stats {
      grid-template-columns: repeat(4, minmax(0, 1fr));
    }
    .card {
      background: var(--panel);
      backdrop-filter: blur(10px);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      padding: 18px;
    }
    .section-title {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-bottom: 14px;
    }
    .section-title h2,
    .section-title h3 {
      margin: 0;
      font-size: 18px;
    }
    .section-title p {
      margin: 4px 0 0;
      color: var(--muted);
      font-size: 13px;
    }
    .mini {
      padding: 16px;
      border-radius: 18px;
      background: var(--panel-strong);
      border: 1px solid var(--line);
    }
    .mini .eyebrow {
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      margin-bottom: 8px;
    }
    .mini .big {
      font-size: 28px;
      font-weight: 800;
      line-height: 1;
    }
    .mini .sub {
      margin-top: 8px;
      color: var(--muted);
      font-size: 13px;
    }
    .presence-list, .run-list {
      display: grid;
      gap: 10px;
    }
    .presence-item, .run-item, .queue-item, .week-item {
      display: grid;
      gap: 6px;
      padding: 12px 14px;
      border-radius: 16px;
      background: var(--panel-strong);
      border: 1px solid var(--line);
    }
    .presence-head, .run-head, .queue-head, .week-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      font-weight: 700;
    }
    .muted {
      color: var(--muted);
      font-size: 13px;
    }
    .pill {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border-radius: 999px;
      padding: 4px 10px;
      font-size: 12px;
      font-weight: 700;
      background: var(--accent-2);
      color: var(--accent-3);
    }
    .pill.off { background: #f3e2dc; color: var(--danger); }
    .controls-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }
    .control {
      background: var(--panel-strong);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 14px;
    }
    .control .name {
      font-weight: 700;
      margin-bottom: 6px;
    }
    .control .desc {
      color: var(--muted);
      font-size: 13px;
      margin-bottom: 12px;
      min-height: 34px;
    }
    .control button {
      width: 100%;
      border: 0;
      border-radius: 14px;
      padding: 12px 14px;
      font-size: 14px;
      font-weight: 700;
      cursor: pointer;
      background: var(--accent);
      color: white;
    }
    .control button.off {
      background: #ecf1ed;
      color: var(--ink);
    }
    .number-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }
    .number-control {
      background: var(--panel-strong);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 14px;
    }
    .number-control label {
      display: block;
      font-size: 13px;
      color: var(--muted);
      margin-bottom: 10px;
    }
    .number-inline {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 8px;
    }
    .number-inline input {
      width: 100%;
      border: 1px solid var(--line);
      background: #fff;
      border-radius: 14px;
      padding: 12px 14px;
      font-size: 15px;
      color: var(--ink);
    }
    .number-inline button {
      border: 0;
      border-radius: 14px;
      padding: 0 16px;
      background: #153529;
      color: white;
      font-weight: 700;
      cursor: pointer;
    }
    .room-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }
    .room-card {
      background: var(--panel-strong);
      border: 1px solid var(--line);
      border-radius: 20px;
      padding: 16px;
    }
    .room-meta {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-bottom: 10px;
    }
    .room-config {
      display: grid;
      gap: 8px;
      margin-top: 12px;
    }
    .room-config .muted {
      display: flex;
      justify-content: space-between;
      gap: 12px;
    }
    .table-like {
      display: grid;
      gap: 10px;
    }
    .bars {
      display: grid;
      gap: 10px;
    }
    .bar-row {
      display: grid;
      gap: 6px;
    }
    .bar {
      height: 10px;
      border-radius: 999px;
      background: #e7ece7;
      overflow: hidden;
    }
    .bar > span {
      display: block;
      height: 100%;
      border-radius: 999px;
      background: linear-gradient(90deg, #1b6848 0%, #3cb07d 100%);
    }
    .config-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      color: var(--muted);
      font-size: 13px;
    }
    .config-grid strong {
      color: var(--ink);
      display: block;
      font-size: 14px;
      margin-bottom: 3px;
    }
    .empty {
      color: var(--muted);
      padding: 12px 0;
      font-size: 14px;
    }
    .footer-note {
      margin-top: 16px;
      color: var(--muted);
      font-size: 12px;
      text-align: right;
    }
    @media (max-width: 1180px) {
      .layout { grid-template-columns: 1fr; }
      .stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
    @media (max-width: 760px) {
      .shell { padding: 16px; }
      .stats, .controls-grid, .number-grid, .room-grid, .config-grid {
        grid-template-columns: 1fr;
      }
      .hero { padding: 20px; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <div class="hero-top">
        <div>
          <div class="badge">Vacuum Arrival Automation</div>
          <h1>Operational Dashboard</h1>
          <p>Live status, detailed controls, travel logic, room tuning, and cleaning history in one place.</p>
        </div>
        <div class="status-chip">
          <div class="label">Current Status</div>
          <div class="value" id="hero-status">Loading</div>
        </div>
      </div>
    </section>

    <div class="layout">
      <div class="stack">
        <section class="card">
          <div class="section-title">
            <div>
              <h2>Live Overview</h2>
              <p>Current run state, travel estimate, and available cleaning window.</p>
            </div>
          </div>
          <div class="grid stats" id="stats"></div>
        </section>

        <section class="card">
          <div class="section-title">
            <div>
              <h2>Automation Controls</h2>
              <p>Enable or disable the main logic, travel protection, learning, and notifications.</p>
            </div>
          </div>
          <div class="controls-grid" id="toggle-controls"></div>
        </section>

        <section class="card">
          <div class="section-title">
            <div>
              <h2>Runtime Configuration</h2>
              <p>Update the numeric tuning values that affect planning and travel logic.</p>
            </div>
          </div>
          <div class="number-grid" id="global-numbers"></div>
        </section>

        <section class="card">
          <div class="section-title">
            <div>
              <h2>Room Configuration</h2>
              <p>Inspect queue priority and tune interval, weight, duration, and enable state per room.</p>
            </div>
          </div>
          <div class="room-grid" id="room-grid"></div>
        </section>

        <section class="card">
          <div class="section-title">
            <div>
              <h2>History And Weekly Performance</h2>
              <p>Recent runs and high-level weekly trend from the automation history database.</p>
            </div>
          </div>
          <div class="bars" id="weekly-bars"></div>
          <div class="table-like" id="recent-runs" style="margin-top: 14px;"></div>
        </section>
      </div>

      <div class="stack">
        <section class="card">
          <div class="section-title">
            <div>
              <h3>Presence And Travel Logic</h3>
              <p>Who is home, why travel mode is active, and what radius is currently in effect.</p>
            </div>
          </div>
          <div class="presence-list" id="presence-list"></div>
        </section>

        <section class="card">
          <div class="section-title">
            <div>
              <h3>Cleaning Queue</h3>
              <p>Decision order based on due state, learning, duration, and travel window.</p>
            </div>
          </div>
          <div class="table-like" id="queue-list"></div>
        </section>

        <section class="card">
          <div class="section-title">
            <div>
              <h3>Configured Entities</h3>
              <p>Read-only view of the static add-on configuration and source entities.</p>
            </div>
          </div>
          <div class="config-grid" id="config-grid"></div>
        </section>
      </div>
    </div>

    <div class="footer-note" id="footer-note"></div>
  </div>

  <script>
    const toggleMeta = {
      enabled: ["Automation", "Turns the whole automation on or off."],
      learning: ["Adaptive Learning", "Uses learned room durations from successful runs."],
      travel_logic: ["Travel Logic", "Long-trip radius and max-distance safety logic."],
      start_push: ["Push On Auto Start", "Send a push for each automatically started room."],
      return_push: ["Push Return Summary", "Send the summary when someone comes home."],
      custom_home: ["Use Custom Home Point", "Use manual home coordinates instead of zone.home."]
    };

    const numberMeta = {
      start_hour: "Allowed start hour",
      end_hour: "Allowed end hour",
      return_buffer: "Return safety buffer (min)",
      fallback_speed: "Fallback speed (km/h)",
      default_travel_time: "Default travel time (min)",
      home_latitude: "Custom home latitude",
      home_longitude: "Custom home longitude",
      travel_pause_radius: "Long-trip radius (km)",
      max_distance_km: "Maximum distance cutoff (km)"
    };

    function entityState(entity, fallback = "unknown") {
      if (!entity || entity.state === undefined || entity.state === null) return fallback;
      return entity.state;
    }

    function boolOn(entity) {
      return ["on", "home", "true"].includes(String(entityState(entity, "off")).toLowerCase());
    }

    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    function localApiUrl(path) {
      const cleanedPath = String(path || "").replace(/^\/+/, "");
      const basePath = window.location.pathname.replace(/\/+$/, "");
      return `${basePath}/${cleanedPath}`;
    }

    async function api(path, options = {}) {
      const response = await fetch(localApiUrl(path), {
        headers: { "Content-Type": "application/json" },
        ...options
      });
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `HTTP ${response.status}`);
      }
      const contentType = response.headers.get("content-type") || "";
      if (contentType.includes("application/json")) return response.json();
      return response.text();
    }

    async function toggleBoolean(entityId) {
      await api(`/api/toggle?entity_id=${encodeURIComponent(entityId)}`, { method: "POST" });
      await load();
    }

    async function setNumber(entityId) {
      const input = document.querySelector(`[data-input='${entityId}']`);
      if (!input) return;
      await api("/api/set_number", {
        method: "POST",
        body: JSON.stringify({ entity_id: entityId, value: Number(input.value) })
      });
      await load();
    }

    function renderStats(summary) {
      const states = summary.states.sensors || {};
      const status = summary.status || {};
      const activeRoomAttrs = (states.active_room || {}).attributes || {};
      const cards = [
        ["Status", entityState(states.status), status.reason || "No reason"],
        ["Active Room", entityState(states.active_room), `${activeRoomAttrs.remaining_min ?? "-"} min remaining`],
        ["Next Room", entityState(states.next_room), `${status.room_queue?.length || 0} candidates in queue`],
        ["Travel Time", `${entityState(states.travel_time)} min`, "Current return estimate"],
        ["Cleaning Window", `${entityState(states.return_window)} min`, "Available time before return"],
        ["Distance Home", `${entityState(states.distance_to_home)} km`, status.travel_mode_reason || "Travel logic idle"],
        ["Weekly Runs", entityState(states.weekly_runs), `${status.history_entries || 0} history entries`],
        ["Weekly Minutes", entityState(states.weekly_minutes), `${status.cleaned_during_absence?.length || 0} rooms cleaned while away`]
      ];

      document.getElementById("stats").innerHTML = cards.map(([label, value, sub]) => `
        <div class="mini">
          <div class="eyebrow">${escapeHtml(label)}</div>
          <div class="big">${escapeHtml(value)}</div>
          <div class="sub">${escapeHtml(sub)}</div>
        </div>
      `).join("");
      document.getElementById("hero-status").textContent = entityState(states.status);
    }

    function renderPresence(summary) {
      const status = summary.status || {};
      const people = status.presence_summary || [];
      const blocks = [];

      blocks.push(`
        <div class="presence-item">
          <div class="presence-head">
            <span>Travel Logic</span>
            <span class="pill ${status.travel_mode_reason ? "" : "off"}">${escapeHtml(status.travel_mode_reason || "inactive")}</span>
          </div>
          <div class="muted">Away since: ${escapeHtml(status.away_since || "not fully away")}</div>
          <div class="muted">Long-trip radius: ${escapeHtml(status.travel_pause_radius_km ?? "unknown")} km</div>
          <div class="muted">Max distance cutoff: ${escapeHtml(status.max_distance_km ?? "off")} km</div>
          <div class="muted">Distance to custom home point: ${escapeHtml(status.travel_home_zone_distance_km ?? "n/a")} km</div>
        </div>
      `);

      if (people.length) {
        for (const person of people) {
          blocks.push(`
            <div class="presence-item">
              <div class="presence-head">
                <span>${escapeHtml(person.entity_id)}</span>
                <span class="pill ${String(person.state).toLowerCase() === "home" ? "" : "off"}">${escapeHtml(person.state)}</span>
              </div>
            </div>
          `);
        }
      } else {
        blocks.push('<div class="empty">No presence data available yet.</div>');
      }

      document.getElementById("presence-list").innerHTML = blocks.join("");
    }

    function renderToggles(summary) {
      const entities = summary.entities.global || {};
      const states = summary.states.global || {};
      document.getElementById("toggle-controls").innerHTML = Object.entries(toggleMeta).map(([key, [title, desc]]) => {
        const entityId = entities[key];
        const on = boolOn(states[key]);
        return `
          <div class="control">
            <div class="name">${escapeHtml(title)}</div>
            <div class="desc">${escapeHtml(desc)}</div>
            <button class="${on ? "" : "off"}" onclick="toggleBoolean('${entityId}')">
              ${on ? "Enabled" : "Disabled"}
            </button>
          </div>
        `;
      }).join("");
    }

    function renderNumbers(summary) {
      const entities = summary.entities.global || {};
      const states = summary.states.global || {};
      document.getElementById("global-numbers").innerHTML = Object.entries(numberMeta).map(([key, label]) => {
        const entityId = entities[key];
        const value = entityState(states[key], "");
        return `
          <div class="number-control">
            <label>${escapeHtml(label)}</label>
            <div class="number-inline">
              <input type="number" step="any" value="${escapeHtml(value)}" data-input="${entityId}">
              <button onclick="setNumber('${entityId}')">Save</button>
            </div>
          </div>
        `;
      }).join("");
    }

    function renderQueue(summary) {
      const queue = summary.status.room_queue || [];
      if (!queue.length) {
        document.getElementById("queue-list").innerHTML = '<div class="empty">No queue data available yet.</div>';
        return;
      }
      document.getElementById("queue-list").innerHTML = queue.map(item => `
        <div class="queue-item">
          <div class="queue-head">
            <span>${escapeHtml(item.room)}</span>
            <span class="pill ${item.fits_now ? "" : "off"}">${item.fits_now ? "fits now" : "too long"}</span>
          </div>
          <div class="muted">Priority ${escapeHtml(item.priority)} · Interval ${escapeHtml(item.interval_h)} h · Duration ${escapeHtml(item.effective_duration_min)} min</div>
          <div class="muted">Forecast ${escapeHtml(item.forecast_score)} · Enabled ${item.enabled ? "yes" : "no"}</div>
        </div>
      `).join("");
    }

    function renderRooms(summary) {
      const rooms = summary.states.rooms || [];
      const roomStats = summary.status.room_stats || [];
      if (!rooms.length) {
        document.getElementById("room-grid").innerHTML = '<div class="empty">No room helpers configured.</div>';
        return;
      }
      document.getElementById("room-grid").innerHTML = rooms.map(room => {
        const stats = roomStats.find(item => item.room_key === room.id) || {};
        const enabledOn = boolOn(room.enabled_state);
        return `
          <div class="room-card">
            <div class="room-meta">
              <div>
                <strong>${escapeHtml(room.name)}</strong>
                <div class="muted">Segment ${escapeHtml(room.segment_id ?? "unknown")}</div>
              </div>
              <span class="pill ${enabledOn ? "" : "off"}">${enabledOn ? "enabled" : "disabled"}</span>
            </div>
            <button class="${enabledOn ? "" : "off"}" onclick="toggleBoolean('${room.enabled}')">
              ${enabledOn ? "Disable room" : "Enable room"}
            </button>
            <div class="room-config">
              <div class="muted"><span>Configured duration</span><span>${escapeHtml(stats.configured_duration_min ?? "-")} min</span></div>
              <div class="muted"><span>Learned duration</span><span>${escapeHtml(stats.learned_duration_min ?? "-")}</span></div>
              <div class="muted"><span>Completed runs</span><span>${escapeHtml(stats.completed_runs ?? 0)}</span></div>
              <div class="muted"><span>Average actual</span><span>${escapeHtml(stats.average_actual_duration_min ?? "-")}</span></div>
            </div>
            <div class="number-grid" style="margin-top: 12px;">
              ${[
                ["weight", "Weight", room.weight],
                ["interval_h", "Interval (h)", room.interval_h],
                ["duration_min", "Duration (min)", room.duration_min]
              ].map(([key, label, entityId]) => `
                <div class="number-control">
                  <label>${escapeHtml(label)}</label>
                  <div class="number-inline">
                    <input type="number" step="any" value="${escapeHtml(entityState(room[`${key}_state`], ""))}" data-input="${entityId}">
                    <button onclick="setNumber('${entityId}')">Save</button>
                  </div>
                </div>
              `).join("")}
            </div>
          </div>
        `;
      }).join("");
    }

    function renderWeekly(summary) {
      const weekly = summary.status.weekly_stats || summary.history.weekly_stats || [];
      const recent = summary.status.recent_runs || summary.history.recent_runs || [];
      const maxMinutes = Math.max(1, ...weekly.map(item => Number(item.minutes || 0)));

      document.getElementById("weekly-bars").innerHTML = weekly.length ? weekly.map(item => `
        <div class="bar-row">
          <div class="week-head">
            <span>${escapeHtml(item.week)}</span>
            <span class="muted">${escapeHtml(item.runs)} runs · ${escapeHtml(item.minutes)} min</span>
          </div>
          <div class="bar"><span style="width:${Math.max(6, (Number(item.minutes || 0) / maxMinutes) * 100)}%"></span></div>
        </div>
      `).join("") : '<div class="empty">No weekly history available yet.</div>';

      document.getElementById("recent-runs").innerHTML = recent.length ? recent.map(item => `
        <div class="run-item">
          <div class="run-head">
            <span>${escapeHtml(item.room || "-")}</span>
            <span class="pill ${String(item.outcome).toLowerCase() === "completed" ? "" : "off"}">${escapeHtml(item.outcome || "unknown")}</span>
          </div>
          <div class="muted">${escapeHtml(item.finished_at || "-")}</div>
          <div class="muted">${escapeHtml(item.actual_duration_min || 0)} min</div>
        </div>
      `).join("") : '<div class="empty">No recent runs available yet.</div>';
    }

    function renderConfig(summary) {
      const options = summary.options || {};
      const rows = [
        ["Vacuum Entity", options.vacuum_entity],
        ["Notify Service", options.notify_service || "disabled"],
        ["Presence Entities", options.presence_entities],
        ["Travel Person", options.travel_person_entity],
        ["Person Entity", options.person_entity],
        ["Waze Entity", options.waze_entity || "not set"],
        ["Distance Entity", options.distance_entity || "not set"],
        ["Home Zone", options.home_zone],
        ["Travel Pause Zone", options.travel_pause_zone || "not set"],
        ["Pause After Hours", options.travel_pause_after_hours],
        ["History Weeks", options.history_weeks],
        ["Learning Window", options.learning_window]
      ];
      document.getElementById("config-grid").innerHTML = rows.map(([label, value]) => `
        <div>
          <strong>${escapeHtml(label)}</strong>
          <span>${escapeHtml(value ?? "n/a")}</span>
        </div>
      `).join("");
    }

    function renderFooter(summary) {
      const generated = new Date().toLocaleString();
      document.getElementById("footer-note").textContent =
        `Last refreshed ${generated}. Auto-refresh every 15 seconds.`;
    }

    function render(summary) {
      renderStats(summary);
      renderPresence(summary);
      renderToggles(summary);
      renderNumbers(summary);
      renderQueue(summary);
      renderRooms(summary);
      renderWeekly(summary);
      renderConfig(summary);
      renderFooter(summary);
    }

    async function load() {
      try {
        const summary = await api("/api/summary");
        render(summary);
      } catch (error) {
        document.body.innerHTML = `<div class="shell"><div class="card"><h2>Dashboard failed to load</h2><p>${escapeHtml(error.message)}</p></div></div>`;
      }
    }

    load();
    setInterval(load, 15000);
  </script>
</body>
</html>
"""


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/summary":
            self._json_response(build_summary())
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(HTML.encode("utf-8"))

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/toggle":
            self._handle_toggle(parsed)
            return
        if parsed.path == "/api/set_number":
            self._handle_set_number()
            return
        self.send_response(404)
        self.end_headers()

    def _handle_toggle(self, parsed):
        query = urllib.parse.parse_qs(parsed.query)
        entity_id = (query.get("entity_id") or [""])[0]
        if not entity_id.startswith("input_boolean."):
            self._json_response({"ok": False, "error": "unsupported entity"}, status=400)
            return

        try:
            service_call("input_boolean", "toggle", entity_id)
            self._json_response({"ok": True})
        except urllib.error.HTTPError as err:
            self._json_response({"ok": False, "error": str(err)}, status=502)
        except Exception as err:
            self._json_response({"ok": False, "error": str(err)}, status=500)

    def _handle_set_number(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            self._json_response({"ok": False, "error": "invalid payload"}, status=400)
            return

        entity_id = str(payload.get("entity_id") or "")
        value = payload.get("value")
        if not entity_id.startswith("input_number."):
            self._json_response({"ok": False, "error": "unsupported entity"}, status=400)
            return

        try:
            service_call("input_number", "set_value", entity_id, {"value": value})
            self._json_response({"ok": True})
        except urllib.error.HTTPError as err:
            self._json_response({"ok": False, "error": str(err)}, status=502)
        except Exception as err:
            self._json_response({"ok": False, "error": str(err)}, status=500)

    def _json_response(self, payload: dict, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def log_message(self, format, *args):
        return


def main():
    port = int(os.environ.get("SIDEBAR_REDIRECT_PORT", "8099"))
    server = HTTPServer(("0.0.0.0", port), DashboardHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
