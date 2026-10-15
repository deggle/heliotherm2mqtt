"""MQTT topic names. See docs/interface.md."""

from __future__ import annotations

from .config import HeatPumpSettings, Settings


class Topics:
    def __init__(self, settings: Settings, pump: HeatPumpSettings) -> None:
        self.bridge_status = bridge_status(settings)
        self.base = f"{settings.prefix_for(pump)}/{pump.id}"
        self.availability = f"{self.base}/availability"

    def state(self, key: str) -> str:
        return f"{self.base}/state/{key}"

    def command(self, key: str) -> str:
        return f"{self.base}/command/{key}"

    def result(self, key: str) -> str:
        return f"{self.base}/command/{key}/result"


def bridge_status(settings: Settings) -> str:
    return f"{settings.mqtt.topic_prefix}/bridge/status"


def command_filters(settings: Settings) -> set[str]:
    """Subscription filters covering every heat pump's command topics."""
    return {f"{settings.prefix_for(p)}/+/command/+" for p in settings.heatpumps}
