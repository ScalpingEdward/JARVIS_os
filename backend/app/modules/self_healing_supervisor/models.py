from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class SupervisorState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    MONITORING = "monitoring"
    DEGRADED = "degraded"
    RECOVERY_PROPOSED = "recovery-proposed"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    APPROVED = "approved"
    RECOVERING = "recovering"
    STABILIZING = "stabilizing"
    HEALTHY = "healthy"
    FAILED = "failed"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"


class RiskDecision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class SignalSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class HealthSignal(BaseModel):
    signal_id: str = Field(min_length=1, max_length=160)
    source: str = Field(min_length=1, max_length=180)
    metric: str = Field(min_length=1, max_length=180)
    status: HealthStatus
    severity: SignalSeverity
    observed_value: float | int | str | bool | None = None
    threshold: float | int | str | bool | None = None
    evidence_refs: list[str] = Field(min_length=1)
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class RecoveryCandidate(BaseModel):
    candidate_id: str = Field(min_length=1, max_length=160)
    orchestration_id: str = Field(min_length=1, max_length=180)
    trigger_signal_ids: list[str] = Field(min_length=1)
    expected_outcome: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0, le=1)
    blast_radius: str = Field(min_length=1, max_length=240)
    evidence_refs: list[str] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SupervisorCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=180)
    target_system: str = Field(min_length=1, max_length=240)
    health_signals: list[HealthSignal] = Field(min_length=1)
    recovery_candidates: list[RecoveryCandidate] = Field(default_factory=list)
    required_healthy_cycles: int = Field(default=3, ge=1, le=100)
    max_recovery_attempts: int = Field(default=3, ge=1, le=20)
    monitoring_evidence_refs: list[str] = Field(min_length=1)
    risk_decision: RiskDecision = RiskDecision.ALLOW
    risk_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_supervisor(self) -> "SupervisorCreate":
        signal_ids = [signal.signal_id for signal in self.health_signals]
        if len(signal_ids) != len(set(signal_ids)):
            raise ValueError("signal_id values must be unique")
        candidate_ids = [candidate.candidate_id for candidate in self.recovery_candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("candidate_id values must be unique")
        known = set(signal_ids)
        for candidate in self.recovery_candidates:
            if not set(candidate.trigger_signal_ids).issubset(known):
                raise ValueError("candidate trigger signals must reference known health signals")
        return self


class SupervisorActionRequest(BaseModel):
    action: str = Field(pattern="^(start-monitoring|ingest-signal|propose-recovery|request-review|approve|start-recovery|record-cycle|complete-recovery|fail-recovery|suspend|resume|archive)$")
    actor: str = Field(min_length=1, max_length=180)
    approval_token: str | None = Field(default=None, max_length=240)
    receipt_id: str | None = Field(default=None, max_length=240)
    signal: HealthSignal | None = None
    candidate_id: str | None = Field(default=None, max_length=160)
    recovery_evidence_refs: list[str] = Field(default_factory=list)
    healthy_cycle: bool | None = None
    note: str | None = Field(default=None, max_length=1000)


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    record_id: str
    workspace_id: str
    action: str
    actor: str
    from_state: SupervisorState | None = None
    to_state: SupervisorState
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = Field(default_factory=dict)


class SelfHealingSupervisor(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    target_system: str
    health_signals: list[HealthSignal]
    recovery_candidates: list[RecoveryCandidate]
    required_healthy_cycles: int
    max_recovery_attempts: int
    monitoring_evidence_refs: list[str]
    risk_decision: RiskDecision
    risk_reason: str | None = None
    state: SupervisorState = SupervisorState.DRAFT
    selected_candidate_id: str | None = None
    approval_actor: str | None = None
    recovery_attempts: int = 0
    consecutive_healthy_cycles: int = 0
    recovery_evidence_refs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
