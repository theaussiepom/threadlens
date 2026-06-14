"""HTTP client for optional ThreadLens agent endpoints."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import httpx

from threadlens import __version__
from threadlens.config import OtbrConfig, ThreadLensConfig
from threadlens.models.agent import AgentApiCapabilities, AgentState, default_agent_capabilities
from threadlens.storage.repositories import CurrentStateType, StorageRepository
from threadlens.utils.time import utc_now

AGENT_REQUEST_TIMEOUT_SECONDS = 5.0
AGENT_POLL_INTERVAL_SECONDS = 60


class AgentCollector:
    """Poll configured OTBR agent URLs and persist reachability/capabilities."""

    def __init__(
        self,
        config: ThreadLensConfig,
        repository: StorageRepository,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config
        self._repository = repository
        self._client = client
        self._owns_client = client is None
        self._task: asyncio.Task[None] | None = None
        self._running = False
        self.last_poll_at: datetime | None = None
        self.reachable_count = 0
        self.unreachable_count = 0

    @property
    def running(self) -> bool:
        return self._running

    @property
    def configured_count(self) -> int:
        return sum(1 for otbr in self._config.otbrs if otbr.agent_url)

    async def start(self) -> None:
        if self._running or self.configured_count == 0:
            return
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=AGENT_REQUEST_TIMEOUT_SECONDS)
        self._running = True
        await self.poll_all()
        self._task = asyncio.create_task(self._poll_loop(), name="agent-collector")

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def poll_all(self) -> list[AgentState]:
        self.last_poll_at = utc_now()
        results: list[AgentState] = []
        self.reachable_count = 0
        self.unreachable_count = 0
        for otbr_config in self._config.otbrs:
            if not otbr_config.agent_url:
                continue
            state = await self.poll_one(otbr_config)
            results.append(state)
            if state.reachable:
                self.reachable_count += 1
            else:
                self.unreachable_count += 1
        return results

    async def poll_one(self, otbr_config: OtbrConfig) -> AgentState:
        if self._client is None:
            raise RuntimeError("Agent collector client is not initialized")
        agent_url = otbr_config.agent_url
        if not agent_url:
            return AgentState(
                otbr_id=otbr_config.id,
                agent_url="",
                reachable=False,
                last_error="agent_url not configured",
            )

        try:
            status_response = await self._client.get(f"{agent_url.rstrip('/')}/api/v1/agent/status")
            caps_response = await self._client.get(
                f"{agent_url.rstrip('/')}/api/v1/agent/capabilities"
            )
            if status_response.status_code != 200:
                return await self._mark_unreachable(
                    otbr_config,
                    last_error=f"status returned {status_response.status_code}",
                )
            if caps_response.status_code != 200:
                return await self._mark_unreachable(
                    otbr_config,
                    last_error=f"capabilities returned {caps_response.status_code}",
                )
            status_payload = status_response.json()
            caps_payload = caps_response.json()
            capabilities = _parse_capabilities(caps_payload)
            now = utc_now()
            state = AgentState(
                otbr_id=otbr_config.id,
                agent_url=agent_url,
                reachable=True,
                last_seen=now,
                last_error=None,
                capabilities=capabilities,
                status=status_payload,
            )
            await self._repository.upsert_model_state(
                CurrentStateType.AGENT,
                otbr_config.id,
                state,
            )
            return state
        except httpx.HTTPError as exc:
            return await self._mark_unreachable(otbr_config, last_error=str(exc))
        except Exception as exc:  # noqa: BLE001 - isolate agent failures
            return await self._mark_unreachable(otbr_config, last_error=str(exc))

    async def _mark_unreachable(self, otbr_config: OtbrConfig, *, last_error: str) -> AgentState:
        previous = await self._repository.get_model_state(
            CurrentStateType.AGENT,
            otbr_config.id,
            AgentState,
        )
        state = AgentState(
            otbr_id=otbr_config.id,
            agent_url=otbr_config.agent_url or "",
            reachable=False,
            last_seen=previous.last_seen if previous else None,
            last_error=last_error,
            capabilities=previous.capabilities
            if previous
            else default_agent_capabilities(__version__),
        )
        await self._repository.upsert_model_state(
            CurrentStateType.AGENT,
            otbr_config.id,
            state,
        )
        return state

    async def _poll_loop(self) -> None:
        while self._running:
            await self.poll_all()
            await asyncio.sleep(AGENT_POLL_INTERVAL_SECONDS)

    def status(self) -> dict[str, Any]:
        return {
            "configured": self.configured_count,
            "collector_running": self._running,
            "reachable": self.reachable_count,
            "unreachable": self.unreachable_count,
            "last_poll_at": self.last_poll_at.isoformat() if self.last_poll_at else None,
        }


def _parse_capabilities(payload: dict[str, Any]) -> AgentApiCapabilities:
    agent_payload = payload.get("agent", payload)
    if not isinstance(agent_payload, dict):
        return default_agent_capabilities(__version__)
    version = str(agent_payload.get("version", __version__))
    return AgentApiCapabilities(
        available=bool(agent_payload.get("available", True)),
        version=version,
        mode=str(agent_payload.get("mode", "agent")),
        local_process=bool(agent_payload.get("local_process", True)),
        otbr_local_diagnostics=bool(agent_payload.get("otbr_local_diagnostics", False)),
        otbr_internal_trel_peer_table=bool(
            agent_payload.get("otbr_internal_trel_peer_table", False)
        ),
        otbr_internal_trel_counters=bool(agent_payload.get("otbr_internal_trel_counters", False)),
        local_log_evidence=bool(agent_payload.get("local_log_evidence", False)),
        docker_socket_available=bool(agent_payload.get("docker_socket_available", False)),
        ssh_available=bool(agent_payload.get("ssh_available", False)),
        mutation_allowed=bool(agent_payload.get("mutation_allowed", False)),
    )
