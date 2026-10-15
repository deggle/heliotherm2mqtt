# 0004: Retain can be switched off

## Context

While testing discovery, retained config messages linger on the broker. Removing them means clearing each topic by hand.

## Decision

`mqtt.retain` (env `H2M_MQTT_RETAIN`), default `true`. When it is `false`, nothing the bridge publishes is retained: not state, availability, discovery or the last will. To keep Home Assistant entities alive without retain, the bridge republishes discovery and state when HA announces `online` on `<discovery_prefix>/status`.

## Consequences

- With retain off, stopping the bridge leaves nothing on the broker. HA entities disappear once HA restarts.
- With retain off, a consumer that subscribes between publishes sees nothing until the next change or periodic republish.
