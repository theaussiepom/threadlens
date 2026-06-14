"""Scheduled Matter read reachability probe loop (read-only, conservative)."""

from __future__ import annotations

import asyncio
import contextlib
import random
from collections.abc import Awaitable, Callable

from threadlens.collectors.matter_probes import MatterProbeRunResult
from threadlens.config import MatterProbeConfig


class MatterProbeScheduler:
    """Run periodic read probes for available nodes when explicitly enabled."""

    def __init__(
        self,
        *,
        config: MatterProbeConfig,
        list_available_node_ids: Callable[[], list[int]],
        run_probe: Callable[[int], Awaitable[MatterProbeRunResult]],
        is_running: Callable[[], bool],
        is_connected: Callable[[], bool],
        random_jitter: Callable[[int], int] | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        self._config = config
        self._list_available_node_ids = list_available_node_ids
        self._run_probe = run_probe
        self._is_running = is_running
        self._is_connected = is_connected
        self._random_jitter = random_jitter or (lambda maximum: random.randint(0, maximum))
        self._sleep = sleep or asyncio.sleep
        self._task: asyncio.Task[None] | None = None
        self._round_robin_index = 0

    @property
    def active(self) -> bool:
        return self._task is not None and not self._task.done()

    def should_run(self) -> bool:
        return self._config.probes_active and self._config.schedule_enabled

    async def start(self) -> None:
        if self._task is not None or not self.should_run():
            return
        self._task = asyncio.create_task(self._loop(), name="matter-probe-scheduler")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def _loop(self) -> None:
        initial_delay = self._initial_delay_seconds()
        await self._sleep(initial_delay)

        while self._is_running():
            if not self.should_run():
                await self._sleep(60.0)
                continue

            if not self._is_connected():
                await self._sleep(30.0)
                continue

            await self._run_cycle()

            delay = self._config.interval_seconds + self._random_jitter(self._config.jitter_seconds)
            await self._sleep(float(delay))

    def _initial_delay_seconds(self) -> float:
        """Avoid probing all nodes immediately on startup."""
        jitter = float(self._random_jitter(self._config.jitter_seconds))
        return max(jitter, self._config.interval_seconds * 0.1)

    async def _run_cycle(self) -> None:
        node_ids = sorted(self._list_available_node_ids())
        if not node_ids:
            return

        limit = max(1, self._config.max_concurrent)
        selected: list[int] = []
        for offset in range(min(limit, len(node_ids))):
            index = (self._round_robin_index + offset) % len(node_ids)
            selected.append(node_ids[index])
        self._round_robin_index = (self._round_robin_index + len(selected)) % len(node_ids)

        semaphore = asyncio.Semaphore(limit)

        async def _probe_one(node_id: int) -> None:
            async with semaphore:
                try:
                    await self._run_probe(node_id)
                except Exception:  # noqa: BLE001 - probe errors must not crash observer
                    return

        await asyncio.gather(*[_probe_one(node_id) for node_id in selected], return_exceptions=True)
