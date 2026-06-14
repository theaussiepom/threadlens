"""Database connection and schema bootstrap."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

from threadlens.storage.migrations import initialize_schema


class Database:
    """Async SQLite database wrapper."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._connection: aiosqlite.Connection | None = None

    @property
    def is_connected(self) -> bool:
        return self._connection is not None

    async def connect(self) -> None:
        if self._connection is not None:
            return
        if self.path != Path(":memory:"):
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = await aiosqlite.connect(self.path)
        self._connection.row_factory = aiosqlite.Row
        await self._connection.execute("PRAGMA journal_mode=WAL")
        await self._connection.execute("PRAGMA foreign_keys=ON")
        await initialize_schema(self._connection)

    async def close(self) -> None:
        if self._connection is None:
            return
        await self._connection.close()
        self._connection = None

    def connection(self) -> aiosqlite.Connection:
        if self._connection is None:
            raise RuntimeError("Database is not connected")
        return self._connection

    @asynccontextmanager
    async def session(self) -> AsyncIterator[aiosqlite.Connection]:
        await self.connect()
        yield self.connection()


async def open_database(path: str | Path) -> Database:
    database = Database(path)
    await database.connect()
    return database
