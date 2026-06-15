"""Repository-style storage access."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from pydantic import BaseModel

from threadlens.models.events import Event
from threadlens.storage.db import Database
from threadlens.storage.migrations import SCHEMA_VERSION
from threadlens.utils.time import utc_now


class CurrentStateType(StrEnum):
    THREAD_ENVIRONMENT = "thread_environment"
    THREAD_NETWORK = "thread_network"
    OTBR = "otbr"
    MDNS_SERVICE = "mdns_service"
    TREL_SERVICE = "trel_service"
    MATTER_SERVER = "matter_server"
    MATTER_NODE = "matter_node"
    THREAD_DEVICE = "thread_device"
    AGENT = "agent"
    CAPABILITIES = "capabilities"


class AggregateBucketSize(StrEnum):
    HOUR = "hour"
    DAY = "day"


def _to_json(value: BaseModel | dict[str, Any]) -> str:
    if isinstance(value, BaseModel):
        return json.dumps(value.model_dump(mode="json"))
    return json.dumps(value, default=str)


def _from_json(payload: str) -> dict[str, Any]:
    loaded = json.loads(payload)
    if not isinstance(loaded, dict):
        raise ValueError("Expected JSON object payload")
    return loaded


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


class StorageRepository:
    """Async repository for ThreadLens persistence."""

    def __init__(self, database: Database) -> None:
        self._database = database

    async def initialize(self) -> None:
        await self._database.connect()
        await self.set_metadata("schema_version", SCHEMA_VERSION)

    async def upsert_current_state(
        self,
        object_type: str | CurrentStateType,
        object_id: str,
        payload: BaseModel | dict[str, Any],
        *,
        updated_at: datetime | None = None,
    ) -> None:
        timestamp = (updated_at or utc_now()).isoformat()
        payload_json = _to_json(payload)
        connection = self._database.connection()
        await connection.execute(
            """
            INSERT INTO current_state (object_type, object_id, updated_at, payload_json)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(object_type, object_id) DO UPDATE SET
                updated_at = excluded.updated_at,
                payload_json = excluded.payload_json
            """,
            (str(object_type), object_id, timestamp, payload_json),
        )
        await connection.commit()

    async def get_current_state(
        self,
        object_type: str | CurrentStateType,
        object_id: str,
    ) -> dict[str, Any] | None:
        connection = self._database.connection()
        cursor = await connection.execute(
            """
            SELECT payload_json, updated_at
            FROM current_state
            WHERE object_type = ? AND object_id = ?
            """,
            (str(object_type), object_id),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        payload = _from_json(row["payload_json"])
        payload["_updated_at"] = row["updated_at"]
        return payload

    async def delete_current_state(
        self,
        object_type: str | CurrentStateType,
        object_id: str,
    ) -> None:
        connection = self._database.connection()
        await connection.execute(
            "DELETE FROM current_state WHERE object_type = ? AND object_id = ?",
            (str(object_type), object_id),
        )
        await connection.commit()

    async def list_current_state(
        self,
        object_type: str | CurrentStateType | None = None,
    ) -> list[dict[str, Any]]:
        connection = self._database.connection()
        if object_type is None:
            cursor = await connection.execute(
                """
                SELECT object_type, object_id, updated_at, payload_json
                FROM current_state
                ORDER BY object_type, object_id
                """
            )
        else:
            cursor = await connection.execute(
                """
                SELECT object_type, object_id, updated_at, payload_json
                FROM current_state
                WHERE object_type = ?
                ORDER BY object_id
                """,
                (str(object_type),),
            )
        rows = await cursor.fetchall()
        results: list[dict[str, Any]] = []
        for row in rows:
            payload = _from_json(row["payload_json"])
            payload["_object_type"] = row["object_type"]
            payload["_object_id"] = row["object_id"]
            payload["_updated_at"] = row["updated_at"]
            results.append(payload)
        return results

    async def insert_event(self, event: Event) -> None:
        connection = self._database.connection()
        await connection.execute(
            """
            INSERT INTO events (
                id, timestamp, source_type, source_id, event_type, severity,
                subject_type, subject_id, message, data_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.id,
                event.timestamp.isoformat(),
                event.source_type.value,
                event.source_id,
                event.event_type,
                event.severity.value,
                event.subject_type.value,
                event.subject_id,
                event.message,
                _to_json(event.data),
            ),
        )
        await connection.commit()

    async def get_events(
        self,
        *,
        subject_type: str | None = None,
        subject_id: str | None = None,
        source_type: str | None = None,
        source_id: str | None = None,
        event_type: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int | None = None,
    ) -> list[Event]:
        clauses: list[str] = []
        params: list[Any] = []

        if subject_type is not None:
            clauses.append("subject_type = ?")
            params.append(subject_type)
        if subject_id is not None:
            clauses.append("subject_id = ?")
            params.append(subject_id)
        if source_type is not None:
            clauses.append("source_type = ?")
            params.append(source_type)
        if source_id is not None:
            clauses.append("source_id = ?")
            params.append(source_id)
        if event_type is not None:
            clauses.append("event_type = ?")
            params.append(event_type)
        if since is not None:
            clauses.append("timestamp >= ?")
            params.append(since.isoformat())
        if until is not None:
            clauses.append("timestamp <= ?")
            params.append(until.isoformat())

        query = "SELECT * FROM events"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY timestamp ASC"
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)

        connection = self._database.connection()
        cursor = await connection.execute(query, params)
        rows = await cursor.fetchall()
        return [self._row_to_event(row) for row in rows]

    async def count_events(
        self,
        *,
        subject_type: str | None = None,
        subject_id: str | None = None,
        source_type: str | None = None,
        source_id: str | None = None,
        event_type: str | None = None,
        event_types: list[str] | None = None,
        severity: str | None = None,
        severities: list[str] | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> int:
        clauses: list[str] = []
        params: list[Any] = []

        if subject_type is not None:
            clauses.append("subject_type = ?")
            params.append(subject_type)
        if subject_id is not None:
            clauses.append("subject_id = ?")
            params.append(subject_id)
        if source_type is not None:
            clauses.append("source_type = ?")
            params.append(source_type)
        if source_id is not None:
            clauses.append("source_id = ?")
            params.append(source_id)
        if event_type is not None:
            clauses.append("event_type = ?")
            params.append(event_type)
        if event_types:
            placeholders = ", ".join("?" for _ in event_types)
            clauses.append(f"event_type IN ({placeholders})")
            params.extend(event_types)
        if severity is not None:
            clauses.append("severity = ?")
            params.append(severity)
        if severities:
            placeholders = ", ".join("?" for _ in severities)
            clauses.append(f"severity IN ({placeholders})")
            params.extend(severities)
        if since is not None:
            clauses.append("timestamp >= ?")
            params.append(since.isoformat())
        if until is not None:
            clauses.append("timestamp <= ?")
            params.append(until.isoformat())

        query = "SELECT COUNT(*) AS count FROM events"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)

        connection = self._database.connection()
        cursor = await connection.execute(query, params)
        row = await cursor.fetchone()
        return int(row["count"])

    async def delete_events_before(self, cutoff: datetime) -> int:
        connection = self._database.connection()
        cursor = await connection.execute(
            "DELETE FROM events WHERE timestamp < ?",
            (cutoff.isoformat(),),
        )
        await connection.commit()
        return cursor.rowcount

    async def cleanup_events(self, retention_days: int) -> int:
        cutoff = utc_now() - timedelta(days=retention_days)
        return await self.delete_events_before(cutoff)

    async def increment_aggregate(
        self,
        *,
        bucket_start: datetime,
        bucket_size: str | AggregateBucketSize,
        metric: str,
        subject_type: str,
        subject_id: str,
        amount: int = 1,
        data: dict[str, Any] | None = None,
    ) -> None:
        connection = self._database.connection()
        await connection.execute(
            """
            INSERT INTO aggregates (
                bucket_start, bucket_size, metric, subject_type, subject_id, count, data_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(bucket_start, bucket_size, metric, subject_type, subject_id) DO UPDATE SET
                count = aggregates.count + excluded.count,
                data_json = CASE
                    WHEN excluded.data_json = '{}' THEN aggregates.data_json
                    ELSE excluded.data_json
                END
            """,
            (
                bucket_start.isoformat(),
                str(bucket_size),
                metric,
                subject_type,
                subject_id,
                amount,
                _to_json(data or {}),
            ),
        )
        await connection.commit()

    async def get_aggregates(
        self,
        *,
        bucket_size: str | AggregateBucketSize | None = None,
        metric: str | None = None,
        subject_type: str | None = None,
        subject_id: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []

        if bucket_size is not None:
            clauses.append("bucket_size = ?")
            params.append(str(bucket_size))
        if metric is not None:
            clauses.append("metric = ?")
            params.append(metric)
        if subject_type is not None:
            clauses.append("subject_type = ?")
            params.append(subject_type)
        if subject_id is not None:
            clauses.append("subject_id = ?")
            params.append(subject_id)
        if since is not None:
            clauses.append("bucket_start >= ?")
            params.append(since.isoformat())
        if until is not None:
            clauses.append("bucket_start <= ?")
            params.append(until.isoformat())

        query = "SELECT * FROM aggregates"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY bucket_start ASC"

        connection = self._database.connection()
        cursor = await connection.execute(query, params)
        rows = await cursor.fetchall()
        results: list[dict[str, Any]] = []
        for row in rows:
            results.append(
                {
                    "bucket_start": row["bucket_start"],
                    "bucket_size": row["bucket_size"],
                    "metric": row["metric"],
                    "subject_type": row["subject_type"],
                    "subject_id": row["subject_id"],
                    "count": row["count"],
                    "data": _from_json(row["data_json"]),
                }
            )
        return results

    async def set_metadata(self, key: str, value: Any) -> None:
        connection = self._database.connection()
        await connection.execute(
            """
            INSERT INTO metadata (key, value_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value_json = excluded.value_json,
                updated_at = excluded.updated_at
            """,
            (key, json.dumps(value, default=str), utc_now().isoformat()),
        )
        await connection.commit()

    async def get_metadata(self, key: str) -> Any | None:
        connection = self._database.connection()
        cursor = await connection.execute(
            "SELECT value_json FROM metadata WHERE key = ?",
            (key,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return json.loads(row["value_json"])

    @staticmethod
    def _row_to_event(row: Any) -> Event:
        return Event(
            id=row["id"],
            timestamp=_parse_datetime(row["timestamp"]),
            source_type=row["source_type"],
            source_id=row["source_id"],
            event_type=row["event_type"],
            severity=row["severity"],
            subject_type=row["subject_type"],
            subject_id=row["subject_id"],
            message=row["message"],
            data=_from_json(row["data_json"]),
        )

    async def upsert_model_state(
        self,
        object_type: str | CurrentStateType,
        object_id: str,
        model: BaseModel,
    ) -> None:
        await self.upsert_current_state(object_type, object_id, model)

    async def get_model_state(
        self,
        object_type: str | CurrentStateType,
        object_id: str,
        model_type: type[BaseModel],
    ) -> BaseModel | None:
        payload = await self.get_current_state(object_type, object_id)
        if payload is None:
            return None
        clean = {key: value for key, value in payload.items() if not key.startswith("_")}
        return model_type.model_validate(clean)
