from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class PostRecoveryState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_READY = "evidence-ready"
    ASSESSED = "assessed"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    MONITORING = "monitoring"
    STABLE = "stable"
    HEALTH_ALERT = "health-alert"
    ERROR_BUDGET_ALERT = "error-budget-alert"
    REGRESSION_ALERT = "regression-alert"
    DEPENDENCY_ALERT = "dependency-alert"
    BUSINESS_ALERT = "business-alert"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class PostRecoveryObservation(BaseModel):
    agent_id: str = Field(min_length=1, max_length=160)
    agent_version: str = Field(min_length=1, max_length=80)
    window_id: str = Field(min_length=1, max_length=160)
    service_health: float = Field(ge=0.0, le=1.0)
    latency_stability: float = Field(ge=0.0, le=1.0)
    error_rate_stability: float = Field(ge=0.0, le=1.0)
    state_integrity: float = Field(ge=0.0, le=1.0)
    dependency_health: float = Field(ge=0.0, le=1.0)
    observability_coverage: float = Field(ge=0.0, le=1.0)
    business_kpi_stability: float = Field(ge=0.0, le=1.0)
    rollback_readiness: float = Field(ge=0.0, le=1.0)
    human_oncall_readiness: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    freshness: float = Field(ge=0.0, le=1.0)
    error_budget_remaining: float = Field(default=1.0, ge=0.0, le=1.0)
    reopened_incidents: int = Field(default=0, ge=0)
    regression_findings: int = Field(default=0, ge=0)
    dependency_incidents: int = Field(default=0, ge=0)
    business_impact_events: int = Field(default=0, ge=0)
    criticality: float = Field(default=0.5, ge=0.0, le=1.0)


class PostRecoveryCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=200)
    requested_by: str = Field(min_length=1, max_length=160)
    observations: List[PostRecoveryObservation] = Field(min_length=1)
    min_health: float = Field(default=0.90, ge=0.0, le=1.0)
    min_error_budget: float = Field(default=0.25, ge=0.0, le=1.0)
    max_residual_risk: float = Field(default=0.30, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def unique_windows(self):
        keys = [(o.agent_id, o.window_id) for o in self.observations]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate agent/window observation")
        return self


class PostRecoveryDisposition(BaseModel):
    agent_id: str
    agent_version: str
    window_id: str
    assurance: float = Field(ge=0.0, le=1.0)
    residual_risk: float = Field(ge=0.0, le=1.0)
    lifecycle_signal: str
    required_actions: List[str] = Field(default_factory=list)


class PostRecoveryScores(BaseModel):
    health_assurance: float = Field(ge=0.0, le=1.0)
    integrity_assurance: float = Field(ge=0.0, le=1.0)
    dependency_assurance: float = Field(ge=0.0, le=1.0)
    observability_assurance: float = Field(ge=0.0, le=1.0)
    business_assurance: float = Field(ge=0.0, le=1.0)
    aggregate_assurance: float = Field(ge=0.0, le=1.0)
    aggregate_residual_risk: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)


class PostRecoveryRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: PostRecoveryState
    scores: PostRecoveryScores
    dispositions: List[PostRecoveryDisposition]
    risk_flags: List[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    version: int = 1


class PostRecoveryAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None
