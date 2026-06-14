"""Tests for Matter websocket request/response correlation."""

from __future__ import annotations

import asyncio

import pytest

from threadlens.collectors.matter_ws import (
    MAX_ERROR_DETAILS_LEN,
    MatterCommandResult,
    MatterWebsocketRequestManager,
    sanitize_error_details,
)


@pytest.mark.asyncio
async def test_correlated_success_response_resolves_pending_request() -> None:
    manager = MatterWebsocketRequestManager()
    manager.register("req-1")

    async def _wait() -> MatterCommandResult:
        return await manager.wait_for("req-1", timeout=1.0)

    waiter = asyncio.create_task(_wait())
    await asyncio.sleep(0)
    assert manager.dispatch_incoming({"message_id": "req-1", "result": {"0/40/5": "Blind"}})

    result = await waiter
    assert result.ok is True
    assert result.result == {"0/40/5": "Blind"}
    assert result.timed_out is False
    assert result.duration_ms is not None
    assert manager.pending_count == 0


@pytest.mark.asyncio
async def test_correlated_error_response_resolves_with_ok_false() -> None:
    manager = MatterWebsocketRequestManager()
    manager.register("req-err")

    async def _wait() -> MatterCommandResult:
        return await manager.wait_for("req-err", timeout=1.0)

    waiter = asyncio.create_task(_wait())
    await asyncio.sleep(0)
    assert manager.dispatch_incoming(
        {"message_id": "req-err", "error_code": 5, "details": "Node not ready"}
    )

    result = await waiter
    assert result.ok is False
    assert result.error_code == 5
    assert result.details == "Node not ready"
    assert result.timed_out is False
    assert manager.pending_count == 0


@pytest.mark.asyncio
async def test_timeout_cleans_pending_map() -> None:
    manager = MatterWebsocketRequestManager()
    manager.register("req-timeout")

    result = await manager.wait_for("req-timeout", timeout=0.05)
    assert result.ok is False
    assert result.timed_out is True
    assert result.duration_ms is not None
    assert manager.pending_count == 0


@pytest.mark.asyncio
async def test_non_correlated_event_is_not_consumed() -> None:
    manager = MatterWebsocketRequestManager()
    assert manager.dispatch_incoming({"event": "node_updated", "data": {"node_id": 1}}) is False
    assert manager.pending_count == 0


@pytest.mark.asyncio
async def test_unknown_message_id_is_not_consumed() -> None:
    manager = MatterWebsocketRequestManager()
    assert manager.dispatch_incoming({"message_id": "unknown", "result": []}) is False
    assert manager.pending_count == 0


@pytest.mark.asyncio
async def test_multiple_pending_requests_resolve_independently() -> None:
    manager = MatterWebsocketRequestManager()
    manager.register("a")
    manager.register("b")

    async def _wait_a() -> MatterCommandResult:
        return await manager.wait_for("a", timeout=1.0)

    async def _wait_b() -> MatterCommandResult:
        return await manager.wait_for("b", timeout=1.0)

    task_a = asyncio.create_task(_wait_a())
    task_b = asyncio.create_task(_wait_b())
    await asyncio.sleep(0)

    assert manager.dispatch_incoming({"message_id": "a", "result": "alpha"})
    assert manager.dispatch_incoming({"message_id": "b", "result": "beta"})

    result_a = await task_a
    result_b = await task_b
    assert result_a.ok and result_a.result == "alpha"
    assert result_b.ok and result_b.result == "beta"
    assert manager.pending_count == 0


@pytest.mark.asyncio
async def test_cancel_all_fails_pending_requests() -> None:
    manager = MatterWebsocketRequestManager()
    manager.register("req-1")
    manager.register("req-2")

    async def _wait() -> MatterCommandResult:
        return await manager.wait_for("req-1", timeout=1.0)

    waiter = asyncio.create_task(_wait())
    await asyncio.sleep(0)
    manager.cancel_all(reason="connection closed")
    result = await waiter
    assert result.ok is False
    assert result.details == "connection closed"
    assert manager.pending_count == 0


def test_sanitize_error_details_truncates_long_text() -> None:
    long_text = "x" * (MAX_ERROR_DETAILS_LEN + 50)
    sanitized = sanitize_error_details(long_text)
    assert sanitized is not None
    assert len(sanitized) == MAX_ERROR_DETAILS_LEN + 3
    assert sanitized.endswith("...")


def test_sanitize_error_details_handles_none_and_blank() -> None:
    assert sanitize_error_details(None) is None
    assert sanitize_error_details("   ") is None


def test_register_rejects_duplicate_message_id() -> None:
    async def _run() -> None:
        manager = MatterWebsocketRequestManager()
        manager.register("dup")
        with pytest.raises(ValueError, match="Duplicate message_id"):
            manager.register("dup")

    asyncio.run(_run())
