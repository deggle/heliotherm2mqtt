"""A fake Heliotherm Remote Control Gateway, for tests and trying the bridge without hardware.

Implements just enough Modbus TCP: function codes 3, 4, 6 and 16.

Run it with: python -m heliotherm2mqtt.simulator --port 5020
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import dataclasses
import logging
import struct

from .codec import encode
from .points import POINTS_BY_KEY, Table

log = logging.getLogger(__name__)

_ILLEGAL_FUNCTION = 0x01
_ILLEGAL_ADDRESS = 0x02
_GATEWAY_TARGET_FAILED = 0x0B

DEFAULT_VALUES = {
    "outdoor_temperature": "4.5",
    "dhw_temperature": "48.2",
    "flow_temperature": "35.1",
    "return_temperature": "30.4",
    "buffer_temperature": "33.0",
    "source_inlet_temperature": "6.0",
    "source_outlet_temperature": "2.5",
    "low_pressure": "6.8",
    "high_pressure": "17.2",
    "heating_circuit_pump": "ON",
    "compressor": "ON",
    "flow_rate": "18.5",
    "compressor_speed": "420",
    "cop": "4.1",
    "fresh_water_temperature": "-50.0",
    "utility_release": "ON",
    "return_setpoint": "30.0",
    "heat_pump_request": "20",
    "dhw_operating_hours": "2100",
    "heating_operating_hours": "9800",
    "room_temperature": "20.8",
    "heating_heat_energy": "45000",
    "heating_electrical_energy": "11000",
    "total_electrical_energy": "13500",
    "electrical_power": "1450",
    "total_heat_energy": "54000",
    "heat_output": "5.9",
    "operating_mode": "auto",
    "room_setpoint": "21.0",
    "dhw_setpoint": "50.0",
}


class SimulatedHeatPump:
    def __init__(self, unit_id: int = 1, *, defaults: bool = True) -> None:
        self.unit_id = unit_id
        self.registers: dict[Table, dict[int, int]] = {Table.INPUT: {}, Table.HOLDING: {}}
        self.writes: list[tuple[int, list[int]]] = []
        self.online = True
        self._server: asyncio.Server | None = None
        self._connections: set[asyncio.StreamWriter] = set()
        if defaults:
            for key, value in DEFAULT_VALUES.items():
                self.set(key, value)

    def set(self, key: str, payload: str) -> None:
        """Set a point using its MQTT payload form, bypassing the point's range checks."""
        point = POINTS_BY_KEY[key]
        unchecked = dataclasses.replace(point, minimum=None, maximum=None)
        for offset, value in enumerate(encode(unchecked, payload)):
            self.registers[point.table][point.address + offset] = value

    def get(self, table: Table, address: int, count: int = 1) -> list[int]:
        regs = self.registers[table]
        return [regs.get(address + i, 0) for i in range(count)]

    @property
    def port(self) -> int:
        assert self._server is not None
        port: int = self._server.sockets[0].getsockname()[1]
        return port

    async def start(self, host: str = "127.0.0.1", port: int = 0) -> None:
        self._server = await asyncio.start_server(self._handle, host, port)

    async def stop(self) -> None:
        self.drop_connections()
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

    def drop_connections(self) -> None:
        for writer in list(self._connections):
            writer.close()

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self._connections.add(writer)
        try:
            while True:
                header = await reader.readexactly(7)
                tid, pid, length, unit = struct.unpack(">HHHB", header)
                pdu = await reader.readexactly(length - 1)
                if not self.online:
                    break
                reply = self._respond(unit, pdu)
                writer.write(struct.pack(">HHHB", tid, pid, len(reply) + 1, unit) + reply)
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            self._connections.discard(writer)
            writer.close()
            with contextlib.suppress(ConnectionError):
                await writer.wait_closed()

    def _respond(self, unit: int, pdu: bytes) -> bytes:
        fc = pdu[0]
        if unit != self.unit_id:
            return bytes([fc | 0x80, _GATEWAY_TARGET_FAILED])
        if fc in (3, 4):
            address, count = struct.unpack(">HH", pdu[1:5])
            if not 1 <= count <= 125:
                return bytes([fc | 0x80, _ILLEGAL_ADDRESS])
            table = Table.HOLDING if fc == 3 else Table.INPUT
            values = self.get(table, address, count)
            return bytes([fc, 2 * count]) + struct.pack(f">{count}H", *values)
        if fc == 6:
            address, value = struct.unpack(">HH", pdu[1:5])
            self._write(address, [value])
            return pdu[:5]
        if fc == 16:
            address, count, _ = struct.unpack(">HHB", pdu[1:6])
            values = list(struct.unpack(f">{count}H", pdu[6 : 6 + 2 * count]))
            self._write(address, values)
            return pdu[:5]
        return bytes([fc | 0x80, _ILLEGAL_FUNCTION])

    def _write(self, address: int, values: list[int]) -> None:
        log.info("Write %s = %s", address, values)
        self.writes.append((address, values))
        for offset, value in enumerate(values):
            self.registers[Table.HOLDING][address + offset] = value


async def _main(host: str, port: int, unit_id: int) -> None:
    sim = SimulatedHeatPump(unit_id)
    await sim.start(host, port)
    log.info("Simulated heat pump listening on %s:%s (unit %s)", host, sim.port, unit_id)
    try:
        await asyncio.Event().wait()
    finally:
        await sim.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5020)
    parser.add_argument("--unit-id", type=int, default=1)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(_main(args.host, args.port, args.unit_id))


if __name__ == "__main__":
    main()
