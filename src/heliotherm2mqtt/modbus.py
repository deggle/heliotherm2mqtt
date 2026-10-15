"""Modbus TCP access to one heat pump."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from typing import Protocol

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

from .points import Table

log = logging.getLogger(__name__)


class DeviceError(Exception):
    """A read or write failed."""


class Device(Protocol):
    async def read(self, table: Table, address: int, count: int) -> list[int]: ...

    async def write(self, address: int, values: Sequence[int]) -> None: ...

    def close(self) -> None: ...


class ModbusDevice:
    """One Modbus TCP connection, reconnected on demand, one request at a time."""

    def __init__(self, host: str, port: int, unit_id: int, timeout: float) -> None:
        self._unit_id = unit_id
        self._label = f"{host}:{port}"
        # reconnect_delay=0 disables pymodbus's background reconnect; we reconnect on demand.
        self._client = AsyncModbusTcpClient(
            host, port=port, timeout=timeout, retries=0, reconnect_delay=0
        )
        self._lock = asyncio.Lock()

    async def _ensure_connected(self) -> None:
        if self._client.connected:
            return
        if not await self._client.connect():
            raise DeviceError(f"cannot connect to {self._label}")
        log.info("Connected to %s", self._label)

    async def read(self, table: Table, address: int, count: int) -> list[int]:
        async with self._lock:
            await self._ensure_connected()
            reader = (
                self._client.read_input_registers
                if table is Table.INPUT
                else self._client.read_holding_registers
            )
            try:
                response = await reader(address, count=count, device_id=self._unit_id)
            except (ModbusException, OSError, TimeoutError) as exc:
                self._client.close()
                raise DeviceError(f"reading {table} {address}+{count}: {exc}") from exc
            if response.isError():
                raise DeviceError(f"reading {table} {address}+{count}: {response}")
            return list(response.registers)

    async def write(self, address: int, values: Sequence[int]) -> None:
        async with self._lock:
            await self._ensure_connected()
            try:
                if len(values) == 1:
                    response = await self._client.write_register(
                        address, values[0], device_id=self._unit_id
                    )
                else:
                    response = await self._client.write_registers(
                        address, list(values), device_id=self._unit_id
                    )
            except (ModbusException, OSError, TimeoutError) as exc:
                self._client.close()
                raise DeviceError(f"writing {address}: {exc}") from exc
            if response.isError():
                raise DeviceError(f"writing {address}: {response}")

    def close(self) -> None:
        self._client.close()
