from __future__ import annotations

import re
import sys
from pathlib import Path

from heliotherm2mqtt.points import POINTS, Block, Kind, Table, read_blocks

ROOT = Path(__file__).resolve().parent.parent


def test_keys_are_unique_snake_case() -> None:
    keys = [p.key for p in POINTS]
    assert len(keys) == len(set(keys))
    assert all(re.fullmatch(r"[a-z0-9]+(_[a-z0-9]+)*", k) for k in keys)


def test_registers_do_not_overlap() -> None:
    used: set[tuple[Table, int]] = set()
    for p in POINTS:
        for addr in range(p.address, p.address + p.count):
            assert (p.table, addr) not in used, p.key
            used.add((p.table, addr))


def test_documented_register_ranges() -> None:
    for p in POINTS:
        if p.table is Table.INPUT:
            assert p.address >= 10 and p.address + p.count <= 76, p.key
        else:
            assert 100 <= p.address <= 152, p.key


def test_read_blocks_cover_the_documented_ranges() -> None:
    assert read_blocks(POINTS) == (
        Block(Table.INPUT, 10, 41),
        Block(Table.INPUT, 60, 16),
        Block(Table.HOLDING, 100, 6),
        Block(Table.HOLDING, 107, 46),
    )


def test_point_metadata_is_consistent() -> None:
    for p in POINTS:
        assert p.scale in (1, 0.1), p.key
        assert (p.kind is Kind.ENUM) == (p.options is not None), p.key
        assert p.category in (None, "diagnostic", "config"), p.key
        if p.writable:
            assert p.table is Table.HOLDING, p.key
            if p.kind is Kind.NUMBER:
                assert p.minimum is not None and p.maximum is not None, p.key


def test_writable_points_are_the_verified_set() -> None:
    writable = sorted(p.address for p in POINTS if p.writable)
    assert writable == [100, 101, 102, 103, 105, 107, 112, 135, 136, 137, 138]


def test_points_doc_is_up_to_date() -> None:
    sys.path.insert(0, str(ROOT / "tools"))
    try:
        from points_doc import render
    finally:
        sys.path.pop(0)
    doc = (ROOT / "docs" / "points.md").read_text(encoding="utf-8")
    assert doc == render(), "run: python tools/points_doc.py"
