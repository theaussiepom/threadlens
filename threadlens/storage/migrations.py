"""Schema versioning and bootstrap."""

from __future__ import annotations

import aiosqlite

SCHEMA_VERSION = 1

_CREATE_CURRENT_STATE = """
CREATE TABLE IF NOT EXISTS current_state (
    object_type TEXT NOT NULL,
    object_id TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (object_type, object_id)
)
"""

_CREATE_EVENTS = """
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    subject_type TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    message TEXT NOT NULL,
    data_json TEXT NOT NULL DEFAULT '{}'
)
"""

_CREATE_AGGREGATES = """
CREATE TABLE IF NOT EXISTS aggregates (
    bucket_start TEXT NOT NULL,
    bucket_size TEXT NOT NULL,
    metric TEXT NOT NULL,
    subject_type TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    data_json TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (bucket_start, bucket_size, metric, subject_type, subject_id)
)
"""

_CREATE_METADATA = """
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_events_event_type ON events(event_type)",
    "CREATE INDEX IF NOT EXISTS idx_events_subject ON events(subject_type, subject_id)",
    "CREATE INDEX IF NOT EXISTS idx_events_source ON events(source_type, source_id)",
    "CREATE INDEX IF NOT EXISTS idx_aggregates_bucket ON aggregates(bucket_start, bucket_size)",
    (
        "CREATE INDEX IF NOT EXISTS idx_aggregates_metric "
        "ON aggregates(metric, subject_type, subject_id)"
    ),
]

_SCHEMA_STATEMENTS = [
    _CREATE_CURRENT_STATE,
    _CREATE_EVENTS,
    _CREATE_AGGREGATES,
    _CREATE_METADATA,
    *_INDEXES,
]


async def initialize_schema(connection: aiosqlite.Connection) -> None:
    """Create tables and indexes idempotently."""
    for statement in _SCHEMA_STATEMENTS:
        await connection.execute(statement)
    await connection.commit()
