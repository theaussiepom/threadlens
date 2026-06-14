"""Configuration loading for ThreadLens."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_CONFIG_PATH = Path("/config/config.yaml")


class RuntimeMode(StrEnum):
    SERVER = "server"
    AGENT = "agent"
    BOTH = "both"


class MatterServerVariant(StrEnum):
    PYTHON = "python"
    UNKNOWN = "unknown"


class ProbeMode(StrEnum):
    OFF = "off"
    CONSERVATIVE = "conservative"
    STANDARD = "standard"
    DIAGNOSTIC = "diagnostic"


_MODE_DEFAULT_INTERVAL_SECONDS: dict[ProbeMode, int] = {
    ProbeMode.OFF: 3600,
    ProbeMode.CONSERVATIVE: 3600,
    ProbeMode.STANDARD: 1800,
    ProbeMode.DIAGNOSTIC: 900,
}


class SiteConfig(BaseModel):
    name: str = "Home"


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = Field(default=8128, ge=1, le=65535)


class AgentConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = Field(default=8129, ge=1, le=65535)


class StorageConfig(BaseModel):
    sqlite_path: str = "/data/threadlens.db"
    event_retention_days: int = Field(default=30, ge=1)


class FlappingConfig(BaseModel):
    debounce_seconds: int = Field(default=30, ge=0)
    matter_node_availability_warning_24h: int = Field(default=3, ge=0)
    matter_node_availability_degraded_24h: int = Field(default=6, ge=0)
    matter_node_unavailable_critical_minutes: int = Field(default=30, ge=0)
    matter_node_read_probe_failures_warning_24h: int = Field(default=1, ge=0)
    matter_node_read_probe_failures_degraded_24h: int = Field(default=3, ge=0)
    otbr_role_changes_warning_1h: int = Field(default=2, ge=0)
    otbr_role_changes_degraded_1h: int = Field(default=5, ge=0)
    mdns_service_flaps_warning_1h: int = Field(default=5, ge=0)
    mdns_service_flaps_degraded_1h: int = Field(default=15, ge=0)


class MqttConfig(BaseModel):
    enabled: bool = True
    host: str = "mqtt"
    port: int = Field(default=1883, ge=1, le=65535)
    username: str | None = None
    password: str | None = None
    discovery_prefix: str = "homeassistant"
    topic_prefix: str = "threadlens"
    retain_discovery: bool = True
    retain_state: bool = True
    publish_interval_seconds: int = Field(default=30, ge=5)
    per_trel_service_entities: bool = False
    per_node_entities: bool = True


class MdnsConfig(BaseModel):
    enabled: bool = True
    services: list[str] = Field(
        default_factory=lambda: [
            "_trel._udp.local.",
            "_meshcop._udp.local.",
            "_matter._tcp.local.",
            "_matterc._udp.local.",
        ]
    )


class OtbrPollingConfig(BaseModel):
    poll_interval_seconds: int = Field(default=60, ge=5)
    request_timeout_seconds: float = Field(default=5.0, gt=0)
    allow_read_only_actions: bool = False
    use_legacy_node_fallback: bool = True


class MatterProbeAttributesConfig(BaseModel):
    """Advanced attribute path overrides for read reachability probes."""

    window_covering: list[str] = Field(default_factory=lambda: ["1/258/10"])
    fallback: list[str] = Field(default_factory=lambda: ["0/40/2", "0/40/4", "0/40/5"])


class MatterProbePerNodeOverride(BaseModel):
    preferred: list[str] = Field(default_factory=list)
    disabled: bool = False


class MatterProbeAdvancedConfig(BaseModel):
    """Low-level probe tuning and advanced attribute overrides."""

    interval_seconds: int | None = Field(default=None, ge=60)
    timeout_seconds: float = Field(default=10.0, gt=0)
    max_concurrent: int = Field(default=1, ge=1)
    jitter_seconds: int = Field(default=300, ge=0)
    ping_enabled: bool = False
    attributes: MatterProbeAttributesConfig = Field(default_factory=MatterProbeAttributesConfig)
    per_node: dict[str, MatterProbePerNodeOverride] = Field(default_factory=dict)


class MatterProbeConfig(BaseModel):
    """User-facing and advanced Matter read reachability probe settings."""

    enabled: bool = False
    mode: ProbeMode | None = None
    manual_enabled: bool = True
    schedule_enabled: bool = False
    advanced: MatterProbeAdvancedConfig = Field(default_factory=MatterProbeAdvancedConfig)

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        advanced = dict(data.get("advanced") or {})
        legacy_map = {
            "interval_seconds": "interval_seconds",
            "timeout_seconds": "timeout_seconds",
            "max_concurrent": "max_concurrent",
            "jitter_seconds": "jitter_seconds",
            "ping_enabled": "ping_enabled",
        }
        for legacy_key, advanced_key in legacy_map.items():
            if legacy_key in data and data[legacy_key] is not None:
                advanced[advanced_key] = data[legacy_key]
        if "attributes" in data and isinstance(data["attributes"], dict):
            attrs = dict(advanced.get("attributes") or {})
            attrs.update(data["attributes"])
            advanced["attributes"] = attrs
        if advanced:
            data["advanced"] = advanced
        return data

    @property
    def effective_mode(self) -> ProbeMode:
        if self.mode is not None:
            return self.mode
        if not self.enabled:
            return ProbeMode.OFF
        return ProbeMode.CONSERVATIVE

    @property
    def probes_active(self) -> bool:
        return self.effective_mode != ProbeMode.OFF

    @property
    def interval_seconds(self) -> int:
        if self.advanced.interval_seconds is not None:
            return self.advanced.interval_seconds
        return _MODE_DEFAULT_INTERVAL_SECONDS[self.effective_mode]

    @property
    def timeout_seconds(self) -> float:
        return self.advanced.timeout_seconds

    @property
    def max_concurrent(self) -> int:
        return self.advanced.max_concurrent

    @property
    def jitter_seconds(self) -> int:
        return self.advanced.jitter_seconds

    @property
    def ping_enabled(self) -> bool:
        return self.advanced.ping_enabled

    @property
    def attributes(self) -> MatterProbeAttributesConfig:
        return self.advanced.attributes


class MatterPollingConfig(BaseModel):
    reconnect_initial_seconds: float = Field(default=5.0, gt=0)
    reconnect_max_seconds: float = Field(default=60.0, gt=0)
    request_timeout_seconds: float = Field(default=10.0, gt=0)
    probes: MatterProbeConfig = Field(default_factory=MatterProbeConfig)


class OtbrConfig(BaseModel):
    id: str
    name: str
    rest_url: str
    agent_url: str | None = None

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("OTBR id must not be empty")
        return value


class MatterServerConfig(BaseModel):
    id: str
    name: str
    websocket_url: str
    variant: MatterServerVariant = MatterServerVariant.PYTHON

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Matter Server id must not be empty")
        return value


class ReportsConfig(BaseModel):
    redact_secrets: bool = True


class HomeAssistantConfig(BaseModel):
    mqtt_discovery_enabled: bool = True


class ThreadLensConfig(BaseModel):
    site: SiteConfig = Field(default_factory=SiteConfig)
    mode: RuntimeMode = RuntimeMode.SERVER
    server: ServerConfig = Field(default_factory=ServerConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    flapping: FlappingConfig = Field(default_factory=FlappingConfig)
    mqtt: MqttConfig = Field(default_factory=MqttConfig)
    mdns: MdnsConfig = Field(default_factory=MdnsConfig)
    otbr: OtbrPollingConfig = Field(default_factory=OtbrPollingConfig)
    otbrs: list[OtbrConfig] = Field(default_factory=list)
    matter: MatterPollingConfig = Field(default_factory=MatterPollingConfig)
    matter_servers: list[MatterServerConfig] = Field(default_factory=list)
    reports: ReportsConfig = Field(default_factory=ReportsConfig)
    homeassistant: HomeAssistantConfig = Field(default_factory=HomeAssistantConfig)


class EnvOverrides(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="THREADLENS_", extra="ignore")

    config_path: str | None = None
    mode: RuntimeMode | None = None
    site_name: str | None = None
    server_host: str | None = None
    server_port: int | None = None
    agent_host: str | None = None
    agent_port: int | None = None


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def resolve_config_path(explicit_path: str | Path | None = None) -> Path:
    if explicit_path is not None:
        return Path(explicit_path)
    env = EnvOverrides()
    if env.config_path:
        return Path(env.config_path)
    return DEFAULT_CONFIG_PATH


def load_config(
    config_path: str | Path | None = None,
    *,
    mode_override: RuntimeMode | Literal["server", "agent", "both"] | None = None,
) -> ThreadLensConfig:
    """Load YAML config and apply environment/CLI overrides."""
    path = resolve_config_path(config_path)
    data: dict[str, Any] = {}

    if path.exists():
        with path.open(encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle)
            if loaded:
                if not isinstance(loaded, dict):
                    raise ValueError(f"Config file must contain a mapping: {path}")
                data = loaded

    env = EnvOverrides()
    env_overrides: dict[str, Any] = {}
    if env.site_name is not None:
        env_overrides["site"] = {"name": env.site_name}
    if env.server_host is not None or env.server_port is not None:
        env_overrides.setdefault("server", {})
        if env.server_host is not None:
            env_overrides["server"]["host"] = env.server_host
        if env.server_port is not None:
            env_overrides["server"]["port"] = env.server_port
    if env.agent_host is not None or env.agent_port is not None:
        env_overrides.setdefault("agent", {})
        if env.agent_host is not None:
            env_overrides["agent"]["host"] = env.agent_host
        if env.agent_port is not None:
            env_overrides["agent"]["port"] = env.agent_port
    if env.mode is not None:
        env_overrides["mode"] = env.mode

    data = _deep_merge(data, env_overrides)

    if mode_override is not None:
        data["mode"] = str(mode_override)

    return ThreadLensConfig.model_validate(data)


def ensure_data_directories(config: ThreadLensConfig) -> None:
    """Create parent directories for config-adjacent paths when writable."""
    db_path = Path(config.storage.sqlite_path)
    if db_path.parent and not db_path.parent.exists():
        try:
            db_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
