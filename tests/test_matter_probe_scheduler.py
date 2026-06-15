"""Tests for scheduled Matter read probe loop."""

from __future__ import annotations

import asyncio

import pytest

from threadlens.collectors.matter_probe_scheduler import MatterProbeScheduler
from threadlens.collectors.matter_probes import MatterProbeRunResult
from threadlens.config import MatterProbeAdvancedConfig, MatterProbeConfig, ProbeMode


class FakeSleep:
    def __init__(self) -> None:
        self.calls: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


@pytest.mark.asyncio
async def test_scheduler_does_not_start_when_disabled() -> None:
    config = MatterProbeConfig(mode=ProbeMode.DISABLED, schedule_enabled=False)
    scheduler = MatterProbeScheduler(
        config=config,
        list_available_node_ids=lambda: [1, 2],
        run_probe=_never_probe,
        is_running=lambda: True,
        is_connected=lambda: True,
    )
    await scheduler.start()
    assert scheduler.active is False


@pytest.mark.asyncio
async def test_scheduler_does_not_start_when_schedule_disabled() -> None:
    config = MatterProbeConfig(mode=ProbeMode.CONSERVATIVE, schedule_enabled=False)
    scheduler = MatterProbeScheduler(
        config=config,
        list_available_node_ids=lambda: [1],
        run_probe=_never_probe,
        is_running=lambda: True,
        is_connected=lambda: True,
    )
    await scheduler.start()
    assert scheduler.active is False


@pytest.mark.asyncio
async def test_scheduler_runs_cycle_when_enabled() -> None:
    probed: list[int] = []
    sleep = FakeSleep()
    state = {"running": True}
    config = MatterProbeConfig(
        mode=ProbeMode.CONSERVATIVE,
        schedule_enabled=True,
        advanced=MatterProbeAdvancedConfig(
            interval_seconds=60,
            jitter_seconds=0,
            max_concurrent=1,
        ),
    )

    async def run_probe(node_id: int) -> MatterProbeRunResult:
        probed.append(node_id)
        state["running"] = False
        return MatterProbeRunResult(node_id=node_id, read_probe_attempted=True, read_probe_ok=True)

    scheduler = MatterProbeScheduler(
        config=config,
        list_available_node_ids=lambda: [7, 8],
        run_probe=run_probe,
        is_running=lambda: state["running"],
        is_connected=lambda: True,
        random_jitter=lambda _maximum: 0,
        sleep=sleep,
    )

    await scheduler.start()
    await asyncio.sleep(0.05)
    await scheduler.stop()

    assert probed == [7]
    assert sleep.calls


@pytest.mark.asyncio
async def test_scheduler_respects_max_concurrent_per_cycle() -> None:
    active = 0
    peak = 0
    probed: list[int] = []
    state = {"running": True, "cycles": 0}

    class CycleSleep:
        async def __call__(self, seconds: float) -> None:
            if seconds >= 60:
                state["running"] = False

    config = MatterProbeConfig(
        mode=ProbeMode.CONSERVATIVE,
        schedule_enabled=True,
        advanced=MatterProbeAdvancedConfig(
            interval_seconds=60,
            jitter_seconds=0,
            max_concurrent=2,
        ),
    )

    async def run_probe(node_id: int) -> MatterProbeRunResult:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        probed.append(node_id)
        await asyncio.sleep(0.01)
        active -= 1
        return MatterProbeRunResult(node_id=node_id, read_probe_attempted=True, read_probe_ok=True)

    scheduler = MatterProbeScheduler(
        config=config,
        list_available_node_ids=lambda: [1, 2, 3, 4],
        run_probe=run_probe,
        is_running=lambda: state["running"],
        is_connected=lambda: True,
        random_jitter=lambda _maximum: 0,
        sleep=CycleSleep(),
    )

    await scheduler.start()
    await asyncio.sleep(0.1)
    await scheduler.stop()

    assert len(probed) == 2
    assert peak <= 2


@pytest.mark.asyncio
async def test_scheduler_handles_probe_errors_without_crashing() -> None:
    sleep = FakeSleep()
    state = {"running": True}
    config = MatterProbeConfig(
        mode=ProbeMode.CONSERVATIVE,
        schedule_enabled=True,
        advanced=MatterProbeAdvancedConfig(jitter_seconds=0),
    )

    async def run_probe(_node_id: int) -> MatterProbeRunResult:
        state["running"] = False
        raise RuntimeError("probe boom")

    scheduler = MatterProbeScheduler(
        config=config,
        list_available_node_ids=lambda: [1],
        run_probe=run_probe,
        is_running=lambda: state["running"],
        is_connected=lambda: True,
        random_jitter=lambda _maximum: 0,
        sleep=sleep,
    )

    await scheduler.start()
    await asyncio.sleep(0.05)
    await scheduler.stop()
    assert scheduler.active is False


@pytest.mark.asyncio
async def test_scheduler_stops_cleanly() -> None:
    sleep = FakeSleep()
    config = MatterProbeConfig(
        mode=ProbeMode.CONSERVATIVE,
        schedule_enabled=True,
        advanced=MatterProbeAdvancedConfig(jitter_seconds=0),
    )
    scheduler = MatterProbeScheduler(
        config=config,
        list_available_node_ids=lambda: [],
        run_probe=_never_probe,
        is_running=lambda: True,
        is_connected=lambda: True,
        random_jitter=lambda _maximum: 0,
        sleep=sleep,
    )
    await scheduler.start()
    assert scheduler.active is True
    await scheduler.stop()
    assert scheduler.active is False


async def _never_probe(_node_id: int) -> MatterProbeRunResult:
    raise AssertionError("probe should not run")
