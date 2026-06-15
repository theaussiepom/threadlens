"""Tests for Home Assistant Matter name enrichment."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from threadlens.enrichment.ha_matter import apply_ha_matter_device_names
from threadlens.models.state import MatterNodeState
from threadlens.storage.repositories import CurrentStateType


@pytest.mark.asyncio
async def test_apply_ha_matter_device_names_updates_matching_nodes() -> None:
    repository = AsyncMock()
    repository.list_current_state.return_value = [
        {
            "server_id": "study",
            "node_id": 27,
            "friendly_name": "Node 27",
        }
    ]
    repository.upsert_model_state = AsyncMock()

    result = await apply_ha_matter_device_names(
        repository,
        {
            "source": "homeassistant",
            "devices": [
                {
                    "server_id": "study",
                    "node_id": 27,
                    "ha_device_name": "Study Blind West",
                    "ha_entity_id": "cover.study_blind_west",
                }
            ],
        },
    )

    assert result["matched_devices"] == 1
    repository.upsert_model_state.assert_awaited_once()
    args = repository.upsert_model_state.await_args.args
    assert args[0] == CurrentStateType.MATTER_NODE
    updated = args[2]
    assert isinstance(updated, MatterNodeState)
    assert updated.ha_device_name == "Study Blind West"
    assert updated.ha_entity_id == "cover.study_blind_west"


@pytest.mark.asyncio
async def test_apply_ha_matter_device_names_skips_unknown_nodes() -> None:
    repository = AsyncMock()
    repository.list_current_state.return_value = []

    result = await apply_ha_matter_device_names(
        repository,
        {
            "devices": [
                {
                    "server_id": "study",
                    "node_id": 99,
                    "ha_device_name": "Missing Node",
                }
            ]
        },
    )

    assert result["matched_devices"] == 0
    repository.upsert_model_state.assert_not_awaited()
