from __future__ import annotations

import asyncio
from typing import Any

import pytest

from heliotherm2mqtt import bridge as bridge_module
from heliotherm2mqtt.bridge import Bridge, HeatPumpWorker, MqttPublisher
from heliotherm2mqtt.config import Settings, WriteSettings
from heliotherm2mqtt.modbus import ModbusDevice
from heliotherm2mqtt.points import Table
from heliotherm2mqtt.simulator import SimulatedHeatPump

from .conftest import FakePublisher, make_settings

STATE = "heliotherm/primary/state/"
AVAILABILITY = "heliotherm/primary/availability"
RESULT = "heliotherm/primary/command/{}/result"


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _settings(sim: SimulatedHeatPump, **overrides: Any) -> Settings:
    pump = {
        "id": "primary",
        "name": "Primary",
        "host": "127.0.0.1",
        "port": sim.port,
        "timeout": 2,
        **overrides.pop("pump", {}),
    }
    return make_settings(heatpumps=[pump], **overrides)


def _worker(settings: Settings, clock: Clock | None = None) -> HeatPumpWorker:
    pump = settings.heatpumps[0]
    device = ModbusDevice(pump.host, pump.port, pump.unit_id, pump.timeout)
    return HeatPumpWorker(settings, pump, device, clock=clock or Clock())


def _fast_writes(settings: Settings) -> Settings:
    # Bypass the 5 second minimum so the tests stay quick.
    writes = WriteSettings.model_construct(enabled=True, min_interval=0.2)
    return settings.model_copy(update={"writes": writes})


async def test_poll_publishes_state_and_availability(
    simulator: SimulatedHeatPump, publisher: FakePublisher
) -> None:
    worker = _worker(_settings(simulator))
    assert await worker.poll_once(publisher)
    assert publisher.last(STATE + "outdoor_temperature") == "4.5"
    assert publisher.last(STATE + "operating_mode") == "auto"
    assert publisher.last(STATE + "compressor") == "ON"
    assert publisher.last(STATE + "total_heat_energy") == "54000"
    assert publisher.last(STATE + "heat_output") == "5.9"
    assert publisher.last(STATE + "fresh_water_temperature") is None  # sensor not fitted
    assert publisher.last(AVAILABILITY) == "online"
    assert all(retain for _, _, retain in publisher.messages)
    worker.device.close()


async def test_only_changes_are_published_until_republish_interval(
    simulator: SimulatedHeatPump, publisher: FakePublisher
) -> None:
    clock = Clock()
    worker = _worker(_settings(simulator), clock)
    await worker.poll_once(publisher)
    publisher.clear()

    simulator.set("outdoor_temperature", "5.0")
    clock.now += 10
    await worker.poll_once(publisher)
    assert publisher.topics() == [STATE + "outdoor_temperature"]

    publisher.clear()
    clock.now += 300
    await worker.poll_once(publisher)
    assert len(publisher.messages) > 50
    worker.device.close()


async def test_excluded_points_are_not_published(
    simulator: SimulatedHeatPump, publisher: FakePublisher
) -> None:
    worker = _worker(_settings(simulator, pump={"exclude_points": ["outdoor_*"]}))
    await worker.poll_once(publisher)
    assert not any("outdoor_temperature" in t for t in publisher.topics())
    worker.device.close()


async def test_offline_after_timeout_and_recovery(
    simulator: SimulatedHeatPump, publisher: FakePublisher
) -> None:
    clock = Clock()
    worker = _worker(_settings(simulator, pump={"offline_after": 30, "timeout": 0.5}), clock)
    await worker.poll_once(publisher)
    simulator.online = False
    simulator.drop_connections()

    clock.now += 10
    assert not await worker.poll_once(publisher)
    assert publisher.last(AVAILABILITY) == "online"
    clock.now += 25
    assert not await worker.poll_once(publisher)
    assert publisher.last(AVAILABILITY) == "offline"

    simulator.online = True
    assert await worker.poll_once(publisher)
    assert publisher.last(AVAILABILITY) == "online"
    worker.device.close()


async def test_unreachable_heat_pump_goes_offline(publisher: FakePublisher) -> None:
    sim = SimulatedHeatPump()
    await sim.start()
    port = sim.port
    await sim.stop()
    clock = Clock()
    settings = make_settings(
        heatpumps=[
            {
                "id": "primary",
                "name": "P",
                "host": "127.0.0.1",
                "port": port,
                "timeout": 0.5,
                "offline_after": 5,
            }
        ]
    )
    worker = _worker(settings, clock)
    clock.now += 6
    assert not await worker.poll_once(publisher)
    assert publisher.last(AVAILABILITY) == "offline"


async def test_commands_rejected_while_writes_disabled(
    simulator: SimulatedHeatPump, publisher: FakePublisher
) -> None:
    worker = _worker(_settings(simulator))
    await worker.handle_command(publisher, "room_setpoint", "22")
    assert publisher.last(RESULT.format("room_setpoint")) == "error: writes are disabled"
    assert simulator.writes == []
    worker.device.close()


async def test_command_writes_reads_back_and_reports(
    simulator: SimulatedHeatPump, publisher: FakePublisher
) -> None:
    worker = _worker(_fast_writes(_settings(simulator)))
    await worker.handle_command(publisher, "room_setpoint", "22.5")
    assert simulator.writes == [(101, [225])]
    assert publisher.last(STATE + "room_setpoint") == "22.5"
    assert publisher.last(RESULT.format("room_setpoint")) == "ok"
    assert ("heliotherm/primary/command/room_setpoint/result", "ok", False) in publisher.messages

    await worker.handle_command(publisher, "operating_mode", "summer")
    assert simulator.get(Table.HOLDING, 100) == [3]
    assert publisher.last(STATE + "operating_mode") == "summer"
    worker.device.close()


async def test_invalid_commands_are_rejected(
    simulator: SimulatedHeatPump, publisher: FakePublisher
) -> None:
    worker = _worker(_fast_writes(_settings(simulator)))
    await worker.handle_command(publisher, "room_setpoint", "40")
    assert (publisher.last(RESULT.format("room_setpoint")) or "").startswith("error: 40 is above")
    await worker.handle_command(publisher, "outdoor_temperature", "1")
    assert publisher.last(RESULT.format("outdoor_temperature")) == "error: point is not writable"
    await worker.handle_command(publisher, "nonsense", "1")
    assert publisher.last(RESULT.format("nonsense")) == "error: unknown point"
    assert simulator.writes == []
    worker.device.close()


async def test_writes_are_paced(simulator: SimulatedHeatPump, publisher: FakePublisher) -> None:
    worker = _worker(_fast_writes(_settings(simulator)), clock=None)
    worker._clock = asyncio.get_running_loop().time
    loop = asyncio.get_running_loop()
    started = loop.time()
    await asyncio.gather(
        worker.handle_command(publisher, "room_setpoint", "20"),
        worker.handle_command(publisher, "dhw_setpoint", "48"),
        worker.handle_command(publisher, "operating_mode", "auto"),
    )
    assert len(simulator.writes) == 3
    assert loop.time() - started >= 0.4
    worker.device.close()


async def test_bridge_routes_commands_and_ignores_retained(
    simulator: SimulatedHeatPump, publisher: FakePublisher
) -> None:
    bridge = Bridge(_fast_writes(_settings(simulator)), device_factory=_device)
    topic = "heliotherm/primary/command/dhw_setpoint"
    await bridge.handle_message(publisher, topic, "51", retained=True)
    await bridge.handle_message(publisher, "heliotherm/other/command/dhw_setpoint", "51", False)
    await bridge.handle_message(publisher, topic + "/result", "ok", retained=False)
    await bridge.handle_message(publisher, topic, "", retained=False)
    await asyncio.sleep(0.1)
    assert simulator.writes == []
    assert publisher.messages == []

    await bridge.handle_message(publisher, topic, "51", retained=False)
    for _ in range(50):
        if publisher.last(RESULT.format("dhw_setpoint")):
            break
        await asyncio.sleep(0.02)
    assert simulator.writes == [(105, [510])]
    for worker in bridge.workers:
        worker.device.close()


async def test_bridge_connect_and_shutdown_messages(
    simulator: SimulatedHeatPump, publisher: FakePublisher
) -> None:
    settings = _settings(simulator, homeassistant={"discovery": True})
    bridge = Bridge(settings, device_factory=_device)
    await bridge.workers[0].poll_once(publisher)
    publisher.clear()

    await bridge.on_connect(publisher)
    topics = publisher.topics()
    assert topics[0] == "homeassistant/binary_sensor/heliotherm_bridge/connection/config"
    assert topics.index("heliotherm/bridge/status") > topics.index(
        "homeassistant/sensor/heliotherm_primary/outdoor_temperature/config"
    )
    assert "homeassistant/sensor/heliotherm_primary/outdoor_temperature/config" in topics
    assert publisher.last(STATE + "outdoor_temperature") == "4.5"

    publisher.clear()
    await bridge.handle_message(publisher, "homeassistant/status", "online", retained=False)
    await asyncio.sleep(0.1)
    assert (
        "homeassistant/sensor/heliotherm_primary/outdoor_temperature/config" in publisher.topics()
    )

    publisher.clear()
    await bridge.shutdown(publisher)
    assert publisher.messages == [
        (AVAILABILITY, "offline", True),
        ("heliotherm/bridge/status", "offline", True),
    ]
    for worker in bridge.workers:
        worker.device.close()


async def test_mqtt_publisher_honours_retain_toggle() -> None:
    calls: list[tuple[str, str, int, bool]] = []

    class Client:
        async def publish(self, topic: str, payload: str, qos: int, retain: bool) -> None:
            calls.append((topic, payload, qos, retain))

    await MqttPublisher(Client(), retain=False).publish("t", "v")  # type: ignore[arg-type]
    await MqttPublisher(Client(), retain=True).publish("t", "v")  # type: ignore[arg-type]
    await MqttPublisher(Client(), retain=True).publish("t", "v", retain=False)  # type: ignore[arg-type]
    assert [c[3] for c in calls] == [False, True, False]


def _device(pump: Any) -> ModbusDevice:
    return ModbusDevice(pump.host, pump.port, pump.unit_id, pump.timeout)


async def test_without_retain_state_waits_for_discovery(
    simulator: SimulatedHeatPump, publisher: FakePublisher, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bridge_module, "DISCOVERY_SETTLE", 0.2)
    settings = _settings(
        simulator, mqtt={"host": "m", "retain": False}, homeassistant={"discovery": True}
    )
    bridge = Bridge(settings, device_factory=_device)
    loop = asyncio.get_running_loop()
    started = loop.time()
    await bridge.on_connect(publisher)
    assert loop.time() - started >= 0.2
    assert publisher.topics()[-1] == "heliotherm/bridge/status"
    for worker in bridge.workers:
        worker.device.close()


async def test_full_republish_includes_availability(
    simulator: SimulatedHeatPump, publisher: FakePublisher
) -> None:
    clock = Clock()
    worker = _worker(_settings(simulator), clock)
    await worker.poll_once(publisher)
    publisher.clear()
    clock.now += 10
    await worker.poll_once(publisher)
    assert AVAILABILITY not in publisher.topics()
    clock.now += 300
    await worker.poll_once(publisher)
    assert publisher.topics()[-1] == AVAILABILITY
    worker.device.close()
