# 0003: Write safety

## Context

The manufacturer warns that writing the wrong data type can damage the controller, and that registers should not be written more often than every 5 seconds. Writes to some registers have been proven on real hardware: operating mode (100), room setpoint (101) and DHW setpoint (105) through Node-RED, plus 102–107 and 112 through ha_heliotherm.

## Decision

- Writes are off unless `writes.enabled` is true.
- Only points marked `writable` in the point map are accepted. The set is registers 100–103, 105, 107 and 112, taken from those proven by the two integrations above.
- The DHW minimum (106) and cooling return minimum (104) are internal tuning values, so they are read-only here even though ha_heliotherm writes them.
- Every write is checked against the point's type and range, then encoded to the documented register format.
- Writes are spaced per heat pump by `writes.min_interval`, minimum 5 seconds. Later commands wait rather than being rejected, so a controller can send a mode and a setpoint together.
- Retained command messages are ignored.

## Consequences

- More registers can be made writable later by flipping `writable` in the point map, once each is confirmed on hardware.
- The "hand" override registers (129–134, 147–152) revert to automatic after a controller reboot, according to the manual. Re-asserting them is a job for the controller sending commands, not the bridge.
