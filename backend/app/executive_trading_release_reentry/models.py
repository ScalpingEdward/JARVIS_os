from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class ReleaseState(str, Enum):
    blocked = "blocked"
    shadow_only = "shadow_only"
    reduced_live = "reduced_live"
    full_live = "full_live"


class VerificationState(str, Enum):
    passed = "passed"
    warning = "warning"
    failed = "failed"


class ReleaseGate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    state: VerificationState
    score: float = Field(default=100, ge=0, le=100)
    blocking: bool = True
    evidence: str = Field(default="", max_length=500)


class ReentryStage(BaseModel):
    stage: int = Field(ge=1, le=5)
    mode: ReleaseState
    max_risk_multiplier: float = Field(ge=0, le=1)
    minimum_observation_trades: int = Field(default=0, ge=0, le=1000)
    minimum_stable_minutes: int = Field(default=0, ge=0, le=10080)
    requirements: list[str] = Field(default_factory=list)


class ReleaseAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    actor_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=160)
    symbol: str = Field(min_length=1, max_length=30)
    account_profile: str = Field(min_length=1, max_length=100)
    incident_recovery_state: str = Field(default="resolved", max_length=40)
    readiness_state: str = Field(default="ready", max_length=40)
    risk_state: str = Field(default="normal", max_length=40)
    trading_decision: str = Field(default="approve", max_length=40)
    open_critical_incidents: int = Field(default=0, ge=0)
    open_warning_incidents: int = Field(default=0, ge=0)
    data_integrity_score: float = Field(default=100, ge=0, le=100)
    recovery_confidence: float = Field(default=80, ge=0, le=100)
    stability_score: float = Field(default=80, ge=0, le=100)
    verification_gates: list[ReleaseGate] = Field(default_factory=list)
    human_release_approved: bool = False
    requested_risk_multiplier: float = Field(default=1, ge=0, le=1)

    @model_validator(mode="after")
    def validate_gates(self):
        names = [gate.name for gate in self.verification_gates]
        if len(names) != len(set(names)):
            raise ValueError("Release gate names must be unique")
        return self


class ReleaseScores(BaseModel):
    recovery_validation: float = Field(ge=0, le=100)
    operational_stability: float = Field(ge=0, le=100)
    risk_clearance: float = Field(ge=0, le=100)
    evidence_quality: float = Field(ge=0, le=100)
    release_confidence: float = Field(ge=0, le=100)


class ReleaseAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    actor_id: str
    source_key: str
    symbol: str
    account_profile: str
    state: ReleaseState
    approved_risk_multiplier: float = Field(ge=0, le=1)
    scores: ReleaseScores
    failed_gates: list[str]
    warnings: list[str]
    reasons: list[str]
    reentry_plan: list[ReentryStage]
    human_release_required: bool = True
    autonomous_release_enabled: bool = False
    assessed_at: datetime


class ReleaseStatusResponse(BaseModel):
    version: str = "18.39"
    assessments: int
    blocked: int
    shadow_only: int
    reduced_live: int
    full_live: int
    autonomous_release_enabled: bool = False


class ReleaseListResponse(BaseModel):
    items: list[ReleaseAssessment]
    count: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    action: str
    actor_id: str
    assessment_id: UUID | None = None
    details: dict = Field(default_factory=dict)
    created_at: datetime
