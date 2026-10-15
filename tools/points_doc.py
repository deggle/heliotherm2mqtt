"""Generate docs/points.md from the point map.

Usage: python tools/points_doc.py
"""

from __future__ import annotations

from pathlib import Path

from heliotherm2mqtt.points import POINTS, Kind, Point, Table

HEADER = """\
# Point map

Generated from `src/heliotherm2mqtt/points.py` by `tools/points_doc.py`. Do not edit by hand.

Addresses are zero-based Modbus register numbers, as in the Heliotherm Remote Control Gateway
documentation. 32-bit values span two registers, most significant word first.
Numbers are published already scaled. **W** marks points accepted as commands (when writes
are enabled). Points marked *hidden* are disabled by default in Home Assistant.
"""


def _values(point: Point) -> str:
    if point.kind is Kind.BOOLEAN:
        return "`ON` / `OFF`"
    if point.kind is Kind.ENUM:
        assert point.options is not None
        return ", ".join(f"`{label}` ({code})" for code, label in point.options.items())
    text = point.unit or ""
    if point.minimum is not None and point.maximum is not None:
        text += f", {point.minimum:g} to {point.maximum:g}"
    return text.strip(", ")


def render() -> str:
    lines = [HEADER]
    for table, title in ((Table.INPUT, "Input registers"), (Table.HOLDING, "Holding registers")):
        lines += [
            f"## {title}",
            "",
            "| Register | Point | Name | Type | Scale | Values | W | Notes |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for p in (p for p in POINTS if p.table is table):
            reg = str(p.address) if p.count == 1 else f"{p.address}-{p.address + p.count - 1}"
            notes = []
            if not p.enabled_by_default:
                notes.append("hidden")
            if p.absent:
                notes.append("not published at -50.0 or -100.0")
            lines.append(
                f"| {reg} | `{p.key}` | {p.name} | {p.dtype} | {p.scale:g} | {_values(p)} "
                f"| {'W' if p.writable else ''} | {', '.join(notes)} |"
            )
        lines.append("")
    return "\n".join(lines)


DOC = Path(__file__).resolve().parent.parent / "docs" / "points.md"

if __name__ == "__main__":
    DOC.write_text(render(), encoding="utf-8", newline="\n")
    print(f"wrote {DOC}")
