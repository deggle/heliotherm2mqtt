"""Poll heat pumps, publish their state and apply commands. See docs/interface.md."""

from __future__ import annotations

import asyncio
import contextlib
import functools
import logging
import math
import ssl
import time
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any, Protocol

import aiomqtt

from . import discovery
from .codec import decode, encode
from .config import HeatPumpSettings, Settings
from .modbus import Device, DeviceError, ModbusDevice
from .points import POINTS, Point, Table, read_blocks
from .topics import Topics, bridge_status, command_filters

log = logging.getLogger(__name__)

ONLINE = "online"
OFFLINE = "offline"
# Time for Home Assistant to process discovery and subscribe before non-retained state follows.
DISCOVERY_SETTLE = 2.0


class Publisher(Protocol):
    async def publish(self, topic: str, payload: str, *, retain: bool = True) -> None: ...


class NullPublisher:
    """Discards messages; used for the first poll before MQTT is connected."""

    async def publish(self, topic: str, payload: str, *, retain: bool = True) -> None:
        pass


class MqttPublisher:
    """Publishes through aiomqtt, with retain switched off globally when configured."""

    def __init__(self, client: aiomqtt.Client, retain: bool) -> None:
        self._client = client
        self._retain = retain

    async def publish(self, topic: str, payload: str, *, retain: bool = True) -> None:
        await self._client.publish(topic, payload, qos=1, retain=retain and self._retain)


class CommandError(Exception):
    pass


class HeatPumpWorker:
    """Polls one heat pump and applies commands to it."""

    def __init__(
        self,
        settings: Settings,
        pump: HeatPumpSettings,
        device: Device,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.settings = settings
        self.pump = pump
        self.device = device
        self.topics = Topics(settings, pump)
        self.points = pump.points()
        self._by_key = {p.key: p for p in self.points}
        self._blocks = read_blocks(POINTS)
        self._clock = clock
        self._published: dict[str, str] = {}
        self._available: bool | None = None
        self._last_success: float | None = None
        self._started = clock()
        self._last_full = -math.inf
        self._write_lock = asyncio.Lock()
        self._last_write = -math.inf
        # Points whose sensor reported "not fitted" in the latest poll.
        self.absent: frozenset[str] = frozenset()
        self.on_absent_changed: Callable[[Publisher], Awaitable[None]] | None = None

    async def run(self, pub: Publisher) -> None:
        while True:
            started = self._clock()
            await self.poll_once(pub)
            elapsed = self._clock() - started
            await asyncio.sleep(max(0.0, self.pump.poll_interval - elapsed))

    async def poll_once(self, pub: Publisher) -> bool:
        """Read every register block and publish what changed. Returns True on success."""
        try:
            image: dict[tuple[Table, int], int] = {}
            for block in self._blocks:
                regs = await self.device.read(block.table, block.address, block.count)
                for offset, value in enumerate(regs):
                    image[(block.table, block.address + offset)] = value
        except DeviceError as exc:
            log.warning("%s: poll failed: %s", self.pump.id, exc)
            await self._check_offline(pub)
            return False

        now = self._clock()
        self._last_success = now
        full = now - self._last_full >= self.settings.republish_interval
        if full:
            self._last_full = now
        absent = set()
        for point in self.points:
            regs = [image[(point.table, point.address + i)] for i in range(point.count)]
            payload = decode(point, regs)
            if payload is None:
                absent.add(point.key)
                self._published.pop(point.key, None)
            else:
                await self._publish_state(pub, point, payload, force=full)
        await self._set_available(pub, True, force=full)
        if absent != self.absent:
            log.info(
                "%s: sensors not fitted: %s", self.pump.id, ", ".join(sorted(absent)) or "none"
            )
            self.absent = frozenset(absent)
            if self.on_absent_changed is not None:
                await self.on_absent_changed(pub)
        return True

    async def republish(self, pub: Publisher) -> None:
        """Publish availability and every known value again, e.g. after reconnecting."""
        if self._available is not None:
            await pub.publish(self.topics.availability, ONLINE if self._available else OFFLINE)
        for key, payload in list(self._published.items()):
            await pub.publish(self.topics.state(key), payload)

    async def mark_offline(self, pub: Publisher) -> None:
        self._available = False
        await pub.publish(self.topics.availability, OFFLINE)

    async def handle_command(self, pub: Publisher, key: str, payload: str) -> None:
        try:
            point = self._check_command(key)
            registers = encode(point, payload)
            async with self._write_lock:
                wait = self._last_write + self.settings.writes.min_interval - self._clock()
                if wait > 0:
                    log.debug("%s: pacing write to %s by %.1fs", self.pump.id, key, wait)
                    await asyncio.sleep(wait)
                log.info("%s: writing %s = %s %s", self.pump.id, key, payload, registers)
                try:
                    await self.device.write(point.address, registers)
                finally:
                    self._last_write = self._clock()
            readback = await self.device.read(point.table, point.address, point.count)
            if (state := decode(point, readback)) is not None:
                await self._publish_state(pub, point, state, force=True)
        except (CommandError, ValueError, DeviceError) as exc:
            log.warning("%s: command %s=%r rejected: %s", self.pump.id, key, payload, exc)
            await pub.publish(self.topics.result(key), f"error: {exc}", retain=False)
        else:
            await pub.publish(self.topics.result(key), "ok", retain=False)

    def _check_command(self, key: str) -> Point:
        if not self.settings.writes.enabled:
            raise CommandError("writes are disabled")
        point = self._by_key.get(key)
        if point is None:
            raise CommandError("unknown point")
        if not point.writable:
            raise CommandError("point is not writable")
        return point

    async def _publish_state(self, pub: Publisher, point: Point, payload: str, force: bool) -> None:
        if force or self._published.get(point.key) != payload:
            self._published[point.key] = payload
            await pub.publish(self.topics.state(point.key), payload)

    async def _check_offline(self, pub: Publisher) -> None:
        since = self._last_success if self._last_success is not None else self._started
        if self._clock() - since >= self.pump.offline_after:
            await self._set_available(pub, False)

    async def _set_available(self, pub: Publisher, available: bool, force: bool = False) -> None:
        if self._available is not available:
            log.info("%s: %s", self.pump.id, ONLINE if available else OFFLINE)
        elif not force:
            return
        self._available = available
        await pub.publish(self.topics.availability, ONLINE if available else OFFLINE)


DeviceFactory = Callable[[HeatPumpSettings], Device]


def modbus_device(pump: HeatPumpSettings) -> Device:
    return ModbusDevice(pump.host, pump.port, pump.unit_id, pump.timeout)


class Bridge:
    def __init__(self, settings: Settings, device_factory: DeviceFactory = modbus_device) -> None:
        self.settings = settings
        self.workers = [HeatPumpWorker(settings, p, device_factory(p)) for p in settings.heatpumps]
        self._by_base = {w.topics.base: w for w in self.workers}
        for worker in self.workers:
            worker.on_absent_changed = functools.partial(self._publish_pump_discovery, worker)
        self._ha_status = f"{settings.homeassistant.discovery_prefix}/status"
        self._tasks: set[asyncio.Task[None]] = set()

    async def on_connect(self, pub: Publisher) -> None:
        await self.publish_discovery(pub)
        if self.settings.homeassistant.discovery and not self.settings.mqtt.retain:
            # Without retain, HA only sees status and state published after it has subscribed.
            await asyncio.sleep(DISCOVERY_SETTLE)
        await pub.publish(bridge_status(self.settings), ONLINE)
        for worker in self.workers:
            await worker.republish(pub)

    async def publish_discovery(self, pub: Publisher) -> None:
        if not self.settings.homeassistant.discovery:
            return
        await pub.publish(*discovery.bridge_message(self.settings))
        for worker in self.workers:
            await self._publish_pump_discovery(worker, pub)

    async def _publish_pump_discovery(self, worker: HeatPumpWorker, pub: Publisher) -> None:
        if not self.settings.homeassistant.discovery:
            return
        for topic, payload in discovery.messages(self.settings, worker.pump, worker.absent):
            await pub.publish(topic, payload)

    async def handle_message(
        self, pub: Publisher, topic: str, payload: str, retained: bool
    ) -> None:
        if topic == self._ha_status:
            if payload == ONLINE and self.settings.homeassistant.discovery:
                log.info("Home Assistant is online; republishing discovery and state")
                self._spawn(self.on_connect(pub))
            return
        base, sep, key = topic.rpartition("/command/")
        worker = self._by_base.get(base)
        if not sep or worker is None or not key or "/" in key:
            return
        if not payload:  # clearing a retained command topic, not a command
            return
        if retained:
            log.warning("Ignoring retained command on %s", topic)
            return
        self._spawn(worker.handle_command(pub, key, payload))

    def _spawn(self, coro: Coroutine[Any, Any, None]) -> None:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def shutdown(self, pub: Publisher) -> None:
        for worker in self.workers:
            await worker.mark_offline(pub)
        await pub.publish(bridge_status(self.settings), OFFLINE)

    def _client(self) -> aiomqtt.Client:
        mqtt = self.settings.mqtt
        return aiomqtt.Client(
            mqtt.host,
            port=mqtt.port,
            username=mqtt.username,
            password=mqtt.password.get_secret_value() if mqtt.password else None,
            identifier=mqtt.client_id,
            keepalive=mqtt.keepalive,
            tls_context=ssl.create_default_context() if mqtt.tls else None,
            will=aiomqtt.Will(bridge_status(self.settings), OFFLINE, qos=1, retain=mqtt.retain),
        )

    async def run(self, stop: asyncio.Event) -> None:
        """Run until `stop` is set, reconnecting to the broker as needed."""
        backoff = 1.0
        # One poll before connecting, so discovery already knows which sensors are fitted.
        await asyncio.gather(*(w.poll_once(NullPublisher()) for w in self.workers))
        try:
            while not stop.is_set():
                try:
                    await self._session(stop)
                    backoff = 1.0
                except aiomqtt.MqttError as exc:
                    log.warning("MQTT connection lost: %s; retrying in %.0fs", exc, backoff)
                    with contextlib.suppress(TimeoutError):
                        await asyncio.wait_for(stop.wait(), backoff)
                    backoff = min(backoff * 2, 60.0)
        finally:
            for worker in self.workers:
                worker.device.close()

    async def _session(self, stop: asyncio.Event) -> None:
        async with self._client() as client:
            log.info(
                "Connected to MQTT broker %s:%s", self.settings.mqtt.host, self.settings.mqtt.port
            )
            pub = MqttPublisher(client, self.settings.mqtt.retain)
            for topic_filter in sorted(command_filters(self.settings)):
                await client.subscribe(topic_filter, qos=1)
            if self.settings.homeassistant.discovery:
                await client.subscribe(self._ha_status, qos=1)
            await self.on_connect(pub)

            async def listen() -> None:
                async for message in client.messages:
                    raw = message.payload
                    text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw)
                    await self.handle_message(pub, str(message.topic), text, message.retain)

            async def heartbeat() -> None:
                while True:
                    await asyncio.sleep(self.settings.republish_interval)
                    await pub.publish(bridge_status(self.settings), ONLINE)

            tasks = [asyncio.create_task(w.run(pub)) for w in self.workers]
            tasks.append(asyncio.create_task(listen()))
            tasks.append(asyncio.create_task(heartbeat()))
            stopper = asyncio.create_task(stop.wait())
            try:
                done, _ = await asyncio.wait([*tasks, stopper], return_when=asyncio.FIRST_COMPLETED)
            finally:
                for task in [*tasks, *self._tasks, stopper]:
                    task.cancel()
                await asyncio.gather(*tasks, *self._tasks, stopper, return_exceptions=True)
            if stop.is_set():
                log.info("Shutting down")
                await self.shutdown(pub)
                return
            for task in done:
                if task is not stopper and (exc := task.exception()) is not None:
                    raise exc
