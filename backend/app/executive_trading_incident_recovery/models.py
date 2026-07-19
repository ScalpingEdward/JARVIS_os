from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class IncidentSeverity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class IncidentStatus(str, Enum):
    detected = "detected"
    contained = "contained"
    recovering = "recovering"
    resolved = "resolved"
    blocked = "blocked"


class RecoveryAction(str, Enum):
    observe = "observe"
    isolate = "isolate"
    restart = "restart"
    rollback = "rollback"
    failover = "failover"
    manual_intervention = "manual_intervention"
    remain_blocked = "remain_blocked"


class IncidentSignal(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    component: str = Field(min_length=1, max_length=100)
    severity: IncidentSeverity
    message: str = Field(min_length=1, max_length=500)
    blocking: bool = False
    recurrence_count: int = Field(default=1, ge=1)
    age_minutes: int = Field(default=0, ge=0)


class RecoveryInput(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    actor_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=160)
    symbol: str = Field(min_length=1, max_length=30)
    account_profile: str = Field(min_length=1, max_length=100)
    readiness_state: str = Field(default="blocked", max_length=30)
    trading_decision: str = Field(default="freeze", max_length=30)
    risk_state: str = Field(default="frozen", max_length=30)
    rollback_available: bool = False
    failover_available: bool = False
    restart_safe: bool = False
    data_integrity_score: float = Field(default=100, ge=0, le=100)
    recovery_confidence: float = Field(default=50, ge=0, le=100)
    incidents: list[IncidentSignal] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_incidents(self):
        codes = [item.code for item in self.incidents]
        if len(codes) != len(set(codes)):
            raise ValueError("Incident codes must be unique")
        return self


class RecoveryPlan(BaseModel):
    primary_action: RecoveryAction
    fallback_action: RecoveryAction
    ordered_steps: list[str]
    verification_checks: list[str]
    rollback_required: bool = False
    human_approval_required: bool = True


class RecoveryScores(BaseModel):
    incident_pressure: float = Field(ge=0, le=100)
    containment_readiness: float = Field(ge=0, le=100)
    recovery_readiness: float = Field(ge=0, le=100)
    resilience_score: float = Field(ge=0, le=100)
    restart_safety: float = Field(ge=0, le=100)


class IncidentRecoveryAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    actor_id: str
    source_key: str
    symbol: str
    account_profile: str
    status: IncidentStatus
    dominant_incident_code: str
    scores: RecoveryScores
    plan: RecoveryPlan
    reasons: list[str]
    trading_blocked: bool = True
    autonomous_recovery_enabled: bool = False
    created_at: datetime


class RecoveryStatusResponse(BaseModel):
    version: str = "18.38"
    assessments: int
    active_incidents: int
    critical_incidents: int
    recovery_ready: int
    resolved: int
    autonomous_recovery_enabled: bool = False


class RecoveryListResponse(BaseModel):
    items: list[IncidentRecoveryAssessment]
    count: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    action: str
    actor_id: str
    assessment_id: UUID | None = None
    details: dict = Field(default_factory=dict)
    created_at: datetime
