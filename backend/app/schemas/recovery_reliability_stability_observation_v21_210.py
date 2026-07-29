from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

class ConsumerStabilityObservation(BaseModel):
    consumer_id: str
    workspace_id: str
    baseline_id: str
    baseline_version: int = Field(ge=1)
    baseline_digest: str
    observed_at: datetime
    healthy: bool
    dependency_satisfied: bool
    latency_quality: float = Field(ge=0.0, le=1.0)
    error_quality: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)

class StabilityObservationRequest(BaseModel):
    source_id: str
    source_state: str
    source_human_approved: bool
    workspace_id: str
    baseline_id: str
    baseline_version: int = Field(ge=1)
    baseline_digest: str
    expected_consumers: list[str]
    observations: list[ConsumerStabilityObservation]
    now: datetime
    observation_ttl_seconds: int = Field(default=900, ge=1)
    min_stability_score: float = Field(default=0.85, ge=0.0, le=1.0)
    max_residual_risk: float = Field(default=0.20, ge=0.0, le=1.0)
    risk_brain_hard_block: bool = False

class StabilityObservationDecision(BaseModel):
    state: Literal['review-required', 'degraded', 'closed', 'blocked']
    stability_score: float
    residual_risk: float
    stable_consumers: list[str]
    degraded_consumers: list[str]
    reasons: list[str]
    audit_digest: str
