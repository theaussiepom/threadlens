"""Config loading tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from threadlens.config import (
    FlappingConfig,
    HomeAssistantConfig,
    MatterProbeConfig,
    MatterServerVariant,
    ProbeMode,
    RuntimeMode,
    ThreadLensConfig,
    load_config,
)

FIXTURES = Path(__file__).parent / "fixtures"
EXAMPLE_CONFIG = FIXTURES / "example_config.yaml"


def test_load_example_config() -> None:
    config = load_config(EXAMPLE_CONFIG)
    assert config.site.name == "Home"
    assert config.mode == RuntimeMode.SERVER
    assert config.server.port == 8128
    assert config.agent.port == 8129
    assert config.flapping.debounce_seconds == 30
    assert config.mqtt.per_trel_service_entities is False
    assert config.mqtt.per_node_entities is False
    assert len(config.otbrs) == 1
    assert config.otbrs[0].id == "primary"
    assert len(config.matter_servers) == 1
    assert config.matter_servers[0].variant == MatterServerVariant.PYTHON
    assert config.homeassistant.mqtt_discovery_enabled is True


def test_load_config_with_defaults() -> None:
    config = ThreadLensConfig()
    assert config.site.name == "Home"
    assert config.mode == RuntimeMode.SERVER
    assert config.storage.sqlite_path == "/data/threadlens.db"
    assert config.flapping == FlappingConfig()
    assert config.mqtt.enabled is True
    assert config.mdns.enabled is True
    assert config.otbrs == []
    assert config.matter_servers == []
    assert config.reports.redact_secrets is True
    assert config.homeassistant == HomeAssistantConfig()
    assert config.homeassistant.mqtt_discovery_enabled is True


def test_matter_probe_config_defaults() -> None:
    config = ThreadLensConfig()
    probes = config.matter.probes
    assert probes.mode == ProbeMode.DISABLED
    assert probes.schedule_enabled is False
    assert probes.manual_enabled is True
    assert probes.timeout_seconds == 10.0
    assert probes.max_concurrent == 1
    assert probes.attributes.fallback == ["0/40/2", "0/40/4", "0/40/5"]
    assert probes.effective_mode.value == "disabled"


def test_probe_mode_disabled_accepted() -> None:
    config = MatterProbeConfig.model_validate({"mode": "disabled"})
    assert config.mode == ProbeMode.DISABLED
    assert config.probes_active is False


def test_probe_mode_off_alias_maps_to_disabled() -> None:
    config = MatterProbeConfig.model_validate({"mode": "off"})
    assert config.mode == ProbeMode.DISABLED


def test_probe_mode_yaml_off_boolean_maps_to_disabled() -> None:
    config = MatterProbeConfig.model_validate({"mode": False})
    assert config.mode == ProbeMode.DISABLED


def test_env_override_site_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("THREADLENS_SITE_NAME", "Lab")
    config = load_config(EXAMPLE_CONFIG)
    assert config.site.name == "Lab"


def test_env_override_config_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("THREADLENS_CONFIG_PATH", str(EXAMPLE_CONFIG))
    config = load_config()
    assert config.otbrs[0].name == "Primary OTBR"


def test_invalid_mode_fails_validation() -> None:
    with pytest.raises(ValidationError):
        ThreadLensConfig.model_validate({"mode": "invalid-mode"})


def test_invalid_matter_server_variant_fails_validation() -> None:
    with pytest.raises(ValidationError):
        ThreadLensConfig.model_validate(
            {
                "matter_servers": [
                    {
                        "id": "bad",
                        "name": "Bad",
                        "websocket_url": "ws://127.0.0.1:5580/ws",
                        "variant": "matterjs",
                    }
                ]
            }
        )
