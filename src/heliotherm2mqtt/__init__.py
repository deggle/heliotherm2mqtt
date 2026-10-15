"""heliotherm2mqtt: a Modbus TCP to MQTT bridge for Heliotherm heat pumps."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("heliotherm2mqtt")
except PackageNotFoundError:  # running from a source tree without installing
    __version__ = "0.0.0"
