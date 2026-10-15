# 0002: Built-in point map

## Context

A "point" is one value the bridge exposes, such as `outdoor_temperature`. Each point has a register address, data type, scale, unit and Home Assistant metadata. The Heliotherm Remote Control Gateway documents a fixed register layout (input registers 10–75, holding registers 100–152), and the same layout applies across models.

## Decision

The point map lives in code (`src/heliotherm2mqtt/points.py`) and is not user configuration. It is documented in `docs/points.md`, and a test checks that the two agree. Users can hide points per heat pump with `exclude_points`, using glob patterns such as `mc2_*`.

Sources cross-checked:

- Heliotherm *Expert Level Instruction Document, Remote Control Gateway X*, tables 12 and 13.
- The register layout used by the community integration [ha_heliotherm](https://github.com/mbuchber/ha_heliotherm): mode codes 0–7, request codes 10/20/30/40 and the -50.0 °C sentinel.
- A working Node-RED integration on real hardware.

The bridge always reads the full register blocks (input 10–50, input 60–75, holding 100–152), whatever is excluded. Exclusion affects publishing only.

## Consequences

- No point-map file to configure or keep in step with releases.
- A firmware variant with different registers needs a code change. That is acceptable until such a variant turns up.
- Point keys are part of the public interface. Renaming one is a breaking change.
