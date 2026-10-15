# heliotherm2mqtt

A bridge between Heliotherm heat pumps and MQTT. It polls each heat pump's Remote Control Gateway over Modbus TCP, publishes the values to MQTT, and can apply commands sent over MQTT. Home Assistant discovery is optional.

One container serves any number of heat pumps.

**Status:** early development. Reading and discovery are complete. Writing works against the simulator and is off by default until it has been checked on hardware.

## What it does

- Polls every documented input and holding register: temperatures, pressures, pump and compressor states, energy meters, modes and setpoints.
- Publishes each value to its own topic, retained by default.
- Optionally publishes Home Assistant discovery: one device per heat pump.
- With writes enabled, accepts commands for a small set of proven registers (operating modes and setpoints). Each command is range-checked and writes are spaced at least 5 seconds apart, as Heliotherm advises.

It does not make control decisions. Scheduling, pricing and comfort logic belong in your controller (Home Assistant, Node-RED and so on).

## Requirements

- A Heliotherm heat pump with Modbus TCP enabled on the Remote Control Gateway (web interface: *Service area → Main settings → Modbus*, then restart the gateway).
- An MQTT broker.
- Docker, or Python 3.11 or later.

## Quick start (Docker)

```sh
mkdir config
curl -o config/config.yaml https://raw.githubusercontent.com/deggle/heliotherm2mqtt/main/config.example.yaml
# edit config/config.yaml: broker, heat pumps
docker run -d --name heliotherm2mqtt --restart unless-stopped \
  -v "$PWD/config:/config:ro" ghcr.io/deggle/heliotherm2mqtt:latest
```

Or use [compose.example.yaml](compose.example.yaml). Images are built for `linux/amd64` and `linux/arm64`. `latest` tracks releases and `edge` tracks the `main` branch.

## Configuration

See [config.example.yaml](config.example.yaml) for every option. A minimal file:

```yaml
mqtt:
  host: mqtt.example.local
heatpumps:
  - id: primary
    name: Primary heat pump
    host: 192.0.2.10
```

Per heat pump:

| Key | Default | Meaning |
|---|---|---|
| `id` | required | Topic id: lower case letters, digits and `_` |
| `name` | required | Home Assistant device name |
| `host`, `port`, `unit_id` | required, `502`, `1` | Modbus TCP address |
| `model` | none | Shown in Home Assistant |
| `topic_prefix` | `mqtt.topic_prefix` | Per-pump topic prefix override |
| `poll_interval` | `10` | Seconds between polls |
| `timeout` | `10` | Modbus timeout in seconds (Heliotherm recommends at least 10) |
| `offline_after` | `60` | Seconds of failed polls before reporting offline |
| `exclude_points` | none | Glob patterns of points to hide, e.g. `mc2_*` |

### Environment variables

These override the file. Useful for secrets and quick testing.

| Variable | Setting |
|---|---|
| `H2M_CONFIG` | Config file path (default `/config/config.yaml`) |
| `H2M_MQTT_HOST`, `H2M_MQTT_PORT` | Broker address |
| `H2M_MQTT_USERNAME`, `H2M_MQTT_PASSWORD` | Broker credentials |
| `H2M_MQTT_CLIENT_ID`, `H2M_MQTT_TOPIC_PREFIX`, `H2M_MQTT_TLS` | Connection details |
| `H2M_MQTT_RETAIN` | `false` publishes nothing retained (see below) |
| `H2M_HA_DISCOVERY`, `H2M_HA_DISCOVERY_PREFIX` | Home Assistant discovery |
| `H2M_WRITES_ENABLED` | Accept commands |
| `H2M_LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING` or `ERROR` |

### Testing without retained messages

Set `mqtt.retain: false` (or `H2M_MQTT_RETAIN=false`) and nothing the bridge publishes is retained: not state, availability, discovery or the last will. Stop the bridge and nothing is left on the broker, so test entities vanish when Home Assistant restarts. While the bridge runs, it re-sends discovery whenever Home Assistant comes online.

## Topics

```
heliotherm/bridge/status                     online | offline
heliotherm/<id>/availability                 online | offline
heliotherm/<id>/state/<point>                value
heliotherm/<id>/command/<point>              value to write
heliotherm/<id>/command/<point>/result       ok | error: <reason>
```

For example, `heliotherm/primary/state/outdoor_temperature` holds `4.5`, and publishing `21.5` to `heliotherm/primary/command/room_setpoint` sets the room setpoint.

- [docs/interface.md](docs/interface.md): the full contract (payloads, availability, commands, discovery).
- [docs/points.md](docs/points.md): every point, its register, scaling and whether it is writable.

## Writing

Writes are disabled by default. Enable them with `writes.enabled: true`. Only these points accept commands:

`operating_mode`, `room_setpoint`, `dhw_setpoint`, `return_setpoint_value`, `return_setpoint_active`, `mc1_operating_mode`, `mc2_operating_mode`, `hc_heat_limit`, `hc_return_at_heat_limit`, `hc_return_at_0c`, `hc_return_at_minus_15c`.

Modes take a label (`off`, `auto`, `cool`, `summer`, `continuous`, `decrease`, `holiday`, `party`, in any case) or its number.

With discovery on, each heat pump shows these controls in Home Assistant:

- **Operating mode**: a dropdown with the eight operating modes.
- **Heating**: a climate card for the room setpoint. The controller doesn't report whether a room sensor is fitted (units without one tend to read a constant 20.0 °C), so if yours has none, add `room_temperature` to `exclude_points` to remove the card. The target is the room setpoint, the current temperature is the room temperature, all eight operating modes are presets, and the action follows the heat pump request.
- **Hot water**: a water heater card for the DHW setpoint.
- **Buffer override**: a climate card. Set the target, then choose the *Heat* mode to activate the override, or *Auto* for the normal heating curve. (Home Assistant only allows its own mode names, so the override can't be labelled "Override".) While the override is active, the heat pump runs whenever the return or buffer temperature is below the target. This is Heliotherm's documented way for an external controller to request heat. The manual says override registers revert to automatic after a controller reboot, so a controller that relies on the override should re-send it periodically. The override has no effect while the delayed outdoor temperature is above the heating limit (see below).
- **Heating curve outdoor limit**: a config number for the outdoor temperature above which the controller doesn't heat at all, even in Auto mode and with the buffer override active. The controller compares it with the *delayed* outdoor temperature, which lags the current reading by several hours. WebControl calls it the heating limit and shows it at the left-hand end of the heating curve.
- **Heating curve at heating limit / at 0 °C / at -15 °C**: config numbers for the curve's three return temperature points (the 30.0 / 40.0 / 50.0 boxes in WebControl).
- **Room setpoint**: a config number for "Normal" in WebControl, shown when the Heating card isn't (no room sensor). It shifts the heating curve. WebControl's *Boost H.in* and *Red. H.inlet* aren't available over Modbus.

The MC1 and MC2 modes are hidden by default.

## Trying it without a heat pump

A simulated gateway is included:

```sh
pip install .
python -m heliotherm2mqtt.simulator --port 5020
# in another shell, with a config pointing a heat pump at 127.0.0.1:5020
heliotherm2mqtt --config config.yaml
```

## Development

```sh
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
ruff check . && ruff format --check . && mypy && pytest
```

Tests need no hardware or broker. After changing `points.py`, run `python tools/points_doc.py` to regenerate `docs/points.md`.

## Acknowledgements

The register map follows Heliotherm's *Remote Control Gateway X* expert documentation, cross-checked against [ha_heliotherm](https://github.com/mbuchber/ha_heliotherm).

## Licence

MIT. See [LICENSE](LICENSE). Not affiliated with Heliotherm.
