"""The Heliotherm Remote Control Gateway register map.

Each `Point` is one value exposed over MQTT. Addresses are zero-based, as in the
manufacturer's tables. See docs/points.md and docs/decisions/0002-built-in-point-map.md.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any


class Table(StrEnum):
    INPUT = "input"
    HOLDING = "holding"


class DataType(StrEnum):
    INT16 = "int16"
    UINT16 = "uint16"
    INT32 = "int32"
    UINT32 = "uint32"

    @property
    def registers(self) -> int:
        return 2 if self in (DataType.INT32, DataType.UINT32) else 1

    @property
    def signed(self) -> bool:
        return self in (DataType.INT16, DataType.INT32)


class Kind(StrEnum):
    NUMBER = "number"
    BOOLEAN = "boolean"
    ENUM = "enum"


@dataclass(frozen=True, slots=True)
class Point:
    key: str
    name: str
    table: Table
    address: int
    dtype: DataType = DataType.INT16
    kind: Kind = Kind.NUMBER
    scale: float = 1
    unit: str | None = None
    device_class: str | None = None
    state_class: str | None = None
    icon: str | None = None
    # Home Assistant entity category: None (primary), "diagnostic" or "config".
    category: str | None = None
    enabled_by_default: bool = True
    options: Mapping[int, str] | None = None
    writable: bool = False
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    # Raw register values that mean "sensor not fitted"; such readings are not published.
    absent: frozenset[int] = frozenset()

    @property
    def count(self) -> int:
        return self.dtype.registers

    @property
    def decimals(self) -> int:
        return 1 if self.scale < 1 else 0


def _options(*labels: tuple[int, str]) -> Mapping[int, str]:
    return MappingProxyType(dict(labels))


OPERATING_MODES = _options(
    (0, "off"),
    (1, "auto"),
    (2, "cool"),
    (3, "summer"),
    (4, "continuous"),
    (5, "decrease"),
    (6, "holiday"),
    (7, "party"),
)

HEAT_PUMP_REQUESTS = _options(
    (0, "none"),
    (10, "cool"),
    (20, "heat"),
    (30, "dhw"),
    (40, "external"),
)

# -50.0 °C (seen by ha_heliotherm) and -100.0 °C (seen on RCG X units).
SENSOR_NOT_FITTED = frozenset({-500, -1000})


def _temp(key: str, name: str, table: Table, address: int, **kw: Any) -> Point:
    kw.setdefault("state_class", "measurement")
    if table is Table.INPUT:
        kw.setdefault("absent", SENSOR_NOT_FITTED)
    return Point(
        key,
        name,
        table,
        address,
        scale=0.1,
        unit="°C",
        device_class="temperature",
        **kw,
    )


def _setpoint(key: str, name: str, address: int, **kw: Any) -> Point:
    kw.setdefault("category", "config")
    kw.setdefault("state_class", None)
    return _temp(key, name, Table.HOLDING, address, **kw)


def _offset(key: str, name: str, address: int, **kw: Any) -> Point:
    return Point(
        key,
        name,
        Table.HOLDING,
        address,
        dtype=DataType.UINT16,
        scale=0.1,
        unit="K",
        category="config",
        enabled_by_default=False,
        **kw,
    )


def _flag(key: str, name: str, table: Table, address: int, **kw: Any) -> Point:
    if table is Table.HOLDING:
        kw.setdefault("dtype", DataType.UINT16)
        kw.setdefault("category", "config")
    return Point(key, name, table, address, kind=Kind.BOOLEAN, **kw)


def _energy(key: str, name: str, address: int, **kw: Any) -> Point:
    return Point(
        key,
        name,
        Table.INPUT,
        address,
        dtype=DataType.UINT32,
        unit="kWh",
        device_class="energy",
        state_class="total_increasing",
        **kw,
    )


IN = Table.INPUT
HO = Table.HOLDING
_DIAG: dict[str, Any] = {"category": "diagnostic"}
_HIDDEN: dict[str, Any] = {"category": "diagnostic", "enabled_by_default": False}
# Return temperature points of the heating curve (registers 136-138).
_CURVE: dict[str, Any] = {
    "writable": True,
    "minimum": 15,
    "maximum": 55,
    "step": 0.1,
    "icon": "mdi:chart-bell-curve-cumulative",
}
_MODE: dict[str, Any] = {
    "dtype": DataType.UINT16,
    "kind": Kind.ENUM,
    "options": OPERATING_MODES,
    "category": "config",
    "icon": "mdi:cog",
}

POINTS: tuple[Point, ...] = (
    # Input registers (function code 4), read only.
    _temp("outdoor_temperature", "Outdoor temperature", IN, 10),
    _temp("dhw_temperature", "DHW temperature", IN, 11, icon="mdi:water-boiler"),
    _temp("flow_temperature", "Flow temperature", IN, 12, icon="mdi:radiator"),
    _temp("return_temperature", "Return temperature", IN, 13, icon="mdi:radiator"),
    _temp("buffer_temperature", "Buffer temperature", IN, 14),
    _temp("source_inlet_temperature", "Source inlet temperature", IN, 15, **_DIAG),
    _temp("source_outlet_temperature", "Source outlet temperature", IN, 16, **_DIAG),
    _temp("suction_line_temperature", "Suction line temperature", IN, 17, **_DIAG),
    _temp("evaporating_temperature", "Evaporating temperature", IN, 18, **_DIAG),
    _temp("condensing_temperature", "Condensing temperature", IN, 19, **_DIAG),
    _temp("discharge_temperature", "Discharge temperature", IN, 20, **_DIAG),
    Point(
        "low_pressure",
        "Low pressure",
        IN,
        21,
        scale=0.1,
        unit="bar",
        device_class="pressure",
        state_class="measurement",
        **_DIAG,
    ),
    Point(
        "high_pressure",
        "High pressure",
        IN,
        22,
        scale=0.1,
        unit="bar",
        device_class="pressure",
        state_class="measurement",
        **_DIAG,
    ),
    _flag("heating_circuit_pump", "Heating circuit pump", IN, 23, device_class="running"),
    _flag("buffer_charging_pump", "Buffer charging pump", IN, 24, device_class="running"),
    _flag("compressor", "Compressor", IN, 25, device_class="running"),
    _flag("fault", "Fault", IN, 26, device_class="problem"),
    _flag("four_way_valve", "Four-way valve (defrost or reversing)", IN, 27, **_DIAG),
    Point(
        "flow_rate",
        "Flow rate",
        IN,
        28,
        scale=0.1,
        unit="L/min",
        device_class="volume_flow_rate",
        state_class="measurement",
    ),
    Point(
        "compressor_speed",
        "Compressor speed",
        IN,
        29,
        unit="‰",
        state_class="measurement",
        icon="mdi:speedometer",
    ),
    Point("cop", "COP", IN, 30, scale=0.1, state_class="measurement", icon="mdi:gauge"),
    _temp("fresh_water_temperature", "Fresh water temperature", IN, 31, **_HIDDEN),
    _flag("utility_release", "Utility (EVU) release", IN, 32, **_DIAG),
    _temp("outdoor_temperature_delayed", "Outdoor temperature (delayed)", IN, 33, **_DIAG),
    _temp("return_setpoint", "Return setpoint", IN, 34, state_class=None),
    _temp("mc1_flow_setpoint", "MC1 flow setpoint", IN, 35, state_class=None, **_HIDDEN),
    _temp("mc2_flow_setpoint", "MC2 flow setpoint", IN, 36, state_class=None, **_HIDDEN),
    _flag("source_pump", "Source pump or fan", IN, 37, device_class="running", **_DIAG),
    _flag("dhw_priority", "DHW priority", IN, 38),
    _flag("passive_cooling_valve", "Passive cooling valve", IN, 39, **_DIAG),
    Point(
        "expansion_valve", "Expansion valve", IN, 40, unit="‰", state_class="measurement", **_DIAG
    ),
    Point(
        "heat_pump_request",
        "Heat pump request",
        IN,
        41,
        kind=Kind.ENUM,
        options=HEAT_PUMP_REQUESTS,
        icon="mdi:fire",
    ),
    Point(
        "dhw_operating_hours",
        "DHW operating hours",
        IN,
        42,
        dtype=DataType.UINT32,
        unit="h",
        device_class="duration",
        state_class="total_increasing",
        **_DIAG,
    ),
    Point(
        "heating_operating_hours",
        "Heating operating hours",
        IN,
        44,
        dtype=DataType.UINT32,
        unit="h",
        device_class="duration",
        state_class="total_increasing",
        **_DIAG,
    ),
    _temp("mc1_flow_temperature", "MC1 flow temperature", IN, 46, **_HIDDEN),
    _temp("mc1_return_temperature", "MC1 return temperature", IN, 47, **_HIDDEN),
    _temp("mc2_flow_temperature", "MC2 flow temperature", IN, 48, **_HIDDEN),
    _temp("mc2_return_temperature", "MC2 return temperature", IN, 49, **_HIDDEN),
    _temp("room_temperature", "Room temperature", IN, 50, icon="mdi:home-thermometer"),
    _energy("heating_heat_energy", "Heating heat energy", 60),
    _energy("heating_electrical_energy", "Heating electrical energy", 62),
    _energy("dhw_heat_energy", "DHW heat energy", 64),
    _energy("dhw_electrical_energy", "DHW electrical energy", 66),
    _energy("total_electrical_energy", "Total electrical energy", 68),
    Point(
        "electrical_power",
        "Electrical power",
        IN,
        70,
        dtype=DataType.UINT32,
        unit="W",
        device_class="power",
        state_class="measurement",
    ),
    _energy("total_heat_energy", "Total heat energy", 72),
    Point(
        "heat_output",
        "Heat output",
        IN,
        74,
        dtype=DataType.UINT32,
        scale=0.1,
        unit="kW",
        device_class="power",
        state_class="measurement",
    ),
    # Holding registers (function codes 3, 6 and 16), read and write.
    Point(
        "operating_mode", "Operating mode", HO, 100, writable=True, **{**_MODE, "category": None}
    ),
    _setpoint(
        "room_setpoint",
        "Room setpoint",
        101,
        writable=True,
        minimum=10,
        maximum=25,
        step=0.5,
    ),
    _setpoint(
        "return_setpoint_value",
        "Return/buffer target override",
        102,
        writable=True,
        minimum=5,
        maximum=65,
        step=0.5,
        category=None,
        icon="mdi:thermometer-chevron-up",
    ),
    _flag(
        "return_setpoint_active",
        "Return/buffer target override active",
        HO,
        103,
        writable=True,
        category=None,
        icon="mdi:thermometer-chevron-up",
    ),
    _setpoint(
        "cooling_return_minimum",
        "Cooling return minimum",
        104,
        category="diagnostic",
        enabled_by_default=False,
    ),
    _setpoint(
        "dhw_setpoint",
        "DHW setpoint",
        105,
        writable=True,
        minimum=5,
        maximum=65,
        step=0.5,
        icon="mdi:water-boiler",
    ),
    Point(
        "mc1_operating_mode",
        "MC1 operating mode",
        HO,
        107,
        writable=True,
        enabled_by_default=False,
        **_MODE,
    ),
    _setpoint("mc1_room_setpoint", "MC1 room setpoint", 108, enabled_by_default=False),
    _setpoint(
        "mc1_flow_setpoint_value", "MC1 flow setpoint override", 109, enabled_by_default=False
    ),
    _flag(
        "mc1_flow_setpoint_active",
        "MC1 flow setpoint override active",
        HO,
        110,
        enabled_by_default=False,
    ),
    _setpoint(
        "mc1_cooling_flow_minimum", "MC1 cooling flow minimum", 111, enabled_by_default=False
    ),
    Point(
        "mc2_operating_mode",
        "MC2 operating mode",
        HO,
        112,
        writable=True,
        enabled_by_default=False,
        **_MODE,
    ),
    _setpoint("mc2_room_setpoint", "MC2 room setpoint", 113, enabled_by_default=False),
    _setpoint(
        "mc2_flow_setpoint_value", "MC2 flow setpoint override", 114, enabled_by_default=False
    ),
    _flag(
        "mc2_flow_setpoint_active",
        "MC2 flow setpoint override active",
        HO,
        115,
        enabled_by_default=False,
    ),
    _setpoint(
        "mc2_cooling_flow_minimum", "MC2 cooling flow minimum", 116, enabled_by_default=False
    ),
    _flag("pv_request", "PV request", HO, 117, enabled_by_default=False),
    _offset("pv_heat_offset", "PV heating offset", 118),
    _offset("pv_cool_offset", "PV cooling offset", 119),
    _offset("mc1_pv_heat_offset", "MC1 PV heating offset", 120),
    _offset("mc1_pv_cool_offset", "MC1 PV cooling offset", 121),
    _offset("mc2_pv_heat_offset", "MC2 PV heating offset", 122),
    _offset("mc2_pv_cool_offset", "MC2 PV cooling offset", 123),
    _setpoint(
        "dhw_normal_maximum",
        "DHW normal maximum",
        124,
        dtype=DataType.UINT16,
        enabled_by_default=False,
    ),
    Point(
        "power_input_request",
        "Power input request",
        HO,
        125,
        dtype=DataType.UINT16,
        unit="W",
        device_class="power",
        category="config",
        enabled_by_default=False,
    ),
    Point(
        "compressor_speed_request",
        "Compressor speed request",
        HO,
        126,
        unit="‰",
        category="config",
        enabled_by_default=False,
    ),
    _flag("external_request", "External request", HO, 127, enabled_by_default=False),
    _flag("clear_error", "Clear error", HO, 128, enabled_by_default=False),
    _setpoint(
        "outdoor_temperature_value",
        "Outdoor temperature override",
        129,
        enabled_by_default=False,
        absent=SENSOR_NOT_FITTED,
    ),
    _flag(
        "outdoor_temperature_active",
        "Outdoor temperature override active",
        HO,
        130,
        enabled_by_default=False,
    ),
    _setpoint(
        "buffer_temperature_value",
        "Buffer temperature override",
        131,
        enabled_by_default=False,
        absent=SENSOR_NOT_FITTED,
    ),
    _flag(
        "buffer_temperature_active",
        "Buffer temperature override active",
        HO,
        132,
        enabled_by_default=False,
    ),
    _setpoint(
        "dhw_temperature_value",
        "DHW temperature override",
        133,
        enabled_by_default=False,
        absent=SENSOR_NOT_FITTED,
    ),
    _flag(
        "dhw_temperature_active",
        "DHW temperature override active",
        HO,
        134,
        enabled_by_default=False,
    ),
    _setpoint(
        "hc_heat_limit",
        "Heating curve outdoor limit",
        135,
        writable=True,
        minimum=10,
        maximum=30,
        step=1,
        icon="mdi:sun-thermometer",
    ),
    _setpoint("hc_return_at_heat_limit", "Heating curve at outdoor limit", 136, **_CURVE),
    _setpoint("hc_return_at_0c", "Heating curve at 0 °C", 137, **_CURVE),
    _setpoint("hc_return_at_minus_15c", "Heating curve at -15 °C", 138, **_CURVE),
    _setpoint("mc1_heat_limit", "MC1 heat limit", 139, enabled_by_default=False),
    _setpoint(
        "mc1_return_at_heat_limit", "MC1 return at heat limit", 140, enabled_by_default=False
    ),
    _setpoint("mc1_return_at_0c", "MC1 return at 0 °C", 141, enabled_by_default=False),
    _setpoint("mc1_return_at_minus_15c", "MC1 return at -15 °C", 142, enabled_by_default=False),
    _setpoint("mc2_heat_limit", "MC2 heat limit", 143, enabled_by_default=False),
    _setpoint(
        "mc2_return_at_heat_limit", "MC2 return at heat limit", 144, enabled_by_default=False
    ),
    _setpoint("mc2_return_at_0c", "MC2 return at 0 °C", 145, enabled_by_default=False),
    _setpoint("mc2_return_at_minus_15c", "MC2 return at -15 °C", 146, enabled_by_default=False),
    _flag(
        "second_stage_hand_value",
        "Second stage override",
        HO,
        147,
        dtype=DataType.INT16,
        enabled_by_default=False,
    ),
    _flag(
        "second_stage_hand_active",
        "Second stage override active",
        HO,
        148,
        enabled_by_default=False,
    ),
    _flag(
        "utility_release_hand_value",
        "Utility release override",
        HO,
        149,
        dtype=DataType.INT16,
        enabled_by_default=False,
    ),
    _flag(
        "utility_release_hand_active",
        "Utility release override active",
        HO,
        150,
        dtype=DataType.INT16,
        enabled_by_default=False,
    ),
    Point("tf22_hand_value", "TF22 override", HO, 151, category="config", enabled_by_default=False),
    _flag("tf22_hand_active", "TF22 override active", HO, 152, enabled_by_default=False),
)

POINTS_BY_KEY: Mapping[str, Point] = MappingProxyType({p.key: p for p in POINTS})


@dataclass(frozen=True, slots=True)
class Block:
    """A contiguous run of registers read in one request."""

    table: Table
    address: int
    count: int


MAX_BLOCK = 100


def read_blocks(points: Iterable[Point]) -> tuple[Block, ...]:
    """Group points into contiguous blocks per table, at most MAX_BLOCK registers each."""
    blocks: list[Block] = []
    for table in Table:
        spans = sorted((p.address, p.address + p.count) for p in points if p.table is table)
        start = end = None
        for lo, hi in spans:
            if start is not None and end is not None and lo <= end and hi - start <= MAX_BLOCK:
                end = max(end, hi)
                continue
            if start is not None and end is not None:
                blocks.append(Block(table, start, end - start))
            start, end = lo, hi
        if start is not None and end is not None:
            blocks.append(Block(table, start, end - start))
    return tuple(blocks)
