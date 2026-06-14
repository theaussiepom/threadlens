"""Live test 0.1.0 setup validation (Ben Home topology examples)."""

from __future__ import annotations

from pathlib import Path

import yaml

from threadlens.config import RuntimeMode, load_config

REPO_ROOT = Path(__file__).resolve().parents[1]
LIVE_TEST_DOC = REPO_ROOT / "LIVE_TEST_0.1.0.md"
STUDY_CONFIG = REPO_ROOT / "examples" / "live" / "study-both.config.yaml"
LOUNGE_CONFIG = REPO_ROOT / "examples" / "live" / "lounge-agent.config.yaml"
STUDY_COMPOSE = REPO_ROOT / "docker-compose.study-both.example.yml"
LOUNGE_COMPOSE = REPO_ROOT / "docker-compose.lounge-agent.example.yml"


def test_live_config_files_validate() -> None:
    study = load_config(STUDY_CONFIG)
    lounge = load_config(LOUNGE_CONFIG)
    assert study.site.name == "Ben Home"
    assert lounge.site.name == "Ben Home"


def test_study_live_config_topology() -> None:
    config = load_config(STUDY_CONFIG)
    assert config.mode == RuntimeMode.BOTH
    assert len(config.otbrs) == 2
    assert config.otbrs[0].id == "study"
    assert config.otbrs[0].rest_url == "http://192.168.100.4:8081"
    assert config.otbrs[0].agent_url == "http://192.168.100.4:8129"
    assert config.otbrs[1].id == "lounge"
    assert config.otbrs[1].rest_url == "http://192.168.100.7:8081"
    assert config.otbrs[1].agent_url == "http://192.168.100.7:8129"
    assert len(config.matter_servers) == 1
    assert config.matter_servers[0].websocket_url == "ws://192.168.100.4:5580/ws"
    assert config.mqtt.enabled is True
    assert config.mqtt.host == "broker.mqtt"
    assert config.mqtt.username is None
    assert config.mqtt.password is None
    assert config.reports.redact_secrets is True
    assert config.homeassistant.mqtt_discovery_enabled is True


def test_lounge_live_config_agent_only() -> None:
    config = load_config(LOUNGE_CONFIG)
    assert config.mode == RuntimeMode.AGENT
    assert config.mqtt.enabled is False
    assert config.mdns.enabled is False
    assert config.otbrs == []
    assert config.matter_servers == []
    assert config.agent.port == 8129
    assert config.storage.sqlite_path == "/data/threadlens.db"


def test_live_compose_files_parse_and_use_host_network() -> None:
    study = yaml.safe_load(STUDY_COMPOSE.read_text(encoding="utf-8"))
    lounge = yaml.safe_load(LOUNGE_COMPOSE.read_text(encoding="utf-8"))
    study_service = study["services"]["threadlens"]
    lounge_service = lounge["services"]["threadlens-agent"]
    assert study_service["network_mode"] == "host"
    assert lounge_service["network_mode"] == "host"
    assert "ports" not in study_service
    assert "ports" not in lounge_service


def test_live_compose_commands_match_modes() -> None:
    study = yaml.safe_load(STUDY_COMPOSE.read_text(encoding="utf-8"))
    lounge = yaml.safe_load(LOUNGE_COMPOSE.read_text(encoding="utf-8"))
    assert study["services"]["threadlens"]["command"] == ["--mode", "both"]
    assert lounge["services"]["threadlens-agent"]["command"] == ["--mode", "agent"]


def test_live_test_doc_exists_with_key_endpoints() -> None:
    content = LIVE_TEST_DOC.read_text(encoding="utf-8")
    assert "192.168.100.4:8128" in content
    assert "192.168.100.4:8129" in content
    assert "192.168.100.7:8129" in content
    assert "/api/v1/otbrs" in content
    assert "/api/v1/report.yaml" in content
    assert "broker.mqtt" in content
