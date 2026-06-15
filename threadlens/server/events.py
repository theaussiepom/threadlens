"""SSE event broadcasting for dashboard live updates."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncIterator, Callable
from typing import Any


class DashboardBroadcaster:
    """Fan-out SSE notifications to connected dashboard clients."""

    def __init__(self) -> None:
        self._queues: list[asyncio.Queue[dict[str, Any]]] = []
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = threading.Lock()

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def subscribe(self) -> AsyncIterator[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        with self._lock:
            self._queues.append(queue)
        try:
            while True:
                item = await queue.get()
                yield item
        finally:
            with self._lock:
                if queue in self._queues:
                    self._queues.remove(queue)

    def publish_sync(self, event: str, data: dict[str, Any]) -> None:
        payload = {"event": event, "data": data}
        with self._lock:
            queues = list(self._queues)
        if not queues or self._loop is None:
            return
        for queue in queues:

            def _put(q: asyncio.Queue[dict[str, Any]] = queue) -> None:
                q.put_nowait(payload)

            self._loop.call_soon_threadsafe(_put)

    def notify(self, event: str = "dashboard_updated") -> None:
        self.publish_sync(event, {"type": event})


def storage_change_listener(broadcaster: DashboardBroadcaster) -> Callable[[], None]:
    """Return a sync callback suitable for StorageRepository on_change hooks."""

    def _notify() -> None:
        broadcaster.notify()

    return _notify
