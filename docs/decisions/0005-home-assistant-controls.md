# 0005: Home Assistant controls

## Context

The first discovery layout hid the operating mode inside the heating climate's presets, gave that climate no target temperature, and switched the buffer override with presets while its HVAC mode stayed fixed at `heat`. In use, presets are awkward to reach, the room setpoint is a natural target for the heating card, and the mode is wanted as a plain dropdown among the controls.

## Decision

- The heating climate's target is `room_setpoint`, and its current temperature is `room_temperature`. Without a room sensor, a room target is meaningless, so the heating climate is only published when `room_temperature` is available. The register documentation gives no "not fitted" value for the room sensor, and units without one have been seen to read a constant 20.0 °C, which is indistinguishable from a real reading. Detection is therefore left to configuration: excluding `room_temperature` removes the heating climate. `room_setpoint` no longer has an entity of its own.
- `operating_mode` gets its own primary entity (a `select` when writes are enabled), as well as remaining the heating climate's presets.
- The buffer override uses HVAC modes instead of presets: `auto` means the override is off, `heat` means it is active. Home Assistant only accepts its own HVAC mode names, so "Override" cannot be used as a label.

## Consequences

- Without a room sensor, the operating mode select is the only mode control, and the room setpoint is reachable over MQTT only.
- With writes enabled, the room setpoint is writable from Home Assistant. It was already writable over MQTT and proven on hardware (see 0003).
- Whether the controller acts on `room_setpoint` depends on the installation (a room sensor or room influence on the heating curve). The bridge does not check this.
