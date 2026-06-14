"""Server-side ThreadLens agent client tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest

from threadlens import __version__
from threadlens.collectors.agent_client import AgentCollector
from threadlens.config import MdnsConfig, OtbrConfig, ThreadLensConfig
from threadlens.models.agent import AgentState
from threadlens.storage.db import Database
from threadlens.storage.repositories import CurrentStateType, StorageRepository


def _agent_status_payload() -> dict[str, Any]:
    return {
        "service": "threadlens-agent",
        "version": __version__,
        "mode": "agent",
        "site": "Home",
        "started_at": "2026-06-14T12:00:00+00:00",
        "capabilities": {
            "available": True,
            "version": __version__,
            "mode": "agent",
            "local_process": True,
            "otbr_local_diagnostics": False,
            "otbr_internal_trel_peer_table": False,
            "otbr_internal_trel_counters": False,
            "local_log_evidence": False,
            "docker_socket_available": False,
            "ssh_available": False,
            "mutation_allowed": False,
        },
    }


def _agent_capabilities_payload() -> dict[str, Any]:
    return {
        "agent": _agent_status_payload()["capabilities"],
        "site": {"name": "Home"},
    }


def _mock_transport(*, fail: bool = False) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if fail:
            raise httpx.ConnectError("connection failed", request=request)
        if request.url.path.endswith("/api/v1/agent/status"):
            return httpx.Response(200, json=_agent_status_payload())
        if request.url.path.endswith("/api/v1/agent/capabilities"):
            return httpx.Response(200, json=_agent_capabilities_payload())
        return httpx.Response(404)

    return httpx.MockTransport(handler)


@pytest.fixture
async def repository(tmp_path: Path) -> StorageRepository:
    database = Database(str(tmp_path / "threadlens.db"))
    repository = StorageRepository(database)
    await repository.initialize()
    yield repository
    await database.close()


@pytest.fixture
def config_with_agent() -> ThreadLensConfig:
    return ThreadLensConfig(
        mdns=MdnsConfig(enabled=False),
        otbrs=[
            OtbrConfig(
                id="study",
                name="Study OTBR",
                rest_url="http://127.0.0.1:8081",
                agent_url="http://127.0.0.1:8129",
            )
        ],
    )


@pytest.fixture
def config_without_agent() -> ThreadLensConfig:
    return ThreadLensConfig(
        mdns=MdnsConfig(enabled=False),
        otbrs=[
            OtbrConfig(
                id="study",
                name="Study OTBR",
                rest_url="http://127.0.0.1:8081",
                agent_url=None,
            )
        ],
    )


@pytest.mark.asyncio
async def test_agent_client_handles_reachable_agent(
    repository: StorageRepository,
    config_with_agent: ThreadLensConfig,
) -> None:
    client = httpx.AsyncClient(transport=_mock_transport())
    collector = AgentCollector(config_with_agent, repository, client=client)
    results = await collector.poll_all()
    assert len(results) == 1
    assert results[0].reachable is True
    assert results[0].capabilities.ssh_available is False
    assert results[0].capabilities.docker_socket_available is False
    stored = await repository.get_model_state(CurrentStateType.AGENT, "study", AgentState)
    assert stored is not None
    assert stored.reachable is True
    await collector.stop()


@pytest.mark.asyncio
async def test_agent_client_handles_unreachable_agent_without_crashing(
    repository: StorageRepository,
    config_with_agent: ThreadLensConfig,
) -> None:
    client = httpx.AsyncClient(transport=_mock_transport(fail=True))
    collector = AgentCollector(config_with_agent, repository, client=client)
    results = await collector.poll_all()
    assert len(results) == 1
    assert results[0].reachable is False
    assert results[0].last_error is not None
    status = collector.status()
    assert status["configured"] == 1
    assert status["unreachable"] == 1
    await collector.stop()


@pytest.mark.asyncio
async def test_agent_url_is_optional(
    repository: StorageRepository,
    config_without_agent: ThreadLensConfig,
) -> None:
    collector = AgentCollector(config_without_agent, repository)
    assert collector.configured_count == 0
    results = await collector.poll_all()
    assert results == []
    await collector.start()
    assert collector.running is False


@pytest.mark.asyncio
async def test_agent_collector_start_does_not_block_on_unreachable_agent(
    repository: StorageRepository,
    config_with_agent: ThreadLensConfig,
) -> None:
    client = httpx.AsyncClient(transport=_mock_transport(fail=True))
    collector = AgentCollector(config_with_agent, repository, client=client)
    await collector.start()
    assert collector.running is True
    assert collector.last_poll_at is not None
    await collector.stop()
