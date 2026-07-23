from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class PortfolioBrainState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    SCORED = "scored"
    POLICY_READY = "policy-ready"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    MONITORING = "monitoring"
    STABLE = "stable"
    RISK_PRESSURE = "risk-pressure"
    REGIME_SHIFT = "regime-shift"
    SIGNAL_CONFLICT = "signal-conflict"
    INFRASTRUCTURE_DEGRADED = "infrastructure-degraded"
    CAPITAL_REVIEW = "capital-review"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class IntelligenceSignal(BaseModel):
    domain: str = Field(min_length=1, max_length=100)
    signal_key: str = Field(min_length=1, max_length=160)
    direction: float = Field(ge=-1, le=1)
    severity: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    freshness: float = Field(ge=0, le=1)
    risk_blocked: bool = False
    provenance: List[str] = Field(default_factory=list)


class PortfolioBrainCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=160)
    signals: List[IntelligenceSignal] = Field(min_length=1)
    current_gross_exposure: float = Field(ge=0)
    current_net_exposure: float
    current_drawdown: float = Field(ge=0, le=1)
    liquidity_buffer: float = Field(ge=0, le=1)
    max_risk_pressure: float = Field(default=0.70, ge=0, le=1)
    requested_by: str = Field(min_length=1, max_length=120)


class PortfolioBrainScores(BaseModel):
    conviction: float
    risk_pressure: float
    regime_stability: float
    signal_coherence: float
    infrastructure_readiness: float
    liquidity_resilience: float
    decision_confidence: float


class PortfolioBrainRecommendation(BaseModel):
    action: str
    priority: int = Field(ge=1, le=5)
    rationale: str
    advisory_parameters: Dict[str, float] = Field(default_factory=dict)


class PortfolioBrainRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: PortfolioBrainState
    scores: PortfolioBrainScores
    recommendations: List[PortfolioBrainRecommendation]
    risk_flags: List[str]
    approved_by: Optional[str] = None
    version: int = 1


class PortfolioBrainAction(BaseModel):
    action: str = Field(pattern="^(score|submit-review|approve|activate|monitor|suspend|revoke|archive)$")
    actor: str = Field(min_length=1, max_length=120)
    operation_id: str = Field(min_length=1, max_length=160)
    reason: Optional[str] = Field(default=None, max_length=500)
