"""Event models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class EventSourceType(StrEnum):
    OTBR = "otbr"
    MATTER_SERVER = "matter_server"
    MDNS = "mdns"
    THREADLENS = "threadlens"
    AGENT = "agent"


class EventSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class EventSubjectType(StrEnum):
    THREAD_NETWORK = "thread_network"
    OTBR = "otbr"
    MATTER_SERVER = "matter_server"
    MATTER_NODE = "matter_node"
    TREL_SERVICE = "trel_service"
    MDNS_SERVICE = "mdns_service"


class Event(BaseModel):
    id: str
    timestamp: datetime
    source_type: EventSourceType
    source_id: str
    event_type: str
    severity: EventSeverity
    subject_type: EventSubjectType
    subject_id: str
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
