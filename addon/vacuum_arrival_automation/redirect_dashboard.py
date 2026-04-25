#!/usr/bin/env python3
"""Small ingress dashboard for the vacuum automation add-on."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


OPTIONS_PATH = Path("/data/options.json")
SUPERVISOR_CORE_API = "http://supervisor/core/api"


def load_options() -> dict:
    try:
        return json.loads(OPTIONS_PATH.read_text())
    except Exception:
        return {}


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
    with urllib.request.urlopen(request, timeout=10) as response:
        raw = response.read().decode("utf-8")
        return json.loads(raw) if raw else None


def state_for(entity_id: str):
    try:
        return api_request(f"/states/{entity_id}")
    except Exception:
        return None


def service_call(domain: str, service: str, entity_id: str):
    return api_request(
        f"/services/{domain}/{service}",
        method="POST",
        payload={"entity_id": entity_id},
    )


def dashboard_entities(options: dict) -> dict:
    prefix = options.get("dashboard_prefix", "vacuum_automation")
    helper_prefix = options.get("helper_prefix", "vacuum_automation")
    return {
        "status": f"sensor.{prefix}_status",
        "active_room": f"sensor.{prefix}_active_room",
        "next_room": f"sensor.{prefix}_next_room",
        "travel_time": f"sensor.{prefix}_travel_time",
        "return_window": f"sensor.{prefix}_return_window",
        "weekly_runs": f"sensor.{prefix}_weekly_runs",
        "weekly_minutes": f"sensor.{prefix}_weekly_minutes",
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
    }


def build_summary() -> dict:
    options = load_options()
    entities = dashboard_entities(options)
    states = {key: state_for(entity_id) for key, entity_id in entities.items()}
    status = states.get("status") or {}
    attrs = status.get("attributes", {}) if isinstance(status, dict) else {}
    return {
        "entities": entities,
        "states": states,
        "meta": {
            "presence_summary": attrs.get("presence_summary", []),
            "travel_mode_reason": attrs.get("travel_mode_reason"),
            "distance_km": attrs.get("distance_km"),
            "travel_pause_radius_km": attrs.get("travel_pause_radius_km"),
            "max_distance_km": attrs.get("max_distance_km"),
        },
    }


HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Vacuum Dashboard</title>
  <style>
    :root {
      --bg: #f4f6f3;
      --panel: #ffffff;
      --ink: #152018;
      --muted: #5f6d62;
      --line: #d7ddd7;
      --accent: #2f7d57;
      --accent-2: #d9efe3;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: ui-sans-serif, system-ui, sans-serif;
      background: linear-gradient(180deg, #eef4ef 0%%, #f8faf8 100%%);
      color: var(--ink);
    }
    .wrap {
      max-width: 1100px;
      margin: 0 auto;
      padding: 24px;
    }
    .hero {
      background: linear-gradient(135deg, #173326 0%%, #2f7d57 100%%);
      color: white;
      padding: 24px;
      border-radius: 20px;
      margin-bottom: 20px;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin-bottom: 20px;
    }
    .card {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 16px;
      box-shadow: 0 8px 24px rgba(0,0,0,0.04);
    }
    .label {
      color: var(--muted);
      font-size: 13px;
      margin-bottom: 8px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    .value {
      font-size: 24px;
      font-weight: 700;
    }
    .subgrid {
      display: grid;
      grid-template-columns: 1.3fr 1fr;
      gap: 16px;
    }
    .toggles {
      display: grid;
      gap: 10px;
    }
    button {
      width: 100%;
      text-align: left;
      padding: 14px 16px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: white;
      color: var(--ink);
      cursor: pointer;
      font-size: 15px;
    }
    button strong {
      display: block;
      margin-bottom: 4px;
    }
    button span {
      color: var(--muted);
      font-size: 13px;
    }
    .pill {
      display: inline-block;
      background: var(--accent-2);
      color: var(--accent);
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
    }
    ul {
      margin: 8px 0 0;
      padding-left: 18px;
    }
    @media (max-width: 800px) {
      .subgrid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
      <div class="pill">Add-on Dashboard</div>
      <h1>Vacuum Automation</h1>
      <p>Status, travel logic, and notification controls without Lovelace.</p>
    </div>

    <div class="grid" id="stats"></div>

    <div class="subgrid">
      <div class="card">
        <div class="label">Residents</div>
        <div id="presence"></div>
      </div>
      <div class="card">
        <div class="label">Controls</div>
        <div class="toggles" id="toggles"></div>
      </div>
    </div>
  </div>

  <script>
    const toggleLabels = {
      enabled: ["Automation", "Main automation on/off"],
      learning: ["Adaptive Learning", "Use learned room durations"],
      travel_logic: ["Travel Logic", "Long-trip and max-distance protection"],
      start_push: ["Push On Auto Start", "Notification for each automatically started room"],
      return_push: ["Push Return Summary", "Summary when someone gets back home"]
    };

    function stateText(entity) {
      if (!entity) return "unknown";
      return entity.state ?? "unknown";
    }

    async function toggle(entityId) {
      await fetch(`/api/toggle?entity_id=${encodeURIComponent(entityId)}`, { method: "POST" });
      await load();
    }

    function render(summary) {
      const states = summary.states || {};
      const meta = summary.meta || {};
      const entities = summary.entities || {};

      const stats = [
        ["Status", stateText(states.status)],
        ["Active Room", stateText(states.active_room)],
        ["Next Room", stateText(states.next_room)],
        ["Travel Time", `${stateText(states.travel_time)} min`],
        ["Cleaning Window", `${stateText(states.return_window)} min`],
        ["Weekly Runs", stateText(states.weekly_runs)],
        ["Weekly Minutes", stateText(states.weekly_minutes)],
        ["Distance", meta.distance_km != null ? `${meta.distance_km} km` : "unknown"]
      ];

      document.getElementById("stats").innerHTML = stats.map(([label, value]) => `
        <div class="card">
          <div class="label">${label}</div>
          <div class="value">${value}</div>
        </div>
      `).join("");

      const presence = meta.presence_summary || [];
      document.getElementById("presence").innerHTML = `
        <div><strong>Travel mode reason:</strong> ${meta.travel_mode_reason || "none"}</div>
        <div><strong>Long-trip radius:</strong> ${meta.travel_pause_radius_km ?? "unknown"} km</div>
        <div><strong>Max distance:</strong> ${meta.max_distance_km ?? "off"} km</div>
        <ul>
          ${presence.map(person => `<li>${person.entity_id}: ${person.state}</li>`).join("") || "<li>No presence data</li>"}
        </ul>
      `;

      document.getElementById("toggles").innerHTML = Object.entries(toggleLabels).map(([key, [title, subtitle]]) => `
        <button onclick="toggle('${entities[key]}')">
          <strong>${title}: ${stateText(states[key])}</strong>
          <span>${subtitle}</span>
        </button>
      `).join("");
    }

    async function load() {
      const response = await fetch("/api/summary");
      render(await response.json());
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
        if parsed.path != "/api/toggle":
            self.send_response(404)
            self.end_headers()
            return

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
