from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ObservabilityState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    INCIDENT_OPEN = "incident-open"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    SELF_HEALING = "self-healing"
    RECOVERY_VERIFYING = "recovery-verifying"
    RECOVERED = "recovered"
    ROLLBACK_REQUIRED = "rollback-required"
    FAILED = "failed"
    ARCHIVED = "archived"


class RuntimeSnapshot(BaseModel):
    service_name: str = Field(min_length=1, max_length=120)
    release_version: str = Field(min_length=1, max_length=80)
    environment: str = Field(min_length=1, max_length=60)
    error_rate_pct: float = Field(ge=0, le=100)
    p95_latency_ms: float = Field(ge=0)
    health_checks_passed: bool = True
    data_feed_healthy: bool = True
    broker_connection_healthy: bool = True
    database_healthy: bool = True
    queue_healthy: bool = True
    vps_healthy: bool = True
    active_alerts: list[str] = Field(default_factory=list, max_length=50)


class ObservabilityLimits(BaseModel):
    max_error_rate_pct: float = Field(default=2.0, ge=0, le=100)
    max_p95_latency_ms: float = Field(default=1500, gt=0)


class ProductionObservabilityCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=160)
    actor_id: str = Field(min_length=1, max_length=100)
    v20_06_deployment_healthy: bool = False
    upstream_risk_brain_blocked: bool = False
    snapshot: RuntimeSnapshot
    limits: ObservabilityLimits = Field(default_factory=ObservabilityLimits)


class ObservabilityExecuteRequest(BaseModel):
    actor_id: str = Field(min_length=1, max_length=100)
    action: str = Field(pattern="^(start-self-healing|verify-recovery|require-rollback|archive)$")
    human_approved: bool | None = None
    recovery_checks_passed: bool | None = None


class IncidentFinding(BaseModel):
    category: str
    severity: str
    detail: str


class ProductionObservabilityRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    state: ObservabilityState
    detail: str
    request: ProductionObservabilityCreate
    severity: str = "none"
    findings: list[IncidentFinding] = Field(default_factory=list)
    allowed_actions: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProductionObservabilityStatus(BaseModel):
    module: str = "executive-production-observability"
    version: str = "20.07"
    workspace_id: str
    total_records: int
    open_incidents: int
    recovered_records: int


class ProductionObservabilityAudit(BaseModel):
    record_id: UUID
    workspace_id: str
    actor_id: str
    action: str
    state: ObservabilityState
    detail: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
