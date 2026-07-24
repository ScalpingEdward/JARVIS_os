from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class ThirdPartyRiskState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    ASSESSED = "assessed"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    MONITORING = "monitoring"
    ACCEPTABLE = "acceptable"
    DUE_DILIGENCE_GAP = "due-diligence-gap"
    CONCENTRATION_ALERT = "concentration-alert"
    SECURITY_ALERT = "security-alert"
    RESILIENCE_ALERT = "resilience-alert"
    CONTRACT_ALERT = "contract-alert"
    EXIT_RISK = "exit-risk"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class ThirdPartyObservation(BaseModel):
    provider_id: str = Field(min_length=1)
    provider_name: str = Field(min_length=1)
    service_domain: str = Field(min_length=1)
    criticality: float = Field(ge=0, le=1)
    due_diligence_coverage: float = Field(ge=0, le=1)
    security_assurance: float = Field(ge=0, le=1)
    privacy_assurance: float = Field(ge=0, le=1)
    operational_resilience: float = Field(ge=0, le=1)
    financial_health: float = Field(ge=0, le=1)
    subcontractor_transparency: float = Field(ge=0, le=1)
    concentration_dependency: float = Field(ge=0, le=1)
    contract_control_coverage: float = Field(ge=0, le=1)
    exit_plan_readiness: float = Field(ge=0, le=1)
    incident_history_score: float = Field(ge=0, le=1)
    open_high_findings: int = Field(ge=0)
    jurisdiction_risk: float = Field(ge=0, le=1)
    freshness: float = Field(ge=0, le=1, default=1.0)
    confidence: float = Field(ge=0, le=1, default=1.0)


class ThirdPartyRiskCreate(BaseModel):
    workspace_id: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    observations: List[ThirdPartyObservation] = Field(min_length=1)
    min_due_diligence_coverage: float = Field(ge=0, le=1, default=0.80)
    max_concentration_dependency: float = Field(ge=0, le=1, default=0.70)
    max_acceptable_residual_risk: float = Field(ge=0, le=1, default=0.45)

    @model_validator(mode="after")
    def unique_providers(self) -> "ThirdPartyRiskCreate":
        identities = [(item.provider_id, item.service_domain) for item in self.observations]
        if len(identities) != len(set(identities)):
            raise ValueError("duplicate provider/service-domain observation")
        return self


class ThirdPartyDisposition(BaseModel):
    provider_id: str
    provider_name: str
    service_domain: str
    assurance_score: float
    residual_risk: float
    lifecycle_signal: str
    required_actions: List[str] = Field(default_factory=list)


class ThirdPartyRiskScores(BaseModel):
    due_diligence_strength: float
    security_privacy_strength: float
    resilience_strength: float
    commercial_strength: float
    supply_chain_transparency: float
    exit_readiness: float
    concentration_resilience: float
    aggregate_assurance: float
    aggregate_residual_risk: float
    confidence: float


class ThirdPartyRiskRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: ThirdPartyRiskState
    scores: ThirdPartyRiskScores
    dispositions: List[ThirdPartyDisposition]
    risk_flags: List[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    version: int = 1


class ThirdPartyRiskAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None
