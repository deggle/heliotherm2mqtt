# CLAUDE.md: heliotherm2mqtt

## Purpose

An open-source bridge between Heliotherm heat pumps (Modbus TCP via the Remote Control Gateway) and MQTT, with optional Home Assistant discovery. One process serves any number of heat pumps. It is published for other people to use, so keep it generic.

## Hard rules

- The bridge translates only. No scheduling, pricing, weather, season or comfort logic. Range checks and write pacing that protect the device are fine; deciding *what* to write is not.
- No site-specific values in code, tests or docs: no real IP addresses, room names or household details. Use `192.0.2.x` (RFC 5737) and `example` names in examples.
- Writes are off by default (`writes.enabled: false`). Only points marked `writable` in the point map can be written.
- `docs/reference/` holds manufacturer PDFs and private flows. It is git-ignored and must never be committed.
- `local/` holds the maintainer's live-test config and compose file with real addresses. It is git-ignored and must never be committed or copied into tracked files.
- The interface contract is `docs/interface.md` and the point map is documented in `docs/points.md`. Change the docs first, then the code, and record decisions in `docs/decisions/`.

## Layout

- `src/heliotherm2mqtt/points.py`: the register map (single source of truth for names, scaling, HA metadata, writability).
- `codec.py`: register values to MQTT payloads and back.
- `modbus.py`: Modbus TCP client wrapper.
- `bridge.py`: per-pump poll loop, command handling, MQTT connection.
- `discovery.py`: Home Assistant discovery payloads.
- `config.py`: YAML config plus `H2M_*` environment overrides.
- `simulator.py`: a fake Heliotherm Modbus device for tests and local trials.

## Conventions

- Python 3.11 or later. Lint and format with ruff, type-check with mypy (strict).
- Tests with pytest and must run without hardware or a broker: use `simulator.py` and fake publishers.
- Docs and comments use British English.
- Commit messages are short and imperative. Tick BACKLOG.md items in the same commit that finishes them.

## Commands

```
pip install -e ".[dev]"
ruff check . && ruff format --check .
mypy
pytest
```

## Working on items

- Work from BACKLOG.md.
- Items marked *verify* need real hardware: stop and ask the user to test.
