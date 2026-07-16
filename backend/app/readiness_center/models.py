from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class CheckState(StrEnum):
    ready = "ready"
    degraded = "degraded"
    blocked = "blocked"
    disabled = "disabled"
    unknown = "unknown"


class CheckCategory(StrEnum):
    core = "core"
    database = "database"
    cache = "cache"
    provider = "provider"
    connector = "connector"
    security = "security"
    trading = "trading"
    notifications = "notifications"
    voice = "voice"
    research = "research"


class DiagnosticCheckCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    category: CheckCategory
    state: CheckState
    required: bool = True
    latency_ms: int | None = Field(default=None, ge=0)
    detail: str = Field(default="", max_length=1000)
    remediation: str | None = Field(default=None, max_length=1000)
    dependency_names: list[str] = Field(default_factory=list, max_length=20)


class DiagnosticCheck(DiagnosticCheckCreate):
    id: UUID = Field(default_factory=uuid4)
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReadinessRunCreate(BaseModel):
    environment: str = Field(default="local", min_length=2, max_length=40)
    owner_salutation: str = Field(default="MASTER Brano", min_length=2, max_length=80)
    checks: list[DiagnosticCheckCreate] = Field(default_factory=list, max_length=100)


class ReadinessRun(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    environment: str
    owner_salutation: str
    state: CheckState
    score: float = Field(ge=0, le=1)
    launch_allowed: bool
    automatic_execution_enabled: bool = False
    automatic_order_execution_enabled: bool = False
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    checks: list[DiagnosticCheck] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReadinessRunList(BaseModel):
    items: list[ReadinessRun]
    count: int


class ReadinessStatus(BaseModel):
    latest_state: CheckState = CheckState.unknown
    latest_score: float = 0
    total_runs: int = 0
    launch_allowed: bool = False
    open_blockers: int = 0
    automatic_execution_enabled: bool = False
    automatic_order_execution_enabled: bool = False
