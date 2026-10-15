# Interface: MQTT topics, availability and discovery

This document is the contract between heliotherm2mqtt and anything that consumes its data.

## Principles

- The bridge translates only. It publishes what the device reports and writes the commands it receives, after validating them.
- One bridge process serves one or more heat pumps. Each heat pump has an `id` (used in topics) and a `name` (used in Home Assistant).
- Every topic sits under a topic prefix, default `heliotherm`. A heat pump may override the prefix.
- State topics are retained by default. Retain can be switched off for testing (`mqtt.retain: false` or `H2M_MQTT_RETAIN=false`). It then applies to every message the bridge publishes, including discovery and availability.
- Payloads are plain strings. Units belong to the point map and discovery config, not the payload.

## Topic layout

```
<prefix>/bridge/status                       online | offline   (retained, last will)
<prefix>/<id>/availability                   online | offline   (retained)
<prefix>/<id>/state/<point>                  <value>            (retained)
<prefix>/<id>/command/<point>                <value>            (not retained)
<prefix>/<id>/command/<point>/result         ok | error: <text> (not retained)
```

`<prefix>` in `bridge/status` is always the global prefix. `<point>` is a snake_case key from the point map ([points.md](points.md)), for example `flow_temperature`.

## Payload formats

| Kind    | State payload                                   | Accepted command payload                     |
|---------|-------------------------------------------------|----------------------------------------------|
| number  | Decimal string, scaled, e.g. `21.5`, `-3.0`, `1450` | A number in the point's range, e.g. `21.5` |
| boolean | `ON` or `OFF`                                   | `ON`/`OFF`, `1`/`0`, `true`/`false`          |
| enum    | A label from the point's options, e.g. `auto`   | A label, or its numeric code                 |

If an enum register holds a code that is not in the map, the raw number is published.

Temperatures that report -50.0 °C or -100.0 °C (the controller's "sensor not fitted" values) are not published.

## Publishing

- Each poll publishes only the values that changed. Every `republish_interval` seconds (default 300), all values are published again.
- After an MQTT reconnect, the bridge publishes discovery (if enabled), then `bridge/status`, availability and every known value again. With retain off, it waits 2 seconds after discovery so Home Assistant has subscribed before the rest arrives.
- The full republish also re-sends `bridge/status` and each heat pump's availability.

## Availability

- `bridge/status` is `online` while the bridge is connected. The MQTT last will sets it to `offline` if the bridge disconnects unexpectedly.
- `<id>/availability` goes `online` after a successful poll and `offline` when polling has failed for longer than `offline_after` seconds (default 60).
- On a clean shutdown, the bridge publishes `offline` for every heat pump and for the bridge.
- A broker supports only one last will per connection, so consumers should treat a heat pump as available only when both `bridge/status` and `<id>/availability` are `online`. Home Assistant discovery does this with `availability_mode: all`.

## Commands

- Writes are disabled by default. While they are disabled, every command gets `error: writes are disabled`.
- Only points marked writable in the point map are accepted. Any other point gets an error result.
- Values are range-checked against the point map before anything is sent to the device.
- Commands delivered with the retain flag set are ignored, so a stale retained command is never replayed when the bridge connects. Empty payloads are ignored.
- Writes to one heat pump are spaced at least `writes.min_interval` seconds apart (default and minimum 5, as the manufacturer advises). A command that arrives sooner waits its turn.
- After a write, the bridge reads the register back and publishes the new state, then publishes `ok`.
- A failed command is reported and not retried.

## Home Assistant discovery

- Discovery is optional and off by default (`homeassistant.discovery: true` enables it).
- The discovery prefix is configurable, default `homeassistant`.
- The bridge is its own HA device (identifier `<global prefix>_bridge`, name from `homeassistant.bridge_name`, default `Heliotherm2MQTT Bridge`), with one diagnostic `binary_sensor` (device class `connectivity`) that follows `bridge/status`. Its config topic is `<discovery_prefix>/binary_sensor/<global prefix>_bridge/connection/config`.
- Each heat pump is one HA device, linked to the bridge device with `via_device`. Each point is one entity, with a retained config message at:
  `<discovery_prefix>/<component>/<node_id>/<point>/config`, where `<node_id>` is `<prefix>_<id>`.
- `unique_id` is `<prefix>_<id>_<point>`, so several heat pumps and several bridges can share a broker.
- Components:

  | Point kind | Read-only (or writes disabled) | Writable, writes enabled |
  |------------|--------------------------------|--------------------------|
  | number     | `sensor`                       | `number`                 |
  | boolean    | `binary_sensor`                | `switch`                 |
  | enum       | `sensor` (device class `enum`) | `select`                 |

- Enum entities show title-case labels in Home Assistant (`Auto`, `Summer`, `DHW`) through `value_template`. The MQTT payloads stay lower case.
- Some points have no entity of their own. Each is part of a combined control instead:
  - `dhw_setpoint` belongs to a `water_heater` entity ("Hot water") at `<discovery_prefix>/water_heater/<node_id>/dhw/config`. Its current temperature is `dhw_temperature` and its target is `dhw_setpoint`. Its mode shows `off` when `operating_mode` is `off`, otherwise `heat_pump`, and is read-only.
  - `room_setpoint` belongs to a `climate` entity ("Heating") when that entity is published, and otherwise has its own entity (a config `number` when writes are enabled). The climate is at `<discovery_prefix>/climate/<node_id>/heating/config`, built around `operating_mode`. All eight operating modes are presets (`Off`, `Auto`, `Summer`…). The HVAC mode shows `off` or `auto`. With writes enabled, choosing either sends an `operating_mode` command. The target is `room_setpoint` (10 to 25 °C in 0.5 steps), and with writes enabled, changing it sends a `room_setpoint` command. The current temperature is `room_temperature`. The action follows `heat_pump_request`: `heating`, `cooling` or `idle`.
  - `return_setpoint_value` and `return_setpoint_active` belong to a second `climate` entity ("Buffer override") at `<discovery_prefix>/climate/<node_id>/buffer_override/config`. This is Heliotherm demand profile 1. Its current temperature is `buffer_temperature`, or `return_temperature` if there is no buffer sensor, and its target is `return_setpoint_value`. It has two HVAC modes and no presets: `auto` (override off, heating curve applies) and `heat` (override active). Home Assistant allows only its own HVAC mode names, so the override shows as *Heat*. With writes enabled, changing the target or the mode sends the matching command (`OFF` or `ON` for `return_setpoint_active`). The controller ignores the override while the delayed outdoor temperature is above the heating limit (`hc_heat_limit`).
  - A combined entity is removed if a point it needs is excluded or not fitted: `dhw_temperature`, `dhw_setpoint` and `operating_mode` for the hot water heater; `return_setpoint_value` and `return_setpoint_active` for the buffer override; `operating_mode` and `room_temperature` for the heating climate. The controller does not report a "not fitted" value for the room sensor (units without one have been seen to read a constant 20.0 °C), so on such units exclude `room_temperature` to remove the heating climate. If `room_setpoint` is excluded, the heating climate has no target.
- `operating_mode` also has its own entity, a primary control: a `select` with the eight modes when writes are enabled, otherwise an enum `sensor`.
- Points whose sensor reports "not fitted" get no entity. The bridge polls each heat pump once before publishing discovery, and updates discovery if a sensor appears or disappears later.
- Entities use `availability` with both availability topics and `availability_mode: all`.
- When a component changes (for example writes are enabled), or a point is excluded or not fitted, the bridge publishes an empty config to the old topic, so Home Assistant removes the stale entity.
- The bridge subscribes to `<discovery_prefix>/status` and publishes discovery and state again when Home Assistant sends `online`. This keeps entities working when retain is off.

## Configuration

Configuration comes from a YAML file (default `/config/config.yaml`, or `H2M_CONFIG`), with `H2M_*` environment variables overriding individual settings. See [config.example.yaml](../config.example.yaml) and the README.
