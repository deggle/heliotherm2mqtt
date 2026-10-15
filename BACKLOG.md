# Backlog

Labels: **build** (code), **spike** (research, written answer), **verify** (needs hardware, the user runs it).

## Foundations

- [x] Project skeleton: `pyproject.toml`, package layout, ruff, mypy, pytest, CI (*build*)
- [x] Configuration: YAML plus `H2M_*` env overrides, validated, several heat pumps (*build*)
- [x] Logging and graceful shutdown (*build*)
- [x] Simulated Modbus device for tests and local trials (*build*)
- [x] Retain toggle for testing (*build*)

## Read path

- [x] Point map from the Heliotherm register documentation and ha_heliotherm (*spike*)
- [x] Modbus TCP client with timeouts and reconnect (*build*)
- [x] Poll loop, publish on change plus periodic republish (*build*)
- [x] Availability and last-will handling (*build*)
- [ ] Verify read path against real heat pumps: values match the gateway web interface (*verify*)
- [ ] Check which input temperatures read -50.0 on units without that sensor, and whether other "not fitted" values occur (*verify*). Room sensor (50) reads a constant 20.0 on units without one; find out whether this is a fixed substitute or configurable.

## Discovery

- [x] HA discovery generated from the point map, off by default, stale-entity cleanup (*build*)
- [ ] Verify discovery entities, units and categories in Home Assistant (*verify*)

## Write path

- [x] Command topics with validation, pacing and result reporting, disabled by default (*build*)
- [ ] Verify writes through the bridge on hardware: mode, room setpoint, DHW setpoint (*verify*)
- [ ] Verify heating curve writes (135–138) on hardware: the values show in WebControl and the heat request follows the limit (*verify*)
- [ ] Confirm whether mode and setpoint writes persist across a gateway reboot (*spike*, then *verify*)
- [ ] Decide whether to make further holding registers writable, one at a time, after hardware checks (*verify*)

## Packaging

- [x] Dockerfile, multi-arch GHCR workflow, example compose file (*build*)
- [x] Example configuration with placeholder values (*build*)
- [ ] First tagged release `v0.1.0` once the read path is verified (*build*)
