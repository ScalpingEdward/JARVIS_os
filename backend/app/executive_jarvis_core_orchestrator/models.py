from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class JarvisCoreState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    INPUT_INVALID = "input-invalid"
    PLAN_PENDING = "plan-pending"
    APPROVAL_REQUIRED = "approval-required"
    READY = "ready"
    EXECUTING = "executing"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    ARCHIVED = "archived"


class ModuleCommand(BaseModel):
    module: str = Field(min_length=1, max_length=120)
    action: str = Field(min_length=1, max_length=160)
    parameters: dict[str, object] = Field(default_factory=dict)
    requires_human_approval: bool = True
    protective_only: bool = False


class JarvisCoreCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=160)
    actor_id: str = Field(min_length=1, max_length=100)
    objective: str = Field(min_length=3, max_length=2000)
    upstream_risk_brain_blocked: bool = False
    market_permission_v19_08: bool = False
    shadow_validation_v19_09: bool = False
    journal_validation_v19_10: bool = False
    optimizer_approval_v19_11: bool = False
    governor_clearance_v19_12: bool = False
    human_approved: bool = False
    commands: list[ModuleCommand] = Field(min_length=1, max_length=50)


class JarvisCoreExecuteRequest(BaseModel):
    actor_id: str = Field(min_length=1, max_length=100)
    action: str = Field(pattern="^(approve|execute|complete|archive)$")
    human_approved: bool | None = None


class OrchestrationStep(BaseModel):
    order: int
    module: str
    action: str
    status: str = "pending"
    detail: str = ""


class JarvisCoreRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    state: JarvisCoreState
    detail: str
    request: JarvisCoreCreate
    plan: list[OrchestrationStep] = Field(default_factory=list)
    blocked_modules: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class JarvisCoreStatus(BaseModel):
    module: str = "executive-jarvis-core-orchestrator"
    version: str = "20.00"
    workspace_id: str
    total_records: int
    active_records: int
    blocked_records: int


class JarvisCoreAudit(BaseModel):
    record_id: UUID
    workspace_id: str
    actor_id: str
    action: str
    state: JarvisCoreState
    detail: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
