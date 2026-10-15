# 0006: Writable heating curve

## Context

The heating limit (register 135, WebControl SP 76) is the outdoor temperature above which the controller does not heat at all, even in Auto mode. It is compared with the delayed outdoor temperature (register 33). Above the limit there is no heat request, and the buffer override (registers 102/103) has no effect. On hardware, raising the limit in WebControl from 18 to 21 °C, with a delayed outdoor temperature of 18.8 °C, started a heat request within 30 seconds, with the override active.

The rest of the heating curve is three return temperature points: at the heating limit (136), at 0 °C (137) and at -15 °C (138). WebControl shows the limit and the three points on one screen, together with "Normal" (the room setpoint, 101), "Boost H.in" and "Red. H.inlet". The page script binds each field to a controller parameter, numbered as the manual's SP number plus 300:

| WebControl | Parameter name | SP | Register |
|---|---|---|---|
| Normal | `SollRaum` | 69 | 101 |
| Boost H.in | `Ueberheizen` | 71 | none |
| Red. H.inlet | `Absenken` | 72 | none |
| Heating limit | `Heizgrenze` | 76 | 135 |
| Curve at the heating limit | `RL_Oben` | 80 | 136 |
| Curve at 0 °C | `RL_Null` | 81 | 137 |
| Curve at -15 °C | `RL_Unten` | 82 | 138 |

Boost and setback are not in the register map. WebControl steps the heating limit in 1 °C and the curve points in 0.1 °C.

Users want to tune the curve from Home Assistant, for example in autumn when rooms need heat while it is mild outside.

## Decision

- `hc_heat_limit` (135) is writable, 10 to 30 °C, step 1 °C, shown as "Heating curve outdoor limit", which says what it does and sorts with the curve points.
- `hc_return_at_heat_limit`, `hc_return_at_0c` and `hc_return_at_minus_15c` (136–138) are writable, 15 to 55 °C, step 0.1 °C.
- Steps follow WebControl, so the bridge only writes values the controller's own interface can produce.
- All four are config entities, enabled by default.
- `room_setpoint` gets its own config number whenever the heating climate is not published (for example, no room sensor), so "Normal" stays adjustable.
- The mixing circuit curves (139–146) stay read-only until they are needed and checked.
- The DHW minimum (106) is removed from the point map. It is an internal tuning value that was read-only and hidden here (see 0003), and WebControl does not offer it for editing, so it added an entity with nothing to do.

## Consequences

- This extends the writable set in 0003. Writes over Modbus still need verifying on hardware (see BACKLOG.md).
- The ranges protect against typing errors, not against a poor curve. Choosing the curve, or changing it with the season, is up to the user or their automations.
