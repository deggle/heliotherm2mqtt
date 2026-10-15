from __future__ import annotations

import pytest

from heliotherm2mqtt.codec import decode, encode, from_int, to_int
from heliotherm2mqtt.points import POINTS_BY_KEY, DataType


@pytest.mark.parametrize(
    ("dtype", "regs", "expected"),
    [
        (DataType.INT16, [0xFFFF], -1),
        (DataType.INT16, [0x7FFF], 32767),
        (DataType.UINT16, [0xFFFF], 65535),
        (DataType.UINT32, [12, 64436], 850868),  # the manufacturer's worked example
        (DataType.INT32, [0xFFFF, 0xFFFE], -2),
    ],
)
def test_to_int(dtype: DataType, regs: list[int], expected: int) -> None:
    assert to_int(dtype, regs) == expected
    assert from_int(dtype, expected) == regs


def test_from_int_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        from_int(DataType.UINT16, -1)
    with pytest.raises(ValueError):
        from_int(DataType.INT16, 40000)


def test_decode_scaled_temperature() -> None:
    point = POINTS_BY_KEY["outdoor_temperature"]
    assert decode(point, [215]) == "21.5"
    assert decode(point, [0xFFFF - 34]) == "-3.5"
    assert decode(point, [0]) == "0.0"


def test_decode_absent_sensor() -> None:
    point = POINTS_BY_KEY["fresh_water_temperature"]
    assert decode(point, [0x10000 - 500]) is None
    assert decode(point, [0x10000 - 1000]) is None
    assert decode(POINTS_BY_KEY["buffer_temperature_value"], [0x10000 - 1000]) is None


def test_decode_boolean_and_enum() -> None:
    assert decode(POINTS_BY_KEY["compressor"], [3]) == "ON"
    assert decode(POINTS_BY_KEY["compressor"], [0]) == "OFF"
    assert decode(POINTS_BY_KEY["operating_mode"], [1]) == "auto"
    assert decode(POINTS_BY_KEY["operating_mode"], [99]) == "99"
    assert decode(POINTS_BY_KEY["heat_pump_request"], [30]) == "dhw"


def test_decode_32_bit_and_integer() -> None:
    assert decode(POINTS_BY_KEY["total_heat_energy"], [12, 64436]) == "850868"
    assert decode(POINTS_BY_KEY["heat_output"], [0, 59]) == "5.9"
    assert decode(POINTS_BY_KEY["compressor_speed"], [420]) == "420"


def test_encode_number() -> None:
    point = POINTS_BY_KEY["room_setpoint"]
    assert encode(point, "21.5") == [215]
    assert encode(point, " 20 ") == [200]
    for bad in ("9.5", "25.5", "warm", "nan", "inf", ""):
        with pytest.raises(ValueError):
            encode(point, bad)


def test_encode_enum() -> None:
    point = POINTS_BY_KEY["operating_mode"]
    assert encode(point, "auto") == [1]
    assert encode(point, "Summer") == [3]
    assert encode(point, "0") == [0]
    for bad in ("8", "heat", "1.0"):
        with pytest.raises(ValueError):
            encode(point, bad)


def test_encode_boolean() -> None:
    point = POINTS_BY_KEY["return_setpoint_active"]
    assert encode(point, "ON") == [1]
    assert encode(point, "false") == [0]
    with pytest.raises(ValueError):
        encode(point, "maybe")
