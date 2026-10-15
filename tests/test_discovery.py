from __future__ import annotations

import json
from typing import Any

from heliotherm2mqtt import discovery
from heliotherm2mqtt.points import POINTS, POINTS_BY_KEY

from .conftest import make_settings


def _config(key: str, **overrides: Any) -> dict[str, Any]:
    settings = make_settings(**overrides)
    return discovery.entity_config(settings, settings.heatpumps[0], POINTS_BY_KEY[key])


def test_temperature_sensor() -> None:
    cfg = _config("outdoor_temperature")
    assert cfg["unique_id"] == "heliotherm_primary_outdoor_temperature"
    assert cfg["state_topic"] == "heliotherm/primary/state/outdoor_temperature"
    assert cfg["unit_of_measurement"] == "°C"
    assert cfg["device_class"] == "temperature"
    assert cfg["state_class"] == "measurement"
    assert cfg["availability"] == [
        {"topic": "heliotherm/bridge/status"},
        {"topic": "heliotherm/primary/availability"},
    ]
    assert cfg["availability_mode"] == "all"
    assert cfg["device"] == {
        "identifiers": ["heliotherm_primary"],
        "name": "Primary",
        "manufacturer": "Heliotherm",
        "via_device": "heliotherm_bridge",
    }
    assert "command_topic" not in cfg


def test_binary_sensor_and_enum_sensor() -> None:
    assert _config("fault")["device_class"] == "problem"
    cfg = _config("heat_pump_request")
    assert cfg["device_class"] == "enum"
    assert cfg["options"] == ["None", "Cool", "Heat", "DHW", "External"]
    mode = _config("mc1_operating_mode")
    assert mode["entity_category"] == "diagnostic"  # config is not valid on read-only entities


def test_label_template_renders() -> None:
    import jinja2

    template = _config("operating_mode")["value_template"]
    render = jinja2.Environment().from_string(str(template)).render
    assert render(value="summer") == "Summer"
    assert render(value="99") == "99"


def test_mc_mode_select_when_writes_enabled() -> None:
    mode = _config("mc1_operating_mode", writes={"enabled": True})
    assert mode["command_topic"] == "heliotherm/primary/command/mc1_operating_mode"
    assert mode["options"][:3] == ["Off", "Auto", "Cool"]
    assert mode["entity_category"] == "config"


def _messages(absent: frozenset[str] = frozenset(), **overrides: object) -> dict[str, str]:
    settings = make_settings(homeassistant={"discovery": True}, **overrides)
    return dict(discovery.messages(settings, settings.heatpumps[0], absent))


def test_messages_components_and_cleanup() -> None:
    msgs = _messages(
        heatpumps=[{"id": "pool", "name": "Pool", "host": "h", "exclude_points": ["mc2_*"]}],
    )
    mode = json.loads(msgs["homeassistant/sensor/heliotherm_pool/operating_mode/config"])
    assert "entity_category" not in mode
    assert msgs["homeassistant/select/heliotherm_pool/operating_mode/config"] == ""
    assert msgs["homeassistant/sensor/heliotherm_pool/mc2_room_setpoint/config"] == ""
    assert json.loads(msgs["homeassistant/binary_sensor/heliotherm_pool/compressor/config"])
    # Combined points never get an entity of their own.
    assert msgs["homeassistant/sensor/heliotherm_pool/dhw_setpoint/config"] == ""
    singles = [
        t for t, p in msgs.items() if p and t.split("/")[1] not in ("water_heater", "climate")
    ]
    expected = [p for p in POINTS if not p.key.startswith("mc2_")]
    assert len(singles) == len(expected) - len(discovery.COMBINED)


def test_absent_points_are_removed() -> None:
    msgs = _messages(absent=frozenset({"buffer_temperature", "dhw_temperature"}))
    assert msgs["homeassistant/sensor/heliotherm_primary/buffer_temperature/config"] == ""
    assert msgs["homeassistant/water_heater/heliotherm_primary/dhw/config"] == ""
    assert json.loads(msgs["homeassistant/climate/heliotherm_primary/heating/config"])


def test_water_heater() -> None:
    cfg = json.loads(_messages()["homeassistant/water_heater/heliotherm_primary/dhw/config"])
    assert cfg["name"] == "Hot water"
    assert cfg["current_temperature_topic"] == "heliotherm/primary/state/dhw_temperature"
    assert cfg["temperature_state_topic"] == "heliotherm/primary/state/dhw_setpoint"
    assert (cfg["min_temp"], cfg["max_temp"], cfg["precision"]) == (5, 65, 0.5)
    assert cfg["device"]["via_device"] == "heliotherm_bridge"
    assert "temperature_command_topic" not in cfg

    msgs = _messages(writes={"enabled": True})
    cfg = json.loads(msgs["homeassistant/water_heater/heliotherm_primary/dhw/config"])
    assert cfg["temperature_command_topic"] == "heliotherm/primary/command/dhw_setpoint"


def test_climate() -> None:
    cfg = json.loads(_messages()["homeassistant/climate/heliotherm_primary/heating/config"])
    assert cfg["name"] == "Heating"
    assert cfg["current_temperature_topic"] == "heliotherm/primary/state/room_temperature"
    assert cfg["temperature_state_topic"] == "heliotherm/primary/state/room_setpoint"
    assert (cfg["min_temp"], cfg["max_temp"], cfg["temp_step"]) == (10, 25, 0.5)
    assert cfg["modes"] == ["off", "auto"]
    assert cfg["preset_modes"] == [
        "Off",
        "Auto",
        "Cool",
        "Summer",
        "Continuous",
        "Decrease",
        "Holiday",
        "Party",
    ]
    assert cfg["action_topic"] == "heliotherm/primary/state/heat_pump_request"
    assert not any(k.endswith("_command_topic") for k in cfg)

    msgs = _messages(writes={"enabled": True})
    cfg = json.loads(msgs["homeassistant/climate/heliotherm_primary/heating/config"])
    assert cfg["mode_command_topic"] == "heliotherm/primary/command/operating_mode"
    assert cfg["preset_mode_command_topic"] == "heliotherm/primary/command/operating_mode"
    assert cfg["temperature_command_topic"] == "heliotherm/primary/command/room_setpoint"


def test_climate_removed_without_room_sensor() -> None:
    msgs = _messages(absent=frozenset({"room_temperature"}), writes={"enabled": True})
    assert msgs["homeassistant/climate/heliotherm_primary/heating/config"] == ""
    assert json.loads(msgs["homeassistant/select/heliotherm_primary/operating_mode/config"])
    # The room setpoint ("Normal") then gets its own number.
    setpoint = json.loads(msgs["homeassistant/number/heliotherm_primary/room_setpoint/config"])
    assert setpoint["command_topic"] == "heliotherm/primary/command/room_setpoint"
    assert setpoint["entity_category"] == "config"


def test_climate_without_room_setpoint_has_no_target() -> None:
    msgs = _messages(
        heatpumps=[
            {"id": "pool", "name": "Pool", "host": "h", "exclude_points": ["room_setpoint"]}
        ],
        writes={"enabled": True},
    )
    cfg = json.loads(msgs["homeassistant/climate/heliotherm_pool/heating/config"])
    assert not any(k.startswith("temperature_") for k in cfg if k != "temperature_unit")


def test_operating_mode_select_is_a_primary_control() -> None:
    msgs = _messages(writes={"enabled": True})
    cfg = json.loads(msgs["homeassistant/select/heliotherm_primary/operating_mode/config"])
    assert cfg["command_topic"] == "heliotherm/primary/command/operating_mode"
    assert cfg["options"][:2] == ["Off", "Auto"]
    assert "entity_category" not in cfg
    assert msgs["homeassistant/sensor/heliotherm_primary/operating_mode/config"] == ""


def test_climate_action_template_renders() -> None:
    import jinja2

    cfg = json.loads(_messages()["homeassistant/climate/heliotherm_primary/heating/config"])
    render = jinja2.Environment().from_string(cfg["action_template"]).render
    assert [render(value=v) for v in ("heat", "cool", "dhw", "none")] == [
        "heating",
        "cooling",
        "idle",
        "idle",
    ]


def test_heating_limit_is_a_config_number() -> None:
    cfg = _config("hc_heat_limit", writes={"enabled": True})
    assert cfg["command_topic"] == "heliotherm/primary/command/hc_heat_limit"
    assert (cfg["min"], cfg["max"], cfg["step"]) == (10, 30, 1)
    assert cfg["entity_category"] == "config"
    assert "enabled_by_default" not in cfg
    curve = _config("hc_return_at_0c", writes={"enabled": True})
    assert (curve["min"], curve["max"], curve["step"]) == (15, 55, 0.1)
    assert curve["entity_category"] == "config"


def test_room_setpoint_has_no_entity_of_its_own() -> None:
    msgs = _messages(writes={"enabled": True})
    assert msgs["homeassistant/sensor/heliotherm_primary/room_setpoint/config"] == ""
    assert msgs["homeassistant/number/heliotherm_primary/room_setpoint/config"] == ""


def test_combined_entities_removed_when_points_excluded() -> None:
    msgs = _messages(
        heatpumps=[{"id": "pool", "name": "Pool", "host": "h", "exclude_points": ["dhw_*"]}]
    )
    assert msgs["homeassistant/water_heater/heliotherm_pool/dhw/config"] == ""
    assert json.loads(msgs["homeassistant/climate/heliotherm_pool/heating/config"])


def test_unique_ids_differ_across_heat_pumps() -> None:
    settings = make_settings(
        heatpumps=[
            {"id": "a", "name": "A", "host": "h"},
            {"id": "a", "name": "B", "host": "h", "topic_prefix": "site/two"},
        ]
    )
    ids = {
        discovery.entity_config(settings, pump, POINTS[0])["unique_id"]
        for pump in settings.heatpumps
    }
    assert ids == {"heliotherm_a_outdoor_temperature", "site_two_a_outdoor_temperature"}


def test_bridge_device() -> None:
    settings = make_settings(homeassistant={"discovery": True, "bridge_name": "My Bridge"})
    topic, payload = discovery.bridge_message(settings)
    assert topic == "homeassistant/binary_sensor/heliotherm_bridge/connection/config"
    cfg = json.loads(payload)
    assert cfg["state_topic"] == "heliotherm/bridge/status"
    assert cfg["device_class"] == "connectivity"
    assert cfg["device"]["identifiers"] == ["heliotherm_bridge"]
    assert cfg["device"]["name"] == "My Bridge"
    assert "availability" not in cfg  # shows disconnected rather than unavailable


def test_buffer_override_climate() -> None:
    import jinja2

    topic = "homeassistant/climate/heliotherm_primary/buffer_override/config"
    msgs = _messages()
    cfg = json.loads(msgs[topic])
    assert msgs["homeassistant/water_heater/heliotherm_primary/buffer_override/config"] == ""
    assert cfg["name"] == "Buffer override"
    assert cfg["current_temperature_topic"] == "heliotherm/primary/state/buffer_temperature"
    assert cfg["temperature_state_topic"] == "heliotherm/primary/state/return_setpoint_value"
    assert cfg["modes"] == ["auto", "heat"]
    assert not any(k.startswith("preset_mode") for k in cfg)
    assert "mode_command_topic" not in cfg

    msgs = _messages(writes={"enabled": True})
    cfg = json.loads(msgs[topic])
    assert cfg["temperature_command_topic"] == "heliotherm/primary/command/return_setpoint_value"
    assert cfg["mode_command_topic"] == "heliotherm/primary/command/return_setpoint_active"
    env = jinja2.Environment()
    command = env.from_string(cfg["mode_command_template"]).render
    state = env.from_string(cfg["mode_state_template"]).render
    assert [command(value=m) for m in ("heat", "auto")] == ["ON", "OFF"]
    assert [state(value=v) for v in ("ON", "OFF")] == ["heat", "auto"]
    # The parts no longer have entities of their own.
    assert msgs["homeassistant/number/heliotherm_primary/return_setpoint_value/config"] == ""
    assert msgs["homeassistant/switch/heliotherm_primary/return_setpoint_active/config"] == ""
