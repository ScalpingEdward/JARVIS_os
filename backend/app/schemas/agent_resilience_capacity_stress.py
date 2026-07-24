from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class CapacityStressState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_READY = "evidence-ready"
    ASSESSED = "assessed"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    MONITORING = "monitoring"
    VERIFIED = "verified"
    CAPACITY_ALERT = "capacity-alert"
    SATURATION_ALERT = "saturation-alert"
    RECOVERY_ALERT = "recovery-alert"
    DEPENDENCY_ALERT = "dependency-alert"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class CapacityStressObservation(BaseModel):
    agent_id: str = Field(min_length=1, max_length=160)
    agent_version: str = Field(min_length=1, max_length=80)
    scenario_id: str = Field(min_length=1, max_length=160)
    load_headroom: float = Field(ge=0.0, le=1.0)
    concurrency_headroom: float = Field(ge=0.0, le=1.0)
    queue_headroom: float = Field(ge=0.0, le=1.0)
    latency_stability: float = Field(ge=0.0, le=1.0)
    error_stability: float = Field(ge=0.0, le=1.0)
    resource_efficiency: float = Field(ge=0.0, le=1.0)
    dependency_capacity: float = Field(ge=0.0, le=1.0)
    degradation_quality: float = Field(ge=0.0, le=1.0)
    recovery_readiness: float = Field(ge=0.0, le=1.0)
    observability_coverage: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    freshness: float = Field(ge=0.0, le=1.0)
    saturation_events: int = Field(default=0, ge=0)
    failed_recovery_checks: int = Field(default=0, ge=0)
    dependency_bottlenecks: int = Field(default=0, ge=0)
    criticality: float = Field(default=0.5, ge=0.0, le=1.0)


class CapacityStressCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=200)
    requested_by: str = Field(min_length=1, max_length=160)
    observations: List[CapacityStressObservation] = Field(min_length=1)
    min_headroom: float = Field(default=0.30, ge=0.0, le=1.0)
    min_stability: float = Field(default=0.85, ge=0.0, le=1.0)
    min_recovery: float = Field(default=0.90, ge=0.0, le=1.0)
    max_residual_risk: float = Field(default=0.30, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def unique_scenarios(self):
        keys = [(o.agent_id, o.scenario_id) for o in self.observations]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate agent/scenario observation")
        return self


class CapacityStressDisposition(BaseModel):
    agent_id: str
    agent_version: str
    scenario_id: str
    assurance: float = Field(ge=0.0, le=1.0)
    residual_risk: float = Field(ge=0.0, le=1.0)
    lifecycle_signal: str
    required_actions: List[str] = Field(default_factory=list)


class CapacityStressScores(BaseModel):
    headroom_assurance: float = Field(ge=0.0, le=1.0)
    stability_assurance: float = Field(ge=0.0, le=1.0)
    dependency_assurance: float = Field(ge=0.0, le=1.0)
    recovery_assurance: float = Field(ge=0.0, le=1.0)
    observability_assurance: float = Field(ge=0.0, le=1.0)
    aggregate_assurance: float = Field(ge=0.0, le=1.0)
    aggregate_residual_risk: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)


class CapacityStressRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: CapacityStressState
    scores: CapacityStressScores
    dispositions: List[CapacityStressDisposition]
    risk_flags: List[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    version: int = 1


class CapacityStressAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None
