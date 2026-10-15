# 0001: One process serves many heat pumps

## Context

Sites often have more than one Heliotherm unit, for example two house units and a pool unit. The options were one container per heat pump, or one container listing several heat pumps in its configuration.

## Decision

One process reads a list of heat pumps from its configuration. Each heat pump gets its own poll task and Modbus connection, so a slow or offline unit does not delay the others. All heat pumps share one MQTT connection and one `bridge/status` topic.

## Consequences

- One image, one config file and one container to update.
- A config with a single heat pump still works, so anyone who prefers one container per unit can run it that way. Each container then needs its own `mqtt.client_id`, and a distinct `topic_prefix` if they share a broker.
- MQTT allows only one last will per connection, so per-pump availability is not covered by the last will. Discovery uses both availability topics with `availability_mode: all`.
