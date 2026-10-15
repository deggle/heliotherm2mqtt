from __future__ import annotations

from pathlib import Path

import pytest

from heliotherm2mqtt.config import ConfigError, load_settings

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "config.example.yaml"


def test_example_config_is_valid() -> None:
    settings = load_settings(EXAMPLE, env={})
    assert [p.id for p in settings.heatpumps] == ["primary", "secondary", "pool"]
    assert settings.mqtt.retain is True
    assert settings.writes.enabled is False
    assert settings.homeassistant.discovery is False
    pool = settings.heatpumps[2]
    assert pool.port == 502 and pool.unit_id == 1 and pool.poll_interval == 10
    assert not any(p.key.startswith("mc1_") for p in pool.points())


def test_env_overrides(tmp_path: Path) -> None:
    settings = load_settings(
        EXAMPLE,
        env={
            "H2M_MQTT_HOST": "broker.example",
            "H2M_MQTT_PORT": "8883",
            "H2M_MQTT_PASSWORD": "secret",
            "H2M_MQTT_RETAIN": "false",
            "H2M_HA_DISCOVERY": "true",
            "H2M_WRITES_ENABLED": "1",
            "H2M_LOG_LEVEL": "debug",
            "H2M_MQTT_USERNAME": "",
        },
    )
    assert settings.mqtt.host == "broker.example"
    assert settings.mqtt.port == 8883
    assert settings.mqtt.password is not None
    assert settings.mqtt.password.get_secret_value() == "secret"
    assert settings.mqtt.username is None
    assert settings.mqtt.retain is False
    assert settings.homeassistant.discovery is True
    assert settings.writes.enabled is True
    assert settings.log_level == "DEBUG"


def test_config_path_from_env(tmp_path: Path) -> None:
    path = tmp_path / "c.yaml"
    path.write_text(EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    assert load_settings(env={"H2M_CONFIG": str(path)}).heatpumps


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(text, encoding="utf-8")
    return path


BASE = "mqtt: {host: m}\nheatpumps:\n"


@pytest.mark.parametrize(
    "pumps",
    [
        "",  # none
        "  - {id: a, name: A, host: h}\n  - {id: a, name: B, host: h}\n",  # duplicate
        "  - {id: Bad-Id, name: A, host: h}\n",
        "  - {id: a, name: A, host: h, exclude_points: [nothing_*]}\n",
        "  - {id: a, name: A, host: h, colour: red}\n",  # unknown key
        "  - {id: a, name: A, host: h, topic_prefix: 'x/#'}\n",
    ],
)
def test_invalid_configs(tmp_path: Path, pumps: str) -> None:
    with pytest.raises(ConfigError):
        load_settings(_write(tmp_path, BASE + pumps), env={})


def test_same_id_under_different_prefixes(tmp_path: Path) -> None:
    pumps = "  - {id: a, name: A, host: h}\n  - {id: a, name: B, host: h, topic_prefix: other}\n"
    settings = load_settings(_write(tmp_path, BASE + pumps), env={})
    assert [settings.prefix_for(p) for p in settings.heatpumps] == ["heliotherm", "other"]


def test_write_interval_cannot_go_below_five_seconds(tmp_path: Path) -> None:
    text = BASE + "  - {id: a, name: A, host: h}\nwrites: {enabled: true, min_interval: 1}\n"
    with pytest.raises(ConfigError):
        load_settings(_write(tmp_path, text), env={})


def test_missing_file() -> None:
    with pytest.raises(ConfigError):
        load_settings("/nonexistent/config.yaml", env={})
