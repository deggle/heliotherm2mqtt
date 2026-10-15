"""Entry point: heliotherm2mqtt [--config PATH]."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import signal
import sys

from . import __version__
from .bridge import Bridge
from .config import ConfigError, Settings, load_settings

log = logging.getLogger("heliotherm2mqtt")


async def _run(settings: Settings) -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):  # not available on Windows
            loop.add_signal_handler(sig, stop.set)
    await Bridge(settings).run(stop)


def main() -> None:
    parser = argparse.ArgumentParser(prog="heliotherm2mqtt", description=__doc__)
    parser.add_argument("--config", help="path to the YAML config (default: $H2M_CONFIG)")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    try:
        settings = load_settings(args.config)
    except ConfigError as exc:
        log.error("%s", exc)
        sys.exit(2)
    logging.getLogger().setLevel(settings.log_level)
    log.info(
        "heliotherm2mqtt %s: %d heat pump(s), discovery %s, writes %s, retain %s",
        __version__,
        len(settings.heatpumps),
        "on" if settings.homeassistant.discovery else "off",
        "ENABLED" if settings.writes.enabled else "disabled",
        "on" if settings.mqtt.retain else "OFF",
    )

    # aiomqtt needs a selector event loop; Windows defaults to the proactor loop.
    factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    with asyncio.Runner(loop_factory=factory) as runner, contextlib.suppress(KeyboardInterrupt):
        runner.run(_run(settings))


if __name__ == "__main__":
    main()
