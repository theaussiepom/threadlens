"""Models for Home Assistant enrichment payloads."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HaMatterDeviceName(BaseModel):
    server_id: str
    node_id: int
    ha_device_name: str
    ha_entity_id: str | None = None


class HaMatterNamesPayload(BaseModel):
    source: str = "homeassistant"
    devices: list[HaMatterDeviceName] = Field(default_factory=list)
