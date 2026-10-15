"""Configuration: a YAML file with H2M_* environment variable overrides."""

from __future__ import annotations

import fnmatch
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

from .points import POINTS, Point

DEFAULT_CONFIG_PATH = "/config/config.yaml"

_TOPIC_SEGMENTS = r"^[^#+/\s]+(/[^#+/\s]+)*$"


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MqttSettings(_Model):
    host: str
    port: int = Field(1883, ge=1, le=65535)
    username: str | None = None
    password: SecretStr | None = None
    client_id: str = "heliotherm2mqtt"
    topic_prefix: str = Field("heliotherm", pattern=_TOPIC_SEGMENTS)
    retain: bool = True
    keepalive: int = Field(60, ge=5)
    tls: bool = False


class HomeAssistantSettings(_Model):
    discovery: bool = False
    discovery_prefix: str = Field("homeassistant", pattern=_TOPIC_SEGMENTS)
    bridge_name: str = "Heliotherm2MQTT Bridge"


class WriteSettings(_Model):
    enabled: bool = False
    # The manufacturer advises not writing registers faster than every 5 seconds.
    min_interval: float = Field(5.0, ge=5.0)


class HeatPumpSettings(_Model):
    id: str = Field(pattern=r"^[a-z0-9_]+$")
    name: str
    host: str
    port: int = Field(502, ge=1, le=65535)
    unit_id: int = Field(1, ge=0, le=255)
    model: str | None = None
    topic_prefix: str | None = Field(None, pattern=_TOPIC_SEGMENTS)
    poll_interval: float = Field(10.0, ge=1.0)
    # The manufacturer recommends a Modbus timeout of at least 10 seconds.
    timeout: float = Field(10.0, gt=0)
    offline_after: float = Field(60.0, gt=0)
    exclude_points: tuple[str, ...] = ()

    @field_validator("exclude_points")
    @classmethod
    def _patterns_match(cls, patterns: tuple[str, ...]) -> tuple[str, ...]:
        for pattern in patterns:
            if not any(fnmatch.fnmatchcase(p.key, pattern) for p in POINTS):
                raise ValueError(f"exclude pattern {pattern!r} matches no point")
        return patterns

    def points(self) -> tuple[Point, ...]:
        """The points published for this heat pump."""
        return tuple(
            p
            for p in POINTS
            if not any(fnmatch.fnmatchcase(p.key, pat) for pat in self.exclude_points)
        )


class Settings(_Model):
    mqtt: MqttSettings
    homeassistant: HomeAssistantSettings = Field(default_factory=HomeAssistantSettings)
    writes: WriteSettings = Field(default_factory=WriteSettings)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    republish_interval: float = Field(300.0, ge=10)
    heatpumps: tuple[HeatPumpSettings, ...] = Field(min_length=1)

    @field_validator("log_level", mode="before")
    @classmethod
    def _upper(cls, value: Any) -> Any:
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def _unique_topics(self) -> Settings:
        seen: set[tuple[str, str]] = set()
        for pump in self.heatpumps:
            key = (self.prefix_for(pump), pump.id)
            if key in seen:
                raise ValueError(f"heat pump id {pump.id!r} is used twice under one prefix")
            seen.add(key)
        return self

    def prefix_for(self, pump: HeatPumpSettings) -> str:
        return pump.topic_prefix or self.mqtt.topic_prefix


# Environment variable -> path in the settings tree.
ENV_OVERRIDES: Mapping[str, tuple[str, ...]] = {
    "H2M_LOG_LEVEL": ("log_level",),
    "H2M_MQTT_HOST": ("mqtt", "host"),
    "H2M_MQTT_PORT": ("mqtt", "port"),
    "H2M_MQTT_USERNAME": ("mqtt", "username"),
    "H2M_MQTT_PASSWORD": ("mqtt", "password"),
    "H2M_MQTT_CLIENT_ID": ("mqtt", "client_id"),
    "H2M_MQTT_TOPIC_PREFIX": ("mqtt", "topic_prefix"),
    "H2M_MQTT_RETAIN": ("mqtt", "retain"),
    "H2M_MQTT_TLS": ("mqtt", "tls"),
    "H2M_HA_DISCOVERY": ("homeassistant", "discovery"),
    "H2M_HA_DISCOVERY_PREFIX": ("homeassistant", "discovery_prefix"),
    "H2M_WRITES_ENABLED": ("writes", "enabled"),
}


class ConfigError(Exception):
    pass


def load_settings(path: str | Path | None = None, env: Mapping[str, str] | None = None) -> Settings:
    """Load the YAML file, apply environment overrides and validate."""
    env = os.environ if env is None else env
    path = Path(path or env.get("H2M_CONFIG") or DEFAULT_CONFIG_PATH)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except OSError as exc:
        raise ConfigError(f"cannot read config file {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path} must contain a mapping at the top level")

    for name, keys in ENV_OVERRIDES.items():
        if (value := env.get(name)) not in (None, ""):
            node = data
            for key in keys[:-1]:
                if not isinstance(node.get(key), dict):
                    node[key] = {}
                node = node[key]
            node[keys[-1]] = value

    try:
        return Settings.model_validate(data)
    except ValueError as exc:
        raise ConfigError(f"invalid configuration in {path}:\n{exc}") from exc
