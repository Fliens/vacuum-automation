#!/usr/bin/env python3
"""Automatically create Home Assistant Helper entities via API.

This script checks if the required Helper entities exist and creates them
via the Home Assistant API if they don't. This eliminates the need for
users to manually import helpers.yaml into their configuration.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


OPTIONS_PATH = Path("/data/options.json")
SUPERVISOR_CORE_API = "http://supervisor/core/api"
DEFAULT_HELPER_PREFIX = "vacuum_automation"

# Helper definitions for the core automation
CORE_INPUT_TEXT_HELPERS = [
    {
        "id": "state",
        "name": "Vacuum Automation State",
        "max": 1024,
        "initial": "{}",
    },
    {
        "id": "one_time_room_override",
        "name": "Vacuum One-Time Room Priority",
        "max": 128,
        "initial": "",
    },
    {
        "id": "selected_presence_entities",
        "name": "Vacuum Selected Presence Entities",
        "max": 1024,
        "initial": "",
    },
    {
        "id": "active_weekdays",
        "name": "Vacuum Active Weekdays",
        "max": 64,
        "initial": "mon,tue,wed,thu,fri,sat",
    },
]

CORE_INPUT_BOOLEAN_HELPERS = [
    {
        "id": "enabled",
        "name": "Vacuum Automation Enabled",
        "icon": "mdi:robot-vacuum",
        "initial": True,
    },
    {
        "id": "learning_enabled",
        "name": "Vacuum Automation Learning Enabled",
        "icon": "mdi:brain",
        "initial": True,
    },
    {
        "id": "home_override_enabled",
        "name": "Vacuum Home Override Enabled",
        "icon": "mdi:home-map-marker",
        "initial": False,
    },
    {
        "id": "travel_mode_enabled",
        "name": "Vacuum Travel Mode Enabled",
        "icon": "mdi:car",
        "initial": True,
    },
    {
        "id": "start_notifications_enabled",
        "name": "Vacuum Start Notifications Enabled",
        "icon": "mdi:bell",
        "initial": False,
    },
    {
        "id": "return_summary_enabled",
        "name": "Vacuum Return Summary Enabled",
        "icon": "mdi:clipboard-check",
        "initial": True,
    },
]

CORE_INPUT_NUMBER_HELPERS = [
    {
        "id": "start_hour",
        "name": "Vacuum Automation Start Hour",
        "min": 0,
        "max": 23,
        "step": 1,
        "mode": "box",
        "initial": 8,
    },
    {
        "id": "end_hour",
        "name": "Vacuum Automation End Hour",
        "min": 1,
        "max": 23,
        "step": 1,
        "mode": "box",
        "initial": 22,
    },
    {
        "id": "return_buffer",
        "name": "Vacuum Automation Return Buffer",
        "min": 0,
        "max": 30,
        "step": 1,
        "unit_of_measurement": "min",
        "mode": "slider",
        "initial": 5,
    },
    {
        "id": "fallback_speed",
        "name": "Vacuum Automation Fallback Speed",
        "min": 5,
        "max": 130,
        "step": 1,
        "unit_of_measurement": "km/h",
        "mode": "slider",
        "initial": 30,
    },
    {
        "id": "default_travel_time",
        "name": "Vacuum Automation Default Travel Time",
        "min": 5,
        "max": 240,
        "step": 5,
        "unit_of_measurement": "min",
        "mode": "slider",
        "initial": 60,
    },
    {
        "id": "home_latitude",
        "name": "Vacuum Home Latitude",
        "min": -90,
        "max": 90,
        "step": 0.0001,
        "mode": "box",
        "initial": 52.52,
    },
    {
        "id": "home_longitude",
        "name": "Vacuum Home Longitude",
        "min": -180,
        "max": 180,
        "step": 0.0001,
        "mode": "box",
        "initial": 13.405,
    },
    {
        "id": "travel_pause_radius",
        "name": "Vacuum Travel Pause Radius",
        "min": 1,
        "max": 500,
        "step": 1,
        "unit_of_measurement": "km",
        "mode": "slider",
        "initial": 100,
    },
    {
        "id": "max_distance_km",
        "name": "Vacuum Max Distance",
        "min": 0,
        "max": 1000,
        "step": 1,
        "unit_of_measurement": "km",
        "mode": "box",
        "initial": 0,
    },
]


def read_options() -> Dict[str, Any]:
    """Read add-on options from the options.json file."""
    if not OPTIONS_PATH.exists():
        return {}
    try:
        return json.loads(OPTIONS_PATH.read_text())
    except Exception:
        return {}


def slugify(value: str) -> str:
    """Convert a string to a valid entity ID slug."""
    text = value.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_") or "room"


def parse_rooms(raw_rooms: Any) -> List[dict]:
    """Parse room configuration from options."""
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
        if not room_id:
            room_id = slugify(item.get("name", ""))
        if not room_id:
            continue

        rooms.append({
            "id": room_id,
            "name": str(item.get("name") or room_id.replace("_", " ").title()),
            "icon": str(item.get("icon") or "mdi:floor-plan"),
            "interval_h": int(item.get("interval_h", 48)),
            "weight": float(item.get("weight", 1.0)),
            "duration_min": int(item.get("duration_min", 15)),
            "enabled": bool(item.get("enabled", True)),
        })
    return rooms


def api_request(
    path: str,
    method: str = "GET",
    payload: dict | None = None,
    timeout: int = 30,
) -> dict | None:
    """Make an API request to the Home Assistant Supervisor API."""
    token = os.environ.get("SUPERVISOR_TOKEN", "")
    if not token:
        print(f"[helper_setup] Warning: No SUPERVISOR_TOKEN found")
        return None

    url = f"{SUPERVISOR_CORE_API}{path}"
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method=method,
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            if body:
                return json.loads(body)
            return {}
    except urllib.error.HTTPError as e:
        error_body = ""
        try:
            error_body = e.read().decode("utf-8")
        except Exception:
            pass
        print(f"[helper_setup] API error {e.code} for {path}: {error_body}")
        return None
    except Exception as e:
        print(f"[helper_setup] API request failed for {path}: {e}")
        return None


def entity_exists(entity_id: str) -> bool:
    """Check if an entity already exists in Home Assistant."""
    result = api_request(f"/states/{entity_id}")
    return result is not None


def create_input_boolean(
    entity_id_suffix: str,
    name: str,
    icon: str = "mdi:toggle-switch",
    initial: bool = False,
    prefix: str = DEFAULT_HELPER_PREFIX,
) -> bool:
    """Create an input_boolean helper entity."""
    entity_id = f"input_boolean.{prefix}_{entity_id_suffix}"

    if entity_exists(entity_id):
        print(f"[helper_setup] {entity_id} already exists, skipping")
        return True

    payload = {
        "name": name,
        "icon": icon,
        "initial": initial,
    }

    result = api_request(
        "/config/config_entries/helper",
        method="POST",
        payload={
            "platform": "input_boolean",
            "name": name,
            "icon": icon,
        },
    )

    if result is None:
        # Fallback: Try using the REST API to create via services
        # This sets an initial state which effectively creates the entity
        print(f"[helper_setup] Trying alternative creation for {entity_id}")
        return create_helper_via_rest(
            "input_boolean",
            prefix,
            entity_id_suffix,
            name,
            icon,
            "on" if initial else "off",
        )

    print(f"[helper_setup] Created {entity_id}")
    return True


def create_input_number(
    entity_id_suffix: str,
    name: str,
    min_val: float,
    max_val: float,
    step: float = 1,
    mode: str = "box",
    unit_of_measurement: str = "",
    initial: float = 0,
    prefix: str = DEFAULT_HELPER_PREFIX,
) -> bool:
    """Create an input_number helper entity."""
    entity_id = f"input_number.{prefix}_{entity_id_suffix}"

    if entity_exists(entity_id):
        print(f"[helper_setup] {entity_id} already exists, skipping")
        return True

    result = api_request(
        "/config/config_entries/helper",
        method="POST",
        payload={
            "platform": "input_number",
            "name": name,
            "min": min_val,
            "max": max_val,
            "step": step,
            "mode": mode,
            "unit_of_measurement": unit_of_measurement,
            "initial": initial,
        },
    )

    if result is None:
        print(f"[helper_setup] Trying alternative creation for {entity_id}")
        return create_helper_via_rest(
            "input_number",
            prefix,
            entity_id_suffix,
            name,
            None,
            str(initial),
            extra={
                "min": min_val,
                "max": max_val,
                "step": step,
                "mode": mode,
                "unit_of_measurement": unit_of_measurement,
            },
        )

    print(f"[helper_setup] Created {entity_id}")
    return True


def create_input_text(
    entity_id_suffix: str,
    name: str,
    max_len: int = 255,
    initial: str = "",
    prefix: str = DEFAULT_HELPER_PREFIX,
) -> bool:
    """Create an input_text helper entity."""
    entity_id = f"input_text.{prefix}_{entity_id_suffix}"

    if entity_exists(entity_id):
        print(f"[helper_setup] {entity_id} already exists, skipping")
        return True

    result = api_request(
        "/config/config_entries/helper",
        method="POST",
        payload={
            "platform": "input_text",
            "name": name,
            "max": max_len,
            "initial": initial,
        },
    )

    if result is None:
        print(f"[helper_setup] Trying alternative creation for {entity_id}")
        return create_helper_via_rest(
            "input_text",
            prefix,
            entity_id_suffix,
            name,
            None,
            initial,
            extra={"max": max_len},
        )

    print(f"[helper_setup] Created {entity_id}")
    return True


def create_helper_via_rest(
    domain: str,
    prefix: str,
    suffix: str,
    name: str,
    icon: Optional[str],
    initial_value: str,
    extra: Optional[dict] = None,
) -> bool:
    """Create a helper by directly posting to the REST API.

    This is a fallback method that creates helpers using the
    input_*.reload and services API.
    """
    entity_id = f"{domain}.{prefix}_{suffix}"

    # Build the helper configuration
    config: Dict[str, Any] = {"name": name}
    if icon:
        config["icon"] = icon
    if extra:
        config.update(extra)

    # For input_text and input_number, we need to try the WebSocket API
    # or config entry API approach. Since we can't use WebSocket directly,
    # we'll try the config/config_entries approach with different payload

    # Try creating via the helper config entry endpoint with explicit object_id
    payload = {
        "platform": domain.replace("input_", ""),
        "name": name,
    }

    if icon:
        payload["icon"] = icon
    if extra:
        payload.update(extra)

    result = api_request(
        f"/config/config_entries/helper",
        method="POST",
        payload=payload,
    )

    if result and "entry_id" in result:
        print(f"[helper_setup] Created {entity_id} via config entry")
        return True

    # If still failing, log and continue - the helper might need manual creation
    print(f"[helper_setup] Could not auto-create {entity_id} - may need manual setup")
    return False


def setup_core_helpers(prefix: str) -> int:
    """Create all core helper entities needed by the automation."""
    created = 0

    print("[helper_setup] Setting up input_text helpers...")
    for helper in CORE_INPUT_TEXT_HELPERS:
        if create_input_text(
            entity_id_suffix=helper["id"],
            name=helper["name"],
            max_len=helper.get("max", 255),
            initial=helper.get("initial", ""),
            prefix=prefix,
        ):
            created += 1

    print("[helper_setup] Setting up input_boolean helpers...")
    for helper in CORE_INPUT_BOOLEAN_HELPERS:
        if create_input_boolean(
            entity_id_suffix=helper["id"],
            name=helper["name"],
            icon=helper.get("icon", "mdi:toggle-switch"),
            initial=helper.get("initial", False),
            prefix=prefix,
        ):
            created += 1

    print("[helper_setup] Setting up input_number helpers...")
    for helper in CORE_INPUT_NUMBER_HELPERS:
        if create_input_number(
            entity_id_suffix=helper["id"],
            name=helper["name"],
            min_val=helper.get("min", 0),
            max_val=helper.get("max", 100),
            step=helper.get("step", 1),
            mode=helper.get("mode", "box"),
            unit_of_measurement=helper.get("unit_of_measurement", ""),
            initial=helper.get("initial", 0),
            prefix=prefix,
        ):
            created += 1

    return created


def setup_room_helpers(rooms: List[dict], prefix: str) -> int:
    """Create helper entities for each room."""
    created = 0

    for room in rooms:
        room_id = room["id"]
        room_name = room["name"]
        room_icon = room.get("icon", "mdi:floor-plan")

        # Room enabled toggle
        if create_input_boolean(
            entity_id_suffix=f"{room_id}_enabled",
            name=f"Vacuum {room_name} Enabled",
            icon=room_icon,
            initial=room.get("enabled", True),
            prefix=prefix,
        ):
            created += 1

        # Room weight
        if create_input_number(
            entity_id_suffix=f"{room_id}_weight",
            name=f"Vacuum {room_name} Weight",
            min_val=0.1,
            max_val=3,
            step=0.05,
            mode="box",
            initial=room.get("weight", 1.0),
            prefix=prefix,
        ):
            created += 1

        # Room interval
        if create_input_number(
            entity_id_suffix=f"{room_id}_interval_h",
            name=f"Vacuum {room_name} Interval",
            min_val=6,
            max_val=168,
            step=1,
            unit_of_measurement="h",
            mode="box",
            initial=room.get("interval_h", 48),
            prefix=prefix,
        ):
            created += 1

        # Room duration
        if create_input_number(
            entity_id_suffix=f"{room_id}_duration_min",
            name=f"Vacuum {room_name} Duration",
            min_val=1,
            max_val=120,
            step=1,
            unit_of_measurement="min",
            mode="box",
            initial=room.get("duration_min", 15),
            prefix=prefix,
        ):
            created += 1

    return created


def wait_for_home_assistant(max_retries: int = 30, delay: float = 2.0) -> bool:
    """Wait for Home Assistant to be ready before creating helpers."""
    print("[helper_setup] Waiting for Home Assistant to be ready...")

    for i in range(max_retries):
        result = api_request("/")
        if result is not None:
            print("[helper_setup] Home Assistant is ready")
            return True

        print(f"[helper_setup] Waiting... ({i + 1}/{max_retries})")
        time.sleep(delay)

    print("[helper_setup] Timeout waiting for Home Assistant")
    return False


def get_all_helper_entity_ids(prefix: str, rooms: List[dict]) -> List[str]:
    """Get a list of all helper entity IDs that should exist."""
    entity_ids = []

    # Core input_text helpers
    for helper in CORE_INPUT_TEXT_HELPERS:
        entity_ids.append(f"input_text.{prefix}_{helper['id']}")

    # Core input_boolean helpers
    for helper in CORE_INPUT_BOOLEAN_HELPERS:
        entity_ids.append(f"input_boolean.{prefix}_{helper['id']}")

    # Core input_number helpers
    for helper in CORE_INPUT_NUMBER_HELPERS:
        entity_ids.append(f"input_number.{prefix}_{helper['id']}")

    # Room-specific helpers
    for room in rooms:
        room_id = room["id"]
        entity_ids.append(f"input_boolean.{prefix}_{room_id}_enabled")
        entity_ids.append(f"input_number.{prefix}_{room_id}_weight")
        entity_ids.append(f"input_number.{prefix}_{room_id}_interval_h")
        entity_ids.append(f"input_number.{prefix}_{room_id}_duration_min")

    return entity_ids


def get_missing_helpers(prefix: str, rooms: List[dict]) -> List[str]:
    """Check which helper entities are missing."""
    expected = get_all_helper_entity_ids(prefix, rooms)
    missing = []

    for entity_id in expected:
        if not entity_exists(entity_id):
            missing.append(entity_id)

    return missing


def delete_helper(entity_id: str) -> bool:
    """Delete a helper entity via the config entries API."""
    # First, we need to find the config entry ID for this entity
    # The entity_id format is domain.object_id (e.g., input_boolean.vacuum_automation_enabled)

    # Try to get the entity registry to find the config entry
    result = api_request("/config/entity_registry")
    if not result:
        print(f"[helper_setup] Could not fetch entity registry")
        return False

    # Find the entity in the registry
    config_entry_id = None
    for entity in result:
        if entity.get("entity_id") == entity_id:
            config_entry_id = entity.get("config_entry_id")
            break

    if not config_entry_id:
        print(f"[helper_setup] Could not find config entry for {entity_id}")
        return False

    # Delete the config entry
    delete_result = api_request(
        f"/config/config_entries/entry/{config_entry_id}",
        method="DELETE",
    )

    if delete_result is not None:
        print(f"[helper_setup] Deleted {entity_id}")
        return True

    print(f"[helper_setup] Failed to delete {entity_id}")
    return False


def cleanup_helpers(prefix: str, rooms: List[dict]) -> int:
    """Delete all helper entities created by this add-on."""
    entity_ids = get_all_helper_entity_ids(prefix, rooms)
    deleted = 0

    print(f"[helper_setup] Cleaning up {len(entity_ids)} helper entities...")

    for entity_id in entity_ids:
        if entity_exists(entity_id):
            if delete_helper(entity_id):
                deleted += 1

    print(f"[helper_setup] Deleted {deleted} helper entities")
    return deleted


def ensure_helpers_exist(prefix: str, rooms: List[dict]) -> List[str]:
    """Check for missing helpers and create them. Returns list of recreated entities."""
    missing = get_missing_helpers(prefix, rooms)

    if not missing:
        return []

    print(f"[helper_setup] Found {len(missing)} missing helpers, recreating...")
    recreated = []

    for entity_id in missing:
        # Parse entity_id to determine type and suffix
        parts = entity_id.split(".")
        if len(parts) != 2:
            continue

        domain, object_id = parts
        # Remove prefix to get the suffix
        if object_id.startswith(f"{prefix}_"):
            suffix = object_id[len(prefix) + 1:]
        else:
            continue

        # Find the helper definition and recreate
        if domain == "input_text":
            for helper in CORE_INPUT_TEXT_HELPERS:
                if helper["id"] == suffix:
                    if create_input_text(
                        entity_id_suffix=helper["id"],
                        name=helper["name"],
                        max_len=helper.get("max", 255),
                        initial=helper.get("initial", ""),
                        prefix=prefix,
                    ):
                        recreated.append(entity_id)
                    break

        elif domain == "input_boolean":
            # Check core helpers first
            found = False
            for helper in CORE_INPUT_BOOLEAN_HELPERS:
                if helper["id"] == suffix:
                    if create_input_boolean(
                        entity_id_suffix=helper["id"],
                        name=helper["name"],
                        icon=helper.get("icon", "mdi:toggle-switch"),
                        initial=helper.get("initial", False),
                        prefix=prefix,
                    ):
                        recreated.append(entity_id)
                    found = True
                    break

            # Check room helpers
            if not found:
                for room in rooms:
                    if suffix == f"{room['id']}_enabled":
                        if create_input_boolean(
                            entity_id_suffix=suffix,
                            name=f"Vacuum {room['name']} Enabled",
                            icon=room.get("icon", "mdi:floor-plan"),
                            initial=room.get("enabled", True),
                            prefix=prefix,
                        ):
                            recreated.append(entity_id)
                        break

        elif domain == "input_number":
            # Check core helpers first
            found = False
            for helper in CORE_INPUT_NUMBER_HELPERS:
                if helper["id"] == suffix:
                    if create_input_number(
                        entity_id_suffix=helper["id"],
                        name=helper["name"],
                        min_val=helper.get("min", 0),
                        max_val=helper.get("max", 100),
                        step=helper.get("step", 1),
                        mode=helper.get("mode", "box"),
                        unit_of_measurement=helper.get("unit_of_measurement", ""),
                        initial=helper.get("initial", 0),
                        prefix=prefix,
                    ):
                        recreated.append(entity_id)
                    found = True
                    break

            # Check room helpers
            if not found:
                for room in rooms:
                    room_id = room["id"]
                    if suffix == f"{room_id}_weight":
                        if create_input_number(
                            entity_id_suffix=suffix,
                            name=f"Vacuum {room['name']} Weight",
                            min_val=0.1,
                            max_val=3,
                            step=0.05,
                            mode="box",
                            initial=room.get("weight", 1.0),
                            prefix=prefix,
                        ):
                            recreated.append(entity_id)
                        break
                    elif suffix == f"{room_id}_interval_h":
                        if create_input_number(
                            entity_id_suffix=suffix,
                            name=f"Vacuum {room['name']} Interval",
                            min_val=6,
                            max_val=168,
                            step=1,
                            unit_of_measurement="h",
                            mode="box",
                            initial=room.get("interval_h", 48),
                            prefix=prefix,
                        ):
                            recreated.append(entity_id)
                        break
                    elif suffix == f"{room_id}_duration_min":
                        if create_input_number(
                            entity_id_suffix=suffix,
                            name=f"Vacuum {room['name']} Duration",
                            min_val=1,
                            max_val=120,
                            step=1,
                            unit_of_measurement="min",
                            mode="box",
                            initial=room.get("duration_min", 15),
                            prefix=prefix,
                        ):
                            recreated.append(entity_id)
                        break

    if recreated:
        print(f"[helper_setup] Recreated {len(recreated)} helpers: {recreated}")

    return recreated


def main() -> int:
    """Main entry point for helper setup."""
    import argparse

    parser = argparse.ArgumentParser(description="Manage Vacuum Automation Helper entities")
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Delete all helper entities created by this add-on",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check for missing helpers and recreate them",
    )
    args = parser.parse_args()

    print("[helper_setup] Starting helper management...")

    # Wait for HA to be ready
    if not wait_for_home_assistant():
        print("[helper_setup] Warning: Could not connect to Home Assistant")
        print("[helper_setup] Helpers may need to be created manually")
        return 1

    # Load options
    options = read_options()
    prefix = options.get("helper_prefix", DEFAULT_HELPER_PREFIX)
    rooms = parse_rooms(options.get("rooms", []))

    print(f"[helper_setup] Using prefix: {prefix}")
    print(f"[helper_setup] Found {len(rooms)} rooms")

    if args.cleanup:
        # Cleanup mode - delete all helpers
        deleted = cleanup_helpers(prefix, rooms)
        print(f"[helper_setup] Cleanup complete, deleted {deleted} helpers")
        return 0

    if args.check:
        # Check mode - only recreate missing helpers
        recreated = ensure_helpers_exist(prefix, rooms)
        if recreated:
            print(f"[helper_setup] Recreated {len(recreated)} missing helpers")
        else:
            print("[helper_setup] All helpers exist")
        return 0

    # Default: Setup mode - create all helpers
    core_count = setup_core_helpers(prefix)
    print(f"[helper_setup] Processed {core_count} core helpers")

    if rooms:
        room_count = setup_room_helpers(rooms, prefix)
        print(f"[helper_setup] Processed {room_count} room helpers")
    else:
        print("[helper_setup] No rooms configured, skipping room helpers")

    print("[helper_setup] Helper setup complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
