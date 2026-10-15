"""Convert between raw register values and MQTT payloads."""

from __future__ import annotations

import math
from collections.abc import Sequence

from .points import DataType, Kind, Point

ON = "ON"
OFF = "OFF"
_TRUE = {"on", "1", "true"}
_FALSE = {"off", "0", "false"}


def to_int(dtype: DataType, registers: Sequence[int]) -> int:
    """Combine big-endian registers into an integer, applying sign."""
    bits = 16 * dtype.registers
    value = 0
    for reg in registers[: dtype.registers]:
        value = (value << 16) | (reg & 0xFFFF)
    if dtype.signed and value >= 1 << (bits - 1):
        value -= 1 << bits
    return value


def from_int(dtype: DataType, value: int) -> list[int]:
    """Split an integer into big-endian registers, checking the type's range."""
    bits = 16 * dtype.registers
    lo, hi = (-(1 << (bits - 1)), (1 << (bits - 1)) - 1) if dtype.signed else (0, (1 << bits) - 1)
    if not lo <= value <= hi:
        raise ValueError(f"{value} is out of range for {dtype}")
    value &= (1 << bits) - 1
    return [(value >> (16 * i)) & 0xFFFF for i in reversed(range(dtype.registers))]


def decode(point: Point, registers: Sequence[int]) -> str | None:
    """Return the MQTT payload for a point, or None if the device reports no value."""
    raw = to_int(point.dtype, registers)
    if raw in point.absent:
        return None
    if point.kind is Kind.BOOLEAN:
        return ON if raw else OFF
    if point.kind is Kind.ENUM:
        assert point.options is not None
        return point.options.get(raw, str(raw))
    if point.decimals:
        return f"{raw * point.scale:.{point.decimals}f}"
    return str(round(raw * point.scale))


def encode(point: Point, payload: str) -> list[int]:
    """Validate a command payload and return the registers to write."""
    text = payload.strip()
    if point.kind is Kind.BOOLEAN:
        if text.lower() in _TRUE:
            return from_int(point.dtype, 1)
        if text.lower() in _FALSE:
            return from_int(point.dtype, 0)
        raise ValueError(f"expected ON or OFF, got {text!r}")

    if point.kind is Kind.ENUM:
        assert point.options is not None
        for code, label in point.options.items():
            if text.lower() == label or text == str(code):
                return from_int(point.dtype, code)
        raise ValueError(f"expected one of {', '.join(point.options.values())}, got {text!r}")

    try:
        value = float(text)
    except ValueError:
        raise ValueError(f"expected a number, got {text!r}") from None
    if not math.isfinite(value):
        raise ValueError(f"expected a finite number, got {text!r}")
    if point.minimum is not None and value < point.minimum:
        raise ValueError(f"{value:g} is below the minimum of {point.minimum:g}")
    if point.maximum is not None and value > point.maximum:
        raise ValueError(f"{value:g} is above the maximum of {point.maximum:g}")
    return from_int(point.dtype, round(value / point.scale))
