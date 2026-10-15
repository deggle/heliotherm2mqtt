from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from heliotherm2mqtt.config import Settings
from heliotherm2mqtt.simulator import SimulatedHeatPump


class FakePublisher:
    """Records what the bridge publishes."""

    def __init__(self) -> None:
        self.messages: list[tuple[str, str, bool]] = []

    async def publish(self, topic: str, payload: str, *, retain: bool = True) -> None:
        self.messages.append((topic, payload, retain))

    def last(self, topic: str) -> str | None:
        for t, payload, _ in reversed(self.messages):
            if t == topic:
                return payload
        return None

    def topics(self) -> list[str]:
        return [t for t, _, _ in self.messages]

    def clear(self) -> None:
        self.messages.clear()


def make_settings(**overrides: Any) -> Settings:
    data: dict[str, Any] = {
        "mqtt": {"host": "mqtt.example.local"},
        "heatpumps": [{"id": "primary", "name": "Primary", "host": "192.0.2.10"}],
    }
    for key, value in overrides.items():
        data[key] = value
    return Settings.model_validate(data)


@pytest.fixture
def publisher() -> FakePublisher:
    return FakePublisher()


@pytest.fixture
async def simulator() -> AsyncIterator[SimulatedHeatPump]:
    sim = SimulatedHeatPump()
    await sim.start()
    yield sim
    await sim.stop()
