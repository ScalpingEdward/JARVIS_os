from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ConnectorOperation(str, Enum):
    read = "read"
    write = "write"
    execute = "execute"
    health = "health"


class ConnectorInvocation(BaseModel):
    operation: ConnectorOperation
    action: str = Field(min_length=1, max_length=120)
    resource: str | None = Field(default=None, max_length=1000)
    payload: dict[str, Any] = Field(default_factory=dict)
    actor: str = Field(default="human", min_length=1, max_length=120)
    idempotency_key: str | None = Field(default=None, max_length=200)


class ConnectorInvocationResult(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    connector_id: UUID
    adapter: str
    action: str
    ok: bool
    status_code: int | None = None
    data: Any = None
    error: str | None = None
    attempts: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConnectorImplementationStatus(BaseModel):
    supported_adapters: list[str]
    registered_connectors: int
    invocations: int
    secret_resolution: str = "environment-reference-only"
    automatic_order_execution: bool = False
    automatic_merge: bool = False
