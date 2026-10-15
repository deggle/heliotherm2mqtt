"""Home Assistant MQTT discovery payloads, generated from the point map."""

from __future__ import annotations

import json
from collections.abc import Iterator, Set
from typing import Any

from . import __version__
from .config import HeatPumpSettings, Settings
from .points import POINTS, POINTS_BY_KEY, Kind, Point
from .topics import Topics, bridge_status

MANUFACTURER = "Heliotherm"
SUPPORT_URL = "https://github.com/deggle/heliotherm2mqtt"

ORIGIN = {"name": "heliotherm2mqtt", "sw_version": __version__, "support_url": SUPPORT_URL}

_READ_ONLY = {Kind.NUMBER: "sensor", Kind.BOOLEAN: "binary_sensor", Kind.ENUM: "sensor"}
_WRITABLE = {Kind.NUMBER: "number", Kind.BOOLEAN: "switch", Kind.ENUM: "select"}


def component_for(point: Point, writes_enabled: bool) -> str:
    table = _WRITABLE if point.writable and writes_enabled else _READ_ONLY
    return table[point.kind]


def _node_id(prefix: str, pump: HeatPumpSettings) -> str:
    return f"{prefix.replace('/', '_')}_{pump.id}"


def bridge_id(settings: Settings) -> str:
    return f"{settings.mqtt.topic_prefix.replace('/', '_')}_bridge"


def bridge_message(settings: Settings) -> tuple[str, str]:
    """The bridge's own device, with a connectivity entity following bridge/status."""
    node = bridge_id(settings)
    config = {
        "name": "Connection",
        "unique_id": f"{node}_connection",
        "state_topic": bridge_status(settings),
        "payload_on": "online",
        "payload_off": "offline",
        "device_class": "connectivity",
        "entity_category": "diagnostic",
        "device": {
            "identifiers": [node],
            "name": settings.homeassistant.bridge_name,
            "manufacturer": "heliotherm2mqtt",
            "model": "Modbus TCP to MQTT bridge",
            "sw_version": __version__,
        },
        "origin": ORIGIN,
    }
    topic = f"{settings.homeassistant.discovery_prefix}/binary_sensor/{node}/connection/config"
    return topic, json.dumps(config, ensure_ascii=False)


def config_topic(settings: Settings, pump: HeatPumpSettings, point: Point, component: str) -> str:
    node = _node_id(settings.prefix_for(pump), pump)
    return f"{settings.homeassistant.discovery_prefix}/{component}/{node}/{point.key}/config"


def _device(settings: Settings, pump: HeatPumpSettings) -> dict[str, Any]:
    device: dict[str, Any] = {
        "identifiers": [_node_id(settings.prefix_for(pump), pump)],
        "name": pump.name,
        "manufacturer": MANUFACTURER,
        "via_device": bridge_id(settings),
    }
    if pump.model:
        device["model"] = pump.model
    return device


def entity_config(settings: Settings, pump: HeatPumpSettings, point: Point) -> dict[str, Any]:
    topics = Topics(settings, pump)
    component = component_for(point, settings.writes.enabled)
    node = _node_id(settings.prefix_for(pump), pump)
    device = _device(settings, pump)

    config: dict[str, Any] = {
        "name": point.name,
        "unique_id": f"{node}_{point.key}",
        "state_topic": topics.state(point.key),
        "availability": [{"topic": topics.bridge_status}, {"topic": topics.availability}],
        "availability_mode": "all",
        "device": device,
        "origin": ORIGIN,
    }
    if point.icon:
        config["icon"] = point.icon
    if not point.enabled_by_default:
        config["enabled_by_default"] = False

    writable = component in _WRITABLE.values()
    if point.category == "diagnostic" or (point.category == "config" and not writable):
        config["entity_category"] = "diagnostic"
    elif point.category == "config":
        config["entity_category"] = "config"

    if writable:
        config["command_topic"] = topics.command(point.key)

    if point.kind is Kind.NUMBER:
        if point.unit:
            config["unit_of_measurement"] = point.unit
        if point.device_class:
            config["device_class"] = point.device_class
        if component == "sensor":
            if point.state_class:
                config["state_class"] = point.state_class
            config["suggested_display_precision"] = point.decimals
        else:
            config["mode"] = "box"
            for key, value in (("min", point.minimum), ("max", point.maximum)):
                if value is not None:
                    config[key] = value
            config["step"] = point.step or point.scale
    elif point.kind is Kind.BOOLEAN:
        if point.device_class and component == "binary_sensor":
            config["device_class"] = point.device_class
    else:
        assert point.options is not None
        config["options"] = [label(v) for v in point.options.values()]
        config["value_template"] = _label_template(point)
        if component == "sensor":
            config["device_class"] = "enum"
    return config


def label(text: str) -> str:
    """Title-case an enum label for display: "auto" -> "Auto", "dhw" -> "DHW"."""
    return "DHW" if text == "dhw" else text.replace("_", " ").title()


def _label_template(point: Point) -> str:
    assert point.options is not None
    mapping = {v: label(v) for v in point.options.values()}
    return "{{ " + json.dumps(mapping) + ".get(value, value) }}"


def _common(
    settings: Settings, pump: HeatPumpSettings, name: str, object_id: str
) -> dict[str, Any]:
    topics = Topics(settings, pump)
    return {
        "name": name,
        "unique_id": f"{_node_id(settings.prefix_for(pump), pump)}_{object_id}",
        "availability": [{"topic": topics.bridge_status}, {"topic": topics.availability}],
        "availability_mode": "all",
        "device": _device(settings, pump),
        "origin": ORIGIN,
    }


def _composite_topic(settings: Settings, pump: HeatPumpSettings, component: str, oid: str) -> str:
    node = _node_id(settings.prefix_for(pump), pump)
    return f"{settings.homeassistant.discovery_prefix}/{component}/{node}/{oid}/config"


def water_heater_config(
    settings: Settings, pump: HeatPumpSettings, available: set[str]
) -> dict[str, Any] | None:
    if not {"dhw_temperature", "dhw_setpoint", "operating_mode"} <= available:
        return None
    topics = Topics(settings, pump)
    setpoint = POINTS_BY_KEY["dhw_setpoint"]
    config = _common(settings, pump, "Hot water", "dhw")
    config |= {
        "current_temperature_topic": topics.state("dhw_temperature"),
        "temperature_state_topic": topics.state("dhw_setpoint"),
        "mode_state_topic": topics.state("operating_mode"),
        "mode_state_template": "{{ 'off' if value == 'off' else 'heat_pump' }}",
        "modes": ["off", "heat_pump"],
        "min_temp": setpoint.minimum,
        "max_temp": setpoint.maximum,
        "precision": setpoint.step,
        "temperature_unit": "C",
    }
    if settings.writes.enabled:
        config["temperature_command_topic"] = topics.command("dhw_setpoint")
    return config


def buffer_override_config(
    settings: Settings, pump: HeatPumpSettings, available: set[str]
) -> dict[str, Any] | None:
    if not {"return_setpoint_value", "return_setpoint_active"} <= available:
        return None
    topics = Topics(settings, pump)
    target = POINTS_BY_KEY["return_setpoint_value"]
    config = _common(settings, pump, "Buffer override", "buffer_override")
    config |= {
        "icon": "mdi:thermometer-chevron-up",
        "temperature_state_topic": topics.state("return_setpoint_value"),
        # HA allows only its own HVAC mode names: "auto" is override off, "heat" is override on.
        "modes": ["auto", "heat"],
        "mode_state_topic": topics.state("return_setpoint_active"),
        "mode_state_template": "{{ 'heat' if value == 'ON' else 'auto' }}",
        "min_temp": target.minimum,
        "max_temp": target.maximum,
        "temp_step": target.step,
        "precision": 0.1,
        "temperature_unit": "C",
    }
    for key in ("buffer_temperature", "return_temperature"):
        if key in available:
            config["current_temperature_topic"] = topics.state(key)
            break
    if settings.writes.enabled:
        config["temperature_command_topic"] = topics.command("return_setpoint_value")
        config["mode_command_topic"] = topics.command("return_setpoint_active")
        config["mode_command_template"] = "{{ 'ON' if value == 'heat' else 'OFF' }}"
    return config


_ACTIONS = {"heat": "heating", "cool": "cooling"}


def climate_config(
    settings: Settings, pump: HeatPumpSettings, available: set[str]
) -> dict[str, Any] | None:
    if not {"operating_mode", "room_temperature"} <= available:
        return None
    topics = Topics(settings, pump)
    mode = POINTS_BY_KEY["operating_mode"]
    assert mode.options is not None
    config = _common(settings, pump, "Heating", "heating")
    config |= {
        "current_temperature_topic": topics.state("room_temperature"),
        "mode_state_topic": topics.state("operating_mode"),
        "mode_state_template": "{{ 'off' if value == 'off' else 'auto' }}",
        "modes": ["off", "auto"],
        "preset_mode_state_topic": topics.state("operating_mode"),
        "preset_mode_value_template": _label_template(mode),
        "preset_modes": [label(v) for v in mode.options.values()],
        "temperature_unit": "C",
        "precision": 0.1,
    }
    has_target = "room_setpoint" in available
    if has_target:
        target = POINTS_BY_KEY["room_setpoint"]
        config |= {
            "temperature_state_topic": topics.state("room_setpoint"),
            "min_temp": target.minimum,
            "max_temp": target.maximum,
            "temp_step": target.step,
        }
    if "heat_pump_request" in available:
        config["action_topic"] = topics.state("heat_pump_request")
        config["action_template"] = (
            "{{ 'off' if value == 'off' else " + json.dumps(_ACTIONS) + ".get(value, 'idle') }}"
        )
    if settings.writes.enabled:
        config["mode_command_topic"] = topics.command("operating_mode")
        config["preset_mode_command_topic"] = topics.command("operating_mode")
        if has_target:
            config["temperature_command_topic"] = topics.command("room_setpoint")
    return config


# Points shown only as part of a combined entity, never on their own.
COMBINED = {"dhw_setpoint", "room_setpoint", "return_setpoint_value", "return_setpoint_active"}


def messages(
    settings: Settings, pump: HeatPumpSettings, absent: Set[str] = frozenset()
) -> Iterator[tuple[str, str]]:
    """Yield (topic, payload) for every discovery message of a heat pump.

    `absent` holds points whose sensor reports "not fitted". Points without an entity, and
    components a point no longer uses, get an empty payload so Home Assistant removes them.
    """
    available = {p.key for p in pump.points()} - set(absent)
    writes = settings.writes.enabled
    climate = climate_config(settings, pump, available)
    # Without the heating climate, the room setpoint ("Normal") gets its own entity.
    combined = COMBINED if climate else COMBINED - {"room_setpoint"}
    for point in POINTS:
        has_entity = point.key in available and point.key not in combined
        current = component_for(point, writes) if has_entity else None
        if current is not None:
            payload = json.dumps(entity_config(settings, pump, point), ensure_ascii=False)
            yield config_topic(settings, pump, point, current), payload
        possible = {_READ_ONLY[point.kind]} | ({_WRITABLE[point.kind]} if point.writable else set())
        for component in possible - {current}:
            yield config_topic(settings, pump, point, component), ""
    for component, oid, config in (
        ("water_heater", "dhw", water_heater_config(settings, pump, available)),
        ("climate", "buffer_override", buffer_override_config(settings, pump, available)),
        ("water_heater", "buffer_override", None),  # earlier location of the buffer override
        ("climate", "heating", climate),
    ):
        payload = json.dumps(config, ensure_ascii=False) if config else ""
        yield _composite_topic(settings, pump, component, oid), payload
